"""Draft-owned selected decisions and immutable evidence, distinct from the chat.

Each subject selects a retained typed revision. Composite keys prevent another draft's
revision becoming current, even when a client knows its ID. Initial pointer constraints
are deferred so a subject and its first revision can be created in one transaction.
"""

from datetime import datetime
from enum import StrEnum

from mendel_authoring.decisions import ActorKind, FactOrigin
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mendel_api.db import Base
from mendel_api.models import _one_of


class Ownership(StrEnum):
    AUTHORED = "authored"
    MANUAL = "manual"


class SelectionAction(StrEnum):
    SELECT = "select"
    RETAIN = "retain"
    RETRACT = "retract"
    INHERIT = "inherit"
    IMPORT = "import"


class ReviewStatus(StrEnum):
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class _Subject(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), index=True
    )
    subject_key: Mapped[str] = mapped_column(String(400))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    current_id: Mapped[str] = mapped_column(String(32))


class _Revision(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(32), index=True)
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    actor_kind: Mapped[str] = mapped_column(
        _one_of(ActorKind, 16, "actor_kind"), default=ActorKind.PERSON,
        server_default=text("'person'")
    )
    who: Mapped[str] = mapped_column(String(200), default="", server_default=text("''"))
    legacy: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    action: Mapped[str] = mapped_column(
        _one_of(SelectionAction, 16, "action"), default=SelectionAction.SELECT,
        server_default=text("'select'")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    turn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


def _subject_keys(family):
    return (
        UniqueConstraint("id", "draft_id", name=f"uq_pipeline_{family}_owner"),
        UniqueConstraint("draft_id", "subject_key", name=f"uq_pipeline_{family}_subject"),
        ForeignKeyConstraint(
            ["current_id", "id", "draft_id"],
            [f"pipeline_{family}_revision.id", f"pipeline_{family}_revision.subject_id",
             f"pipeline_{family}_revision.draft_id"],
            name=f"fk_pipeline_{family}_current", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
    )


def _revision_keys(family):
    return (
        UniqueConstraint("id", "subject_id", "draft_id",
                         name=f"uq_pipeline_{family}_revision_owner"),
        ForeignKeyConstraint(
            ["subject_id", "draft_id"], [f"pipeline_{family}.id", f"pipeline_{family}.draft_id"],
            name=f"fk_pipeline_{family}_revision_subject", ondelete="RESTRICT",
        ),
        CheckConstraint("actor_kind != 'unknown' OR legacy", name="unknown_is_legacy"),
    )


class PipelineObservation(Base):
    __tablename__ = "pipeline_observation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), index=True
    )
    subject: Mapped[str] = mapped_column(String(128))
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    origin: Mapped[str] = mapped_column(_one_of(FactOrigin, 16, "origin"))
    pieces: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    measured_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invocation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    legacy: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class PipelineEvidenceAccess(Base):
    __tablename__ = "pipeline_evidence_access"

    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), primary_key=True
    )
    observation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_observation.id", ondelete="RESTRICT"), primary_key=True
    )
    inherited: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class PipelineInput(_Subject):
    __tablename__ = "pipeline_input"
    __table_args__ = _subject_keys("input")


class PipelineInputRevision(_Revision):
    __tablename__ = "pipeline_input_revision"
    __table_args__ = _revision_keys("input")

    type_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    states: Mapped[list] = mapped_column(JSON, default=list)
    present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    origin: Mapped[str] = mapped_column(
        _one_of(FactOrigin, 16, "origin"), default=FactOrigin.PERSON_SAID
    )


class PipelineWant(_Subject):
    __tablename__ = "pipeline_want"
    __table_args__ = _subject_keys("want")


class PipelineWantRevision(_Revision):
    __tablename__ = "pipeline_want_revision"
    __table_args__ = _revision_keys("want")

    type_id: Mapped[str] = mapped_column(String(128))
    states: Mapped[list] = mapped_column(JSON, default=list)
    present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class PipelineFact(_Subject):
    __tablename__ = "pipeline_fact"
    __table_args__ = _subject_keys("fact")


class PipelineFactRevision(_Revision):
    __tablename__ = "pipeline_fact_revision"
    __table_args__ = (*_revision_keys("fact"), ForeignKeyConstraint(
        ["draft_id", "observation_id"],
        ["pipeline_evidence_access.draft_id", "pipeline_evidence_access.observation_id"],
        name="fk_pipeline_fact_evidence", ondelete="RESTRICT",
    ))

    observation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PipelineProducer(_Subject):
    __tablename__ = "pipeline_producer"
    __table_args__ = _subject_keys("producer")


class PipelineProducerRevision(_Revision):
    __tablename__ = "pipeline_producer_revision"
    __table_args__ = _revision_keys("producer")

    type_id: Mapped[str] = mapped_column(String(128))
    states: Mapped[list] = mapped_column(JSON, default=list)
    contract: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PipelineParameter(_Subject):
    __tablename__ = "pipeline_parameter"
    __table_args__ = _subject_keys("parameter")


class PipelineParameterRevision(_Revision):
    __tablename__ = "pipeline_parameter_revision"
    __table_args__ = _revision_keys("parameter")

    name: Mapped[str] = mapped_column(String(128))
    value: Mapped[object] = mapped_column(JSON, nullable=True)


class PipelineReview(_Subject):
    __tablename__ = "pipeline_review"
    __table_args__ = _subject_keys("review")


class PipelineReviewRevision(_Revision):
    __tablename__ = "pipeline_review_revision"
    __table_args__ = _revision_keys("review")

    node: Mapped[str] = mapped_column(String(128))
    contract: Mapped[str] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(_one_of(ReviewStatus, 16, "status"))
    decision_revision: Mapped[int] = mapped_column(Integer)


class PipelinePhrasing(Base):
    __tablename__ = "pipeline_phrasing"

    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), primary_key=True
    )
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    decision_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    asked: Mapped[dict | None] = mapped_column(JSON, nullable=True)

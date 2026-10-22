"""Draft-owned selected decisions and immutable evidence, distinct from the chat.

Each subject selects a retained typed revision. Composite keys prevent another draft's
revision becoming current, even when a client knows its ID. Initial pointer constraints
are deferred so a subject and its first revision can be created in one transaction.
"""

from datetime import datetime
from enum import StrEnum

from mendel_authoring.decisions import ActorKind, FactOrigin
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mendel_api.db import Base
from mendel_api.models import _one_of
from mendel_api.shape_versions import stamp
from mendel_api.shapes import Json


class Ownership(StrEnum):
    AUTHORED = "authored"
    MANUAL = "manual"


class SelectionAction(StrEnum):
    SELECT = "select"
    RETAIN = "retain"
    RETRACT = "retract"
    INHERIT = "inherit"
    IMPORT = "import"


class EvidenceDisposition(StrEnum):
    AGREEMENT = "agreement"
    RETAINED = "retained"
    SELECTED = "selected"
    OBSOLETE = "obsolete"


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
        _one_of(ActorKind, 16, "actor_kind"),
        default=ActorKind.PERSON,
        server_default=text("'person'"),
    )
    who: Mapped[str] = mapped_column(String(200), default="", server_default=text("''"))
    legacy: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    action: Mapped[str] = mapped_column(
        _one_of(SelectionAction, 16, "action"),
        default=SelectionAction.SELECT,
        server_default=text("'select'"),
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    turn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    heard: Mapped[str | None] = mapped_column(Text, nullable=True)
    """The person's own words this revision was taken from, checked against what they typed
    (Part I.0 §5.3); `None` when nobody quoted them. Never written into a payload."""
    heard_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """The turn those words are in."""


def _subject_keys(family):
    return (
        UniqueConstraint("id", "draft_id", name=f"uq_pipeline_{family}_owner"),
        UniqueConstraint("draft_id", "subject_key", name=f"uq_pipeline_{family}_subject"),
        ForeignKeyConstraint(
            ["current_id", "id", "draft_id"],
            [
                f"pipeline_{family}_revision.id",
                f"pipeline_{family}_revision.subject_id",
                f"pipeline_{family}_revision.draft_id",
            ],
            name=f"fk_pipeline_{family}_current",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )


def _revision_keys(family):
    return (
        UniqueConstraint(
            "id", "subject_id", "draft_id", name=f"uq_pipeline_{family}_revision_owner"
        ),
        ForeignKeyConstraint(
            ["subject_id", "draft_id"],
            [f"pipeline_{family}.id", f"pipeline_{family}.draft_id"],
            name=f"fk_pipeline_{family}_revision_subject",
            ondelete="RESTRICT",
        ),
        CheckConstraint("actor_kind != 'unknown' OR legacy", name="unknown_is_legacy"),
    )


class PipelineObservation(Base):
    __tablename__ = "pipeline_observation"
    shape_version: Mapped[int] = stamp("pipeline_observation")
    __table_args__ = (
        UniqueConstraint(
            "draft_id", "ingestion_key", "subject", name="uq_pipeline_observation_ingestion_subject"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), index=True
    )
    subject: Mapped[str] = mapped_column(String(128))
    value: Mapped[object] = mapped_column(Json, nullable=True)
    origin: Mapped[str] = mapped_column(_one_of(FactOrigin, 16, "origin"))
    pieces: Mapped[list] = mapped_column(Json, default=list)
    evidence: Mapped[dict | None] = mapped_column(Json, nullable=True)
    measured_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invocation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ingestion_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    legacy: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    heard: Mapped[str | None] = mapped_column(Text, nullable=True)
    """The words a person-said observation was taken from (Part I.0 §6.1)."""
    heard_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PipelineEvidenceAccess(Base):
    __tablename__ = "pipeline_evidence_access"
    __table_args__ = (
        CheckConstraint(
            "(acknowledged_as IS NULL AND acknowledged_revision IS NULL AND "
            "acknowledged_at IS NULL AND acknowledged_by IS NULL AND acknowledged_kind IS NULL) "
            "OR (acknowledged_as IS NOT NULL AND acknowledged_revision IS NOT NULL AND "
            "acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL AND "
            "acknowledged_kind IS NOT NULL AND acknowledged_kind != 'unknown')",
            name="complete_acknowledgement",
        ),
    )

    acknowledged_as: Mapped[str | None] = mapped_column(
        _one_of(EvidenceDisposition, 16, "acknowledged_as"), nullable=True
    )
    acknowledged_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_kind: Mapped[str | None] = mapped_column(
        _one_of(ActorKind, 16, "acknowledged_kind"), nullable=True
    )

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
    shape_version: Mapped[int] = stamp("pipeline_input_revision")
    __table_args__ = _revision_keys("input")

    type_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    states: Mapped[list] = mapped_column(Json, default=list)
    present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    origin: Mapped[str] = mapped_column(
        _one_of(FactOrigin, 16, "origin"), default=FactOrigin.PERSON_SAID
    )


class PipelineWant(_Subject):
    __tablename__ = "pipeline_want"
    __table_args__ = _subject_keys("want")


class PipelineWantRevision(_Revision):
    __tablename__ = "pipeline_want_revision"
    shape_version: Mapped[int] = stamp("pipeline_want_revision")
    __table_args__ = _revision_keys("want")

    states_order: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("states_order >= 0", name="states_order_nonnegative"),
        nullable=True,
    )
    type_id: Mapped[str] = mapped_column(String(128))
    states: Mapped[list] = mapped_column(Json, default=list)
    present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class PipelineFact(_Subject):
    __tablename__ = "pipeline_fact"
    __table_args__ = _subject_keys("fact")


class PipelineFactRevision(_Revision):
    __tablename__ = "pipeline_fact_revision"
    __table_args__ = (
        *_revision_keys("fact"),
        ForeignKeyConstraint(
            ["draft_id", "observation_id"],
            ["pipeline_evidence_access.draft_id", "pipeline_evidence_access.observation_id"],
            name="fk_pipeline_fact_evidence",
            ondelete="RESTRICT",
        ),
    )

    observation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PipelineProducer(_Subject):
    __tablename__ = "pipeline_producer"
    __table_args__ = _subject_keys("producer")


class PipelineProducerRevision(_Revision):
    __tablename__ = "pipeline_producer_revision"
    shape_version: Mapped[int] = stamp("pipeline_producer_revision")
    __table_args__ = _revision_keys("producer")

    type_id: Mapped[str] = mapped_column(String(128))
    states: Mapped[list] = mapped_column(Json, default=list)
    contract: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PipelineRole(_Subject):
    """A role a person switched off (A1, the one-builder design); keyed by the role."""

    __tablename__ = "pipeline_role"
    __table_args__ = _subject_keys("role")


class PipelineRoleRevision(_Revision):
    __tablename__ = "pipeline_role_revision"
    __table_args__ = _revision_keys("role")

    role: Mapped[str] = mapped_column(String(128))
    absent: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class PipelineExclusion(_Subject):
    """A tool a person excluded at a site (A1); keyed by the site and the tool."""

    __tablename__ = "pipeline_exclusion"
    __table_args__ = _subject_keys("exclusion")


class PipelineExclusionRevision(_Revision):
    __tablename__ = "pipeline_exclusion_revision"
    shape_version: Mapped[int] = stamp("pipeline_exclusion_revision")
    __table_args__ = _revision_keys("exclusion")

    type_id: Mapped[str] = mapped_column(String(128))
    states: Mapped[list] = mapped_column(Json, default=list)
    contract: Mapped[str] = mapped_column(String(200))
    excluded: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class PipelineSource(_Subject):
    """What a person chose to feed a step's input (A1); keyed by the consumer and its port."""

    __tablename__ = "pipeline_source"
    __table_args__ = _subject_keys("source")


class PipelineSourceRevision(_Revision):
    __tablename__ = "pipeline_source_revision"
    __table_args__ = _revision_keys("source")

    consumer: Mapped[str] = mapped_column(String(200))
    port: Mapped[str] = mapped_column(String(128))
    producer: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PipelineParameter(_Subject):
    __tablename__ = "pipeline_parameter"
    __table_args__ = _subject_keys("parameter")


class PipelineParameterRevision(_Revision):
    __tablename__ = "pipeline_parameter_revision"
    shape_version: Mapped[int] = stamp("pipeline_parameter_revision")
    __table_args__ = _revision_keys("parameter")

    name: Mapped[str] = mapped_column(String(128))
    value: Mapped[object] = mapped_column(Json, nullable=True)


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


class PipelineAsked(_Subject):
    """Something the person asked for that nothing here can make (Part I.0 §5.1). Kept so the
    conversation never promises it; never part of the goal the resolver reads."""

    __tablename__ = "pipeline_asked"
    __table_args__ = _subject_keys("asked")


class PipelineAskedRevision(_Revision):
    __tablename__ = "pipeline_asked_revision"
    __table_args__ = _revision_keys("asked")

    phrase: Mapped[str] = mapped_column(Text)
    present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class PipelinePhrasing(Base):
    __tablename__ = "pipeline_phrasing"
    shape_version: Mapped[int] = stamp("pipeline_phrasing")

    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), primary_key=True
    )
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    decision_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    asked: Mapped[dict | None] = mapped_column(Json, nullable=True)

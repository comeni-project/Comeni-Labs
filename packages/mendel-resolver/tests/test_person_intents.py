"""A person's structural intent (A1, the one-builder design), over the shipped registry: a role
switched off, a tool excluded at a site, a port's source pinned. Each is honoured on every
re-plan, and a conflict is raised with a code rather than resolved silently."""

import pytest
from comeni_core.goal.asked import RoleAbsence
from mendel_resolver.router import IntentConflict


def _node(ir, node_id):
    return next(n for n in ir.nodes if n.id == node_id)


def test_switching_trimming_off_routes_the_reads_straight_to_the_aligner(resolve_rnaseq):
    ir = resolve_rnaseq(absent_roles=[RoleAbsence(role="trimming")])
    assert "trimgalore" not in {n.id for n in ir.nodes}
    feeding_star = {e.from_node for e in ir.edges if e.to_node == "star_align"}
    assert feeding_star, "the aligner is fed by something"
    assert "trimgalore" not in feeding_star


def test_switching_off_a_role_the_goal_needs_is_a_coded_conflict(resolve_rnaseq):
    with pytest.raises(IntentConflict, match="MD03") as raised:
        resolve_rnaseq(absent_roles=[RoleAbsence(role="alignment")])
    assert raised.value.intent == RoleAbsence(role="alignment")
    assert "alignment" in str(raised.value)

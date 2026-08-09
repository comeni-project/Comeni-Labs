"""A setting declares the route that carries it, and a setting that reaches nothing is refused.

The whole declared-param surface was two entries and both were dead: `star/align` and
`hisat2/align` each declared `seq_platform`, which resolved to a `params.<node>_<name>` line in
`main.nf` that no module reads. The resolver ran, flagged tier 4, printed `REVIEW`, and the
pipeline behaved identically whatever the answer was. Issue #10.

`via:` is mandatory, so that state is now unrepresentable rather than merely detectable.
"""

import pytest
from comeni_core.contract import Param
from comeni_core.directives import LEGAL_DIRECTIVES, NEXTFLOW_VERSION
from comeni_core.marks import substitutable
from comeni_core.routes import TEMPLATED, ExtKey, Via
from pydantic import ValidationError


def test_a_param_without_a_route_is_refused():
    """MD0200. `via` has no default, so this is a missing-field error."""
    with pytest.raises(ValidationError):
        Param(name="seq_platform", tier_hint=4)


def test_ext_requires_a_key():
    with pytest.raises(ValidationError, match="MD0205"):
        Param(name="seq_platform", via=Via.EXT, template="--x {value}")


def test_a_key_on_a_non_ext_route_is_refused():
    with pytest.raises(ValidationError, match="MD0205"):
        Param(name="cpus", via=Via.DIRECTIVE, key=ExtKey.ARGS)


def test_when_is_not_a_legal_key():
    """`ext.when` skips a process entirely. A setting that switches off a step would let
    `steps:` describe a pipeline that does not run — a second routing mechanism competing with
    resolution. Whether a step exists is decided by resolving the goal."""
    with pytest.raises(ValidationError):
        Param(name="off", via=Via.EXT, key="when", template="{value}")


def test_a_template_must_mention_the_value():
    """MD0204. Deadness wearing a bridge: renders real flags, discards the resolved value, and
    is harder to spot than an honest no-op because it looks wired."""
    with pytest.raises(ValidationError, match="MD0204"):
        Param(name="seq_platform", via=Via.EXT, key=ExtKey.ARGS, template="--flag fixed")


def test_a_templated_key_requires_a_template():
    with pytest.raises(ValidationError, match="MD0204"):
        Param(name="seq_platform", via=Via.EXT, key=ExtKey.ARGS)


def test_a_template_is_illegal_where_the_route_takes_one_value():
    """`prefix` names outputs and a directive takes a typed value. `cpus = "--cpus 12"` is not
    a thing, so a template there has nothing to compose into."""
    with pytest.raises(ValidationError, match="MD0204"):
        Param(name="cpus", via=Via.DIRECTIVE, template="--cpus {value}")


def test_an_unknown_directive_is_refused():
    """MD0209, and the premise was measured rather than assumed: a config carrying
    `withName: FOO { cpuz = 4 }` runs to exit 0 with no error and no warning on Nextflow
    25.10.4. Nothing else would catch this."""
    with pytest.raises(ValidationError, match="MD0209"):
        Param(name="cpuz", via=Via.DIRECTIVE)


def test_a_real_directive_validates():
    assert Param(name="cpus", via=Via.DIRECTIVE).via is Via.DIRECTIVE


def test_ext_is_not_reachable_as_a_directive():
    """Two routes to one scope is two writers for one destination. Forbid it at the source
    rather than catching it downstream."""
    assert "ext" not in LEGAL_DIRECTIVES
    with pytest.raises(ValidationError, match="MD0209"):
        Param(name="ext", via=Via.DIRECTIVE)


def test_a_routed_param_validates():
    p = Param(
        name="seq_platform",
        tier_hint=4,
        via=Via.EXT,
        key=ExtKey.ARGS,
        template="--outSAMattrRGline 'ID:${meta.id}' 'SM:${meta.id}' 'PL:{value}'",
    )
    assert p.key is ExtKey.ARGS
    assert "{value}" in p.template


def test_the_directive_list_records_the_nextflow_it_was_read_against():
    """Toolchain fact, not biology. It moves when Nextflow moves, and a reader needs to know
    which Nextflow the list describes."""
    assert NEXTFLOW_VERSION
    assert "cpus" in LEGAL_DIRECTIVES


@pytest.mark.parametrize(
    "value", ["illumina", "reverse", 10, 1.5, True, False, "GRCh38.p14", "a:b+c-d"]
)
def test_substitutable_accepts_ordinary_values(value):
    assert substitutable(value)


@pytest.mark.parametrize(
    "value",
    ["has space", "/data/x", "it's", 'say "x"', "$(id)", "a`b`", "a;b", "a\nb"],
)
def test_substitutable_refuses_what_would_break_out(value):
    """Refuse rather than escape. Escaping-for-context is where injection bugs live, and a
    value that cannot contain a quote cannot close one. The space and the slash are the
    deliberate assumption — see MD0201's message, which asks for a counterexample."""
    assert not substitutable(value)


def test_templated_keys_are_the_argument_string_ones():
    assert {ExtKey.ARGS, ExtKey.ARGS2, ExtKey.ARGS3} == TEMPLATED
    assert ExtKey.PREFIX not in TEMPLATED

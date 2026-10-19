"""`/health/registry`: what the registry in use holds."""

from mendel_api.routes.health import registry_health


def test_the_strip_counts_the_registry_s_tools_and_types():
    strip = registry_health()
    assert strip.contracts > 0
    assert strip.types > 0

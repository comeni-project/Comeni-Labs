"""What the compose files say, read rather than run.

**No container is started here.** `make check`'s lane has no Docker, and the failures worth
catching are declarative: a service that reaches no registry serves 500s on every screen, and
a prod overlay that mounts code is not prod. Both are invisible until somebody runs the image,
and both are visible in the YAML.

The rule the overlay exists to hold: **it changes safety, never capability.** Dev can do
everything prod can — that is spec §3.1, and `test_the_overlay_names_only_services_the_base_has`
is the structural half of it.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def base() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


class _TolerantLoader(yaml.SafeLoader):
    """Compose's `!reset` and `!override` are YAML tags `safe_load` refuses."""


for _tag in ("!reset", "!override"):
    _TolerantLoader.add_constructor(_tag, lambda loader, node: loader.construct_sequence(node))


@pytest.fixture(scope="module")
def prod() -> dict:
    return yaml.load((ROOT / "docker-compose.prod.yml").read_text(), Loader=_TolerantLoader)


@pytest.fixture(scope="module")
def prod_text() -> str:
    return (ROOT / "docker-compose.prod.yml").read_text()


def test_the_stack_is_five_services(base):
    """Named literally: adding one means editing this test, which is where somebody notices
    that a sixth service needs a healthcheck and a place in the overlay."""
    assert sorted(base["services"]) == ["api", "postgres", "redis", "web", "worker"]


def test_the_overlay_names_only_services_the_base_has(base, prod):
    """An overlay naming a service the base does not define creates one — silently, with no
    image and no healthcheck. That is how two compose files start to drift into two stacks."""
    unknown = set(prod["services"]) - set(base["services"])
    assert unknown == set(), f"the overlay invents {unknown}"


def test_every_service_is_healthchecked_or_waits_for_one_that_is(base):
    for name, service in base["services"].items():
        healthy = "healthcheck" in service
        waits = bool(service.get("depends_on"))
        assert healthy or waits, f"{name} neither reports health nor waits for anything"


def test_the_api_and_the_worker_share_one_image(base):
    """They import the same packages and read the same declared data; only the command
    differs. Two images would be two places to keep one dependency pin honest."""
    assert base["services"]["api"]["build"] == base["services"]["worker"]["build"] == "."


def test_the_registry_and_the_vendored_modules_reach_the_api(base):
    """**The one worth having.** `settings.registry_root` and `source_root` are read by the
    queue, the contracts list, the drift report and the source catalogue. A container that
    cannot see them answers 500 on every screen, and nothing else here would notice."""
    mounts = " ".join(base["services"]["api"]["volumes"])
    assert "/app/registry" in mounts
    assert "/app/vendor" in mounts


def test_the_api_gets_a_registry_it_can_commit_to(base):
    """A CLONE, not the submodule. A submodule's `.git` is a pointer at a host path that
    resolves to nothing inside a container, so accepting a drift would refuse with MF0107 —
    and dev must be able to do what prod can. `make dev` creates `.run/registry`."""
    for service in ("api", "worker"):
        mounts = " ".join(base["services"][service]["volumes"])
        assert ".run/registry:/app/registry" in mounts, service


def test_the_containers_do_not_run_as_root(base):
    """Two things break otherwise, both found by running it: git refuses a bind-mounted
    repository owned by another uid, and drafts written into `./workspace` land root-owned and
    undeletable by whoever started the stack."""
    for service in ("api", "worker"):
        assert "user" in base["services"][service], f"{service} runs as root"


def test_no_command_uses_a_login_shell(base):
    """`sh -lc` re-reads `/etc/profile`, which resets `PATH` and drops `/app/.venv/bin` — so
    `alembic: not found` and the container exits. Measured, and it cost a debugging round."""
    for name, service in base["services"].items():
        command = service.get("command", "")
        assert "sh -lc" not in str(command), f"{name} uses a login shell"


def test_prod_mounts_no_code(base, prod):
    """The half that must fail otherwise: dev mounts `./packages` live, and prod must not —
    the code is the image. The registry and the workspace stay mounted, because a commit
    needs a checkout and drafts need to survive a restart."""
    dev_mounts = " ".join(base["services"]["api"]["volumes"])
    assert "./packages:" in dev_mounts, "dev stopped mounting code — this test is now vacuous"

    for service in ("api", "worker"):
        for mount in prod["services"][service]["volumes"]:
            assert "./packages" not in mount, f"prod mounts code into {service}"


def test_prod_does_not_reload(base, prod):
    assert "--reload" in base["services"]["api"]["command"]
    assert "--reload" not in prod["services"]["api"]["command"]


def test_prod_closes_the_ports_with_reset_rather_than_an_empty_list(base, prod_text):
    """**`ports: []` does not close a port**, and this test asserted that it did.

    Compose MERGES sequences across files, so an empty list adds nothing and the base's
    published port survives. Measured while bringing the stack up: postgres answered on 5432
    with `ports: []` in the overlay, and this test passed. `!reset` is the mechanism, so the
    mechanism is what is asserted — a test that reads the literal it wanted to see is exactly
    the vacuous shape this one used to be.
    """
    # Comments stripped first: the block above this test's subject explains the trap and
    # quotes the very literal it forbids, which failed this assertion on its first run.
    declared = "\n".join(
        line for line in prod_text.splitlines() if not line.lstrip().startswith("#")
    )
    assert declared.count("ports: !reset") == 3, "postgres, redis and api each reset theirs"
    assert "ports: []" not in declared, (
        "`ports: []` is a no-op under compose's merge — it reads as closed and is not"
    )


def test_prod_publishes_the_web_port_and_nothing_else(prod):
    """`web` is the only way in, and it keeps the base's port rather than restating it."""
    assert "ports" not in prod["services"]["web"]
    for service in ("postgres", "redis", "api"):
        assert prod["services"][service].get("ports") == [], service


def test_prod_restarts_everything(prod):
    for name, service in prod["services"].items():
        assert service.get("restart") == "unless-stopped", name

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


def _default_stack(base) -> dict:
    """What `make dev` brings up — everything without a profile.

    A profiled service is defined here and started only when asked for, which is how the
    telemetry three can live in this file without a ClickHouse landing on somebody who is
    working on the forge."""
    return {name: svc for name, svc in base["services"].items() if not svc.get("profiles")}


def _publish_a_host_port(base) -> set[str]:
    """Which services the base exposes on the host. Derived, because a written-out list is a
    list that stops matching the stack the day somebody adds a service to it."""
    return {name for name, service in _default_stack(base).items() if service.get("ports")}


def test_the_stack_is_nine_services(base):
    """Named literally: adding one means editing this test, which is where somebody notices
    that a new service needs a healthcheck and a place in the overlay.

    **It worked.** `wiener-postgres` and `wiener-api` arrived on 2026-08-24 and this test is
    what stopped them arriving with a host-published port that the prod overlay had never
    heard of — the plan's Task 5 said "add the compose services" and said nothing about the
    overlay, which is precisely the gap a literal list catches."""
    assert sorted(_default_stack(base)) == [
        "api", "postgres", "redis", "web",
        "wiener-api", "wiener-ingest", "wiener-postgres", "wiener-worker", "worker",
    ]


def test_the_ingest_app_is_never_published(base, prod):
    """**§13.1's guarantee, as a test rather than a sentence.** The head process must reach it
    and the internet must not, so it is its own service on the compose network with no port on
    the host — in the base file and in the overlay.

    It moved out of "loopback" on 2026-08-24 because the head process moves: `kuberun` is
    deprecated and the production Kubernetes pattern runs Nextflow in its own pod, so a
    topology that only works while the head is a child of the worker is one that gets rewritten
    under pressure in W5.
    """
    assert not base["services"]["wiener-ingest"].get("ports"), (
        "the ingest app is published on the host; §13.1 says the internet may not reach it"
    )
    assert not prod["services"].get("wiener-ingest", {}).get("ports")


def test_the_public_api_is_reached_through_nginx_and_not_a_second_port(base):
    """One origin, split by path — the same split `vite.config.ts` makes in development. Two
    published ports is prod and dev disagreeing about where Wiener lives."""
    assert not base["services"]["wiener-api"].get("ports")
    assert base["services"]["web"].get("ports"), "nginx is the way in"


def test_nginx_routes_both_halves_of_the_api():
    """The config is what makes the previous test true, so it is read rather than assumed."""
    conf = (ROOT / "ops" / "nginx" / "default.conf").read_text()
    assert "location /api/runs" in conf and "wiener-api:8001" in conf
    assert "location /api/artifacts" in conf
    assert "location /api/" in conf and "api:8000" in conf
    assert "$connection_upgrade" in conf, (
        "the WebSocket needs Upgrade forwarded, or the console never connects and nothing on "
        "screen says why"
    )


def test_the_telemetry_backend_is_opt_in(base):
    """**`make dev` must not grow a ClickHouse** for somebody working on the forge, and the
    backend must not be a second compose file either — two files drift, which is the argument
    `docker-compose.prod.yml`'s own header makes about overlays.

    A profile is the third option: defined here, started when asked for. `make telemetry`."""
    profiled = {name for name, svc in base["services"].items() if svc.get("profiles")}
    assert profiled == {"clickhouse", "otel-collector", "grafana"}
    assert all(base["services"][name]["profiles"] == ["telemetry"] for name in profiled)


def test_nothing_in_the_default_stack_depends_on_a_profiled_service(base):
    """A dependency on something that does not start is a stack that does not come up. Wiener
    reaches the collector by URL — `WIENER_OTLP_ENDPOINT` — and by nothing else."""
    profiled = {name for name, svc in base["services"].items() if svc.get("profiles")}
    for name, svc in _default_stack(base).items():
        assert not (set(svc.get("depends_on") or {}) & profiled), (
            f"{name} depends on {profiled & set(svc.get('depends_on') or {})}, which "
            "`make dev` does not start"
        )


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
    """**The one worth having.** `settings.registry_root` is read by the queue, the contracts
    list, the drift report and the source catalogue. A container that cannot see it answers 500
    on every screen, and nothing else here would notice.

    **One mount since Plan 5A, where there were two.** `MENDEL_SOURCE_ROOT: /app/vendor` was a
    second bind of a second directory holding the code the first one's contracts describe — on
    a different release cadence, in a different repository. The layer carries both now, so a
    container that has the registry has everything, and there is no way to mount one without
    the other.
    """
    mounts = " ".join(base["services"]["api"]["volumes"])
    assert "/app/registry" in mounts
    assert "/app/vendor" not in mounts, (
        "the vendor mount is back — module source lives in the layer, and a second root is "
        "how a contract and its module came to be versioned apart"
    )


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
    closes = _publish_a_host_port(base) - {"web"}
    assert declared.count("ports: !reset") == len(closes), (
        f"each of {sorted(closes)} must reset its ports; the overlay does it "
        f"{declared.count('ports: !reset')} times. **The number is derived from the base, not "
        "written here** — it read `== 3` until wiener-postgres and wiener-api arrived and made "
        "it 5, which is a count in a test going stale exactly the way CLAUDE.md says counts do."
    )
    assert "ports: []" not in declared, (
        "`ports: []` is a no-op under compose's merge — it reads as closed and is not"
    )


def test_prod_publishes_the_web_port_and_nothing_else(base, prod):
    """`web` is the only way in, and it keeps the base's port rather than restating it.

    **The list is derived from the base.** It was written out — `("postgres", "redis", "api")`
    — which meant a service added to the base was not checked here at all: the test would have
    passed with `wiener-postgres` published on the host in production."""
    assert "ports" not in prod["services"]["web"]
    for service in sorted(_publish_a_host_port(base) - {"web"}):
        assert prod["services"][service].get("ports") == [], (
            f"{service} publishes a host port in the base and the overlay does not close it"
        )


def test_prod_restarts_everything(prod):
    for name, service in prod["services"].items():
        assert service.get("restart") == "unless-stopped", name


def test_the_draft_root_is_a_volume_shared_by_the_api_and_the_worker(base):
    """`keep` writes an artifact and the worker gates it. Two containers, one directory.

    `MENDEL_DRAFT_ROOT` was set on both services with **nothing backing it**, so the API wrote
    into its own ephemeral layer: the file vanished on restart and the worker could not see it
    at all. A gate job would then have run `nextflow` in a directory that does not exist and
    reported a Nextflow error — the worst kind of failure, a true message about the wrong
    thing.

    Found by asking what a container does, which is the method that found phase 8's two.
    """
    services = base["services"]
    for name in ("api", "worker"):
        root = services[name]["environment"]["MENDEL_DRAFT_ROOT"]
        mounts = [v.split(":")[1] for v in services[name]["volumes"] if ":" in v]
        assert root in mounts, f"{name}: MENDEL_DRAFT_ROOT={root} is backed by no volume"


def _database_owners(services: dict) -> dict[str, list[str]]:
    """Every service that reads a database, grouped by the database it reads.

    Derived rather than listed, so a third database arriving with a third service is covered
    the day it lands instead of the day somebody remembers this file.
    """
    owners: dict[str, list[str]] = {}
    for name, service in services.items():
        for key, url in (service.get("environment") or {}).items():
            if key.endswith("_DATABASE_URL"):
                owners.setdefault(url, []).append(name)
    return owners


def test_every_database_in_the_base_stack_is_migrated_by_exactly_one_service(base):
    """A database nobody migrates is a stack that comes up green and 500s on the first request.

    `wiener-api` ran `alembic upgrade head` in `docker-compose.prod.yml` **and nowhere else**,
    so `make prod` came up migrated and `make dev` came up with no `run` table. Nothing in the
    stack looked wrong — nine containers healthy — and `/runs` answered with a traceback naming
    `relation "run" does not exist`. The fix is one line of compose; the reason it survived is
    that the only copy lived in the overlay, which is the file for what prod *removes*.

    **Exactly one**, not at least one: two services racing `alembic upgrade head` against one
    database is how a migration deadlocks on a cold start.

    This is the docstring at the top of this file arriving a second time — a service that
    reaches no database serves 500s on every screen, and it is visible in the YAML.
    """
    for url, services in _database_owners(base["services"]).items():
        migrators = [
            s for s in services
            if "alembic upgrade head" in str(base["services"][s].get("command", ""))
        ]
        assert len(migrators) == 1, (
            f"{url.rsplit('/', 1)[-1]}: read by {services}, migrated by {migrators or 'nobody'}"
        )


def test_the_overlay_never_introduces_a_migration_the_base_lacks(base, prod):
    """The drift that hid the bug above, guarded in the direction it actually drifted.

    An overlay may reasonably drop `--reload` from a command. It may not be the only place a
    database gets created, because then dev and prod are not the same stack with the unsafe
    parts removed — they are two stacks, and only one of them works.
    """
    for name, service in prod["services"].items():
        prod_command = str(service.get("command", ""))
        if "alembic upgrade head" not in prod_command:
            continue
        base_command = str(base["services"][name].get("command", ""))
        assert "alembic upgrade head" in base_command, (
            f"{name}: the overlay migrates and the base does not — dev comes up unmigrated"
        )

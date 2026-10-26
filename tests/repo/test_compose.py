"""What the compose files say, read rather than run.

**No container is started here.** `make check`'s lane has no Docker, and the failures worth
catching are declarative: a service that reaches no registry serves 500s on every screen, and
a prod overlay that mounts code is not prod. Both are invisible until somebody runs the image,
and both are visible in the YAML.

The rule the overlay exists to hold: **it changes safety, never capability.** Dev can do
everything prod can — that is spec §3.1, and `test_the_overlay_names_only_services_the_base_has`
is the structural half of it.
"""

import json

import pytest
import yaml
from support.compose import configuration
from support.paths import ROOT


@pytest.fixture(scope="module")
def base() -> dict:
    parsed = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    # Most tests here loop over `base["services"]` and assert inside the loop, which is a
    # green tick over a missing key: a compose file that parsed to `{}` would pass every one
    # of them. Asserted at the fixture rather than in each test, because it is one fact.
    assert parsed.get("services"), "docker-compose.yml parsed to no services"
    return parsed


@pytest.fixture(scope="function")
def effective_prod(tmp_path):
    result = configuration(tmp_path, production=True, token="synthetic-test-token")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def env_of(service: dict) -> dict[str, str | None]:
    """One service's environment, whichever of compose's two spellings it uses.

    **A guard that understands one form is blind to the other**, and compose accepts both: a
    mapping (`NAME: value`) and a list, where a bare `- NAME` means *pass it through from the
    host if it is set, and leave it unset otherwise*. That second form is the only way to say
    "unset" — `NAME: ${NAME:-}` sets an empty string, which is a different thing to every
    program that checks whether a variable is present.

    A bare name reads as `None` here: present as a declaration, carrying no literal. Every
    guard below goes through this, because the first list-form entry in this file broke two
    guards that had nothing to do with it.
    """
    declared = service.get("environment") or {}
    if isinstance(declared, dict):
        return dict(declared)
    pairs = (str(entry).partition("=") for entry in declared)
    return {name: (value if sep else None) for name, sep, value in pairs}


class _TolerantLoader(yaml.SafeLoader):
    """Compose's `!reset` and `!override` are YAML tags `safe_load` refuses."""


for _tag in ("!reset", "!override"):
    _TolerantLoader.add_constructor(_tag, lambda loader, node: loader.construct_sequence(node))


@pytest.fixture(scope="module")
def prod() -> dict:
    parsed = yaml.load((ROOT / "docker-compose.prod.yml").read_text(), Loader=_TolerantLoader)
    assert parsed.get("services"), "docker-compose.prod.yml parsed to no services"
    return parsed


@pytest.fixture(scope="module")
def prod_text() -> str:
    return (ROOT / "docker-compose.prod.yml").read_text()


def _default_stack(base) -> dict:
    """What `make dev` brings up — everything without a profile.

    A profiled service is defined here and started only when asked for, which is how the
    telemetry three can live in this file without a ClickHouse landing on somebody who is
    working on the forge."""
    return {name: svc for name, svc in base["services"].items() if not svc.get("profiles")}


def _overlay_names() -> set[str]:
    """Which services the prod overlay says anything about.

    Read from the file rather than passed in, because it is asked for inside one assertion and
    a fixture would put it in every signature that does not need it.
    """
    parsed = yaml.load((ROOT / "docker-compose.prod.yml").read_text(), Loader=_TolerantLoader)
    return set(parsed["services"])


def _publish_a_host_port(base) -> set[str]:
    """Which services the base exposes on the host. Derived, because a written-out list is a
    list that stops matching the stack the day somebody adds a service to it."""
    return {name for name, service in _default_stack(base).items() if service.get("ports")}


def test_the_default_stack_has_the_expected_services(base):
    """A new default service requires a deliberate review of its deployment wiring."""
    assert sorted(_default_stack(base)) == [
        "ai-worker",
        "api",
        "mendel-worker",
        "postgres",
        "redis",
        "web",
        "wiener-api",
        "wiener-ingest",
        "wiener-worker",
        "wiki",
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
    assert "location /api/wiener" in conf
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
    assert profiled == {"clickhouse", "otel-collector", "grafana", "ollama"}
    telemetry = profiled - {"ollama"}
    assert all(base["services"][name]["profiles"] == ["telemetry"] for name in telemetry)


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
    build = base["services"]["api"]["build"]
    assert build == base["services"]["mendel-worker"]["build"]
    assert build["context"] == "."


def test_the_registry_and_the_vendored_modules_reach_the_api(base):
    """**The one worth having.** `settings.registry_root` is read by every build. A container
    that cannot see it answers 500 on every screen, and nothing else here would notice.

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
    for service in ("api", "mendel-worker"):
        mounts = " ".join(base["services"][service]["volumes"])
        assert ".run/registry:/app/registry" in mounts, service


def test_the_containers_do_not_run_as_root(base):
    """Two things break otherwise, both found by running it: git refuses a bind-mounted
    repository owned by another uid, and drafts written into `./workspace` land root-owned and
    undeletable by whoever started the stack."""
    for service in ("api", "mendel-worker"):
        assert "user" in base["services"][service], f"{service} runs as root"


def test_no_command_uses_a_login_shell(base):
    """`sh -lc` re-reads `/etc/profile`, which resets `PATH` and drops `/app/.venv/bin` — so
    `alembic: not found` and the container exits. Measured, and it cost a debugging round."""
    for name, service in base["services"].items():
        command = service.get("command", "")
        assert "sh -lc" not in str(command), f"{name} uses a login shell"


def test_prod_mounts_no_code(base, effective_prod):
    """Check effective mounts after Compose merges all Mendel services."""
    assert any("/app/packages" in mount for mount in base["services"]["api"]["volumes"])
    for name in ("api", "mendel-worker", "ai-worker"):
        targets = {mount["target"] for mount in effective_prod["services"][name]["volumes"]}
        assert "/app/packages" not in targets, name
        assert {"/app/registry", "/app/workspace", "/app/drafts"} <= targets, name


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
    # **Derived from what the overlay covers**, not from the default stack. `ollama` publishes
    # a port in the base and is profiled, so it is absent from `_publish_a_host_port` — and it
    # is named in the overlay, which resets it, because an unauthenticated inference endpoint on
    # the host's interface is exactly what "safety, not capability" removes. Deriving from the
    # default stack alone made a correct reset look like an extra one.
    covered = {
        name
        for name, service in base["services"].items()
        if service.get("ports") and name in _overlay_names()
    }
    closes = covered - {"web"}
    assert declared.count("ports: !reset") == len(closes), (
        f"each of {sorted(closes)} must reset its ports; the overlay does it "
        f"{declared.count('ports: !reset')} times. **The number is derived from the files, not "
        "written here** — it read `== 3` until wiener-postgres and wiener-api arrived and made "
        "it 5, which is a count in a test going stale exactly the way CLAUDE.md says counts do."
    )
    assert "ports: []" not in declared, (
        "`ports: []` is a no-op under compose's merge — it reads as closed and is not"
    )


def test_prod_publishes_the_web_port_and_nothing_else(effective_prod):
    """Optional profiles must also keep their unauthenticated interfaces internal."""
    published = {
        name for name, service in effective_prod["services"].items() if service.get("ports")
    }
    assert published == {"web"}


def test_prod_restarts_everything(effective_prod):
    for name, service in effective_prod["services"].items():
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
    for name in ("api", "mendel-worker"):
        root = env_of(services[name])["MENDEL_DRAFT_ROOT"]
        mounts = [v.split(":")[1] for v in services[name]["volumes"] if ":" in v]
        assert root in mounts, f"{name}: MENDEL_DRAFT_ROOT={root} is backed by no volume"


def _database_owners(services: dict) -> dict[str, list[str]]:
    """Every service that reads a database, grouped by the database it reads.

    Derived rather than listed, so a third database arriving with a third service is covered
    the day it lands instead of the day somebody remembers this file.
    """
    owners: dict[str, list[str]] = {}
    for name, service in services.items():
        for key, url in env_of(service).items():
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
            s
            for s in services
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


# ── the AI lane ───────────────────────────────────────────────────────────────────────

FORGE_SERVICES = ("api", "mendel-worker", "ai-worker")
"""The three that touch the forge's workspace.

`web` serves files and the Wiener services are the other half of the product; none of them
reads a scaffold, so requiring them to mount one would be requiring a mount for its own sake.
"""


def _mounts(service: dict) -> dict[str, str]:
    """`{container path: host path}` for a service's bind mounts.

    Short form only, which is all these files use. A long-form `type: bind` entry would be
    absent from this mapping and the assertions below would fail naming the path — loudly, not
    silently, which is the direction that matters.
    """
    found = {}
    for volume in service.get("volumes", ()):
        if not isinstance(volume, str) or ":" not in volume:
            continue
        host, container, *_ = volume.split(":")
        found[container] = host
    return found


def test_the_forge_services_agree_on_where_the_workspace_is(base):
    """**A generation job reads the scaffold the API wrote.** `read_source` and `read_holes`
    open `MENDEL_WORKSPACE_ROOT/forge/<id>/`, so a container whose workspace is somewhere else
    refuses with `MF0008` for a draft that is right there — and the refusal names the draft
    rather than the mount, so nobody would think to look here."""
    declared = {
        name: env_of(base["services"][name])["MENDEL_WORKSPACE_ROOT"] for name in FORGE_SERVICES
    }
    assert len(set(declared.values())) == 1, declared

    mounted = {name: _mounts(base["services"][name]).get(declared[name]) for name in FORGE_SERVICES}
    assert all(mounted.values()), f"a workspace path with nothing behind it: {mounted}"
    assert len(set(mounted.values())) == 1, mounted


def test_the_forge_services_agree_on_where_the_registry_is(base):
    """The candidate is validated against the layer and then landed into it. Two clones would
    make *green* a statement about a different registry than the one a contract lands in —
    which is the fact `MF0301`'s stale-base refusal exists to catch one level up."""
    declared = {
        name: env_of(base["services"][name])["MENDEL_REGISTRY_ROOT"] for name in FORGE_SERVICES
    }
    assert len(set(declared.values())) == 1, declared

    mounted = {name: _mounts(base["services"][name]).get(declared[name]) for name in FORGE_SERVICES}
    assert all(mounted.values()), mounted
    assert len(set(mounted.values())) == 1, mounted


def test_prod_keeps_the_forge_paths_the_base_has(base, prod):
    """**The overlay is safety, not capability** — its own header. A mount it drops is a mount
    prod does not have.

    `.run/drafts` was exactly that until 2026-09-05: the base fixed a shared-artifact bug in
    August, this file kept the shape from before it, and `make prod` therefore still had the
    bug the base's comment describes as fixed. Found by writing this test.
    """
    for name in FORGE_SERVICES:
        mounted = _mounts(prod["services"][name])
        assert "/app/workspace" in mounted, name
        assert "/app/registry" in mounted, name
        assert "/app/drafts" in mounted, f"{name}: keep writes here and the gate job reads it"


def test_the_ai_worker_is_not_behind_a_profile(base):
    """**The other half of the model server's profile.** It is the image `api` already builds,
    so it costs no download; and without it the AI queue never drains, so an adaptation sits at
    `queued` forever with nothing on screen saying why. `/api/health/ai` reports a missing
    worker, which is only a meaningful report if having one is the ordinary arrangement."""
    assert "profiles" not in base["services"]["ai-worker"]


def test_the_pulled_models_survive_a_restart(base):
    """A named volume, not an anonymous one. Anonymous makes every `down` and `up` a
    re-download, which is the whole cost this service has.

    **The mount became a setting and the property is now about its default.** `OLLAMA_MODELS`
    lets an operator bind a host Ollama's home in place rather than downloading a second copy
    of several gigabytes — and an operator who sets nothing must land on the named volume, not
    on an anonymous one. This guard caught its own service changing under it.
    """
    declared = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["volumes"]
    assert "ollama-models" in declared

    mounts = base["services"]["ollama"]["volumes"]
    assert any(m.startswith("${OLLAMA_MODELS:-ollama-models}:") for m in mounts), mounts


def test_the_ai_lane_is_configured_by_the_shared_names(base):
    """**`COMENI_AI_*` and nothing else**, which is what makes a hosted deployment a
    configuration change rather than a code change — invariant 13. A `MENDEL_AI_MODEL` beside
    them would be a second answer to *which model*, and an operator's `.env` would have to know
    which consumer read which. `comeni_ai.access` is where those names are declared."""
    lane = env_of(base["services"]["ai-worker"])
    assert {"COMENI_AI_MODEL", "COMENI_AI_BASE_URL", "COMENI_AI_API_KEY"} <= set(lane)
    assert not [name for name in lane if name.startswith("MENDEL_AI_")]


def test_no_credential_is_written_into_the_compose_file(base):
    """Every `COMENI_` name is `${...}` with an empty default, so a secret lives in `.env` and
    never in a file that is committed. A literal here would be a credential in git history,
    which is the one mistake with no undo.

    **Every service and every `COMENI_` name, not the AI worker's `COMENI_AI_` block.** It was
    scoped to one service and one prefix, and `COMENI_FORGE_GITHUB_TOKEN` arrived on three
    services — outside the loop on both axes. A guard that only watches where the last
    credential went is a guard that misses the next one.
    """
    for service, spec in base["services"].items():
        environment = env_of(spec)
        for name, value in environment.items():
            if name.startswith("COMENI_"):
                assert str(value).startswith("${"), f"{service}.{name} is a literal"


def test_the_token_reaches_every_service_that_reads_an_upstream(base):
    """**Every Mendel service gets it**, so whichever one the forge publishes from has it.

    The forge opens pull requests and publishes releases on the registry
    (`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`). A missing token is not an error
    at startup; it is publishing that says it is unavailable.
    """
    for service in ("api", "mendel-worker", "ai-worker"):
        environment = env_of(base["services"][service])
        assert "COMENI_FORGE_GITHUB_TOKEN" in environment, service


def test_nothing_but_the_ai_worker_runs_the_ai_queue(base):
    """`AIWorkerSettings.functions` is the allowlist of what may reach a provider, and it is an
    allowlist only if one process runs it. Two services on that worker would make *which
    container called the model* depend on which one ARQ handed the job to."""
    running = [
        name
        for name, service in base["services"].items()
        if "ai_worker.AIWorkerSettings" in str(service.get("command", ""))
    ]
    assert running == ["ai-worker"]


def test_the_model_server_keeps_the_model_loaded_and_serves_one_slot(base):
    """#184, #185: an unloaded model costs 7–8 s to reload, and a prefix is reused only by the
    slot that last held it. Defaults an operator can override; the app assumes neither."""
    env = base["services"]["ollama"]["environment"]
    assert "OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE:-1h}" in env
    assert "OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-1}" in env


def test_the_model_server_image_is_pinned_to_an_exact_version(base):
    image = base["services"]["ollama"]["image"]
    assert image.startswith("${OLLAMA_IMAGE:-ollama/ollama:")
    assert ":latest" not in image and "0.6.5" not in image


def test_every_service_that_reaches_a_model_gets_every_model_setting(base):
    """Review I2 and I3 (settings, 14.7.5.4). A service handed `COMENI_AI_MODEL` reads Settings →
    Models too, so it needs the key that opens stored secrets and every purpose's `.env` pin.
    One process with the key and another without is the crash the review reproduced."""
    from comeni_core.settings import SETTINGS_KEY_ENV, catalogue

    needed = {SETTINGS_KEY_ENV} | {
        s.env for s in (catalogue.DEFAULT_MODEL, *catalogue.PURPOSE_SETTINGS) if s.env
    }
    reaching = {
        name: set(service.get("environment") or {})
        for name, service in base["services"].items()
        if "COMENI_AI_MODEL" in (service.get("environment") or {})
    }
    assert reaching, "no service is handed COMENI_AI_MODEL — this test is measuring nothing"
    missing = {name: sorted(needed - env) for name, env in reaching.items() if needed - env}
    assert not missing, f"services that reach a model without every model setting: {missing}"


def test_a_service_that_restarts_itself_has_what_it_depends_on_restart_too(base):
    """Issue 268: after a reboot the workers, the ingest and the web came back (they are
    `unless-stopped`, for crash recovery) while Postgres and Redis did not, so the workers
    crash-looped until somebody ran `make dev`. Whatever comes back on its own must find what
    it needs: the operator chose the whole stack coming back, as the prod overlay already does."""
    services = base["services"]
    restarting = {name for name, svc in services.items() if svc.get("restart")}
    assert restarting, "nothing restarts: this would check nothing"
    stranded = {
        (name, needed)
        for name in restarting
        for needed in services[name].get("depends_on", {})
        if needed not in restarting
    }
    assert stranded == set(), (
        f"these restart by themselves and depend on a service that does not: {sorted(stranded)}"
    )

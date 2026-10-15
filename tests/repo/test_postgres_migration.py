"""Real PostgreSQL initialization, role isolation, restore verification and cutover refusal.

All containers and named volumes are disposable and uniquely named. No application stack or
existing volume is used. Run with -m slow and Docker access.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

import psycopg
import pytest
from support.paths import ROOT

pytestmark = pytest.mark.slow


def docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], text=True, capture_output=True, check=check, timeout=90
    )


def migration_tool():
    spec = importlib.util.spec_from_file_location(
        "consolidate_postgres", ROOT / "tools/consolidate_postgres.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def servers(tmp_path_factory):
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    prefix = "comeni-pg-test-" + uuid.uuid4().hex[:10]
    made_containers, made_volumes = [], []
    found = {"project": prefix, "root": tmp_path_factory.mktemp("postgres-migration")}
    try:
        for name in ("mendel", "wiener", "target", "fresh"):
            container = f"{prefix}-{name}"
            volume = f"{container}-data"
            label = f"{name}-pg" if name in ("mendel", "wiener") else "comeni-pg"
            docker(
                "volume",
                "create",
                "--label",
                f"com.docker.compose.project={prefix}",
                "--label",
                f"com.docker.compose.volume={label}",
                volume,
            )
            made_volumes.append(volume)
            user = name if name in ("mendel", "wiener") else "comeni_admin"
            args = [
                "run",
                "-d",
                "--name",
                container,
                "--publish",
                "127.0.0.1::5432",
                "--mount",
                f"type=volume,source={volume},target=/var/lib/postgresql/data",
                "-e",
                f"POSTGRES_USER={user}",
                "-e",
                f"POSTGRES_PASSWORD={user}",
                "-e",
                f"POSTGRES_DB={name if name in ('mendel', 'wiener') else 'postgres'}",
            ]
            if name in ("target", "fresh"):
                args += ["-e", "MENDEL_DB_PASSWORD=mendel", "-e", "WIENER_DB_PASSWORD=wiener"]
                for source, target in (
                    (
                        "validate-passwords.sh",
                        "/docker-entrypoint-initdb.d/00-validate-passwords.sh",
                    ),
                    ("init.sql", "/docker-entrypoint-initdb.d/10-applications.sql"),
                    ("healthcheck.sh", "/usr/local/bin/comeni-postgres-health"),
                ):
                    args += [
                        "--mount",
                        f"type=bind,source={ROOT / 'ops/postgres' / source},"
                        f"target={target},readonly",
                    ]
            docker(*args, "postgres:17-alpine")
            made_containers.append(container)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                probe = docker(
                    "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", user, check=False
                )
                if probe.returncode == 0:
                    break
                time.sleep(0.2)
            else:
                pytest.fail(
                    f"Disposable PostgreSQL {name} did not initialize: "
                    + docker("logs", container).stdout[-2000:]
                )
            port = json.loads(docker("inspect", container).stdout)[0]["NetworkSettings"]["Ports"][
                "5432/tcp"
            ][0]["HostPort"]
            found[name] = {"container": container, "volume": volume, "port": port}
        yield found
    finally:
        for container in reversed(made_containers):
            docker("rm", "-f", container, check=False)
        for volume in reversed(made_volumes):
            docker("volume", "rm", volume, check=False)


def upgrade(server, database):
    url = f"postgresql+psycopg://{database}:{database}@127.0.0.1:{server['port']}/{database}"
    env = {**os.environ, f"{database.upper()}_DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=ROOT / "packages" / f"{database}-api",
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr


def connect(server, user, database):
    return psycopg.connect(
        host="127.0.0.1",
        port=server["port"],
        user=user,
        password=user,
        dbname=database,
        connect_timeout=3,
    )


def test_fresh_server_runs_both_migration_chains_with_isolated_roles(servers):
    server = servers["fresh"]
    module = migration_tool()
    module.check_roles(server["container"])
    assert (
        docker(
            "exec", server["container"], "sh", "/usr/local/bin/comeni-postgres-health"
        ).returncode
        == 0
    )
    for owner, other in (("mendel", "wiener"), ("wiener", "mendel")):
        upgrade(server, owner)
        with connect(server, owner, owner) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            assert db.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
                "WHERE rolname = current_user"
            ).fetchone() == (False, False, False)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("CREATE ROLE forbidden_role")
        for database in (other, "postgres"):
            with pytest.raises(psycopg.OperationalError, match="permission denied for database"):
                connect(server, owner, database)


def test_existing_data_round_trip_is_verified_and_legacy_volumes_survive(servers, tmp_path):
    module = migration_tool()
    sources = {name: servers[name]["container"] for name in ("mendel", "wiener")}
    for database in sources:
        upgrade(servers[database], database)
        module.sql(
            sources[database],
            database,
            database,
            """
            CREATE TABLE migration_probe (id bigserial PRIMARY KEY, payload jsonb, raw bytea);
            INSERT INTO migration_probe(payload, raw)
            VALUES ('{"text":"tab\\tline\\n雪"}', '\\x00ff');
            INSERT INTO migration_probe(payload, raw)
            VALUES ('{"number":42}', '\\x0102');
            SELECT nextval('migration_probe_id_seq');
        """,
        )
    directory = tmp_path / "backup"
    module.backup(directory, sources)
    assert directory.stat().st_mode & 0o077 == 0
    assert all(path.stat().st_mode & 0o077 == 0 for path in directory.iterdir())
    manifest = module.load_backup(directory)
    target = servers["target"]["container"]
    root = servers["root"]
    (root / "docker-compose.yml").write_text(
        f"name: {servers['project']}\nservices:\n  postgres:\n    image: postgres:17-alpine\n"
        f"    volumes: [comeni-pg:/var/lib/postgresql/data]\nvolumes:\n  comeni-pg:\n"
        f"    external: true\n    name: {servers['target']['volume']}\n"
    )
    with pytest.raises(RuntimeError, match="Legacy PostgreSQL volumes exist"):
        module.check_cutover(root)
    record = root / module.MARKER
    with pytest.raises(RuntimeError, match="legacy source data volume"):
        module.verify(directory, sources["mendel"], restore=True)
    module.verify(directory, target, restore=True, record=record)
    module.verify(directory, target, restore=True)  # A verified first half can safely resume.
    module.check_cutover(root)
    module.sql(target, "mendel", "mendel", "ALTER TABLE retention_sweep ADD COLUMN unexpected text")
    with pytest.raises(RuntimeError, match="schema, data or sequence state differs"):
        module.verify(directory, target)
    module.sql(target, "mendel", "mendel", "ALTER TABLE retention_sweep DROP COLUMN unexpected")
    module.verify(directory, target)
    for database in sources:
        upgrade(servers["target"], database)
        with connect(servers["target"], database, database) as db:
            rows = db.execute("SELECT id, payload, raw FROM migration_probe ORDER BY id").fetchall()
            assert rows == [
                (1, {"text": "tab\tline\n雪"}, b"\x00\xff"),
                (2, {"number": 42}, b"\x01\x02"),
            ]
            assert db.execute("SELECT nextval('migration_probe_id_seq')").fetchone()[0] == 4
        assert (
            module.volume_identity(servers[database]["volume"])
            == manifest["databases"][database]["source_volume"]
        )
        # Advancing a restored sequence is meaningful drift, not a successful verification.
    with pytest.raises(RuntimeError, match="sequence state differs"):
        module.verify(directory, target)
    with pytest.raises(RuntimeError, match="refusing overwrite"):
        module.verify(directory, target, restore=True)
    recorded = json.loads(record.read_text())
    recorded["target_volume"]["CreatedAt"] = "a replaced volume"
    record.write_text(json.dumps(recorded))
    with pytest.raises(RuntimeError, match="Legacy PostgreSQL volumes exist"):
        module.check_cutover(root)
    corrupt = tmp_path / "corrupt"
    shutil.copytree(directory, corrupt)
    with (corrupt / "wiener.dump").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RuntimeError, match="checksum does not match"):
        module.verify(corrupt, target, restore=True)


def test_backup_refuses_live_application_connections(servers, tmp_path):
    module = migration_tool()
    with (
        connect(servers["mendel"], "mendel", "mendel"),
        pytest.raises(RuntimeError, match="Stop all application connections"),
    ):
        module.backup(tmp_path / "active-backup", {"mendel": servers["mendel"]["container"]})

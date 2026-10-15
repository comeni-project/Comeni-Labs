#!/usr/bin/env python3
"""Back up, restore and verify the two legacy databases without deleting their volumes.

Requires Python 3.12+ and the Docker CLI. Stop application writers before backup or restore.
Archives and manifests contain application data or fingerprints; keep the backup directory private.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DATABASES = ("mendel", "wiener")
ROOT = Path(__file__).resolve().parent.parent
MARKER = ".run/postgres-consolidated.json"


def command(args, *, data=None, stdin=None, stdout=subprocess.PIPE, timeout=300):
    """Capture errors without printing credentials, SQL values or database rows."""
    result = subprocess.run(
        args,
        input=data,
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed; no source volume was removed")
    return result.stdout


def sql(container, user, database, statement, *, stdout=subprocess.PIPE):
    return command(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-XqAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            user,
            "-d",
            database,
        ],
        data=statement.encode(),
        stdout=stdout,
    )


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def volume_identity(name):
    volume = json.loads(command(["docker", "volume", "inspect", name]))[0]
    return {key: volume[key] for key in ("Name", "CreatedAt", "Driver")}


def data_volume(container):
    info = json.loads(command(["docker", "inspect", container]))[0]
    mounts = [m for m in info["Mounts"] if m["Destination"] == "/var/lib/postgresql/data"]
    if len(mounts) != 1 or mounts[0]["Type"] != "volume":
        raise RuntimeError("Cutover recording requires a named PostgreSQL data volume")
    return volume_identity(mounts[0]["Name"])


def no_clients(container, user, database):
    count = sql(
        container,
        user,
        database,
        """
        SELECT count(*) FROM pg_stat_activity
        WHERE datname = current_database() AND pid <> pg_backend_pid()
          AND backend_type = 'client backend';
    """,
    )
    if int(count):
        raise RuntimeError(f"Stop all application connections to {database} before migration")


def schema_digest(container, user, database):
    """Hash schema meaning independently of object creation order and owner-role OIDs."""
    metadata = sql(
        container,
        user,
        database,
        """
        SET search_path = pg_catalog;
        -- Parse deparsed predicates once more, as pg_restore does. PostgreSQL can move
        -- casts from an array to its elements without changing a check's meaning.
        CREATE FUNCTION pg_temp.comeni_predicate(expression text, relation regclass)
        RETURNS text LANGUAGE plpgsql AS $body$
        BEGIN
            EXECUTE format('CREATE OR REPLACE TEMP VIEW comeni_schema_expression AS '
                           'SELECT %s AS value FROM %s', expression, relation);
            RETURN pg_get_viewdef('pg_temp.comeni_schema_expression'::regclass);
        END;
        $body$;
        WITH namespaces AS (
            SELECT oid, nspname FROM pg_namespace
            WHERE nspname NOT IN ('pg_catalog', 'information_schema')
              AND nspname NOT LIKE 'pg_toast%' AND nspname NOT LIKE 'pg_temp_%'
        ), entries AS (
            SELECT 'schema' AS kind, n.nspname AS schema, n.nspname AS name,
                '' AS definition FROM namespaces n
            UNION ALL
            SELECT 'relation', n.nspname, c.relname,
                json_build_array(c.relkind, c.relpersistence, c.relrowsecurity,
                    c.relforcerowsecurity, pg_get_partkeydef(c.oid),
                    pg_get_expr(c.relpartbound, c.oid),
                    CASE WHEN c.relkind IN ('v', 'm') THEN pg_get_viewdef(c.oid) END)::text
            FROM pg_class c JOIN namespaces n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'v', 'm')
            UNION ALL
            SELECT 'column', n.nspname, c.relname,
                json_build_array(row_number() OVER (PARTITION BY c.oid ORDER BY a.attnum),
                    a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                    pg_get_expr(d.adbin, d.adrelid), a.attidentity, a.attgenerated)::text
            FROM pg_class c JOIN namespaces n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
            WHERE c.relkind IN ('r', 'p', 'v', 'm') AND a.attnum > 0 AND NOT a.attisdropped
            UNION ALL
            SELECT 'constraint', n.nspname, c.relname,
                json_build_array(k.conname, k.contype, k.convalidated,
                    CASE WHEN k.contype = 'c'
                    THEN pg_temp.comeni_predicate(pg_get_expr(k.conbin, k.conrelid), k.conrelid)
                    ELSE pg_get_constraintdef(k.oid) END)::text
            FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
            JOIN namespaces n ON n.oid = c.relnamespace
            UNION ALL
            SELECT 'index', n.nspname, c.relname,
                json_build_array(am.amname, i.indisunique, i.indisprimary, i.indisexclusion,
                    i.indisvalid, i.indnkeyatts, i.indoption::text,
                    ARRAY(SELECT pg_get_indexdef(i.indexrelid, position, false)
                          FROM generate_series(1, i.indnatts) position),
                    ARRAY(SELECT opn.nspname || '.' || op.opcname
                          FROM unnest(i.indclass) WITH ORDINALITY cl(id, position)
                          JOIN pg_opclass op ON op.oid = cl.id
                          JOIN pg_namespace opn ON opn.oid = op.opcnamespace ORDER BY position),
                    ARRAY(SELECT id::regcollation::text
                          FROM unnest(i.indcollation) WITH ORDINALITY co(id, position)
                          ORDER BY position),
                    CASE WHEN i.indpred IS NOT NULL
                    THEN pg_temp.comeni_predicate(pg_get_expr(i.indpred, i.indrelid), i.indrelid)
                    END)::text
            FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_am am ON am.oid = c.relam
            JOIN namespaces n ON n.oid = c.relnamespace
            UNION ALL
            SELECT 'sequence', n.nspname, c.relname,
                json_build_array(format_type(s.seqtypid, NULL), s.seqstart, s.seqincrement,
                    s.seqmax, s.seqmin, s.seqcache, s.seqcycle)::text
            FROM pg_sequence s JOIN pg_class c ON c.oid = s.seqrelid
            JOIN namespaces n ON n.oid = c.relnamespace
            UNION ALL
            SELECT 'function', n.nspname, p.proname, pg_get_functiondef(p.oid)
            FROM pg_proc p JOIN namespaces n ON n.oid = p.pronamespace
            WHERE p.prokind IN ('f', 'p', 'w')
            UNION ALL
            SELECT 'trigger', n.nspname, c.relname, pg_get_triggerdef(t.oid)
            FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            JOIN namespaces n ON n.oid = c.relnamespace WHERE NOT t.tgisinternal
            UNION ALL
            SELECT 'enum', n.nspname, t.typname,
                (SELECT json_agg(e.enumlabel ORDER BY e.enumsortorder)::text
                 FROM pg_enum e WHERE e.enumtypid = t.oid)
            FROM pg_type t JOIN namespaces n ON n.oid = t.typnamespace WHERE t.typtype = 'e'
        )
        SELECT COALESCE(json_agg(json_build_array(kind, schema, name, definition)
            ORDER BY kind COLLATE "C", schema COLLATE "C", name COLLATE "C",
                     definition COLLATE "C"), '[]'::json) FROM entries;
    """,
    )
    return hashlib.sha256(metadata).hexdigest()


def fingerprint(container, user, database):
    """Hash sorted COPY rows on disk, bounding Python memory independently of database size."""
    relations = json.loads(
        sql(
            container,
            user,
            database,
            """
        SELECT COALESCE(json_agg(json_build_array(n.nspname, c.relname, c.relkind)
            ORDER BY n.nspname COLLATE "C", c.relname COLLATE "C"), '[]'::json)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r', 'p', 'S');
    """,
        )
    )
    tables, sequences = [], []
    for schema, name, kind in relations:
        qualified = f"{identifier(schema)}.{identifier(name)}"
        if kind == "S":
            state = json.loads(
                sql(
                    container,
                    user,
                    database,
                    f"SELECT json_build_array(last_value, is_called) FROM {qualified};",
                )
            )
            sequences.append({"schema": schema, "name": name, "state": state})
            continue
        statement = (
            "SET timezone = 'UTC'; SET datestyle = 'ISO, YMD'; SET extra_float_digits = 3;\n"
            f"COPY (SELECT row_to_json(t)::text FROM {qualified} t "
            'ORDER BY row_to_json(t)::text COLLATE "C") TO STDOUT;'
        )
        digest, rows = hashlib.sha256(), 0
        with tempfile.TemporaryFile() as output:
            sql(container, user, database, statement, stdout=output)
            output.seek(0)
            while chunk := output.read(1024 * 1024):
                digest.update(chunk)
                rows += chunk.count(b"\n")
        tables.append({"schema": schema, "name": name, "rows": rows, "sha256": digest.hexdigest()})
    return {
        "schema_sha256": schema_digest(container, user, database),
        "tables": tables,
        "sequences": sequences,
    }


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def backup(directory, sources):
    """Create new private archives and verify that the source data stayed unchanged."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {"version": 1, "databases": {}}
    for database, container in sources.items():
        no_clients(container, database, database)
        before = fingerprint(container, database, database)
        archive = directory / f"{database}.dump"
        with archive.open("xb") as output:
            archive.chmod(0o600)
            command(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_dump",
                    "-Fc",
                    "--no-owner",
                    "--no-acl",
                    "-U",
                    database,
                    "-d",
                    database,
                ],
                stdout=output,
            )
        after = fingerprint(container, database, database)
        no_clients(container, database, database)
        if before != after:
            raise RuntimeError(
                f"{database} changed during backup; freeze writers and start a new backup"
            )
        manifest["databases"][database] = {
            "source_container": container,
            "source_volume": data_volume(container),
            "archive_sha256": file_digest(archive),
            "fingerprint": before,
        }
    write_private(directory / "manifest.json", manifest)
    print(f"Backed up both databases to {directory}; source volumes retained.")


def load_backup(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("version") != 1 or set(manifest.get("databases", {})) != set(DATABASES):
        raise RuntimeError("Unrecognized or incomplete migration manifest")
    for database in DATABASES:
        if (
            file_digest(directory / f"{database}.dump")
            != manifest["databases"][database]["archive_sha256"]
        ):
            raise RuntimeError(f"{database} backup checksum does not match; target left untouched")
    return manifest


def check_roles(container):
    valid = sql(
        container,
        "comeni_admin",
        "postgres",
        """
        SELECT count(*) = 2 AND bool_and(NOT rolsuper AND NOT rolcreatedb
            AND NOT rolcreaterole AND NOT rolreplication)
        FROM pg_roles WHERE rolname IN ('mendel', 'wiener');
        SELECT has_database_privilege('mendel', 'mendel', 'CONNECT')
           AND has_database_privilege('wiener', 'wiener', 'CONNECT')
           AND NOT has_database_privilege('mendel', 'wiener', 'CONNECT')
           AND NOT has_database_privilege('wiener', 'mendel', 'CONNECT')
           AND NOT has_database_privilege('mendel', 'postgres', 'CONNECT')
           AND NOT has_database_privilege('wiener', 'postgres', 'CONNECT');
    """,
    )
    if valid.split() != [b"t", b"t"]:
        raise RuntimeError("Target application roles are missing, privileged or not isolated")


def verify(directory, target, *, restore=False, record=None):
    """Restore only empty databases, then compare every table and sequence with the backup."""
    manifest = load_backup(directory)
    target_volume = data_volume(target)
    if target_volume in [m["source_volume"] for m in manifest["databases"].values()]:
        raise RuntimeError("A legacy source data volume cannot be the restore target")
    check_roles(target)
    for database in DATABASES:
        no_clients(target, "comeni_admin", database)
        expected = manifest["databases"][database]["fingerprint"]
        current = fingerprint(target, database, database)
        if restore and current != expected:
            if current["tables"] or current["sequences"]:
                raise RuntimeError(
                    f"Target {database} is not empty or already verified; refusing overwrite"
                )
            with (directory / f"{database}.dump").open("rb") as archive:
                command(
                    [
                        "docker",
                        "exec",
                        "-i",
                        target,
                        "pg_restore",
                        "--single-transaction",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                        "-U",
                        database,
                        "-d",
                        database,
                    ],
                    stdin=archive,
                )
            current = fingerprint(target, database, database)
        if current != expected:
            raise RuntimeError(f"{database} schema, data or sequence state differs from the backup")
    if record is not None:
        write_private(
            record,
            {
                "version": 1,
                "target_volume": data_volume(target),
                "backup": str(directory.resolve()),
            },
        )
    print(
        "Both databases match their backups; schemas, table contents, sequence state "
        "and role isolation verified."
    )


def check_cutover(root):
    """Refuse silent fresh startup when legacy Compose volumes still hold application data."""
    model = json.loads(
        command(
            [
                "docker",
                "compose",
                "--project-directory",
                str(root),
                "-f",
                str(root / "docker-compose.yml"),
                "config",
                "--format",
                "json",
            ],
            timeout=30,
        )
    )
    names = command(
        [
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={model['name']}",
            "--format",
            "{{.Name}}",
        ]
    )
    legacy = []
    for name in names.decode().splitlines():
        info = json.loads(command(["docker", "volume", "inspect", name]))[0]
        if (info.get("Labels") or {}).get("com.docker.compose.volume") in {
            "mendel-pg",
            "wiener-pg",
        }:
            legacy.append(name)
    if not legacy:
        return
    marker = root / MARKER
    if marker.exists():
        recorded = json.loads(marker.read_text())
        name = model["volumes"]["comeni-pg"]["name"]
        if recorded.get("version") == 1 and recorded.get("target_volume") == volume_identity(name):
            return
    raise RuntimeError(
        "Legacy PostgreSQL volumes exist. Back up, restore and verify them before startup; "
        "see ops/postgres/README.md. Existing volumes were left untouched."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check", help="refuse unverified cutover from legacy volumes")
    check.add_argument("--root", type=Path, default=ROOT)
    save = sub.add_parser("backup", help="back up quiescent legacy sources to a new directory")
    save.add_argument("--directory", required=True, type=Path)
    save.add_argument("--mendel-container", default="mendel-db")
    save.add_argument("--wiener-container", default="wiener-db")
    for name in ("restore", "verify"):
        action = sub.add_parser(name, help=f"{name} both databases against a migration backup")
        action.add_argument("--directory", required=True, type=Path)
        action.add_argument("--target", default="comeni-db")
        action.add_argument(
            "--record", type=Path, help="record verified volume identity for Make startup"
        )
    args = parser.parse_args()
    for key in ("target", "mendel_container", "wiener_container"):
        value = getattr(args, key, None)
        if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
            parser.error("container names must contain only letters, digits, _, . and -")
    os.umask(0o077)
    if args.action == "check":
        check_cutover(args.root)
    elif args.action == "backup":
        backup(args.directory, {"mendel": args.mendel_container, "wiener": args.wiener_container})
    else:
        verify(args.directory, args.target, restore=args.action == "restore", record=args.record)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"PostgreSQL migration: {error}", file=sys.stderr)
        raise SystemExit(1) from None

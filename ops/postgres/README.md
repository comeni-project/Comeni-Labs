# PostgreSQL operations

One PostgreSQL 17 server holds two databases. `mendel` owns Mendel's application schema and
`wiener` owns execution records. Each has its own login role, password and Alembic history.
`comeni_admin` administers the server; application containers never receive that account.

| File | Purpose |
|---|---|
| [init.sql](init.sql) | Create application roles/databases and revoke default cross-database access on an empty volume. |
| [validate-passwords.sh](validate-passwords.sh) | Refuse application passwords that would break the connection URLs. |
| [healthcheck.sh](healthcheck.sh) | Require the final TCP listener and both non-privileged database owners. |
| [consolidate_postgres.py](../../tools/consolidate_postgres.py) | Back up the old servers, restore into the new server, verify contents and record cutover. |

`postgres` publishes `127.0.0.1:${DB_HOST_PORT:-5432}` in development. Both databases use that
port; the old Wiener port 5433 and `WIENER_DB_HOST_PORT`/`WIENER_DB_CONTAINER_NAME` no longer
configure the new service. Production publishes no database port. Application roles have no
superuser, role-creation, database-creation or replication privileges. Their own database
ownership permits schema migration; connections to the other database, `postgres` and
`template1` are denied. Database names remain visible in PostgreSQL's system catalogue.

## Fresh installation

Run `make dev`. The service initializes the new `comeni-pg` Compose volume once. The two APIs
run their own migrations before serving. The worker services keep their original database
ownership and use the same internal server hostname, `postgres`.

Local defaults are `comeni-local-admin`, `mendel` and `wiener` for the three passwords.
Before `make prod`, set distinct `POSTGRES_ADMIN_PASSWORD`, `MENDEL_DB_PASSWORD` and
`WIENER_DB_PASSWORD` values, as well as `WIENER_API_TOKEN`. Generate values with
`openssl rand -hex 24`. Application passwords must contain only letters, digits, `_` and `-`;
Compose embeds them in application connection URLs. Set host-side connection URLs to match.

The official image runs initialization files only when its data directory is empty.
Changing `.env` does not rotate an existing database role's password. Rotate a password with
an administrator's `ALTER ROLE`, then update the affected application URL/setting and restart
its clients together. Do not delete a volume to rerun initialization.

## Migrate the two existing servers

Use a maintenance window. The commands below assume default container names; substitute the
names configured by your old checkout. Keep the same Compose project name throughout cutover.
A fresh project name creates different volumes and is not a migration.

1. **Prepare rollback and freeze writers.** Record the old application commit, Compose project
   name, container names and database image versions. Keep a checkout of that commit, its two
   Compose files and the old `.env` configuration in private backup storage. Stop all old
   application writers: Mendel API, ordinary/AI workers, Wiener API/ingest/worker and any direct
   database clients. Keep both old PostgreSQL containers running for backup. Stop or pause
   Nextflow runs so they do not continue submitting events during the maintenance window.
   For a default installation:

   ```bash
   docker stop mendel-api mendel-worker mendel-ai-worker wiener-api wiener-ingest wiener-worker
   ```

2. **Create and preserve a verified source backup.** From the updated checkout:

   ```bash
   python3 tools/consolidate_postgres.py backup \
     --mendel-container mendel-db --wiener-container wiener-db \
     --directory .run/postgres-backups/before-shared-server
   ```

   The directory must be new. The tool refuses active database clients, writes custom-format
   archives, and checks that table contents and sequence state did not change during backup.
   `manifest.json` records archive SHA-256 hashes, source volume identities, schema/table fingerprints
   and sequence values. Alembic version tables are included. A failed backup has no usable
   completed manifest: keep writers stopped, diagnose the cause and use a new backup directory.
   Copy the completed private directory to separate backup storage before continuing. It
   contains application data; access permissions are restricted by the tool.

3. **Stop the old servers and start the empty shared server.** Keep their named volumes.
   Configure the new passwords in `.env`, then run:

   ```bash
   docker stop mendel-db wiener-db
   docker compose up -d postgres
   docker compose ps postgres
   ```

   Wait for the new service to be healthy. Its default container name is `comeni-db`; override
   `DB_CONTAINER_NAME` if needed. Its new volume is distinct from the old `mendel-pg` and
   `wiener-pg` volumes. Compose may replace the old Mendel container because the service key is
   still `postgres`; the old named volume survives. Do not use `down -v`, volume pruning or
   `--remove-orphans` during cutover.

4. **Restore and verify before starting applications.**

   ```bash
   python3 tools/consolidate_postgres.py restore \
     --directory .run/postgres-backups/before-shared-server \
     --target comeni-db --record .run/postgres-consolidated.json
   ```

   The tool checks all archive hashes and target role isolation before writing. It restores
   each database as its application owner, with one transaction per database. Nonempty target
   databases are refused unless their complete recorded contents already match the backup;
   that allows a matching first restore to resume after the second fails. Mismatching partial
   data is never overwritten automatically. A legacy source data volume cannot be the target.

   Verification compares restorable schema definitions, sorted table contents, row counts and
   sequence state. Schema comparison ignores ownership, ACLs, comments and tablespace placement,
   since the restore deliberately assigns application ownership. Predicate comparison uses
   connection-local temporary views to normalize equivalent PostgreSQL cast expressions;
   application tables and records are not modified. The tool also
   verifies that the application roles cannot connect to one another's database. On success,
   it records the new volume's name, creation time and driver. Make checks that identity before
   allowing startup when legacy Compose volumes remain. Replacing the target volume invalidates
   the record; retaining a stale marker does not authorize another empty cutover.

5. **Check schemas, then reopen writes.**

   ```bash
   docker compose run --rm --no-deps api sh -c 'cd packages/mendel-api && alembic upgrade head'
   docker compose run --rm --no-deps wiener-api sh -c 'cd packages/wiener-api && alembic upgrade head'
   make dev
   # Or, after setting all production credentials: make prod
   ```

   Confirm saved drafts, authoring history, run/artifact records and representative queries
   through both APIs before accepting writes. The restore comparison establishes source-data
   preservation; application migrations may intentionally transform that data afterwards.
   Keep the old volumes and backup until the installation's retention policy allows removal.
   This repository's migration tests exercise fresh migrations, restored migrations, schema drift, JSON/byte
   data, sequences, cross-database denial, live-client refusal and checksum/cutover failures on
   disposable servers. They do not migrate this installation's live data for you.

`verify` repeats the comparison without changing application tables or records:

```bash
python3 tools/consolidate_postgres.py verify \
  --directory .run/postgres-backups/before-shared-server --target comeni-db
```

Run it before reopening writers. Normal application writes, sequence advancement or later
schema migrations can make a valid running database differ from its pre-cutover backup.

## Rollback

Before reopening writes, stop the new application processes and shared server. In the retained
old checkout, restore the old `.env` values and use the original Compose project name and old
Compose files to start the two old databases. Confirm their volume mounts match the source
volume identities in the backup manifest before starting old application code. The original
volumes still contain the pre-cutover datasets; no dump restore into them is necessary.

If the old volumes are unavailable, restore the custom archives into separate PostgreSQL 17
recovery servers with the original application roles, verify their data, and point the retained
old configuration at those servers. Do not restore over an existing dataset.

After writes have reopened on the shared server, switching to the old volumes would discard
new work. Freeze writers, back up the shared server and plan the reverse data transfer and any
schema downgrade for the application's current revisions before changing the live target.
The forward migration tool deliberately does not perform that downgrade.

## Shared-server maintenance

A restart, upgrade, storage outage or resource shortage now affects both applications.
Schedule maintenance and test backup recovery for both databases together; keep their logical
archives, role credentials and migration revisions separate. Restore application ownership
and cross-database access restrictions whenever rebuilding the cluster. Monitor connection
budgets and workload contention across both applications.

Separate servers become useful again when independent availability, upgrade schedules,
resource isolation or an organizational security boundary outweigh the administrative cost.
That change should retain the same two application-owned schemas and migration histories.

PostgreSQL documents default database `CONNECT` grants in its
[privilege reference](https://www.postgresql.org/docs/17/ddl-priv.html), and dump/restore ownership
behavior in its [backup guide](https://www.postgresql.org/docs/17/backup-dump.html).
The [official image documentation](https://hub.docker.com/_/postgres) explains one-time
initialization of an empty data directory.

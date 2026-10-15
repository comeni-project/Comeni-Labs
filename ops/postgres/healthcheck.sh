#!/bin/sh
# TCP stays unavailable until initialization ends; also reject incomplete role/database setup.
set -eu
pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres >/dev/null
roles=$(psql -XqAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c \
  "SELECT count(*) FROM pg_roles WHERE rolname IN ('mendel','wiener') AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication")
databases=$(psql -XqAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c \
  "SELECT count(*) FROM pg_database WHERE (datname='mendel' AND pg_get_userbyid(datdba)='mendel') OR (datname='wiener' AND pg_get_userbyid(datdba)='wiener')")
[ "$roles" = 2 ] && [ "$databases" = 2 ]

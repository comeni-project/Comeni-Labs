-- Run once on an empty PostgreSQL volume, as the separate cluster administrator.
-- Application passwords must be URL-safe because Compose embeds them in connection URLs.
\getenv mendel_password MENDEL_DB_PASSWORD
\getenv wiener_password WIENER_DB_PASSWORD

CREATE ROLE mendel LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD :'mendel_password';
CREATE ROLE wiener LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD :'wiener_password';
CREATE DATABASE mendel OWNER mendel;
CREATE DATABASE wiener OWNER wiener;

-- CONNECT is granted to PUBLIC by default, including on the maintenance databases.
REVOKE ALL ON DATABASE mendel, wiener, postgres, template1 FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE mendel TO mendel;
GRANT CONNECT, TEMPORARY ON DATABASE wiener TO wiener;

\connect mendel
REVOKE ALL ON SCHEMA public FROM PUBLIC;
\connect wiener
REVOKE ALL ON SCHEMA public FROM PUBLIC;

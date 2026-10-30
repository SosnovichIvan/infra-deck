#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\set owner_password `cat /run/secrets/db_owner_password`
\set app_password `cat /run/secrets/db_app_password`
CREATE ROLE infradeck_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE infradeck_app LOGIN PASSWORD :'app_password';
CREATE DATABASE infradeck OWNER infradeck_owner;
REVOKE ALL ON DATABASE infradeck FROM PUBLIC;
GRANT CONNECT ON DATABASE infradeck TO infradeck_app;
\connect infradeck
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO infradeck_app;
ALTER DEFAULT PRIVILEGES FOR ROLE infradeck_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO infradeck_app;
ALTER DEFAULT PRIVILEGES FOR ROLE infradeck_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO infradeck_app;
SQL

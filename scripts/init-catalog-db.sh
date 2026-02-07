#!/bin/bash
# Create the catalog database if it doesn't exist.
# Intended to run inside the postgres container or as a postgres init script.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE catalog OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'catalog')\gexec
EOSQL

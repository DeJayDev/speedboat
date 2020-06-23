#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "rowboat" -d rowboat -c "CREATE DATABASE rowboat;"
psql -v ON_ERROR_STOP=1 --username "rowboat" -d rowboat -c "CREATE EXTENSION hstore;"
psql -v ON_ERROR_STOP=1 --username "rowboat" -d rowboat -c "CREATE EXTENSION pg_trgm WITH SCHEMA pg_catalog;"

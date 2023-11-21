set -e

psql -v ON_ERROR_STOP=1 rowboat -c "CREATE DATABASE IF NOT EXISTS rowboat;"
psql -v ON_ERROR_STOP=1 rowboat -c "CREATE EXTENSION hstore;"
psql -v ON_ERROR_STOP=1 rowboat -c "CREATE EXTENSION pg_trgm;"

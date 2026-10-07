#!/bin/sh
set -eu

: "${PGHOST:?Define PGHOST}"
: "${PGPORT:?Define PGPORT}"
: "${PGDATABASE:?Define PGDATABASE}"
: "${PGUSER:?Define PGUSER}"
: "${BACKUP_DIR:=/var/backups/herramientas-jg}"
: "${BACKUP_RETENTION_DAYS:=14}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$BACKUP_DIR/herramientas_jg_${timestamp}.dump"
temporary="${output}.tmp"

trap 'rm -f "$temporary"' EXIT HUP INT TERM
pg_dump --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --dbname="$PGDATABASE" --format=custom --no-owner --no-acl --file="$temporary"
mv "$temporary" "$output"
find "$BACKUP_DIR" -type f -name 'herramientas_jg_*.dump' \
    -mtime "+${BACKUP_RETENTION_DAYS}" -delete

#!/usr/bin/env bash
# DB data only. Key material must have an independent protected off-VPS backup.
set -euo pipefail
[[ "$EUID" = 0 ]] || exit 2
umask 077
directory=/var/backups/infradeck
install -d -m 700 "$directory"
temporary="$(mktemp "$directory/.dump.XXXXXX")"
trap 'rm -f "$temporary"' EXIT
docker exec infradeck-db-1 pg_dump -U postgres -Fc infradeck > "$temporary"
docker exec -i infradeck-db-1 pg_restore --list < "$temporary" >/dev/null
mv "$temporary" "$directory/daily-$(date -u +%Y%m%dT%H%M%SZ).dump"
find "$directory" -maxdepth 1 -type f -name 'daily-*.dump' -mtime +14 -delete

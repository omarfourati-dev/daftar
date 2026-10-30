#!/bin/sh
# Daftar – backup of the database (fixlist 7). Runs in the container daftar-backup (postgres:17-alpine, see
# docker-compose.prod.yml); the dumps live in the named Docker volume daftar_backups, outside /home/daftar (which the
# deploy syncs with rsync --delete).
#
#   backup.sh           one backup now: pg_dump -Fc → $BACKUP_DIR/daftar-YYYY-MM-DD_HHMM.dump, then delete the dumps
#                       older than $RETENTION_DAYS days
#   backup.sh --daily   wait for $BACKUP_TIME (wall clock of $TZ), back up, repeat – the container's command
#   backup.sh --next    print the seconds until the next $BACKUP_TIME (NOW=<epoch seconds> replaces the clock; tests)
#
# Connection: the libpq variables PGHOST, PGPORT, PGUSER, PGDATABASE and PGPASSWORD. The password is never printed:
# no `set -x`, no environment dumps; pg_dump reads PGPASSWORD itself and its messages never contain it.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
BACKUP_TIME="${BACKUP_TIME:-02:30}"
PREFIX=daftar

log() {
  printf '%s backup: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"
}

backup_once() {
  mkdir -p "$BACKUP_DIR"
  target="$BACKUP_DIR/$PREFIX-$(date '+%Y-%m-%d_%H%M').dump"
  partial="$target.partial"
  if ! pg_dump --format=custom --file="$partial"; then
    rm -f "$partial"
    log "FAILED – pg_dump could not back up the database (see the message above)"
    return 1
  fi
  mv "$partial" "$target"
  log "ok $target ($(wc -c < "$target") bytes)"
  # keep RETENTION_DAYS days: -mtime +N means "at least N+1 full days old"
  find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PREFIX-*.dump" -mtime "+$((RETENTION_DAYS - 1))" | while read -r old; do
    rm -f "$old" && log "deleted $old"
  done
  # leftovers of interrupted runs
  find "$BACKUP_DIR" -maxdepth 1 -type f -name "$PREFIX-*.dump.partial" -mmin +60 -exec rm -f {} \;
}

seconds_until() {
  now="${NOW:-$(date +%s)}"
  next=$(date -d "$(date -d "@$now" '+%Y-%m-%d') $1" +%s)
  if [ "$next" -le "$now" ]; then
    next=$(date -d "$(date -d "@$((now + 86400))" '+%Y-%m-%d') $1" +%s)
  fi
  echo $((next - now))
}

daily() {
  trap 'log "stopped"; exit 0' TERM INT
  log "daily at $BACKUP_TIME (${TZ:-UTC}) into $BACKUP_DIR, keeping $RETENTION_DAYS days"
  while :; do
    sleep "$(seconds_until "$BACKUP_TIME")" &
    wait $!
    backup_once || log "next try tomorrow at $BACKUP_TIME"
  done
}

case "${1:-}" in
  "") backup_once ;;
  --daily) daily ;;
  --next) seconds_until "$BACKUP_TIME" ;;
  *) echo "usage: backup.sh [--daily | --next]" >&2; exit 2 ;;
esac

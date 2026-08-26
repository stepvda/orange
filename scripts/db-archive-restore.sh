#!/usr/bin/env bash
# Rebuild data/radar.db from the split archive in data/db-archive/.
#
# `unzip` cannot read a split archive directly — it reports "missing 1 required
# disk" and stops, which is the single most common way this trips people up.
# The parts have to be rejoined into one ordinary zip first, which is what
# `zip -s 0 --out` does; that step needs room for a temporary ~30 MB copy.
#
#   ./scripts/db-archive-restore.sh           # refuses to overwrite an existing DB
#   ./scripts/db-archive-restore.sh --force   # replaces it
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${RADAR_DB:-$REPO_ROOT/data/radar.db}"
ARCHIVE_DIR="$REPO_ROOT/data/db-archive"
BASENAME="radar-db"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

command -v zip   >/dev/null || { echo "restore: zip not found" >&2; exit 1; }
command -v unzip >/dev/null || { echo "restore: unzip not found" >&2; exit 1; }

[ -f "$ARCHIVE_DIR/$BASENAME.zip" ] || {
  echo "restore: no archive at $ARCHIVE_DIR/$BASENAME.zip" >&2; exit 1; }

if [ -e "$DB" ] && [ "$FORCE" -ne 1 ]; then
  echo "restore: $DB already exists — pass --force to replace it" >&2
  exit 1
fi

if [ -f "$ARCHIVE_DIR/SHA256SUMS" ]; then
  echo "restore: verifying parts"
  # SHA256SUMS also carries the line for the rebuilt radar.db, which does not
  # exist yet; check only the part files.
  ( cd "$ARCHIVE_DIR" && grep -E " +${BASENAME}\.(z[0-9]+|zip)$" SHA256SUMS | shasum -a 256 -c - )
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "restore: rejoining parts"
cp "$ARCHIVE_DIR/$BASENAME".z[0-9]* "$ARCHIVE_DIR/$BASENAME.zip" "$WORK/"
( cd "$WORK" && zip -q -s 0 "$BASENAME.zip" --out joined.zip && unzip -q -o joined.zip )

[ -f "$WORK/radar.db" ] || { echo "restore: archive did not yield radar.db" >&2; exit 1; }
sqlite3 "$WORK/radar.db" "pragma integrity_check" | grep -qx ok || {
  echo "restore: rebuilt database failed integrity_check" >&2; exit 1; }

# The stale -wal/-shm of the database being replaced belong to the old file; a
# WAL left next to a different database is how a restore ends up silently
# serving a mix of the two.
mkdir -p "$(dirname "$DB")"
rm -f "$DB" "$DB-wal" "$DB-shm"
mv "$WORK/radar.db" "$DB"

echo "restore: wrote $DB"
ls -la "$DB"

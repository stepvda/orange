#!/usr/bin/env bash
# Pack data/radar.db into the committable split archive under data/db-archive/.
#
# The database is ~126 MB, and GitHub rejects any single file over 100 MB
# outright, so it cannot be committed as-is. Two steps get it under the limit:
#
#   * VACUUM INTO, not `cp`. The database runs in WAL mode, so a plain copy of
#     radar.db taken while the app holds it open can miss committed pages that
#     still live in the -wal file. VACUUM INTO takes a read transaction and
#     writes a fresh, defragmented, self-consistent database — safe to run
#     against a live file, and it drops the freelist while it is there.
#   * zip -s 25m. Deflate takes the snapshot to roughly 30 MB, and the split
#     keeps every part well under GitHub's 50 MB warning threshold, not just
#     under the 100 MB hard limit. As the database grows the part size stays
#     put and the part count rises, so the limit is never re-approached.
#
# Run it after a pipeline refresh whenever the committed archive should follow:
#   ./scripts/db-archive-pack.sh
#
# Restore with the companion script:
#   ./scripts/db-archive-restore.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${RADAR_DB:-$REPO_ROOT/data/radar.db}"
ARCHIVE_DIR="$REPO_ROOT/data/db-archive"
BASENAME="radar-db"
PART_SIZE="${PART_SIZE:-25m}"

command -v sqlite3 >/dev/null || { echo "pack: sqlite3 not found" >&2; exit 1; }
command -v zip     >/dev/null || { echo "pack: zip not found" >&2; exit 1; }

[ -f "$DB" ] || { echo "pack: no database at $DB" >&2; exit 1; }

# Snapshot to a scratch file first. Zipping radar.db directly would archive a
# WAL-mode database whose -wal file is not part of the archive.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SNAPSHOT="$WORK/radar.db"

echo "pack: snapshotting $DB"
sqlite3 "$DB" "VACUUM INTO '$SNAPSHOT'"
sqlite3 "$SNAPSHOT" "pragma integrity_check" | grep -qx ok || {
  echo "pack: snapshot failed integrity_check" >&2; exit 1; }

# zip refuses to write a split archive over an existing one, and stale parts
# from a larger previous database would otherwise be left behind to be picked
# up by the restore.
mkdir -p "$ARCHIVE_DIR"
rm -f "$ARCHIVE_DIR/$BASENAME".z[0-9]* "$ARCHIVE_DIR/$BASENAME.zip"

echo "pack: compressing into $PART_SIZE parts"
( cd "$WORK" && zip -q -9 -s "$PART_SIZE" "$ARCHIVE_DIR/$BASENAME.zip" radar.db )

# Checksums cover the parts (so a truncated clone or a mangled Git LFS/CRLF
# round-trip is caught before unzip) and the database they rebuild.
( cd "$ARCHIVE_DIR" && shasum -a 256 "$BASENAME".z[0-9]* "$BASENAME.zip" > SHA256SUMS )
( cd "$WORK" && shasum -a 256 radar.db ) >> "$ARCHIVE_DIR/SHA256SUMS"

echo "pack: done"
ls -la "$ARCHIVE_DIR"

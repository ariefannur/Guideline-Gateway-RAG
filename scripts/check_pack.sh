#!/usr/bin/env bash

# -------------------------------------------------------------------
# check_pack.sh – Build, validate, and audit a knowledge pack
#
# Assumes execution from repository root:
#   /Users/ariefmaffrudin/Code/AI/guideline-RAG
# -------------------------------------------------------------------

set -euo pipefail

# ---------- Helper functions ----------
log() {
  echo -e "[\033[1;34mINFO\033[0m] $*"
}
err() {
  echo -e "[\033[1;31mERROR\033[0m] $*" >&2
  exit 1
}

# ---------- Configuration ----------
PACK_NAME="football-laws"
EDITION="2024-2025"
SOURCE_DIR="packs/${PACK_NAME}"
DIST_DIR="dist"
PACK_FILE="${DIST_DIR}/${PACK_NAME}-${EDITION}.kpack"
TMP_DIR="$(mktemp -d)"
# Set to 1 to run the optional token‑length audit (requires Python + transformers)
RUN_TOKEN_AUDIT=${RUN_TOKEN_AUDIT:-0}

# If manifest.json is misplaced inside eval/, move it to the pack root before building
if [[ ! -f "${SOURCE_DIR}/manifest.json" && -f "${SOURCE_DIR}/eval/manifest.json" ]]; then
  log "Moving manifest.json from eval/ to pack root"
  mv "${SOURCE_DIR}/eval/manifest.json" "${SOURCE_DIR}/manifest.json"
fi

# ---------- 1️⃣ Build the pack ----------
log "Building pack ${PACK_NAME}…"
# Determine which CLI to use – prefer kp (lightweight)
if command -v kp > /dev/null 2>&1; then
  PACK_CMD="kp"
elif command -v kpack > /dev/null 2>&1; then
  PACK_CMD="kpack"
else
  err "Neither 'kp' nor 'kpack' command found – please install the kpack CLI"
fi

log "Running: ${PACK_CMD} build \"${SOURCE_DIR}\""
if ! ${PACK_CMD} build "${SOURCE_DIR}"; then
  err "${PACK_CMD} build failed"
fi

# Verify that the .kpack file was produced
if [[ ! -f "${PACK_FILE}" ]]; then
  err "Pack file not found: ${PACK_FILE}"
fi
log "Pack built: ${PACK_FILE}"

# ---------- 2️⃣ Validate the pack using Python Packager ----------
log "Validating ${PACK_FILE} via Python Packager…"
python3 - <<PY
import sys, pathlib
from kpack.packager import Packager

pkg = pathlib.Path("${PACK_FILE}")
try:
    # Extracts to a temp dir and validates required files
    Packager.extract_kpack(str(pkg), pathlib.Path('/tmp/validate_tmp'))
    print("✅ Validation succeeded")
except Exception as e:
    print(f"❌ Validation error: {e}")
    sys.exit(1)
PY

# ---------- 3️⃣ Extract the pack ----------
log "Extracting pack to temporary directory ${TMP_DIR}…"
mkdir -p "${TMP_DIR}"
if ! tar -xzf "${PACK_FILE}" -C "${TMP_DIR}"; then
  err "Failed to extract ${PACK_FILE}"
fi
log "Extraction complete"

# ---------- 4️⃣ Verify manifest location ----------
MANIFEST_PATH="${TMP_DIR}/manifest.json"
if [[ -f "${MANIFEST_PATH}" ]]; then
  log "manifest.json found at pack root"
else
  err "manifest.json NOT found at pack root (expected ${MANIFEST_PATH})"
fi

# ---------- 5️⃣ Quick SQLite sanity check ----------
DB_PATH="${TMP_DIR}/knowledge.sqlite"
if [[ ! -f "${DB_PATH}" ]]; then
  err "SQLite DB not found at ${DB_PATH}"
fi
log "Running SQLite sanity query (first 20 chunks)…"
sqlite3 "${DB_PATH}" <<'SQL'
.headers on
.mode column
SELECT
    rowid        AS id,
    chunk_id,
    law_no,
    law_title,
    page,
    edition,
    LENGTH(text) AS char_len,
    SUBSTR(text,1,80) || '…' AS snippet
FROM chunks
ORDER BY law_no, page
LIMIT 20;
SQL

# ---------- 6️⃣ Optional token‑length audit ----------
if [[ "${RUN_TOKEN_AUDIT}" -eq 1 ]]; then
  log "Running token‑length audit (requires Python & transformers)…"
  python3 - <<'PY'
import pathlib, sqlite3, sys
from transformers import AutoTokenizer

DB = pathlib.Path("${DB_PATH}")
if not DB.is_file():
    sys.exit("SQLite DB not found")

tok = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-small")
conn = sqlite3.connect(DB)
cur = conn.cursor()
bad = []
for rowid, txt in cur.execute("SELECT rowid, text FROM chunks"):
    n = len(tok.encode(txt, add_special_tokens=False))
    if not (150 <= n <= 350):
        bad.append((rowid, n))
print(f"Total chunks checked: {cur.rowcount}")
print(f"Chunks out of range (150‑350 tokens): {len(bad)}")
if bad:
    for r, n in bad[:10]:
        print(f"  rowid={r} tokens={n}")
PY
else
  log "Token audit skipped (set RUN_TOKEN_AUDIT=1 to enable)"
fi

# ---------- Cleanup ----------
log "Cleaning up temporary directory"
rm -rf "${TMP_DIR}"
log "All done!"

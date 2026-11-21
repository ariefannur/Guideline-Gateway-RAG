#!/usr/bin/env bash

# -------------------------------------------------------------------
# build_pack.sh – Build a .kpack Knowledge Pack
#
# Usage:
#   ./scripts/build_pack.sh [pack_name] [edition]
#   Defaults: pack_name=football-laws, edition=2024-2025
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

# ---------- Argument handling ----------
PACK_NAME=${1:-football-laws}
EDITION=${2:-2024-2025}
SOURCE_DIR="packs/${PACK_NAME}"
DIST_DIR="dist"
OUTPUT_FILE="${DIST_DIR}/${PACK_NAME}-${EDITION}.kpack"

log "Building pack '${PACK_NAME}' (edition ${EDITION})"

# Ensure source directory exists
if [[ ! -d "${SOURCE_DIR}" ]]; then
  err "Source directory not found: ${SOURCE_DIR}"
fi

# Move manifest.json to the pack root if it lives under eval/
if [[ ! -f "${SOURCE_DIR}/manifest.json" && -f "${SOURCE_DIR}/eval/manifest.json" ]]; then
  log "Moving manifest.json from eval/ to pack root"
  mv "${SOURCE_DIR}/eval/manifest.json" "${SOURCE_DIR}/manifest.json"
fi

# Ensure the original PDF from the top-level sources directory is present in the pack's sources folder
TOP_PDF_DIR="packs/sources"
mkdir -p "${SOURCE_DIR}/sources"
if compgen -G "${TOP_PDF_DIR}/*.pdf" > /dev/null; then
  log "Copying original PDF(s) from ${TOP_PDF_DIR} to ${SOURCE_DIR}/sources/"
  cp "${TOP_PDF_DIR}"/*.pdf "${SOURCE_DIR}/sources/"
  # Primary extraction with pdftotext
  if command -v pdftotext > /dev/null 2>&1; then
    PDF_PATH="${SOURCE_DIR}/sources/Laws-of-the-Game-2024_25.pdf"
    MD_PATH="${SOURCE_DIR}/sources/laws.md"
    log "Extracting PDF to markdown with pdftotext (primary)"
    pdftotext -layout "$PDF_PATH" "$MD_PATH"
  else
    log "pdftotext not installed – skipping primary extraction"
  fi

  # Fallback extraction with pdfminer (captures tables/columns)
  if command -v pdf2txt.py > /dev/null 2>&1; then
    log "Running pdfminer fallback extraction"
    pdf2txt.py -o "${SOURCE_DIR}/sources/laws_fallback.txt" "$PDF_PATH"
    if [ -s "${SOURCE_DIR}/sources/laws_fallback.txt" ]; then
      log "Appending fallback extraction to laws.md"
      cat "${SOURCE_DIR}/sources/laws_fallback.txt" >> "$MD_PATH"
    fi
  else
    log "pdfminer not installed – no fallback extraction"
  fi
fi


# Determine which CLI to use – prefer kp (the lightweight builder)
if command -v kp > /dev/null 2>&1; then
  PACK_CMD="kp"
elif command -v kpack > /dev/null 2>&1; then
  PACK_CMD="kpack"
else
  err "Neither 'kp' nor 'kpack' command found on PATH – please install the kpack CLI"
fi

log "Running: ${PACK_CMD} build \"${SOURCE_DIR}\""
if ! ${PACK_CMD} build "${SOURCE_DIR}"; then
  err "${PACK_CMD} build failed"
fi

# Verify the archive was created; kpack may place the .kpack next to the source directory
if [[ -f "${OUTPUT_FILE}" ]]; then
  log "Pack archive found at expected location: ${OUTPUT_FILE}"
else
  SRC_KPACK="${SOURCE_DIR}.kpack"
  if [[ -f "${SRC_KPACK}" ]]; then
    log "Pack archive found at ${SRC_KPACK}, moving to ${OUTPUT_FILE}"
    mkdir -p "${DIST_DIR}"
    mv "${SRC_KPACK}" "${OUTPUT_FILE}"
  else
    err "Expected pack file not found after build: ${OUTPUT_FILE}"
  fi
fi

# Compute SHA‑256 checksum
if command -v shasum > /dev/null 2>&1; then
  SHA=$(shasum -a 256 "${OUTPUT_FILE}" | awk '{print $1}')
elif command -v sha256sum > /dev/null 2>&1; then
  SHA=$(sha256sum "${OUTPUT_FILE}" | awk '{print $1}')
else
  SHA="(sha256 not available)"
fi

log "Pack built: ${OUTPUT_FILE}"
log "SHA‑256: ${SHA}"

exit 0

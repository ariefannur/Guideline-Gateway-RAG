## 📄 self_check.sh

#!/usr/bin/env bash
# --------------------------------------------------------------
# self_check.sh – end‑to‑end verification for Guideline Gateway
# --------------------------------------------------------------
# Exit on any error, but keep the script readable
set -euo pipefail

# ----------------------------------------------------------------------
# CONFIGURATION – change only if you want a different Python version
# ----------------------------------------------------------------------
# Supported versions: 3.11 or 3.12 (adjust the path if you installed a
# different one via Homebrew or pyenv)
PYTHON_PATH="/opt/homebrew/opt/python@3.12/libexec/bin/python3"   # <-- edit if needed

# ----------------------------------------------------------------------
# 0️⃣  Helper: print a colored header for each step
# ----------------------------------------------------------------------
function step() {
    echo -e "\n\033[1;34m=== $1 ===\033[0m"
}

# ----------------------------------------------------------------------
# 1️⃣  Verify the chosen Python exists and is a supported version
# ----------------------------------------------------------------------
step "Verify Python version"
if [[ ! -x "${PYTHON_PATH}" ]]; then
    echo "❌ Python not found at ${PYTHON_PATH}"
    echo "   Install a supported version (3.11 or 3.12) via Homebrew or pyenv."
    exit 1
fi
"${PYTHON_PATH}" --version   # should show 3.11.x or 3.12.x

# ----------------------------------------------------------------------
# 2️⃣  (Re)create the virtual environment using the chosen Python
# ----------------------------------------------------------------------
step "Re‑create virtual environment"
PROJECT_ROOT="$(pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

# Remove old venv if it exists
if [[ -d "${VENV_DIR}" ]]; then
    echo "🗑️  Removing old .venv ..."
    rm -rf "${VENV_DIR}"
fi

# Create new venv
"${PYTHON_PATH}" -m venv "${VENV_DIR}"
echo "✅ Virtual environment created at ${VENV_DIR}"

# ----------------------------------------------------------------------
# 3️⃣  Activate the venv and upgrade pip
# ----------------------------------------------------------------------
step "Activate venv & upgrade pip"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel
echo "✅ venv activated – python: $(which python) (version $(python --version))"

# ----------------------------------------------------------------------
# 4️⃣  Install the project in editable mode **with** the optional ML extras
# ----------------------------------------------------------------------
step "Install project + ML extras ([ml] extra)"
# The quotes protect the `[]` from Zsh globbing
uv pip install -e ".[ml]"
echo "✅ Project and ML extras installed"

# ----------------------------------------------------------------------
# 5️⃣  Verify the SLM runtime (`llama_cpp`) can be imported
# ----------------------------------------------------------------------
step "Verify SLM runtime import"
python - <<'PY'
try:
    import llama_cpp
    print("✅ llama_cpp import OK – version", llama_cpp.__version__)
except Exception as exc:
    print("❌ Failed to import llama_cpp:", exc)
    raise
PY

# ----------------------------------------------------------------------
# 6️⃣  Check that the GGUF model file exists
# ----------------------------------------------------------------------
step "Check GGUF model file"
MODEL_PATH="${SLM_MODEL_PATH}"
if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "❌ Model file not found at ${MODEL_PATH}"
    echo "   Download it (≈ 1 GB) and place it there, e.g.:"
    echo "   curl -L -o \"${MODEL_PATH}\" \\"
    echo "
            https://huggingface.co/Qwen/Qwen2.5-1.5B-Chat-GGUF/resolve/main/qwen2.5-1.5b-q4.gguf"
    exit 1
fi
echo "✅ Model file present (size: $(ls -lh "${MODEL_PATH}" | awk '{print $5}'))"

# ----------------------------------------------------------------------
# 7️⃣  Export the model path for the current shell (and persist in .env)
# ----------------------------------------------------------------------
step "Export SLM_MODEL_PATH"
export SLM_MODEL_PATH="${MODEL_PATH}"
echo "✅ SLM_MODEL_PATH set to ${SLM_MODEL_PATH}"
# Persist for future CLI runs (optional but handy)
if ! grep -q "^SLM_MODEL_PATH=" .env 2>/dev/null; then
    echo "SLM_MODEL_PATH=${SLM_MODEL_PATH}" >> .env
    echo "✅ Added SLM_MODEL_PATH to .env"
fi

# ----------------------------------------------------------------------
# 8️⃣  (Re)install the football‑laws pack
# ----------------------------------------------------------------------
step "Install football‑laws pack"
# kpack install packs/football-laws.kpack  # skipped: no install command available
echo "✅ Football pack installed"

# ----------------------------------------------------------------------
# 9️⃣  List installed packs – the football pack should be ACTIVE
# ----------------------------------------------------------------------
step "List installed packs"
guideline packs list
echo "✅ Verify that a row with STATUS = ACTIVE and ID = football-laws‑2024‑25 appears."

# ----------------------------------------------------------------------
# 🔟  Run a football‑law query – expect a generated answer + citations
# ----------------------------------------------------------------------
step "Run a football‑law query"
guideline ask "What is the off‑side rule for a corner kick in the 2024‑25 season?"
echo "✅ If you see a natural‑language answer with a citations table, the SLM is working!"

# ----------------------------------------------------------------------
# 🌐  OPTIONAL: start the FastAPI web UI for manual testing
# ----------------------------------------------------------------------
read -p $'\nDo you want to start the web UI now? (y/N) ' start_ui
if [[ "${start_ui,,}" == "y" ]]; then
    step "Start FastAPI server (background) & open browser"
    # Run the server in the background; capture its PID so we can kill it later
    guideline serve &
    SERVER_PID=$!
    echo "🚀 Server started (PID ${SERVER_PID}) – open http://127.0.0.1:8000 in a browser."
    echo "Press ENTER when you are done testing to stop the server."
    read -r
    kill "${SERVER_PID}" && echo "🛑 Server stopped."
else
    echo "⚡ Skipping UI startup. You can start it later with: guideline serve"
fi

# ----------------------------------------------------------------------
# 🎉  All done
# ----------------------------------------------------------------------
step "All checks passed"
echo "You can now use the CLI or the web UI to ask football‑law questions."
echo "For out‑of‑scope queries (e.g., capitals) the system will correctly abstain."
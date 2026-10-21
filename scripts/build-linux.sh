#!/usr/bin/env bash
# Meikova Relay Enterprise - Linux Build Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "=============================================================="
echo "       MEIKOVA RELAY ENTERPRISE - LINUX BUILD ENGINE"
echo "=============================================================="

# 1. Ensure Python 3
if ! command -v python3 &> /dev/null; then
    echo "[X] python3 not found. Please install python3."
    exit 1
fi

# 2. Check / Setup Virtualenv
if [ ! -d ".venv" ]; then
    echo "[*] Creating .venv..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# 3. Install requirements
echo "[*] Checking build dependencies..."
pip install --upgrade pip > /dev/null
pip install -r host_agent/requirements.txt > /dev/null
pip install pyinstaller > /dev/null

# 4. Run tests
echo "[*] Running test suite..."
python3 -m unittest discover tests

# 5. Build multi-format Linux distribution
echo "[*] Compiling binary, .deb, and .tar.gz packages..."
python3 scripts/build.py --target linux

echo ""
echo "[✓] Build complete! Artifacts in dist/:"
ls -lh dist/meikova-relay-host* dist/SHA256SUMS.txt 2>/dev/null || true
echo "=============================================================="

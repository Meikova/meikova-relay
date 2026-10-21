#!/usr/bin/env bash
# Meikova Relay Host Agent - Linux Launcher
# Supports Ubuntu, Debian, Fedora, Arch, Raspberry Pi OS, etc.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== MEIKOVA RELAY HOST AGENT (LINUX) ==="

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] python3 chưa được cài đặt. Vui lòng chạy: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
    exit 1
fi

# Set up virtual environment if not present
if [ ! -d ".venv" ]; then
    echo "[INFO] Đang khởi tạo môi trường ảo Python .venv..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install essential dependencies
echo "[INFO] Kiểm tra gói phụ thuộc..."
pip install --upgrade pip -q
pip install websockets pillow psutil screeninfo pynput -q

# Run Agent
echo "[INFO] Khởi động Meikova Relay Host Agent..."
python3 host_service.py "$@"

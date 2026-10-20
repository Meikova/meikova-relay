#!/usr/bin/env bash
# Titan Remote Host Agent - macOS Launcher
# Supports macOS Monterey, Ventura, Sonoma, Sequoia (Intel & Apple Silicon M1/M2/M3/M4)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TITAN REMOTE HOST AGENT (macOS) ==="
echo "[LƯU Ý QUAN TRỌNG]: Trên macOS, ứng dụng cần được cấp quyền:"
echo "  1. System Settings -> Privacy & Security -> Screen Recording"
echo "  2. System Settings -> Privacy & Security -> Accessibility"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] python3 chưa được cài đặt. Vui lòng cài qua brew: brew install python3"
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
pip install websockets pillow psutil screeninfo pynput pyobjc-framework-Quartz -q

# Run Agent
echo "[INFO] Khởi động Titan Remote Host Agent..."
python3 host_service.py "$@"

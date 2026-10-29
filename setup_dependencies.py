#!/usr/bin/env python3
"""One-Click & CLI Dependency Installer / Bundler for Meikova Relay.

Usage examples:
  1. Check & automatically install all required libraries for the current OS:
     python setup_dependencies.py

  2. Embed all libraries directly inside `vendor/packages/` in the source tree:
     python setup_dependencies.py --embed-source

  3. Download offline `.whl` installers into `vendor/wheels/` for offline deployment:
     python setup_dependencies.py --download-wheels

  4. Inspect current dependency status as JSON:
     python setup_dependencies.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from host_agent.auto_bootstrap import (
    activate_vendor_paths,
    download_wheelhouse,
    ensure_dependencies,
     inspect_dependencies,
    install_into_vendor_packages,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Meikova Relay - Trình cài đặt & đóng gói thư viện tự động (Zero-Touch Dependency Manager)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Chỉ kiểm tra trạng thái các thư viện hiện tại (không cài đặt)",
    )
    parser.add_argument(
        "--embed-source",
        action="store_true",
        help="Tải và nhúng trực tiếp các thư viện vào thư mục nguồn vendor/packages/ để chạy thẳng từ source",
    )
    parser.add_argument(
        "--download-wheels",
        action="store_true",
        help="Tải toàn bộ gói .whl về thư mục vendor/wheels/ trong source để mang đi cài đặt Offline",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới định dạng JSON",
    )
    args = parser.parse_args(argv)

    activate_vendor_paths()

    if args.check:
        report = inspect_dependencies()
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"=== Meikova Relay Dependency Check ({report['os'].upper()} / Python {report['python_version']}) ===")
            print(f"Đã cài đặt: {report['installed_count']} | Còn thiếu: {report['missing_count']}")
            for item in report["installed"]:
                print(f"  [OK]      {item['import_name']:<20} ({item['pip_spec']}) - {item['description']}")
            for item in report["missing"]:
                print(f"  [MISSING] {item['import_name']:<20} ({item['pip_spec']}) - {item['description']}")
        return 0

    if args.download_wheels:
        res = download_wheelhouse()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[Wheelhouse] Target: {res['target_dir']} | Success: {res['success']} | Wheels: {res['wheel_count']}")
        return 0 if res["success"] else 1

    if args.embed_source:
        res = install_into_vendor_packages()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"[EmbedSource] Target: {res['target_dir']} | Success: {res['success']}")
        return 0 if res["success"] else 1

    report = ensure_dependencies(auto_install=True, quiet=args.json)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== Hoàn tất kiểm tra & cài đặt tự động ({report['os'].upper()}) ===")
        print(f"Đã sẵn sàng: {report['installed_count']} thư viện | Còn thiếu: {report['missing_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

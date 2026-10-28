#!/usr/bin/env python3
"""
Meikova Relay - Single Source of Truth (SSOT) Version Manager.
Reads root version.json and propagates version across all 11+ project touchpoints in a single operation.

Usage:
    python scripts/version.py               # Sync all files to match version.json
    python scripts/version.py 1.2.0         # Set explicit version and sync all
    python scripts/version.py --bump patch  # 1.2.0 -> 1.2.1 and sync all
    python scripts/version.py --bump minor  # 1.2.0 -> 1.3.0 and sync all
    python scripts/version.py --bump major  # 1.2.0 -> 2.0.0 and sync all
"""

import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "version.json"


def load_version() -> str:
    if not VERSION_FILE.exists():
        VERSION_FILE.write_text(json.dumps({"version": "1.0.0"}, indent=2), encoding="utf-8")
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    return data.get("version", "1.0.0")


def save_version(ver: str) -> None:
    VERSION_FILE.write_text(json.dumps({"version": ver}, indent=2) + "\n", encoding="utf-8")


def bump_semver(ver: str, part: str) -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver)
    if not m:
        raise ValueError(f"Invalid SemVer: {ver}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump part: {part}")


def update_file(path: Path, pattern: str, replacement: str) -> bool:
    if not path.exists():
        print(f"  [-] Skipped (not found): {path.relative_to(REPO_ROOT)}")
        return False
    content = path.read_text(encoding="utf-8")
    new_content, count = re.subn(pattern, replacement, content)
    if count > 0:
        path.write_text(new_content, encoding="utf-8")
        print(f"  [+] Updated ({count} match{'es' if count > 1 else ''}): {path.relative_to(REPO_ROOT)}")
        return True
    else:
        print(f"  [.] Already up to date: {path.relative_to(REPO_ROOT)}")
        return False


def sync_all(version: str):
    print(f"=== Syncing Meikova Relay to Version {version} (SSOT) ===")

    # 1. Root version.json
    save_version(version)
    print(f"  [+] Saved version.json: {version}")

    # 2. relay-server/package.json
    pkg_file = REPO_ROOT / "relay-server" / "package.json"
    if pkg_file.exists():
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
        pkg["version"] = version
        pkg_file.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
        print(f"  [+] Updated: relay-server/package.json")

    # 3. installer_host.iss & installer_client.iss
    for iss in ["installer_host.iss", "installer_client.iss"]:
        update_file(
            REPO_ROOT / iss,
            r'#define MyAppVersion "[^"]+"',
            f'#define MyAppVersion "{version}"'
        )

    # 4. scripts/build.py
    update_file(
        REPO_ROOT / "scripts" / "build.py",
        r'VERSION\s*=\s*"[^"]+"',
        f'VERSION = "{version}"'
    )

    # 5. host_agent/gui_agent.py
    update_file(
        REPO_ROOT / "host_agent" / "gui_agent.py",
        r'APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{version}"'
    )

    # 6. host_agent/host_service.py
    update_file(
        REPO_ROOT / "host_agent" / "host_service.py",
        r'APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{version}"'
    )

    # 7. client_desktop/desktop_client.py
    update_file(
        REPO_ROOT / "client_desktop" / "desktop_client.py",
        r'APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{version}"'
    )
    update_file(
        REPO_ROOT / "client_desktop" / "desktop_client.py",
        r'MEIKOVA RELAY // v[0-9\.]+',
        f'MEIKOVA RELAY // v{version}'
    )

    # 8. HTML files (relay-server/public/index.html & web-client/index.html)
    for html_rel in ["relay-server/public/index.html", "web-client/index.html"]:
        p = REPO_ROOT / html_rel
        if not p.exists(): continue
        # Landing badge
        update_file(p, r'data-i18n="landing\.badge">v[0-9\.]+', f'data-i18n="landing.badge">v{version}')
        # Telemetry HUD
        update_file(p, r'MEIKOVA RELAY v[0-9\.]+', f'MEIKOVA RELAY v{version}')
        # Cache query strings
        update_file(p, r'(\.css|\.js)\?v=[0-9\.]+', rf'\1?v={version}')

    # 9. i18n dictionaries (relay-server/public/js/i18n.js & web-client/js/i18n.js)
    for js_rel in ["relay-server/public/js/i18n.js", "web-client/js/i18n.js"]:
        p = REPO_ROOT / js_rel
        if not p.exists(): continue
        update_file(p, r"('landing\.badge':\s*'v)[0-9\.]+", rf"\g<1>{version}")

    # 10. Service Workers (relay-server/public/sw.js & web-client/sw.js)
    for sw_rel in ["relay-server/public/sw.js", "web-client/sw.js"]:
        p = REPO_ROOT / sw_rel
        if not p.exists(): continue
        update_file(p, r'// Meikova Relay PWA Service Worker \(v[0-9\.]+\)', f'// Meikova Relay PWA Service Worker (v{version})')
        update_file(p, r"const CACHE_NAME = 'meikova-relay-cache-v[0-9\.]+';", f"const CACHE_NAME = 'meikova-relay-cache-v{version}';")

    print(f"\n[OK] Version synchronization complete -> v{version} active everywhere!")


def main():
    current = load_version()
    if len(sys.argv) == 1:
        sync_all(current)
        return

    arg = sys.argv[1].strip()
    if arg in ("--bump", "-b") and len(sys.argv) > 2:
        part = sys.argv[2].lower()
        new_ver = bump_semver(current, part)
        sync_all(new_ver)
    elif re.match(r"^\d+\.\d+\.\d+$", arg):
        sync_all(arg)
    elif arg in ("--help", "-h"):
        print(__doc__)
    else:
        print(f"Error: Invalid argument: {arg}")
        print("Usage: python scripts/version.py [X.Y.Z | --bump patch|minor|major]")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Titan Remote Enterprise - Multi-Platform Workstation Build & Packaging Tool.
Supports Windows (.exe, .zip), Linux (ELF, .deb, .tar.gz), and macOS (.app, .dmg, .tar.gz).
Zero external dependencies outside standard Python library & PyInstaller.
"""

import os
import sys
import io
import time
import shutil
import tarfile
import zipfile
import hashlib
import argparse
import subprocess
from pathlib import Path

VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"

def make_ar_header(name: str, size: int, mode: int = 0o100644, mtime: int = 0) -> bytes:
    """Creates a 60-byte Unix ar archive header."""
    name_field = name.ljust(16)[:16].encode("ascii")
    mtime_field = str(mtime).ljust(12)[:12].encode("ascii")
    owner_field = b"0".ljust(6)
    group_field = b"0".ljust(6)
    mode_field = oct(mode)[2:].rjust(8, "0")[:8].encode("ascii")
    size_field = str(size).ljust(10)[:10].encode("ascii")
    trailer = b"`\n"
    return name_field + mtime_field + owner_field + group_field + mode_field + size_field + trailer

def create_deb_package(binary_path: Path, output_deb_path: Path, version: str = VERSION) -> Path:
    """
    Builds a Debian / Ubuntu .deb package without requiring dpkg-deb.
    // ponytail: pure stdlib ar + tarfile format builder
    """
    output_deb_path.parent.mkdir(parents=True, exist_ok=True)
    bin_name = "titan-remote-host"
    now = int(time.time())

    # 1. debian-binary member
    debian_binary = b"2.0\n"

    # 2. control.tar.gz
    control_content = (
        f"Package: {bin_name}\n"
        f"Version: {version}\n"
        f"Section: net\n"
        f"Priority: optional\n"
        f"Architecture: amd64\n"
        f"Maintainer: Titan Remote Enterprise <support@titan-remote.internal>\n"
        f"Description: Ultra low-latency remote desktop workstation host agent.\n"
        f" High-performance multi-monitor remote screen sharing, audio loopback,\n"
        f" file browser, terminal, and 120 FPS display synchronization.\n"
    ).encode("utf-8")

    postinst_content = (
        b"#!/bin/sh\n"
        b"set -e\n"
        b"if command -v systemctl >/dev/null 2>&1; then\n"
        b"    systemctl daemon-reload || true\n"
        b"fi\n"
        b"echo 'Titan Remote Host installed. Run \"titan-remote-host\" to launch.'\n"
        b"exit 0\n"
    )

    prerm_content = (
        b"#!/bin/sh\n"
        b"set -e\n"
        b"if command -v systemctl >/dev/null 2>&1; then\n"
        b"    systemctl stop titan-remote.service || true\n"
        b"    systemctl disable titan-remote.service || true\n"
        b"fi\n"
        b"exit 0\n"
    )

    control_buf = io.BytesIO()
    with tarfile.open(fileobj=control_buf, mode="w:gz") as tar:
        # ./control
        ti = tarfile.TarInfo(name="./control")
        ti.size = len(control_content)
        ti.mode = 0o644
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(control_content))

        # ./postinst
        ti = tarfile.TarInfo(name="./postinst")
        ti.size = len(postinst_content)
        ti.mode = 0o755
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(postinst_content))

        # ./prerm
        ti = tarfile.TarInfo(name="./prerm")
        ti.size = len(prerm_content)
        ti.mode = 0o755
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(prerm_content))

    control_bytes = control_buf.getvalue()

    # 3. data.tar.gz
    data_buf = io.BytesIO()
    with tarfile.open(fileobj=data_buf, mode="w:gz") as tar:
        # Binary in /usr/bin
        bin_data = binary_path.read_bytes() if binary_path.exists() else b"#!/bin/sh\necho 'Titan Remote'\n"
        ti = tarfile.TarInfo(name=f"./usr/bin/{bin_name}")
        ti.size = len(bin_data)
        ti.mode = 0o755
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(bin_data))

        # Systemd unit in /lib/systemd/system
        unit_file = REPO_ROOT / "host_agent" / "titan-remote.service"
        unit_data = unit_file.read_bytes() if unit_file.exists() else b"[Unit]\nDescription=Titan Remote Host\n"
        ti = tarfile.TarInfo(name="./lib/systemd/system/titan-remote.service")
        ti.size = len(unit_data)
        ti.mode = 0o644
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(unit_data))

        # Desktop entry in /usr/share/applications
        desktop_data = (
            b"[Desktop Entry]\n"
            b"Name=Titan Remote Host\n"
            b"Comment=Titan Remote Workstation Host Agent\n"
            b"Exec=titan-remote-host\n"
            b"Terminal=false\n"
            b"Type=Application\n"
            b"Categories=Network;RemoteAccess;\n"
        )
        ti = tarfile.TarInfo(name="./usr/share/applications/titan-remote.desktop")
        ti.size = len(desktop_data)
        ti.mode = 0o644
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(desktop_data))

    data_bytes = data_buf.getvalue()

    # Write ar archive
    with open(output_deb_path, "wb") as deb:
        deb.write(b"!<arch>\n")

        # 1. debian-binary
        deb.write(make_ar_header("debian-binary", len(debian_binary), 0o100644, now))
        deb.write(debian_binary)

        # 2. control.tar.gz
        deb.write(make_ar_header("control.tar.gz", len(control_bytes), 0o100644, now))
        deb.write(control_bytes)
        if len(control_bytes) % 2 != 0:
            deb.write(b"\n")

        # 3. data.tar.gz
        deb.write(make_ar_header("data.tar.gz", len(data_bytes), 0o100644, now))
        deb.write(data_bytes)
        if len(data_bytes) % 2 != 0:
            deb.write(b"\n")

    return output_deb_path

def create_linux_tarball(binary_path: Path, output_tar_path: Path) -> Path:
    """Packs Linux standalone binary, systemd unit, and install script into .tar.gz."""
    output_tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_tar_path, "w:gz") as tar:
        if binary_path.exists():
            tar.add(binary_path, arcname="titan-remote-host")
        service_file = REPO_ROOT / "host_agent" / "titan-remote.service"
        if service_file.exists():
            tar.add(service_file, arcname="titan-remote.service")
        
        # Embedded one-click installer script inside tarball
        installer_script = (
            "#!/usr/bin/env bash\n"
            "set -e\n"
            "echo 'Installing Titan Remote Host Agent to /usr/local/bin...'\n"
            "sudo cp titan-remote-host /usr/local/bin/\n"
            "sudo chmod +x /usr/local/bin/titan-remote-host\n"
            "if [ -f 'titan-remote.service' ]; then\n"
            "    sudo cp titan-remote.service /etc/systemd/system/\n"
            "    sudo systemctl daemon-reload\n"
            "    echo 'Systemd service installed. Start with: sudo systemctl start titan-remote'\n"
            "fi\n"
            "echo 'Installation complete!'\n"
        ).encode("utf-8")
        ti = tarfile.TarInfo(name="install.sh")
        ti.size = len(installer_script)
        ti.mode = 0o755
        tar.addfile(ti, io.BytesIO(installer_script))

    return output_tar_path

def create_macos_tarball(binary_path: Path, output_tar_path: Path) -> Path:
    """Packs macOS binary, launchd plist, and install script into .tar.gz."""
    output_tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_tar_path, "w:gz") as tar:
        if binary_path.exists():
            tar.add(binary_path, arcname="titan-remote-host")
        plist_file = REPO_ROOT / "host_agent" / "com.titan.remote.plist"
        if plist_file.exists():
            tar.add(plist_file, arcname="com.titan.remote.plist")
        
        install_script = (
            "#!/usr/bin/env bash\n"
            "set -e\n"
            "echo 'Installing Titan Remote Host on macOS...'\n"
            "mkdir -p \"$HOME/.titan-remote/bin\"\n"
            "cp titan-remote-host \"$HOME/.titan-remote/bin/\"\n"
            "chmod +x \"$HOME/.titan-remote/bin/titan-remote-host\"\n"
            "if [ -f 'com.titan.remote.plist' ]; then\n"
            "    mkdir -p \"$HOME/Library/LaunchAgents\"\n"
            "    cp com.titan.remote.plist \"$HOME/Library/LaunchAgents/\"\n"
            "    launchctl load \"$HOME/Library/LaunchAgents/com.titan.remote.plist\" || true\n"
            "fi\n"
            "echo 'macOS Installation complete!'\n"
        ).encode("utf-8")
        ti = tarfile.TarInfo(name="install.sh")
        ti.size = len(install_script)
        ti.mode = 0o755
        tar.addfile(ti, io.BytesIO(install_script))

    return output_tar_path

def create_windows_zip(exe_path: Path, output_zip_path: Path) -> Path:
    """Bundles Windows portable executable and setup launcher into a .zip package."""
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if exe_path.exists():
            zf.write(exe_path, arcname="TitanRemoteHost.exe")
        
        readme = (
            "==============================================================\r\n"
            "        TITAN REMOTE ENTERPRISE - HOST AGENT\r\n"
            "==============================================================\r\n\r\n"
            "1. Chay truc tiep TitanRemoteHost.exe de bat dau truyen phat man hinh.\r\n"
            "2. Hoac su dung tham so --autostart de chay an duoi khay he thong.\r\n"
            "3. De cai dat Service chay ngam 24/7, chay file setup.bat tu Relay Server.\r\n"
        )
        zf.writestr("README.txt", readme)

    return output_zip_path

def generate_checksums(dist_dir: Path) -> Path:
    """Generates SHA256 checksums file for all built artifacts."""
    checksums_file = dist_dir / "SHA256SUMS.txt"
    lines = []
    for file_path in sorted(dist_dir.iterdir()):
        if file_path.is_file() and file_path.name != "SHA256SUMS.txt" and not file_path.name.endswith(".sha256"):
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            lines.append(f"{hasher.hexdigest()}  {file_path.name}")
    
    checksums_content = "\n".join(lines) + "\n"
    checksums_file.write_text(checksums_content, encoding="utf-8")
    return checksums_file

def run_pyinstaller(target_os: str, dist_dir: Path) -> Path:
    """Invokes PyInstaller to compile gui_agent.py for current OS."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    entry_point = REPO_ROOT / "host_agent" / "gui_agent.py"
    sep = ";" if sys.platform == "win32" else ":"
    data_args = [
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'gui_view.html'}{sep}host_agent",
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'gui_view.html'}{sep}.",
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'icon.ico'}{sep}host_agent",
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'icon.ico'}{sep}.",
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'icon.png'}{sep}host_agent",
        "--add-data", f"{REPO_ROOT / 'host_agent' / 'icon.png'}{sep}.",
    ]

    if target_os == "windows":
        name = "TitanRemoteHost"
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--onefile", "--windowed",
            "--name", name,
            "--distpath", str(dist_dir),
            "--workpath", str(REPO_ROOT / "build"),
            "--clean",
            *data_args,
            str(entry_point)
        ]
        out_bin = dist_dir / f"{name}.exe"
    elif target_os == "macos":
        name = "TitanRemoteHost"
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--onefile", "--windowed",
            "--name", name,
            "--distpath", str(dist_dir),
            "--workpath", str(REPO_ROOT / "build"),
            "--clean",
            *data_args,
            str(entry_point)
        ]
        out_bin = dist_dir / name
    else: # linux
        name = "titan-remote-host"
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--onefile",
            "--name", name,
            "--distpath", str(dist_dir),
            "--workpath", str(REPO_ROOT / "build"),
            "--clean",
            *data_args,
            str(entry_point)
        ]
        out_bin = dist_dir / name

    print(f"[*] Running PyInstaller for {target_os.upper()}...")
    res = subprocess.run(cmd, cwd=REPO_ROOT)
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {res.returncode}")

    return out_bin

def build(target: str = "auto", dist_dir: Path = DIST_DIR, skip_pyinstaller: bool = False, version: str = VERSION):
    """Executes multi-platform build workflow."""
    if target == "all":
        for t in ["windows", "linux", "macos"]:
            build(target=t, dist_dir=dist_dir, skip_pyinstaller=skip_pyinstaller, version=version)
        return

    if target == "auto":
        if sys.platform == "win32":
            target = "windows"
        elif sys.platform == "darwin":
            target = "macos"
        else:
            target = "linux"

    print(f"=== Titan Remote Build Engine: Target [{target.upper()}] ===")
    dist_dir.mkdir(parents=True, exist_ok=True)

    if target == "windows":
        exe_path = dist_dir / "TitanRemoteHost.exe"
        if not skip_pyinstaller:
            exe_path = run_pyinstaller("windows", dist_dir)
        zip_path = dist_dir / "TitanRemoteHost-windows-x64.zip"
        create_windows_zip(exe_path, zip_path)
        print(f"[+] Windows artifacts: {exe_path.name}, {zip_path.name}")

    elif target == "linux":
        bin_path = dist_dir / "titan-remote-host"
        if not skip_pyinstaller:
            bin_path = run_pyinstaller("linux", dist_dir)
        deb_path = dist_dir / f"titan-remote-host_{version}_amd64.deb"
        deb_symlink = dist_dir / "titan-remote-host_amd64.deb"
        tar_path = dist_dir / "titan-remote-host-linux-x64.tar.gz"

        create_deb_package(bin_path, deb_path, version=version)
        if deb_path != deb_symlink:
            shutil.copyfile(deb_path, deb_symlink)
        create_linux_tarball(bin_path, tar_path)
        print(f"[+] Linux artifacts: {bin_path.name}, {deb_path.name}, {tar_path.name}")

    elif target == "macos":
        bin_path = dist_dir / "TitanRemoteHost"
        if not skip_pyinstaller:
            bin_path = run_pyinstaller("macos", dist_dir)
        tar_path = dist_dir / "titan-remote-host-macos.tar.gz"
        create_macos_tarball(bin_path, tar_path)
        
        # If running on macOS with hdiutil, create .dmg
        if sys.platform == "darwin" and shutil.which("hdiutil"):
            dmg_path = dist_dir / "TitanRemoteHost-macos.dmg"
            cmd = ["hdiutil", "create", "-volname", "TitanRemoteHost", "-srcfolder", str(bin_path), "-ov", "-format", "UDZO", str(dmg_path)]
            subprocess.run(cmd, check=False)
            print(f"[+] macOS DMG: {dmg_path.name}")

        print(f"[+] macOS artifacts: {bin_path.name}, {tar_path.name}")

    checksums = generate_checksums(dist_dir)
    print(f"[+] Generated Checksums: {checksums.name}")
    print("=== Build Completed Successfully ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Titan Remote Multi-Platform Build Engine")
    parser.add_argument("--target", choices=["auto", "windows", "linux", "macos", "all"], default="auto")
    parser.add_argument("--dist", type=Path, default=DIST_DIR)
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Skip compilation, only test packaging")
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()

    if args.target == "all":
        for t in ["windows", "linux", "macos"]:
            build(target=t, dist_dir=args.dist, skip_pyinstaller=args.skip_pyinstaller, version=args.version)
    else:
        build(target=args.target, dist_dir=args.dist, skip_pyinstaller=args.skip_pyinstaller, version=args.version)

"""
Protocol Prober for Meikova Relay.
Probes native system services (RDP, SSH, SFTP, FTP, VNC) on localhost.
Enables Native-First negotiation with seamless Meikova Bypass fallback.
// ponytail: stdlib socket only, zero third-party dependencies.
"""

import socket
import sys
import time
from typing import Dict, Any, Optional

RDP_X224_CR = b"\x03\x00\x00\x13\x0e\xe0\x00\x00\x00\x00\x00\x01\x00\x08\x00\x03\x00\x00\x00"

def probe_tcp_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Checks if a TCP port is open and accepting connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            res = s.connect_ex((host, port))
            return res == 0
    except Exception:
        return False

def probe_rdp(host: str = "127.0.0.1", port: int = 3389, timeout: float = 0.8) -> Dict[str, Any]:
    """
    Probes RDP service by establishing TCP connection and sending X.224 Connection Request.
    Confirms TermService response (X.224 Connection Confirm or RDP NegRsp).
    """
    result = {
        "protocol": "rdp",
        "port": port,
        "available": False,
        "handshake": False,
        "details": "Port closed"
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) != 0:
                return result
            result["available"] = True
            result["details"] = "Port open, awaiting X.224 handshake"

            # Send X.224 Connection Request
            s.sendall(RDP_X224_CR)
            resp = s.recv(128)
            if resp and len(resp) >= 4 and resp[0] == 0x03 and resp[1] == 0x00:
                result["handshake"] = True
                result["details"] = "RDP TermService active (X.224 confirmed)"
            else:
                result["details"] = "Port open (RDP response pending)"
    except socket.timeout:
        if result["available"]:
            result["details"] = "Port open (Handshake timed out)"
    except Exception as e:
        if result["available"]:
            result["details"] = f"Port open (Handshake error: {e})"
    return result

def probe_ssh(host: str = "127.0.0.1", port: int = 22, timeout: float = 0.8) -> Dict[str, Any]:
    """
    Probes SSH service by checking TCP port and reading identification banner.
    // ponytail: stdlib socket reads SSH-2.0 banner directly without paramiko
    """
    result = {
        "protocol": "ssh",
        "port": port,
        "available": False,
        "banner": "",
        "details": "Port closed"
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) != 0:
                return result
            result["available"] = True
            result["details"] = "Port open"

            data = s.recv(256)
            if data:
                banner = data.decode("utf-8", errors="replace").strip()
                result["banner"] = banner
                if banner.startswith("SSH-"):
                    result["details"] = f"SSH Server active ({banner.split('-')[1] if len(banner.split('-')) > 1 else 'SSH'})"
    except Exception as e:
        if result["available"]:
            result["details"] = f"Port open ({e})"
    return result

def probe_sftp(host: str = "127.0.0.1", port: int = 22, timeout: float = 0.8) -> Dict[str, Any]:
    """SFTP runs over SSH subsystem; availability matches active SSH daemon."""
    ssh_res = probe_ssh(host=host, port=port, timeout=timeout)
    return {
        "protocol": "sftp",
        "port": port,
        "available": ssh_res["available"] and bool(ssh_res.get("banner", "").startswith("SSH-")),
        "details": "SFTP Subsystem ready via SSH" if ssh_res["available"] else "SFTP closed (SSH unavailable)"
    }

def probe_ftp(host: str = "127.0.0.1", port: int = 21, timeout: float = 0.8) -> Dict[str, Any]:
    """Probes standard FTP port 21 and reads 220 banner."""
    result = {
        "protocol": "ftp",
        "port": port,
        "available": False,
        "banner": "",
        "details": "Port closed"
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) != 0:
                return result
            result["available"] = True
            data = s.recv(256)
            if data:
                banner = data.decode("utf-8", errors="replace").strip()
                result["banner"] = banner
                result["details"] = f"FTP Server active ({banner[:30]})"
            else:
                result["details"] = "Port open"
    except Exception:
        pass
    return result

def probe_vnc(host: str = "127.0.0.1", port: int = 5900, timeout: float = 0.8) -> Dict[str, Any]:
    """Probes RFB / VNC port 5900 and reads RFB banner."""
    result = {
        "protocol": "vnc",
        "port": port,
        "available": False,
        "banner": "",
        "details": "Port closed"
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) != 0:
                return result
            result["available"] = True
            data = s.recv(64)
            if data:
                banner = data.decode("utf-8", errors="replace").strip()
                result["banner"] = banner
                result["details"] = f"VNC Server active ({banner})"
            else:
                result["details"] = "Port open"
    except Exception:
        pass
    return result

def probe_all_protocols(host: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Evaluates all native remote, terminal, and file protocols on host.
    Produces protocol negotiation matrix with preferred routes.
    """
    rdp_info = probe_rdp(host)
    vnc_info = probe_vnc(host)
    ssh_info = probe_ssh(host)
    sftp_info = probe_sftp(host)
    ftp_info = probe_ftp(host)

    # Determine preferred protocol for Remote Desktop
    if rdp_info["available"]:
        remote_pref = "rdp"
    elif vnc_info["available"]:
        remote_pref = "vnc"
    else:
        remote_pref = "bypass"

    # Determine preferred protocol for Terminal
    terminal_pref = "ssh" if ssh_info["available"] else "bypass"

    # Determine preferred protocol for File Transfer
    if sftp_info["available"]:
        file_pref = "sftp"
    elif ftp_info["available"]:
        file_pref = "ftp"
    else:
        file_pref = "bypass"

    return {
        "remote": {
            "preferred": remote_pref,
            "rdp": rdp_info,
            "vnc": vnc_info,
            "bypass": {
                "available": True,
                "details": "Meikova Screen/Audio Loopback Stream"
            }
        },
        "terminal": {
            "preferred": terminal_pref,
            "ssh": ssh_info,
            "bypass": {
                "available": True,
                "details": "Meikova Interactive Shell Subprocess"
            }
        },
        "file": {
            "preferred": file_pref,
            "sftp": sftp_info,
            "ftp": ftp_info,
            "bypass": {
                "available": True,
                "details": "Meikova Chunked File Transfer Shelf"
            }
        },
        "timestamp": time.time(),
        "platform": sys.platform
    }

if __name__ == "__main__":
    import json
    matrix = probe_all_protocols()
    print("=== MEIKOVA PROTOCOL PROBING MATRIX ===")
    print(json.dumps(matrix, indent=2))

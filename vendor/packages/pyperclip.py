"""Built-in pure-Python cross-platform clipboard module (`pyperclip` compatible).
Bundled directly in `vendor/packages/pyperclip.py` so Meikova Relay works out-of-the-box
on Windows (Win32 / clip), macOS (pbcopy / pbpaste), and Linux (xclip / xsel / wl-clipboard)
without requiring `pip install pyperclip`.
"""

from __future__ import annotations

import subprocess
import sys

_FALLBACK_BUFFER = ""


def copy(text: str) -> None:
    global _FALLBACK_BUFFER
    text_str = "" if text is None else str(text)
    _FALLBACK_BUFFER = text_str
    plat = sys.platform.lower()
    try:
        if plat.startswith("win"):
            subprocess.run(["clip"], input=text_str.encode("utf-16le"), check=False, timeout=2)
            return
        if plat == "darwin":
            subprocess.run(["pbcopy"], input=text_str.encode("utf-8"), check=False, timeout=2)
            return
        for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["wl-copy"]):
            try:
                res = subprocess.run(cmd, input=text_str.encode("utf-8"), check=False, timeout=1.5, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return
            except FileNotFoundError:
                continue
    except Exception:
        pass


def paste() -> str:
    plat = sys.platform.lower()
    try:
        if plat.startswith("win"):
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                return res.stdout.rstrip("\r\n")
        elif plat == "darwin":
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                return res.stdout
        else:
            for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"], ["wl-paste", "-n"]):
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return res.stdout
                except FileNotFoundError:
                    continue
    except Exception:
        pass
    return _FALLBACK_BUFFER

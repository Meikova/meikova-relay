import os
import re
import sys
import subprocess
import threading
import atexit
from collections import deque
from typing import Callable, Optional

# Matches "PS>", "PS >", "PS C:\path>", "C:\path>", or POSIX "$ " / "# " prompts with optional echoed command
_PS_ECHO_PROMPT_RE = re.compile(r"^(?:PS(?:\s+[^>]*)?>|[A-Za-z]:\\[^>]*>)\s*(.*)$", re.IGNORECASE)
_CWD_MARKER_PREFIX = "__MKV_CWD__"


class TerminalManager:
    """Manages an interactive background PowerShell / POSIX shell session without duplicate command echoing."""

    def __init__(self, on_output: Callable[[str], None]):
        self.on_output = on_output
        self.process: Optional[subprocess.Popen] = None
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._pending_echo_cmds: deque = deque(maxlen=32)
        self._lock = threading.Lock()
        self.current_cwd: str = os.getcwd()

    def start(self):
        if self._running:
            return

        self._running = True
        self.current_cwd = os.getcwd()
        if sys.platform == "win32":
            # Configure UTF-8 encoding and a custom prompt function that emits the current working directory
            # with a newline so stdout flushes immediately after every command. Returning a single space ' '
            # prevents PowerShell from falling back to its built-in "PS>" default prompt string.
            init_cmd = (
                "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
                "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
                "$OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
                "function prompt { [Console]::Out.WriteLine('__MKV_CWD__' + $executionContext.SessionState.Path.CurrentLocation); return ' ' }"
            )
            shell_cmd = ["powershell.exe", "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", init_cmd]
            ready_msg = ""
        else:
            shell_bin = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
            shell_cmd = [shell_bin]
            ready_msg = ""

        try:
            self.process = subprocess.Popen(
                shell_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self._reader_thread = threading.Thread(target=self._read_output_loop, daemon=True)
            self._reader_thread.start()
            atexit.register(self.stop)
            if ready_msg:
                self.on_output(ready_msg)
        except Exception as e:
            self.on_output(f"Failed to start terminal: {e}\n")

    def _should_skip_echo_line(self, raw_line: str) -> bool:
        """Returns True if raw_line is merely the subprocess echoing back the command just written to stdin."""
        stripped = raw_line.strip()
        if not stripped:
            return False

        m = _PS_ECHO_PROMPT_RE.match(stripped)
        with self._lock:
            if not self._pending_echo_cmds:
                # Always strip bare empty PS prompt lines like "PS>", "PS >", or "PS C:\path>" with no command output
                if m and not m.group(1).strip():
                    return True
                return False

            expected = self._pending_echo_cmds[0]
            # Direct echo match (e.g. "ls")
            if stripped == expected:
                self._pending_echo_cmds.popleft()
                return True

            # PowerShell prompt + command echo match (e.g. "PS>ls", "PS > ls", "PS D:\path> ls")
            if m:
                echoed_cmd = m.group(1).strip()
                if echoed_cmd == expected:
                    self._pending_echo_cmds.popleft()
                    return True
                if not echoed_cmd:
                    return True
                # Check if echoed_cmd matches any queued command in _pending_echo_cmds
                if echoed_cmd in self._pending_echo_cmds:
                    try:
                        self._pending_echo_cmds.remove(echoed_cmd)
                    except ValueError:
                        pass
                    return True
        return False

    def _read_output_loop(self):
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break

                # Check if line contains CWD update marker from custom prompt
                if _CWD_MARKER_PREFIX in line:
                    parts = line.split(_CWD_MARKER_PREFIX)
                    before = parts[0]
                    after = parts[1].strip() if len(parts) > 1 else ""
                    if after:
                        self.current_cwd = after
                    if before and not self._should_skip_echo_line(before):
                        self.on_output(before)
                    # Notify client of updated working directory prompt
                    if self.current_cwd:
                        self.on_output(f"{_CWD_MARKER_PREFIX}{self.current_cwd}\n")
                    continue

                if self._should_skip_echo_line(line):
                    continue

                self.on_output(line)
            except Exception:
                break

    def send_input(self, text: str):
        if not self._running or not self.process:
            self.start()
        if self.process and self.process.stdin:
            try:
                cmd = text.strip()
                if cmd:
                    with self._lock:
                        self._pending_echo_cmds.append(cmd)
                if os.name == 'nt':
                    if cmd:
                        self.process.stdin.write(f"{cmd}\n")
                    else:
                        self.process.stdin.write("\n")
                else:
                    if cmd:
                        self.process.stdin.write(f"{cmd}\nprintf '{_CWD_MARKER_PREFIX}%s\\n' \"$(pwd)\"\n")
                    else:
                        self.process.stdin.write("\n")
                self.process.stdin.flush()
            except Exception as e:
                self.on_output(f"\n[Stdin Error]: {e}\n")

    def stop(self):
        self._running = False
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass
        if self.process:
            try:
                if self.process.stdin:
                    try:
                        self.process.stdin.close()
                    except Exception:
                        pass
                if self.process.stdout:
                    try:
                        self.process.stdout.close()
                    except Exception:
                        pass
                self.process.kill()
                self.process.wait(timeout=1.0)
            except Exception:
                pass
            self.process = None

        if self._reader_thread and self._reader_thread.is_alive():
            try:
                self._reader_thread.join(timeout=0.5)
            except Exception:
                pass
            self._reader_thread = None

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

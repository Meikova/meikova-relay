import os
import sys
import subprocess
import threading
from typing import Callable, Optional

class TerminalManager:
    """Manages an interactive background PowerShell session for remote administration."""

    def __init__(self, on_output: Callable[[str], None]):
        self.on_output = on_output
        self.process: Optional[subprocess.Popen] = None
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return

        self._running = True
        # Use powershell on Windows with UTF-8 configuration for Vietnamese diacritics
        init_cmd = (
            "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)"
        )
        shell_cmd = ["powershell.exe", "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", init_cmd]
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
            self.on_output("=== TITAN REMOTE POWERSHELL (UTF-8) READY ===\n")
        except Exception as e:
            self.on_output(f"Failed to start PowerShell: {e}\n")

    def _read_output_loop(self):
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.on_output(line)
            except Exception:
                break

    def send_input(self, text: str):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self.on_output(f"\n[Stdin Error]: {e}\n")

    def stop(self):
        self._running = False
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                if self.process.stdout:
                    self.process.stdout.close()
                self.process.terminate()
                self.process.wait(timeout=1)
            except Exception:
                pass
            self.process = None

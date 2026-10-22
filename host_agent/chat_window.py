import os
import sys
import time
import threading
import tkinter as tk
from typing import Callable, Optional

# Ponytail: Pure stdlib Tkinter floating chat for host workstation.
# Zero dependencies. Thread-safe for both Tkinter mainloop & pywebview thread.

class HostChatWindow:
    """Floating Ambient Dark chat window for host workstation."""

    def __init__(
        self,
        on_send_reply: Optional[Callable[[str], None]] = None,
        parent: Optional[tk.Tk] = None,
        title: str = "Meikova Relay // Trò chuyện"
    ):
        self.on_send_reply = on_send_reply
        self.parent = parent
        self.title_text = title
        self.root: Optional[tk.Toplevel | tk.Tk] = None
        self._text_area = None
        self._entry = None
        self._ready_event = threading.Event()
        self._is_standalone = parent is None
        self.history = []

        if self.parent:
            self._init_ui(parent=self.parent)
            self._ready_event.set()
        else:
            self._thread = threading.Thread(target=self._standalone_worker, daemon=True)
            self._thread.start()
            self._ready_event.wait(timeout=3.0)

    def _standalone_worker(self):
        # macOS Cocoa AppKit strictly prohibits NSWindow creation on secondary threads
        if sys.platform == "darwin":
            self._ready_event.set()
            return

        try:
            root = tk.Tk()
            root.withdraw()
            self._init_ui(parent=None, tk_root=root)
            self._ready_event.set()
            root.mainloop()
        except Exception:
            self._ready_event.set()

    def _init_ui(self, parent=None, tk_root=None):
        if tk_root:
            self.root = tk_root
        elif parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        # Hide window immediately before configuring style/geometry to prevent momentary flash
        try:
            self.root.withdraw()
        except Exception:
            pass

        self.root.title(self.title_text)
        self.root.configure(bg="#070D17")
        self.root.attributes("-topmost", True)

        # Window Size & Position (Bottom Right above taskbar)
        w, h = 380, 460
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(10, sw - w - 24)
        y = max(10, sh - h - 60)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(320, 340)

        # Hide on window manager close (X button) instead of destroying
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Title bar banner
        header = tk.Frame(self.root, bg="#0D1524", height=44, padx=14, pady=10)
        header.pack(fill=tk.X)

        dot = tk.Label(header, text="●", fg="#22C55E", bg="#0D1524", font=("Segoe UI", 11, "bold"))
        dot.pack(side=tk.LEFT, padx=(0, 8))

        title_lbl = tk.Label(header, text="Trò chuyện trực tiếp", fg="#F8FAFC", bg="#0D1524", font=("Segoe UI", 10, "bold"))
        title_lbl.pack(side=tk.LEFT)

        sub_lbl = tk.Label(header, text="// Kỹ thuật viên", fg="#94A3B8", bg="#0D1524", font=("Segoe UI", 9))
        sub_lbl.pack(side=tk.LEFT, padx=(4, 0))

        btn_close = tk.Button(
            header,
            text="✕",
            fg="#94A3B8",
            bg="#0D1524",
            activebackground="#EF4444",
            activeforeground="#FFFFFF",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=8,
            command=self.hide
        )
        btn_close.pack(side=tk.RIGHT)

        # Chat history area
        history_frame = tk.Frame(self.root, bg="#070D17", padx=10, pady=8)
        history_frame.pack(fill=tk.BOTH, expand=True)

        self._text_area = tk.Text(
            history_frame,
            bg="#0A1120",
            fg="#F1F5F9",
            insertbackground="#22C55E",
            font=("Segoe UI", 9),
            wrap=tk.WORD,
            bd=1,
            relief=tk.SOLID,
            highlightthickness=1,
            highlightcolor="#1E293B",
            highlightbackground="#1E293B",
            padx=12,
            pady=10,
            state=tk.DISABLED
        )
        self._text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure message color tags
        self._text_area.tag_config("time", foreground="#64748B", font=("Consolas", 8))
        self._text_area.tag_config("remote_sender", foreground="#38BDF8", font=("Segoe UI", 9, "bold"))
        self._text_area.tag_config("local_sender", foreground="#22C55E", font=("Segoe UI", 9, "bold"))
        self._text_area.tag_config("system", foreground="#94A3B8", font=("Segoe UI", 8, "italic"))
        self._text_area.tag_config("body", foreground="#F8FAFC", font=("Segoe UI", 9))

        scrollbar = tk.Scrollbar(history_frame, command=self._text_area.yview, bg="#0A1120", bd=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text_area.config(yscrollcommand=scrollbar.set)

        # Input Area
        input_frame = tk.Frame(self.root, bg="#0D1524", padx=10, pady=10)
        input_frame.pack(fill=tk.X)

        self._entry = tk.Entry(
            input_frame,
            bg="#070D17",
            fg="#F8FAFC",
            insertbackground="#22C55E",
            font=("Segoe UI", 10),
            bd=1,
            relief=tk.SOLID,
            highlightthickness=1,
            highlightcolor="#22C55E",
            highlightbackground="#1E293B"
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))
        self._entry.bind("<Return>", lambda e: self._send_message())

        btn_send = tk.Button(
            input_frame,
            text="Gửi",
            bg="#22C55E",
            fg="#070D17",
            activebackground="#16A34A",
            activeforeground="#070D17",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=16,
            pady=5,
            cursor="hand2",
            command=self._send_message
        )
        btn_send.pack(side=tk.RIGHT)

        # Initially hidden until message received or user opens
        self.root.withdraw()

    def show(self):
        if not self._ready_event.is_set() or not self.root:
            return
        self.root.after(0, self._show_ui)

    def _show_ui(self):
        if not self.root:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        if self._entry:
            self._entry.focus_set()

    def hide(self):
        if not self._ready_event.is_set() or not self.root:
            return
        self.root.after(0, self._hide_ui)

    def _hide_ui(self):
        if self.root:
            self.root.withdraw()

    def add_message(self, sender: str, text: str, is_local: bool = False):
        self.history.append({"sender": sender, "text": text, "is_local": is_local, "time": time.time()})
        if not self._ready_event.is_set() or not self.root:
            return
        try:
            self.root.after(0, lambda: self._add_message_ui(sender, text, is_local))
        except Exception:
            pass

    def _add_message_ui(self, sender: str, text: str, is_local: bool = False):
        if not self._text_area:
            return
        timestamp = time.strftime("%H:%M:%S")

        self._text_area.config(state=tk.NORMAL)
        self._text_area.insert(tk.END, f"[{timestamp}] ", "time")
        if is_local:
            self._text_area.insert(tk.END, "Bạn: ", "local_sender")
        else:
            self._text_area.insert(tk.END, f"{sender}: ", "remote_sender")
        self._text_area.insert(tk.END, f"{text}\n\n", "body")
        self._text_area.see(tk.END)
        self._text_area.config(state=tk.DISABLED)

        # Play system notification sound on remote incoming message
        if not is_local:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            # Reveal and raise window
            self._show_ui()

    def _send_message(self):
        if not self._entry:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)
        self._add_message_ui("Bạn", text, is_local=True)
        if self.on_send_reply:
            try:
                self.on_send_reply(text)
            except Exception as e:
                print(f"[Chat Error] Failed to send reply: {e}", file=sys.stderr)

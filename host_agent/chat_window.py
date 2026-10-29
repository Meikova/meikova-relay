import os
import sys
import time
import queue
import threading
try:
    import tkinter as tk
except ImportError:
    class _TkStub:
        Tk = object
        Toplevel = object
        TclError = RuntimeError
    tk = _TkStub()
from pathlib import Path
from typing import Callable, Optional

try:
    from host_agent.engines import get_active_os_engine
except ModuleNotFoundError:
    try:
        from engines import get_active_os_engine
    except Exception:
        get_active_os_engine = None


class HostChatWindow:
    """Floating Ambient Dark frameless chat window for host workstation (Windows, macOS, Linux)."""

    PLACEHOLDER_TEXT = "Nhập tin nhắn gửi kỹ thuật viên..."

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
        self._text_area: Optional[tk.Text] = None
        self._entry: Optional[tk.Entry] = None
        self._placeholder_active = True
        self._ready_event = threading.Event()
        self._is_standalone = parent is None
        self.history = []
        self._icon_img = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_start_x = 0
        self._win_start_y = 0
        self._ui_queue: "queue.Queue" = queue.Queue()
        self._destroyed = False

        os_eng = get_active_os_engine() if get_active_os_engine else None
        fonts = os_eng.get_ui_fonts() if os_eng else {"sans": "Segoe UI", "mono": "Consolas"}
        self.f_sans = fonts.get("sans", "Segoe UI")
        self.f_mono = fonts.get("mono", "Consolas")

        if self.parent:
            self._init_ui(parent=self.parent)
            self._ready_event.set()
            self._schedule_queue_poll()
        else:
            self._thread = threading.Thread(target=self._standalone_worker, daemon=True)
            self._thread.start()
            self._ready_event.wait(timeout=3.0)

    def _enqueue_ui(self, fn: Callable[[], None]):
        if self._destroyed:
            return
        self._ui_queue.put(fn)
        if self.root is not None:
            try:
                self.root.after_idle(self._drain_queue)
            except Exception:
                pass

    def _drain_queue(self):
        while not self._destroyed:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass

    def _schedule_queue_poll(self):
        if self._destroyed or not self.root:
            return
        self._drain_queue()
        try:
            if hasattr(self.root, "winfo_exists") and self.root.winfo_exists():
                self.root.after(80, self._schedule_queue_poll)
        except Exception:
            pass

    def _standalone_worker(self):
        # macOS Cocoa AppKit strictly prohibits NSWindow creation on secondary threads
        if sys.platform == "darwin":
            self._ready_event.set()
            return

        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            self._init_ui(parent=None, tk_root=root)
            self._ready_event.set()
            self._schedule_queue_poll()
            root.mainloop()
        except Exception:
            self._ready_event.set()
        finally:
            if hasattr(self, "_icon_img") and self._icon_img is not None:
                try:
                    self._icon_img.name = None
                except Exception:
                    pass
                self._icon_img = None
            self._text_area = None
            self._entry = None
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
                del root
            self.root = None

    def _find_icon_asset(self) -> Optional[str]:
        """Locates brand squircle icon for titlebar and window."""
        search_dirs = [
            Path(__file__).resolve().parent / "tray_icons",
            Path(__file__).resolve().parent,
            Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None,
            Path(os.environ.get("LOCALAPPDATA", "")) / "MeikovaRelayHost" if sys.platform == "win32" else None,
        ]
        candidate_names = ["black-16.png", "icon-16.png", "black-20.png", "tray_icon.png", "icon.png"]
        for d in search_dirs:
            if not d or not d.is_dir():
                continue
            for name in candidate_names:
                f = d / name
                if f.is_file():
                    return str(f)
        return None

    def _init_ui(self, parent=None, tk_root=None):
        if tk_root:
            self.root = tk_root
        elif parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        try:
            self.root.withdraw()
        except Exception:
            pass

        try:
            self.root.overrideredirect(True)
        except Exception:
            pass

        self.root.title(self.title_text)
        self.root.configure(bg="#111315")
        self.root.attributes("-topmost", True)

        w, h = 380, 500
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(10, sw - w - 24)
        y = max(10, sh - h - 68)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(320, 360)

        self.root.bind("<Button-1>", lambda e: self._on_window_click())

        outer_border = tk.Frame(self.root, bg="#282B30", padx=1, pady=1)
        outer_border.pack(fill=tk.BOTH, expand=True)

        inner_container = tk.Frame(outer_border, bg="#111315")
        inner_container.pack(fill=tk.BOTH, expand=True)

        # ==================== CUSTOM TITLEBAR (36px Ambient Dark) ====================
        titlebar = tk.Frame(inner_container, bg="#16181A", height=36, padx=10, pady=0)
        titlebar.pack(side=tk.TOP, fill=tk.X)
        titlebar.pack_propagate(False)

        titlebar.bind("<ButtonPress-1>", self._start_drag)
        titlebar.bind("<B1-Motion>", self._on_drag)

        icon_path = self._find_icon_asset()
        if icon_path:
            try:
                self._icon_img = tk.PhotoImage(file=icon_path, master=self.root)
                icon_lbl = tk.Label(titlebar, image=self._icon_img, bg="#16181A", bd=0)
                icon_lbl.pack(side=tk.LEFT, padx=(0, 6))
                icon_lbl.bind("<ButtonPress-1>", self._start_drag)
                icon_lbl.bind("<B1-Motion>", self._on_drag)
            except Exception:
                self._icon_img = None

        dot = tk.Label(titlebar, text="●", fg="#83E8AC", bg="#16181A", font=(self.f_sans, 10, "bold"), bd=0)
        dot.pack(side=tk.LEFT, padx=(0, 6))
        dot.bind("<ButtonPress-1>", self._start_drag)
        dot.bind("<B1-Motion>", self._on_drag)

        title_lbl = tk.Label(
            titlebar,
            text="TRÒ CHUYỆN TRỰC TIẾP",
            fg="#F4F6F8",
            bg="#16181A",
            font=(self.f_sans, 9, "bold"),
            bd=0
        )
        title_lbl.pack(side=tk.LEFT)
        title_lbl.bind("<ButtonPress-1>", self._start_drag)
        title_lbl.bind("<B1-Motion>", self._on_drag)

        sub_lbl = tk.Label(
            titlebar,
            text="// KỸ THUẬT VIÊN",
            fg="#7D8590",
            bg="#16181A",
            font=(self.f_sans, 8),
            bd=0
        )
        sub_lbl.pack(side=tk.LEFT, padx=(4, 0))
        sub_lbl.bind("<ButtonPress-1>", self._start_drag)
        sub_lbl.bind("<B1-Motion>", self._on_drag)

        btn_close = tk.Button(
            titlebar,
            text="X",
            fg="#A0AAB4",
            bg="#16181A",
            activebackground="#FF5E6C",
            activeforeground="#FFFFFF",
            bd=0,
            font=(self.f_sans, 9, "bold"),
            cursor="hand2",
            padx=10,
            pady=0,
            command=self.hide
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_close_enter(e):
            btn_close.config(bg="#FF5E6C", fg="#FFFFFF")
        def _on_close_leave(e):
            btn_close.config(bg="#16181A", fg="#A0AAB4")
        btn_close.bind("<Enter>", _on_close_enter)
        btn_close.bind("<Leave>", _on_close_leave)

        btn_min = tk.Button(
            titlebar,
            text="—",
            fg="#A0AAB4",
            bg="#16181A",
            activebackground="#23272D",
            activeforeground="#FFFFFF",
            bd=0,
            font=(self.f_sans, 9, "bold"),
            cursor="hand2",
            padx=10,
            pady=0,
            command=self.hide
        )
        btn_min.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_min_enter(e):
            btn_min.config(bg="#23272D", fg="#FFFFFF")
        def _on_min_leave(e):
            btn_min.config(bg="#16181A", fg="#A0AAB4")
        btn_min.bind("<Enter>", _on_min_enter)
        btn_min.bind("<Leave>", _on_min_leave)

        title_sep = tk.Frame(inner_container, bg="#282B30", height=1)
        title_sep.pack(side=tk.TOP, fill=tk.X)

        # ==================== INPUT AREA (ANCHORED AT BOTTOM) ====================
        input_container = tk.Frame(inner_container, bg="#16181A")
        input_container.pack(side=tk.BOTTOM, fill=tk.X)

        input_sep = tk.Frame(input_container, bg="#282B30", height=1)
        input_sep.pack(side=tk.TOP, fill=tk.X)

        input_frame = tk.Frame(input_container, bg="#16181A", padx=10, pady=10)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self._entry = tk.Entry(
            input_frame,
            bg="#0D0E10",
            fg="#7D8590",
            insertbackground="#83E8AC",
            font=(self.f_sans, 9),
            bd=1,
            relief=tk.SOLID,
            highlightthickness=1,
            highlightcolor="#83E8AC",
            highlightbackground="#282B30"
        )
        self._entry.insert(0, self.PLACEHOLDER_TEXT)
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))
        self._entry.bind("<FocusIn>", self._on_entry_focus_in)
        self._entry.bind("<FocusOut>", self._on_entry_focus_out)
        self._entry.bind("<Return>", lambda e: self._send_message())

        btn_send = tk.Button(
            input_frame,
            text="GỬI",
            bg="#83E8AC",
            fg="#111315",
            activebackground="#6AD696",
            activeforeground="#111315",
            font=(self.f_sans, 9, "bold"),
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._send_message
        )
        btn_send.pack(side=tk.RIGHT)

        def _on_send_enter(e):
            btn_send.config(bg="#9BF0BF")
        def _on_send_leave(e):
            btn_send.config(bg="#83E8AC")
        btn_send.bind("<Enter>", _on_send_enter)
        btn_send.bind("<Leave>", _on_send_leave)

        # ==================== CHAT HISTORY AREA (FILL REMAINING) ====================
        history_frame = tk.Frame(inner_container, bg="#111315", padx=10, pady=8)
        history_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._text_area = tk.Text(
            history_frame,
            bg="#0D0E10",
            fg="#F4F6F8",
            insertbackground="#83E8AC",
            font=(self.f_sans, 9),
            wrap=tk.WORD,
            bd=1,
            relief=tk.SOLID,
            highlightthickness=1,
            highlightcolor="#282B30",
            highlightbackground="#282B30",
            padx=10,
            pady=8,
            state=tk.NORMAL
        )
        self._text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._text_area.tag_config("time", foreground="#7D8590", font=(self.f_mono, 8))
        self._text_area.tag_config("remote_sender", foreground="#83E8AC", font=(self.f_sans, 9, "bold"))
        self._text_area.tag_config("local_sender", foreground="#83E8AC", font=(self.f_sans, 9, "bold"))
        self._text_area.tag_config("system", foreground="#A0AAB4", font=(self.f_sans, 8, "italic"))
        self._text_area.tag_config("body", foreground="#F4F6F8", font=(self.f_sans, 9))

        self._text_area.insert(
            tk.END,
            "[Hệ thống] Trò chuyện trực tiếp 2 chiều với kỹ thuật viên.\nNhập tin nhắn bên dưới và bấm GỬI (hoặc Enter) để phản hồi.\n\n",
            "system"
        )
        self._text_area.config(state=tk.DISABLED)

        scrollbar = tk.Scrollbar(history_frame, command=self._text_area.yview, bg="#0D0E10", bd=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text_area.config(yscrollcommand=scrollbar.set)

        if sys.platform == "win32":
            try:
                self.root.update_idletasks()
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if hwnd:
                    GWL_EXSTYLE = -20
                    WS_EX_APPWINDOW = 0x00040000
                    WS_EX_TOOLWINDOW = 0x00000080
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            except Exception:
                pass

        self.root.withdraw()

    def _start_drag(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        if self.root:
            self._win_start_x = self.root.winfo_x()
            self._win_start_y = self.root.winfo_y()

    def _on_drag(self, event):
        if not self.root:
            return
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        self.root.geometry(f"+{self._win_start_x + dx}+{self._win_start_y + dy}")

    def _on_window_click(self):
        if self.root:
            self.root.focus_force()

    def _on_entry_focus_in(self, event):
        if self._placeholder_active:
            self._entry.delete(0, tk.END)
            self._entry.config(fg="#F4F6F8")
            self._placeholder_active = False

    def _on_entry_focus_out(self, event):
        if not self._entry.get().strip():
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self.PLACEHOLDER_TEXT)
            self._entry.config(fg="#7D8590")
            self._placeholder_active = True

    def show(self):
        if not self._ready_event.is_set() or not self.root:
            return
        self._enqueue_ui(self._show_ui)

    def _show_ui(self):
        if not self.root:
            return
        try:
            self.root.overrideredirect(True)
        except Exception:
            pass
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        if self._entry:
            self._entry.focus_set()

    def hide(self):
        if not self._ready_event.is_set() or not self.root:
            return
        self._enqueue_ui(self._hide_ui)

    def _hide_ui(self):
        if self.root:
            self.root.withdraw()

    def add_message(self, sender: str, text: str, is_local: bool = False):
        self.history.append({"sender": sender, "text": text, "is_local": is_local, "time": time.time()})
        if not self._ready_event.is_set() or not self.root:
            return
        self._enqueue_ui(lambda: self._add_message_ui(sender, text, is_local))

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

        if not is_local:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            self._show_ui()

    def _send_message(self):
        if not self._entry:
            return
        text = self._entry.get().strip()
        if not text or self._placeholder_active or text == self.PLACEHOLDER_TEXT:
            return
        self._entry.delete(0, tk.END)
        self.history.append({"sender": "Bạn", "text": text, "is_local": True, "time": time.time()})
        self._add_message_ui("Bạn", text, is_local=True)
        if self.on_send_reply:
            try:
                self.on_send_reply(text)
            except Exception as e:
                print(f"[Chat Error] Failed to send reply: {e}", file=sys.stderr)

    def destroy(self):
        self._destroyed = True
        if hasattr(self, "_icon_img") and self._icon_img is not None:
            try:
                self._icon_img.name = None
            except Exception:
                pass
            self._icon_img = None
        if self.root:
            try:
                self.root.after(0, self.root.quit)
            except Exception:
                try:
                    self.root.quit()
                except Exception:
                    pass
        if hasattr(self, "_thread") and self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass
        self.root = None

    def __del__(self):
        try:
            self.destroy()
        except Exception:
            pass

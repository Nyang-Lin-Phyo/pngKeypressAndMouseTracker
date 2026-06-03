"""
PNGvtuber Launcher + WebSocket Server (combined)
Everything runs in one process — safe to freeze with PyInstaller.

Install deps:
    pip install websockets keyboard mouse pyinstaller
Build exe:
    double-click build.bat
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os, sys, json, threading, asyncio
import websockets
import keyboard
import mouse

# ── Expected files ────────────────────────────────────────────────────────────
REQUIRED_FILES = [
    "base.png", "rightHandMouse.png",
    "press1.png", "press2.png", "press3.png", "press4.png",
    "pressQ.png", "pressW.png", "pressE.png", "pressR.png",
    "pressA.png", "pressS.png", "pressD.png", "pressF.png",
    "pressSpace.png",
]

def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_base_dir(), "launcher_config.json")

# ── Colours ───────────────────────────────────────────────────────────────────
BG      = "#0e0e12"
SURFACE = "#1a1a22"
BORDER  = "#2e2e3e"
TEXT    = "#e8e8f0"
MUTED   = "#666680"
GREEN   = "#6ee86e"
RED     = "#e85a5a"
YELLOW  = "#e8b86e"
ACCENT  = "#7b8cff"

# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket server (runs in a background thread + asyncio loop)
# ═══════════════════════════════════════════════════════════════════════════════
HOST = "localhost"
PORT = 8765
TRACKED_KEYS = {'1','2','3','4','q','w','e','r','a','s','d','f','space'}
MOUSE_THRESHOLD = 2

_press_order: list = []
_mouse_x: int = 0
_mouse_y: int = 0
_state_lock = threading.Lock()
_clients: set = set()
_server_loop: asyncio.AbstractEventLoop = None
_server_running = False


async def _broadcast(message: str):
    if not _clients:
        return
    dead = set()
    for ws in list(_clients):
        try:
            await ws.send(message)
        except websockets.ConnectionClosed:
            dead.add(ws)
    _clients.difference_update(dead)


def _send_state():
    if _server_loop is None:
        return
    with _state_lock:
        msg = json.dumps({
            "held_keys": list(_press_order),
            "mouse_x":   _mouse_x,
            "mouse_y":   _mouse_y,
        })
    asyncio.run_coroutine_threadsafe(_broadcast(msg), _server_loop)


def _on_key(event):
    key = event.name.lower()
    if key not in TRACKED_KEYS:
        return
    with _state_lock:
        if event.event_type == keyboard.KEY_DOWN:
            if key not in _press_order:
                _press_order.append(key)
        elif event.event_type == keyboard.KEY_UP:
            if key in _press_order:
                _press_order.remove(key)
    _send_state()


_last_mx = _last_my = 0

def _on_mouse(event):
    global _last_mx, _last_my, _mouse_x, _mouse_y
    if not isinstance(event, mouse.MoveEvent):
        return
    if abs(event.x - _last_mx) < MOUSE_THRESHOLD and \
       abs(event.y - _last_my) < MOUSE_THRESHOLD:
        return
    _last_mx, _last_my = event.x, event.y
    with _state_lock:
        _mouse_x = event.x
        _mouse_y = event.y
    _send_state()


async def _handler(websocket):
    _clients.add(websocket)
    try:
        with _state_lock:
            msg = json.dumps({
                "held_keys": list(_press_order),
                "mouse_x":   _mouse_x,
                "mouse_y":   _mouse_y,
            })
        await websocket.send(msg)
        await websocket.wait_closed()
    finally:
        _clients.discard(websocket)


async def _server_main(stop_event: asyncio.Event):
    global _server_loop
    _server_loop = asyncio.get_running_loop()
    async with websockets.serve(_handler, HOST, PORT):
        await stop_event.wait()   # blocks until stop() is called


def _run_server_thread(stop_event_holder: list):
    """Runs the asyncio server loop in a daemon thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()
    stop_event_holder.append((loop, stop_event))
    try:
        loop.run_until_complete(_server_main(stop_event))
    finally:
        loop.close()


def start_server():
    """Start keyboard/mouse hooks and WebSocket server. Returns a stop() callable."""
    global _server_running
    if _server_running:
        return lambda: None

    keyboard.hook(_on_key)
    mouse.hook(_on_mouse)

    stop_event_holder = []
    t = threading.Thread(target=_run_server_thread, args=(stop_event_holder,), daemon=True)
    t.start()

    def stop():
        global _server_running, _server_loop
        keyboard.unhook(_on_key)
        mouse.unhook(_on_mouse)
        # Signal the asyncio event
        if stop_event_holder:
            loop, ev = stop_event_holder[0]
            loop.call_soon_threadsafe(ev.set)
        _server_loop = None
        _press_order.clear()
        _clients.clear()

    _server_running = True
    return stop


# ═══════════════════════════════════════════════════════════════════════════════
# Launcher GUI
# ═══════════════════════════════════════════════════════════════════════════════
class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNGvtuber Launcher")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.png_folder = tk.StringVar()
        self.center_x   = tk.StringVar(value="960")
        self.center_y   = tk.StringVar(value="540")
        self.radius_x   = tk.StringVar(value="1100")
        self.radius_y   = tk.StringVar(value="800")
        self._stop_fn   = None   # callable to stop the server

        self._load_config()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.png_folder.get():
            self.after(100, self._validate)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        title_frame = tk.Frame(self, bg=BG)
        title_frame.pack(fill="x", padx=16, pady=(16, 12))
        tk.Label(title_frame, text="●", fg=GREEN, bg=BG,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(title_frame, text="  PNGvtuber Overlay", fg=TEXT, bg=BG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        self._divider()

        # PNG Folder
        self._section("PNG Folder")
        folder_frame = tk.Frame(self, bg=BG)
        folder_frame.pack(fill="x", padx=16, pady=(0, 8))
        self.folder_label = tk.Label(
            folder_frame, textvariable=self.png_folder,
            fg=MUTED, bg=SURFACE, anchor="w",
            font=("Segoe UI", 9), width=34, relief="flat", padx=8, pady=5,
            highlightthickness=1, highlightbackground=BORDER,
        )
        self.folder_label.pack(side="left", fill="x", expand=True)
        self._button(folder_frame, "Browse…", self._browse).pack(side="left", padx=(6, 0))

        self.check_frame = tk.Frame(self, bg=BG)
        self.check_frame.pack(fill="x", padx=16, pady=(0, 10))

        self._divider()

        # Mouse Center
        self._section("Mouse Center (screen coords)")
        row1 = tk.Frame(self, bg=BG)
        row1.pack(fill="x", padx=16, pady=(0, 4))
        self._coord_field(row1, "Center X:", self.center_x)
        tk.Label(row1, text="    ", bg=BG).pack(side="left")
        self._coord_field(row1, "Center Y:", self.center_y)
        tk.Label(self, fg=MUTED, bg=BG, font=("Segoe UI", 8), anchor="w",
                 text="Move mouse to mousepad center → note coords from server output"
                 ).pack(fill="x", padx=16, pady=(0, 10))

        self._divider()

        # Mouse Radius
        self._section("Mouse Radius (how far mouse travels to reach edge)")
        row2 = tk.Frame(self, bg=BG)
        row2.pack(fill="x", padx=16, pady=(0, 4))
        self._coord_field(row2, "Radius X:", self.radius_x, width=6)
        tk.Label(row2, text="    ", bg=BG).pack(side="left")
        self._coord_field(row2, "Radius Y:", self.radius_y, width=6)
        tk.Label(self, fg=MUTED, bg=BG, font=("Segoe UI", 8), anchor="w",
                 text="Increase if hand hits left/right or top/bottom wall too early"
                 ).pack(fill="x", padx=16, pady=(0, 10))

        self._divider()

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=12)
        self.launch_btn = self._button(btn_frame, "▶  Launch Server", self._launch, accent=True)
        self.launch_btn.pack(side="left")
        self.stop_btn = self._button(btn_frame, "■  Stop", self._stop, danger=True)
        self.stop_btn.pack(side="left", padx=(8, 0))
        self.stop_btn.config(state="disabled")

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        self.status_bar = tk.Label(
            self, textvariable=self.status_var,
            fg=MUTED, bg=SURFACE, anchor="w",
            font=("Segoe UI", 9), padx=10, pady=5,
        )
        self.status_bar.pack(fill="x", side="bottom")

    def _divider(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=6)

    def _section(self, text):
        tk.Label(self, text=text.upper(), fg=MUTED, bg=BG,
                 font=("Segoe UI", 8, "bold"), anchor="w"
                 ).pack(fill="x", padx=16, pady=(4, 4))

    def _button(self, parent, text, cmd, accent=False, danger=False):
        fg = BG if accent else TEXT
        if danger:
            bg, abg, fg = "#3a1a1a", "#5a2a2a", RED
        elif accent:
            bg, abg = ACCENT, "#9aaafe"
        else:
            bg, abg = SURFACE, "#25252f"
        b = tk.Button(parent, text=text, command=cmd,
                      fg=fg, bg=bg, activeforeground=fg, activebackground=abg,
                      font=("Segoe UI", 9), relief="flat", padx=12, pady=5,
                      cursor="hand2", bd=0)
        b.bind("<Enter>", lambda e: b.config(bg=abg))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    def _coord_field(self, parent, label, var, width=7):
        tk.Label(parent, text=label, fg=MUTED, bg=BG,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(parent, textvariable=var, width=width,
                 fg=TEXT, bg=SURFACE, insertbackground=TEXT,
                 font=("Segoe UI", 10), relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT,
                 ).pack(side="left", ipady=4, padx=(2, 0))

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse(self):
        folder = filedialog.askdirectory(title="Select your PNGs folder")
        if folder:
            self.png_folder.set(folder)
            self._validate()
            self._save_config()

    def _validate(self):
        for w in self.check_frame.winfo_children():
            w.destroy()
        folder = self.png_folder.get()
        if not folder or not os.path.isdir(folder):
            self.folder_label.config(fg=MUTED)
            return
        self.folder_label.config(fg=TEXT)
        files_in_folder = {f.lower() for f in os.listdir(folder)}
        missing = [f for f in REQUIRED_FILES if f.lower() not in files_in_folder]
        if not missing:
            row = tk.Frame(self.check_frame, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="✓", fg=GREEN, bg=BG,
                     font=("Segoe UI", 9, "bold"), width=2).pack(side="left")
            tk.Label(row, text=f"All {len(REQUIRED_FILES)} files found",
                     fg=GREEN, bg=BG, font=("Segoe UI", 9)).pack(side="left")
            self._set_status("All files OK — ready to launch.", GREEN)
        else:
            row = tk.Frame(self.check_frame, bg=BG)
            row.pack(fill="x", pady=(2, 4))
            tk.Label(row, text="✗", fg=RED, bg=BG,
                     font=("Segoe UI", 9, "bold"), width=2).pack(side="left")
            tk.Label(row, text=f"{len(missing)} file(s) missing:",
                     fg=RED, bg=BG, font=("Segoe UI", 9)).pack(side="left")
            for f in missing:
                mrow = tk.Frame(self.check_frame, bg=BG)
                mrow.pack(fill="x")
                tk.Label(mrow, text="  –", fg=MUTED, bg=BG,
                         font=("Segoe UI", 9)).pack(side="left")
                tk.Label(mrow, text=f, fg=YELLOW, bg=BG,
                         font=("Segoe UI", 9, "italic")).pack(side="left")
            self._set_status(f"{len(missing)} missing file(s).", YELLOW)
        self.update_idletasks()
        self.geometry("")

    def _launch(self):
        folder = self.png_folder.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("No folder", "Please select your PNGs folder first.")
            return
        try:
            cx = int(self.center_x.get())
            cy = int(self.center_y.get())
            rx = int(self.radius_x.get())
            ry = int(self.radius_y.get())
        except ValueError:
            messagebox.showerror("Bad values", "All fields must be integers.")
            return

        self._save_config()

        self._stop_fn = start_server()
        self.launch_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._set_status(f"Server running on ws://localhost:{PORT}", GREEN)

    def _stop(self):
        if self._stop_fn:
            self._stop_fn()
            self._stop_fn = None
        global _server_running
        _server_running = False
        self.launch_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._set_status("Server stopped.", MUTED)

    def _on_close(self):
        self._stop()
        self.destroy()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _set_status(self, text, color=None):
        self.status_var.set(text)
        if color:
            self.status_bar.config(fg=color)

    def _save_config(self):
        try:
            cfg = {
                "png_folder": self.png_folder.get(),
                "center_x": int(self.center_x.get()),
                "center_y": int(self.center_y.get()),
                "radius_x": int(self.radius_x.get()),
                "radius_y": int(self.radius_y.get()),
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            self.png_folder.set(cfg.get("png_folder", ""))
            self.center_x.set(str(cfg.get("center_x", "960")))
            self.center_y.set(str(cfg.get("center_y", "540")))
            self.radius_x.set(str(cfg.get("radius_x", "1100")))
            self.radius_y.set(str(cfg.get("radius_y", "800")))
        except Exception:
            pass


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
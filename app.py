# app.py
import os, socket, threading, sys
from collections import deque

import customtkinter as ctk
from tkinter import messagebox, filedialog

from config import (
    APP_TITLE, DEFAULT_MIN_RAM, DEFAULT_MAX_RAM, WINDOW_GEOMETRY, WINDOW_ALPHA,
    PLAYER_LIST_POLL_SECS, TIMEOUT_MINUTES,
)
from theme import apply_theme, COLORS
from utils.hover import add_hover_effect
from utils.parsers import maybe_parse_players, parse_online_counts
from server_controller import ServerController

from tabs.console_tab import ConsoleTab
from tabs.stats_tab import StatsTab
from tabs.players_tab import PlayersTab
from widgets.folder_tabs import FolderTabs 
from tkinter import PhotoImage  

SERVER_PROPERTIES = "server.properties"


# ---------- resource helper ----------
def _resource_path(relative: str) -> str:
    """Absolute path for a resource; works in dev and in PyInstaller EXE."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative)


class ServerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_GEOMETRY)
        self.configure(fg_color=COLORS["window_bg"])
        self.attributes("-alpha", WINDOW_ALPHA)
        apply_theme()

        # --- Window icon setup (robust) ---
        ico_path = os.path.abspath(_resource_path("assets/tempo.ico"))   # must be .ico
        png_path = os.path.abspath(_resource_path("assets/tempo.png"))   # optional PNG

        # 1) Try proper .ico for title bar/system menu (Windows requirement)
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception as e:
            print("iconbitmap failed:", e)

        # 2) Also set iconphoto with a PNG for better scaling in taskbar on some setups
        try:
            if os.path.exists(png_path):
                self.iconphoto(True, PhotoImage(file=png_path))
        except Exception as e:
            print("iconphoto failed:", e)

        # state
        self.players = set()
        self.players_version = 0
        self._last_lines = deque(maxlen=200)
        self._running_state = None
        self._port_probe_skip = 0
        self._running_false_streak = 0   # need 2 consecutive "not running" before flipping

        # window-move debounce
        self._move_job = None
        self._move_active = False
        self._prev_geo = None

        # controller + initial paths
        self.controller = ServerController(on_output=self._on_output, on_exit=self._on_exit)
        self.jar_path = self.controller.find_jar()
        self._server_root = self._derive_server_root(self.jar_path)
        self._max_players = self._read_max_players()

        self._build_ui()
        self.after(500, self._check_eula_state)
        self.after(1000 * PLAYER_LIST_POLL_SECS, self._tick_player_poll)
        self.after(2000, self._tick_proc_state)
        self.bind("<Configure>", self._on_configure_window)

    # ---------------- UI ----------------
    def _build_ui(self):
        # === TOP SECTION (centered with left/right gutters) ===
        top_container = ctk.CTkFrame(
            self, fg_color=COLORS["top_bg"], corner_radius=10,
            border_width=1, border_color=COLORS["top_border"]
        )
        top_container.pack(pady=12, padx=24, fill="x")

        top = ctk.CTkFrame(top_container, fg_color=COLORS["top_bg"])
        top.pack(anchor="center", pady=8, fill="x", padx=24)

        # grid with gutters so content sits centered
        GUTTER = 2
        TOTAL_COLS = 12
        for col in range(TOTAL_COLS):
            top.grid_columnconfigure(col, weight=1)

        def C(i: int) -> int:
            return i + GUTTER

        # Row 0 — Server jar  (logo removed; shift back left)
        ctk.CTkLabel(top, text="Server jar:").grid(row=0, column=C(0), padx=5, pady=6, sticky="e")

        self.jar_var = ctk.StringVar(value=self.jar_path)
        self.jar_var.trace_add("write", self._on_jar_change)

        jar_frame = ctk.CTkFrame(
            top, fg_color=COLORS["input_frame"], corner_radius=6,
            border_width=2, border_color=COLORS["input_border"]
        )
        # back to starting at C(1) and spanning 8 cols
        jar_frame.grid(row=0, column=C(1), columnspan=8, pady=6, padx=5, sticky="ew")
        jar_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            jar_frame, textvariable=self.jar_var, fg_color=COLORS["input_frame"],
            text_color="white", border_width=0, corner_radius=6
        ).grid(row=0, column=0, sticky="ew", padx=(8, 0), pady=3)

        ctk.CTkButton(
            jar_frame, text="▼", width=34, fg_color=COLORS["btn_alt"],
            hover_color=COLORS["btn_hover"], text_color="white",
            corner_radius=0, command=self._browse_jar
        ).grid(row=0, column=1, sticky="ns")

        self.jar_status_lbl = ctk.CTkLabel(
            top, text="🔴", text_color="red", font=("Segoe UI", 14, "bold")
        )
        self.jar_status_lbl.grid(row=0, column=C(9), padx=(5, 0), sticky="w")

        # Row 1 — RAM, nogui, max players, verify
        ctk.CTkLabel(top, text="Min RAM:").grid(row=1, column=C(0), pady=5, sticky="e")
        self.min_ram = ctk.StringVar(value=DEFAULT_MIN_RAM)
        ctk.CTkComboBox(top, variable=self.min_ram,
                        values=[f"{g}G" for g in (1, 2, 3, 4, 6, 8, 10, 12)],
                        width=80).grid(row=1, column=C(1), pady=5, padx=8)

        ctk.CTkLabel(top, text="Max RAM:").grid(row=1, column=C(2), pady=5, sticky="e")
        self.max_ram = ctk.StringVar(value=DEFAULT_MAX_RAM)
        ctk.CTkComboBox(top, variable=self.max_ram,
                        values=[f"{g}G" for g in (1, 2, 3, 4, 6, 8, 10, 12)],
                        width=80).grid(row=1, column=C(3), pady=5, padx=8)

        self.nogui_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(top, text="nogui", variable=self.nogui_var)\
            .grid(row=1, column=C(4), pady=5, padx=5, sticky="w")

        ctk.CTkLabel(top, text="Max players:").grid(row=1, column=C(5), pady=5, sticky="e")
        self.max_players_var = ctk.StringVar(value=str(self._max_players))
        self.max_entry = ctk.CTkEntry(top, textvariable=self.max_players_var, width=70, justify="right")
        self.max_entry.grid(row=1, column=C(6), pady=5, padx=6, sticky="w")
        self.max_entry.bind("<FocusIn>", self._select_all_max_entry)
        self.max_entry.bind("<Return>", self._apply_max_players_event)
        self.max_entry.bind("<KP_Enter>", self._apply_max_players_event)
        self.max_entry.bind("<FocusOut>", self._apply_max_players)

        self.verify_btn = ctk.CTkButton(
            top, text="Verify RAM", width=90,
            fg_color=COLORS.get("btn_alt", "#4a4a4a"),
            hover_color=COLORS.get("btn_hover", "#5a5a5a"),
            command=self._verify_ram,
        )
        self.verify_btn.grid(row=1, column=C(7), pady=5, padx=6, sticky="w")

        # === Start/Stop/EULA buttons ===
        btns = ctk.CTkFrame(self, fg_color=COLORS["window_bg"])
        btns.pack(pady=8)

        self.start_btn = ctk.CTkButton(btns, text="Start", command=self._start_server,
                                       fg_color=COLORS["green"], width=120, height=32, corner_radius=8, font=("Segoe UI", 10, "bold"))
        self.stop_btn = ctk.CTkButton(btns, text="Stop", command=self._stop_server,
                                      fg_color=COLORS["red"], width=120, height=32, corner_radius=8, font=("Segoe UI", 10, "bold"), state="disabled")
        self.eula_btn = ctk.CTkButton(btns, text="Accept EULA", command=self._accept_eula,
                                      fg_color=COLORS["button_default"], width=150, height=32, corner_radius=8, font=("Segoe UI", 10, "bold"))
        self.start_btn.grid(row=0, column=0, padx=10)
        self.stop_btn.grid(row=0, column=1, padx=10)
        self.eula_btn.grid(row=0, column=2, padx=10)

        add_hover_effect(self.start_btn, COLORS["green"], COLORS["green_hover"])
        add_hover_effect(self.stop_btn, COLORS["red"], COLORS["red_hover"])
        add_hover_effect(self.eula_btn, COLORS["button_default"], COLORS["btn_hover"])

        # --- Folder-style tabs ---
        tabs = FolderTabs(self, tab_width=110)
        tabs.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        self.console_tab = ConsoleTab(tabs.content, send_callback=self._send_command)
        self.console_tab.set_max_lines(1200)

        self.stats_tab = StatsTab(tabs.content)
        self.stats_tab.set_controller(self.controller)
        self.stats_tab.set_server_root(self._server_root)
        self.stats_tab.start_loop()

        self.players_tab = PlayersTab(tabs.content, initial_max_players=self._max_players)

        tabs.add_tab("Console", self.console_tab)
        tabs.add_tab("Stats", self.stats_tab)
        tabs.add_tab("Players", self.players_tab)
        tabs.select("Console")

        self._print_line(f"Working dir: {os.getcwd()}")
        if self._server_root and self._server_root != os.getcwd():
            self._print_line(f"Server root: {self._server_root}")
        self._on_jar_change()

    # ------------- window move debounce -------------
    def _on_configure_window(self, _evt=None):
        try:
            geo = (self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height())
        except Exception:
            return
        if geo == self._prev_geo:
            return
        self._prev_geo = geo
        if not self._move_active:
            self._begin_window_move()
        if self._move_job is not None:
            try: self.after_cancel(self._move_job)
            except Exception: pass
        self._move_job = self.after(180, self._end_window_move)

    def _begin_window_move(self):
        self._move_active = True
        try: self.console_tab.set_suspended(True)
        except Exception: pass
        try: self.stats_tab.pause(True)
        except Exception: pass

    def _end_window_move(self):
        self._move_active = False
        try: self.console_tab.set_suspended(False)
        except Exception: pass
        try:
            self.stats_tab.pause(False)
            self.stats_tab.force_redraw()
        except Exception:
            pass

    # ------------- running state -------------
    def _set_running(self, running: bool):
        if self._running_state is running:
            return
        self._running_state = running
        def apply():
            self.start_btn.configure(state="disabled" if running else "normal")
            self.stop_btn.configure(state="normal" if running else "disabled")
        self.after(0, apply)

    # ------------- helpers / paths -------------
    def _fmt_bytes(self, b):
        if b is None:
            return "?"
        mb = b / (1024 * 1024)
        if mb >= 1024:
            return f"{mb/1024:.1f} GiB"
        return f"{mb:.0f} MiB"

    def _derive_server_root(self, jar_path: str) -> str:
        if jar_path and os.path.isfile(jar_path):
            return os.path.dirname(os.path.abspath(jar_path))
        return os.path.abspath(getattr(self, "_server_root", os.getcwd()))

    def _props_path(self):
        root = self._server_root or os.getcwd()
        return os.path.join(root, SERVER_PROPERTIES)

    def _get_server_port(self) -> int:
        path = self._props_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("server-port="):
                        return int(line.split("=", 1)[1].strip())
        except Exception:
            pass
        return 25565

    def _is_port_open(self, host="127.0.0.1") -> bool:
        port = self._get_server_port()
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except Exception:
            return False

    # ------------- controller callbacks -------------
    def _on_output(self, line: str):
        """Called from ServerController thread."""
        self._print_line(line)

        updated = maybe_parse_players(line, self.players)
        if updated is not None:
            self.players = updated
            self.players_tab.set_players(sorted(self.players, key=str.lower))
            self.players_version += 1

        counts = parse_online_counts(line)
        if counts:
            _, running_max = counts
            self.players_tab.set_max_players(running_max)

    def _on_exit(self, _rc):
        def apply():
            self._set_running(False)
            self.players.clear()
            self.players_tab.set_players([])
        self.after(0, apply)

    # ------------- UI helpers -------------
    def _print_line(self, text: str):
        self.console_tab.print_line(text)
        self._last_lines.append(text)

    def _browse_jar(self):
        file_path = filedialog.askopenfilename(
            title="Select Server Jar",
            filetypes=[("Java JAR files", "*.jar"), ("All files", "*.*")]
        )
        if file_path:
            self.jar_var.set(file_path)
            self._print_line(f"Selected server jar: {os.path.basename(file_path)}")

    def _on_jar_change(self, *_):
        path = (self.jar_var.get() or "").strip()
        if path and os.path.isfile(path):
            self._server_root = self._derive_server_root(path)
            self.stats_tab.set_server_root(self._server_root)
            self._print_line(f"Server jar set to: {os.path.basename(path)}")
            self._print_line(f"Server root: {self._server_root}")
            self.jar_status_lbl.configure(text="🟢", text_color="green")
            self._max_players = self._read_max_players()
            self.players_tab.set_max_players(self._max_players)
            self._check_eula_state()  # ensure EULA reflects this folder
        else:
            self.jar_status_lbl.configure(text="🔴", text_color="red")
            if not self._last_lines or not self._last_lines[-1].startswith("No server jar"):
                self._print_line("No server jar selected. Click ▼ to choose your server .jar.")

    # ------------- max players -------------
    def _read_max_players(self) -> int:
        path = self._props_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("max-players="):
                        return int(line.split("=", 1)[1].strip())
        except Exception:
            pass
        return 20

    def _write_max_players(self, n: int):
        path = self._props_path()
        lines, found = [], False
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                lines = []

        new_lines = []
        for ln in lines:
            if ln.strip().startswith("max-players=") and not found:
                new_lines.append(f"max-players={n}\n")
                found = True
            else:
                new_lines.append(ln)
        if not found:
            new_lines.append(f"max-players={n}\n")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            self._print_line(f"Max players set to {n} (applies on next server start).")
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't write server.properties:\n{e}")

    def _apply_max_players(self, _evt=None):
        raw = (self.max_players_var.get() or "").strip()
        try:
            val = max(1, min(1000, int(raw)))
        except Exception:
            self.max_players_var.set(str(self._max_players))
            return
        self._max_players = val
        self.max_players_var.set(str(val))
        self.players_tab.set_max_players(val)
        self._write_max_players(val)

    def _select_all_max_entry(self, _evt=None):
        try:
            self.max_entry.select_range(0, "end")
            self.max_entry.icursor("end")
        except Exception:
            pass

    def _apply_max_players_event(self, _evt=None):
        self._apply_max_players()
        running = self.controller.is_running()
        target = self.stop_btn if running else self.start_btn
        try:
            target.focus_set()
        except Exception:
            self.focus_set()
        return "break"

    # ------------- EULA -------------
    def _check_eula_state(self):
        exists, accepted = self.controller.check_eula_state(self._server_root)
        if exists and accepted:
            self.eula_btn.configure(text="EULA accepted ✓", state="disabled")
        else:
            self.eula_btn.configure(text=("Accept EULA" if exists else "Create & Accept EULA"), state="normal")

    def _accept_eula(self):
        try:
            self.controller.accept_eula(self._server_root)
            self._check_eula_state()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------- server control -------------
    def _start_server(self):
        if self.controller.is_running() or self._is_port_open():
            messagebox.showinfo("Server is running", "A server is already running (port is in use).")
            return
        try:
            self.controller.start(
                jar_path=self.jar_var.get().strip(),
                min_ram=self.min_ram.get(),
                max_ram=self.max_ram.get(),
                use_nogui=self.nogui_var.get(),
                server_root=self._server_root,
            )
            self._set_running(True)
        except Exception as e:
            messagebox.showerror("Missing jar", str(e))

    def _stop_server(self):
        self.controller.stop()

    def _send_command(self, raw: str, *, echo: bool = True) -> bool:
        return self.controller.send_command(raw, echo=echo)

    # ------------- Verify RAM (async) -------------
    def _verify_ram(self):
        if not self.controller.is_running():
            messagebox.showinfo("Verify RAM", "Start the server first, then try again.")
            return

        def worker():
            info = self.controller.get_heap_limits()
            if not info:
                self._print_line("[verify] Could not read heap limits (server not running?).")
                return

            src = info.get("source", "?")
            init_b = info.get("initial")
            max_b = info.get("max")
            self._print_line(f"[verify] Heap limits via {src}: Xms={self._fmt_bytes(init_b)}, Xmx={self._fmt_bytes(max_b)}")

            try:
                from server_controller import _parse_mem_string_to_bytes as _p
            except Exception:
                _p = lambda _: None

            ui_xms = _p(self.min_ram.get())
            ui_xmx = _p(self.max_ram.get())

            tol = 8 * 1024 * 1024
            warn = []
            if init_b is not None and ui_xms is not None and abs(init_b - ui_xms) > tol:
                warn.append(f"Xms differs (UI={self._fmt_bytes(ui_xms)} vs JVM={self._fmt_bytes(init_b)})")
            if max_b is not None and ui_xmx is not None and abs(max_b - ui_xmx) > tol:
                warn.append(f"Xmx differs (UI={self._fmt_bytes(ui_xmx)} vs JVM={self._fmt_bytes(max_b)})")

            if warn:
                for w in warn:
                    self._print_line(f"[verify] ⚠ {w}")
            else:
                self._print_line("[verify] ✓ JVM heap matches your UI settings (within tolerance).")

        threading.Thread(target=worker, daemon=True).start()

    # ------------- pollers -------------
    def _tick_proc_state(self):
        try:
            proc_running = self.controller.is_running()
        except Exception:
            proc_running = False

        port_running = False
        if not proc_running:
            if self._port_probe_skip <= 0:
                self._port_probe_skip = 5  # ~10s
                port_running = self._is_port_open()
            else:
                self._port_probe_skip -= 1

        if proc_running or port_running:
            self._running_false_streak = 0
            running = True
        else:
            self._running_false_streak += 1
            running = False if self._running_false_streak >= 2 else (self._running_state if self._running_state is not None else False)

        self._set_running(running)
        self.after(2000, self._tick_proc_state)

    def _tick_player_poll(self):
        if self.controller.is_running():
            self._send_command("list", echo=False)
        self.after(1000 * PLAYER_LIST_POLL_SECS, self._tick_player_poll)


if __name__ == "__main__":
    app = ServerApp()
    app.mainloop()

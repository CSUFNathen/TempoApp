# tabs/stats_tab.py
from collections import deque
import os, socket
import customtkinter as ctk
from theme import COLORS

try:
    import psutil
except Exception:
    psutil = None

REFRESH_MS = 1000
WINDOW_SEC = 120
AUTO_ZOOM = True
MIN_RANGE_MB = 8.0
AMPLIFY_SMALL_CHANGES = 6.0

class StatsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["tab_bg"])

        self.card = ctk.CTkFrame(
            self, fg_color=COLORS["card_bg"], corner_radius=12,
            border_width=1, border_color=COLORS["card_border"]
        )
        self.card.pack(fill="both", expand=True, padx=8, pady=8)

        graph_frame = ctk.CTkFrame(self.card, fg_color=COLORS["inset_bg"], corner_radius=10)
        graph_frame.pack(fill="x", padx=12, pady=(12, 6))

        self.canvas = ctk.CTkCanvas(graph_frame, height=120, bg=COLORS["inset_bg"], highlightthickness=0)
        self.canvas.pack(fill="x", expand=True, padx=10, pady=10)

        text_frame = ctk.CTkFrame(self.card, fg_color=COLORS["card_bg"])
        text_frame.pack(fill="x", padx=12, pady=(0, 12))
        self.lbl_mem = ctk.CTkLabel(text_frame, text="Memory use: — mb (—% free)", font=("Segoe UI", 13))
        self.lbl_src = ctk.CTkLabel(text_frame, text="", font=("Segoe UI", 11))
        self.lbl_mem.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_src.pack(anchor="w", padx=6, pady=(0, 4))

        self.controller = None
        self.server_root = os.getcwd()     # <<<<<< default, will be updated by app
        maxlen = max(2, int((WINDOW_SEC * 1000) / REFRESH_MS))
        self.mem_hist = deque(maxlen=maxlen)
        self._last_good_mb = 0.0
        self._running_prev = False

        self._paused = False
        self._cfg_job = None
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    # API
    def set_controller(self, controller):
        self.controller = controller

    def set_server_root(self, root_path: str):
        if root_path:
            self.server_root = root_path

    def start_loop(self):
        self.after(REFRESH_MS, self._tick)

    def pause(self, flag: bool):
        self._paused = bool(flag)

    def force_redraw(self):
        if not self._paused:
            self._redraw()

    # ----- helpers -----
    def _props_path(self):
        return os.path.join(self.server_root, "server.properties")  # <<<<<< use server_root

    def _get_server_port(self) -> int:
        try:
            with open(self._props_path(), "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("server-port="):
                        return int(line.split("=", 1)[1].strip())
        except Exception:
            pass
        return 25565

    def _is_port_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self._get_server_port()), timeout=0.25):
                return True
        except Exception:
            return False

    def _running(self) -> bool:
        try:
            if self.controller and self.controller.proc and self.controller.proc.poll() is None:
                return True
        except Exception:
            pass
        return self._is_port_open()

    def _sample_java_rss_mb(self) -> float | None:
        if not psutil or not self.controller or not self.controller.proc or self.controller.proc.poll() is not None:
            return None
        try:
            root = psutil.Process(self.controller.proc.pid)
            rss_vals = [root.memory_info().rss]
            for ch in root.children(recursive=True):
                try:
                    rss_vals.append(ch.memory_info().rss)
                except Exception:
                    pass
            return max(rss_vals) / (1024 * 1024)
        except Exception:
            return None

    def _tick(self):
        if self._paused:
            self.after(REFRESH_MS, self._tick)
            return

        running = self._running()
        if running != self._running_prev:
            self.mem_hist.clear()
            self._running_prev = running

        used_mb, free_pct = None, None
        if running:
            used_mb = self._sample_java_rss_mb()
            if used_mb is not None:
                self._last_good_mb = used_mb
                src = "source: Java RSS (process/children)"
            else:
                used_mb = self._last_good_mb
                src = "source: last good sample"
        else:
            used_mb = max(0.0, self._last_good_mb * 0.85)
            self._last_good_mb = used_mb
            src = "source: server stopped"

        if psutil:
            try:
                vm = psutil.virtual_memory()
                free_pct = 100 - vm.percent
            except Exception:
                free_pct = None

        self.mem_hist.append(float(used_mb))
        self._request_redraw()

        self.lbl_mem.configure(
            text=f"Memory use: {used_mb:.0f} mb ({free_pct:.0f}% free)" if free_pct is not None
                 else f"Memory use: {used_mb:.0f} mb"
        )
        self.lbl_src.configure(text=src)

        self.after(REFRESH_MS, self._tick)

    # ---- configure/debounced redraws ----
    def _on_canvas_configure(self, _evt=None):
        self._request_redraw(delay=100)

    def _request_redraw(self, delay: int = 0):
        if self._paused:
            return
        if self._cfg_job is not None:
            try: self.after_cancel(self._cfg_job)
            except Exception: pass
        if delay <= 0:
            self._redraw()
        else:
            self._cfg_job = self.after(delay, self._redraw)

    def _redraw(self):
        self._cfg_job = None
        c = self.canvas
        c.delete("all")
        data = list(self.mem_hist)
        if not data:
            return

        w = int(c.winfo_width() or 680)
        h = int(c.winfo_height() or 120)
        if w <= 8 or h <= 8:
            return

        # grid
        for y in range(20, h, 20):
            c.create_line(0, h - y, w, h - y, fill="#242424")

        samples = data
        if len(samples) > w:
            step = len(samples) / w
            samples = [samples[int(i * step)] for i in range(w)]

        if AUTO_ZOOM and samples:
            vmin = min(samples); vmax = max(samples)
            vrange = max(1e-6, vmax - vmin)
            if vrange < MIN_RANGE_MB:
                samples = [(s - vmin) * AMPLIFY_SMALL_CHANGES for s in samples]
                vmax = max(samples) or 1.0
            else:
                samples = [s - vmin for s in samples]
                vmax = max(samples) or 1.0
        else:
            vmax = max(samples) or 1.0

        pts = []
        n = len(samples)
        x_step = (w - 1) / (n - 1) if n > 1 else w - 1
        for i, val in enumerate(samples):
            x = int(i * x_step)
            y = h - int((val / (vmax * 1.10)) * (h - 4)) - 2
            y = max(2, min(h - 2, y))
            pts.append((x, y))

        flat = [p for xy in pts for p in xy]
        if len(flat) >= 4:
            c.create_line(*flat, fill="#c42f2f", width=2, smooth=1)
        lx, ly = pts[-1]
        c.create_oval(lx - 2, ly - 2, lx + 2, ly + 2, fill="#c42f2f", outline="")

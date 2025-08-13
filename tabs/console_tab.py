# tabs/console_tab.py
import re
import customtkinter as ctk

class ConsoleTab(ctk.CTkFrame):
    """Buffered console + command entry; trims old lines; color-codes log levels."""
    def __init__(self, master, send_callback):
        super().__init__(master, fg_color="transparent")
        self.send_callback = send_callback

        # Console area
        outer = ctk.CTkFrame(self, fg_color="#333333", corner_radius=10, border_width=1, border_color="#555555")
        outer.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.console = ctk.CTkTextbox(outer, fg_color="black", text_color="white", corner_radius=10, border_width=0)
        self.console.pack(fill="both", expand=True, padx=5, pady=5)
        self.console.configure(state="disabled")

        # Text tags
        self.console.tag_config("LOG_ERROR",    foreground="#ff6b6b")  # red
        self.console.tag_config("LOG_WARN",     foreground="#ffd166")  # amber
        self.console.tag_config("LOG_SUCCESS",  foreground="#8bd17c")  # green
        self.console.tag_config("LOG_INFO",     foreground="#e0e0e0")  # light gray
        self.console.tag_config("LOG_CMD",      foreground="#7bdff6")  # cyan
        self.console.tag_config("LOG_APP",      foreground="#b39ddb")  # purple

        # Command row
        cmd_outer = ctk.CTkFrame(self, fg_color="#333333", corner_radius=10, border_width=1, border_color="#555555")
        cmd_outer.pack(fill="x", padx=8, pady=(4, 8))
        self.cmd_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(cmd_outer, textvariable=self.cmd_var, corner_radius=8)
        self.entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.entry.bind("<Return>", self._on_send)
        self.entry.bind("<KP_Enter>", self._on_send)
        ctk.CTkButton(cmd_outer, text="Send", command=self._on_send_click,
                      fg_color="#555", width=90, corner_radius=8).pack(side="right", padx=5, pady=5)

        # Buffered printing
        self._buffer = []          # pending lines
        self._line_count = 0       # number of lines in widget
        self._max_lines = 1500     # trim target
        self._suspended = False    # pause flushing during window drag

        # Regex helpers
        self._ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")  # strip ANSI if present
        self._re_error = re.compile(r"\b(error|fatal|severe)\b", re.IGNORECASE)
        self._re_warn  = re.compile(r"\b(warn|warning)\b", re.IGNORECASE)
        self._re_done  = re.compile(r"\b(done|started|eula accepted)\b", re.IGNORECASE)
        self._re_mc_l  = re.compile(r"\[.+?/(INFO|WARN|ERROR|DEBUG|TRACE)\]")  # [thread/LEVEL]

        self.after(120, self._flush_loop)

    # ----- public API -----
    def print_line(self, text: str):
        if text is None:
            return
        self._buffer.append(text)

    def set_max_lines(self, n: int):
        self._max_lines = max(200, int(n))

    def set_suspended(self, flag: bool):
        self._suspended = bool(flag)

    # ----- internal -----
    def _tag_for(self, line: str) -> str | None:
        s = self._ansi.sub("", line)

        # Verify lines: green on success, red on problems
        if s.lower().startswith("[verify]"):
            sl = s.lower()
            if "✓" in s or "match" in sl or "ok" in sl:
                return "LOG_SUCCESS"
            if "⚠" in s or "differ" in sl or "could not" in sl or "not running" in sl or "unknown" in sl or "fail" in sl:
                return "LOG_ERROR"
            return "LOG_SUCCESS"

        if s.startswith("> "):  # our echoed commands
            return "LOG_CMD"

        m = self._re_mc_l.search(s)
        if m:
            lvl = m.group(1).upper()
            if lvl == "ERROR":
                return "LOG_ERROR"
            if lvl == "WARN":
                return "LOG_WARN"
            if lvl in ("DEBUG", "TRACE"):
                return "LOG_INFO"

        if self._re_error.search(s):
            return "LOG_ERROR"
        if "unknown or incomplete command" in s.lower():
            return "LOG_WARN"
        if self._re_warn.search(s):
            return "LOG_WARN"
        if self._re_done.search(s):
            return "LOG_SUCCESS"

        if s.startswith(("Working dir:", "Selected server jar:", "Max players set to", "No server jar selected.", "Server root:")):
            return "LOG_APP"

        return None

    def _flush_loop(self):
        if self._buffer and not self._suspended:
            lines = self._buffer
            self._buffer = []

            self.console.configure(state="normal")
            for line in lines:
                tag = self._tag_for(line)
                if tag:
                    self.console.insert("end", line + "\n", tag)
                else:
                    self.console.insert("end", line + "\n")
            self.console.see("end")
            self.console.configure(state="disabled")

            # Track & trim
            self._line_count += len(lines)
            if self._line_count > self._max_lines:
                overflow = self._line_count - self._max_lines
                self.console.configure(state="normal")
                self.console.delete("1.0", f"{overflow + 1}.0")
                self.console.configure(state="disabled")
                self._line_count -= overflow

        self.after(120, self._flush_loop)

    def _on_send(self, _evt=None):
        raw = (self.cmd_var.get() or "").strip()
        if raw:
            try:
                if self.send_callback(raw):
                    self.cmd_var.set("")
            except Exception:
                pass
        return "break"

    def _on_send_click(self):
        self._on_send()

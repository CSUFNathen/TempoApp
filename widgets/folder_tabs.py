# widgets/folder_tabs.py
import customtkinter as ctk
from theme import COLORS

class FolderTabs(ctk.CTkFrame):
    """
    Top-aligned folder-style tabs with content below.
    The selected tab is shown in a darker shade so it's obvious where you are.
    """
    def __init__(self, master, tab_width=110, tab_height=34):
        super().__init__(master, fg_color=COLORS["tab_bg"])
        self._tabs = {}      # name -> frame
        self._buttons = {}   # name -> button
        self._current = None
        self._tab_w = tab_width
        self._tab_h = tab_height

        # Colors (with safe fallbacks if theme doesn't define them)
        self._bg_unselected = COLORS.get("tab_unselected_bg", "#1f1f1f")
        self._bg_hover      = COLORS.get("tab_hover_bg", "#2b2b2b")
        self._bg_selected   = COLORS.get("tab_selected_bg", "#121212")   # darker shade
        self._txt_unselected= COLORS.get("tab_unselected_text", "white")
        self._txt_selected  = COLORS.get("tab_selected_text", "white")
        self._border_color  = COLORS.get("card_border", "#3a3a3a")

        # --- Tab strip (top) ---
        self.bar = ctk.CTkFrame(self, fg_color=COLORS["top_bg"], corner_radius=10)
        self.bar.pack(side="top", fill="x", padx=0, pady=(0, 0))

        self.row = ctk.CTkFrame(self.bar, fg_color=COLORS["top_bg"])
        self.row.pack(side="left", padx=10, pady=8)

        # Thin divider under tabs to feel attached to content
        self.div = ctk.CTkFrame(self, fg_color=self._border_color, height=1, corner_radius=0)
        self.div.pack(side="top", fill="x")

        # --- Content area (below tabs) ---
        self.content = ctk.CTkFrame(self, fg_color=COLORS["tab_bg"], corner_radius=0)
        self.content.pack(side="top", fill="both", expand=True)

    def add_tab(self, name: str, frame: ctk.CTkFrame):
        """Register a tab. The frame should be a child of self.content."""
        self._tabs[name] = frame

        btn = ctk.CTkButton(
            self.row, text=name, width=self._tab_w, height=self._tab_h,
                corner_radius=10, anchor="center", 
            fg_color=self._bg_unselected,
            hover_color=self._bg_hover,
            text_color=self._txt_unselected,
            border_width=1, border_color=self._border_color,
            command=lambda n=name: self.select(n),
        )
        btn.pack(side="left", padx=(0, 6), pady=0)
        self._buttons[name] = btn

        # Make sure the content frame is not already packed
        try:
            frame.pack_forget()
        except Exception:
            pass

    def select(self, name: str):
        if name not in self._tabs:
            return

        # Update button styles so the selected tab looks darker/pressed-in
        for n, b in self._buttons.items():
            if n == name:
                b.configure(
                    fg_color=self._bg_selected,
                    hover_color=self._bg_selected,  # keep solid while selected
                    text_color=self._txt_selected,
                    border_width=2,                 # subtle emphasis
                )
            else:
                b.configure(
                    fg_color=self._bg_unselected,
                    hover_color=self._bg_hover,
                    text_color=self._txt_unselected,
                    border_width=1,
                )

        # Swap content
        for fr in self._tabs.values():
            try:
                fr.pack_forget()
            except Exception:
                pass

        # Content sits under the divider
        self._tabs[name].pack(fill="both", expand=True, padx=(10, 10), pady=(10, 10))
        self._current = name

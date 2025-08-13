# tabs/players_tab.py
import customtkinter as ctk
from theme import COLORS

class PlayersTab(ctk.CTkFrame):
    def __init__(self, master, initial_max_players: int = 20):
        super().__init__(master, fg_color=COLORS["tab_bg"])

        self.max_players = int(initial_max_players)
        self._current_players: list[str] = []

        card = ctk.CTkFrame(
            self, fg_color=COLORS["card_bg"], corner_radius=12,
            border_width=1, border_color=COLORS["card_border"]
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        # Header row: title on the left, "X/Y" on the right
        header_row = ctk.CTkFrame(card, fg_color=COLORS["card_bg"])
        header_row.pack(fill="x", padx=12, pady=(10, 4))

        self.header_lbl = ctk.CTkLabel(header_row, text="Connected Players",
                                       font=("Segoe UI", 14, "bold"))
        self.header_lbl.pack(side="left")

        self.count_lbl = ctk.CTkLabel(header_row, text="", font=("Segoe UI Semibold", 14))
        self.count_lbl.pack(side="right")

        # Table area
        self.table = ctk.CTkScrollableFrame(card, fg_color=COLORS["players_list_bg"], corner_radius=10)
        self.table.pack(fill="both", expand=True, padx=12, pady=8)
        self.table.grid_columnconfigure(0, minsize=40)   # index column
        self.table.grid_columnconfigure(1, weight=1)     # name column

        # Table header
        head = ctk.CTkFrame(self.table, fg_color=COLORS["players_list_bg"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(head, text="#", width=40, anchor="w",
                     font=("Segoe UI Semibold", 12)).pack(side="left", padx=(4, 6))
        ctk.CTkLabel(head, text="Player", anchor="w",
                     font=("Segoe UI Semibold", 12)).pack(side="left")

        self._render([])
        self._update_counter()

    # ---- public API called by app.py ----
    def set_players(self, names: list[str]):
        self._current_players = list(names)
        self._render(self._current_players)
        self._update_counter()

    def set_max_players(self, n: int):
        try:
            self.max_players = int(n)
        except Exception:
            return
        self._update_counter()

    # ---- internal ----
    def _update_counter(self):
        self.count_lbl.configure(text=f"{len(self._current_players)}/{self.max_players}")

    def _render(self, players: list[str]):
        # Clear existing rows (but keep header at grid row 0)
        for w in self.table.winfo_children():
            # don't delete the header frame we added first
            if isinstance(w, ctk.CTkFrame) and any(isinstance(c, ctk.CTkLabel) for c in w.winfo_children()):
                # it's the header if it's at row=0 and columnspan=2; we skip it
                # we can't easily inspect grid_info for columnspan, so just skip the first frame
                header = w
                break
        # remove everything then re-add header
        for child in self.table.winfo_children():
            child.destroy()

        # Recreate header
        head = ctk.CTkFrame(self.table, fg_color=COLORS["players_list_bg"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(head, text="#", width=40, anchor="w",
                     font=("Segoe UI Semibold", 12)).pack(side="left", padx=(4, 6))
        ctk.CTkLabel(head, text="Player", anchor="w",
                     font=("Segoe UI Semibold", 12)).pack(side="left")

        if not players:
            empty = ctk.CTkLabel(self.table, text="No players online.", text_color=COLORS["muted_text"])
            empty.grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 10))
            return

        # One row per player: index + indented name
        for idx, name in enumerate(players, start=1):
            row = ctk.CTkFrame(self.table, fg_color=COLORS["player_row_bg"], corner_radius=8)
            row.grid(row=idx, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

            # index column
            ctk.CTkLabel(row, text=str(idx), width=40, anchor="e",
                         font=("Segoe UI", 12)).grid(row=0, column=0, sticky="e", padx=(8, 6), pady=8)

            # name column (indented)
            name_lbl = ctk.CTkLabel(row, text=name, anchor="w", font=("Segoe UI", 13, "bold"))
            name_lbl.grid(row=0, column=1, sticky="w", padx=(12, 10), pady=8)

            row.grid_columnconfigure(0, minsize=40)
            row.grid_columnconfigure(1, weight=1)

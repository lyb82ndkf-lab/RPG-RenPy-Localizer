from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SplitPaneController:
    def __init__(self, root: tk.Misc, main: tk.PanedWindow, side: tk.PanedWindow | None = None) -> None:
        self.root = root
        self.main = main
        self.side = side
        self._library_collapsed = False

    def toggle_library(self) -> None:
        panes = self.main.panes()
        if len(panes) < 2:
            return
        if self._library_collapsed:
            self.main.paneconfigure(panes[0], width=420)
            self.main.paneconfigure(panes[1], stretch="always")
            self._library_collapsed = False
        else:
            self.main.paneconfigure(panes[0], width=240)
            self.main.paneconfigure(panes[1], stretch="always")
            self._library_collapsed = True
        self.root.update_idletasks()

    def collapse_library_on_load(self) -> None:
        if not self._library_collapsed:
            self.toggle_library()


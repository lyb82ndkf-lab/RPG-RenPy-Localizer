from __future__ import annotations

import tkinter as tk


class DashboardLayoutController:
    def __init__(
        self,
        root: tk.Misc,
        parent: tk.Frame,
        library_container: tk.Frame,
        overview_container: tk.Frame,
        narrow_library_shell: tk.Frame,
        expand_handle: tk.Label,
        collapse_handle: tk.Label,
    ) -> None:
        self.root = root
        self.parent = parent
        self.library_container = library_container
        self.overview_container = overview_container
        self.narrow_library_shell = narrow_library_shell
        self.expand_handle = expand_handle
        self.collapse_handle = collapse_handle
        self.collapsed = False
        self._apply()

    def toggle_library(self, collapse: bool | None = None) -> None:
        self.collapsed = not self.collapsed if collapse is None else collapse
        self._apply()

    def _apply(self) -> None:
        for child in self.parent.winfo_children():
            child.grid_remove()
        if self.collapsed:
            self.parent.grid_columnconfigure(0, weight=0, minsize=54)
            self.parent.grid_columnconfigure(1, weight=9, minsize=540)
            self.narrow_library_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            self.overview_container.grid(row=0, column=1, sticky="nsew")
            self.collapse_handle.place_forget()
        else:
            self.parent.grid_columnconfigure(0, weight=4, minsize=320)
            self.parent.grid_columnconfigure(1, weight=6, minsize=520)
            self.library_container.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
            self.overview_container.grid(row=0, column=1, sticky="nsew")
        self.root.update_idletasks()

    def collapse_on_load(self) -> None:
        self.toggle_library(True)

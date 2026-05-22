from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def configure_app_style(
    root: tk.Misc,
    *,
    panel_bg: str,
    text_main: str,
    text_muted: str,
    accent: str,
) -> None:
    style = ttk.Style(root)
    for candidate in ("vista", "clam", "default"):
        try:
            style.theme_use(candidate)
            break
        except tk.TclError:
            continue

    button_font = ("Microsoft YaHei UI", 10)
    compact_font = ("Microsoft YaHei UI", 9)
    style.configure(".", font=button_font)
    style.configure("TButton", padding=(6, 2), font=button_font)
    style.configure("Primary.TButton", padding=(6, 2), font=button_font)
    style.configure("Tool.TButton", padding=(5, 1), font=compact_font)
    style.configure("TCheckbutton", padding=(1, 1), background=panel_bg, font=button_font)
    style.configure("Compact.TCheckbutton", padding=(0, 0), background=panel_bg, font=compact_font)
    style.configure("TEntry", padding=(3, 2))
    style.configure("TCombobox", padding=(3, 2))
    style.configure("Treeview", rowheight=24, font=button_font)
    style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))

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
    # The Windows native "vista" combobox can lose its top/bottom border on
    # high-DPI Win11 when compact padding is used. "clam" honors explicit
    # border colors and gives stable rendering across DPI scales.
    for candidate in ("clam", "vista", "default"):
        try:
            style.theme_use(candidate)
            break
        except tk.TclError:
            continue

    button_font = ("Microsoft YaHei UI", 8)
    compact_font = ("Microsoft YaHei UI", 7)
    style.configure(".", font=button_font)
    style.configure("TButton", padding=(4, 0), font=button_font)
    style.configure("Primary.TButton", padding=(4, 0), font=button_font)
    style.configure("Tool.TButton", padding=(3, 0), font=compact_font)
    style.configure("TCheckbutton", padding=(0, 0), background=panel_bg, font=button_font)
    style.configure("Compact.TCheckbutton", padding=(0, 0), background=panel_bg, font=compact_font)
    style.configure("TEntry", padding=(2, 0))
    style.configure(
        "TCombobox",
        padding=(6, 3),
        relief="solid",
        borderwidth=1,
        bordercolor="#9aa8ba",
        lightcolor="#d6dfeb",
        darkcolor="#9aa8ba",
        fieldbackground="#ffffff",
        background="#ffffff",
        foreground=text_main,
        arrowcolor=accent,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", "#ffffff"), ("disabled", "#f3f6fa")],
        foreground=[("disabled", text_muted), ("readonly", text_main)],
        bordercolor=[("focus", accent), ("readonly", "#9aa8ba")],
        arrowcolor=[("disabled", text_muted), ("readonly", accent)],
    )
    style.configure("Treeview", rowheight=20, font=button_font)
    style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 8, "bold"))

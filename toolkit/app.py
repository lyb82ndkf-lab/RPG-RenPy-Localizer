from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .detectors import detect_project
from .models import DataRecord, MapRecord, ProjectInfo, SaveSlot, TranslationEntry
from .renpy import RenPyService
from .rpgmaker import RPGMakerService
from .storage import export_translation_pack, import_translation_pack, load_json
from .workspace import LibraryEntry, RecentTask, Workspace


APP_BG = "#eef3f8"
NAV_BG = "#142238"
NAV_ACTIVE = "#244266"
PANEL_BG = "#ffffff"
TEXT_MAIN = "#18253b"
TEXT_MUTED = "#5a6a82"
ACCENT = "#0f6ad9"
SUCCESS = "#1f9d68"
WARN = "#b7791f"
BORDER = "#d6dfeb"


class ToolkitApp:
    def __init__(self, root: tk.Tk, initial_path: str | Path | None = None) -> None:
        self.root = root
        self.root.title("RPG Maker / Ren'Py 本地化工作台")
        self.root.geometry("1500x940")
        self.root.minsize(1280, 780)
        self.root.configure(bg=APP_BG)

        self.workspace = Workspace(self._project_root())
        self.library_entries: list[LibraryEntry] = self.workspace.load_library()
        self.recent_tasks: list[RecentTask] = self.workspace.load_recent_tasks()

        self.project: ProjectInfo | None = None
        self.game_process: subprocess.Popen[bytes] | None = None
        self.translation_entries: list[TranslationEntry] = []
        self.translation_map: dict[str, TranslationEntry] = {}
        self.data_records: list[DataRecord] = []
        self.data_record_map: dict[str, DataRecord] = {}
        self.data_object_map: dict[str, list[DataRecord]] = {}
        self.save_slots: list[SaveSlot] = []
        self.save_payload: dict | None = None
        self.current_save_path: Path | None = None
        self.map_records: list[MapRecord] = []
        self.runtime_state: dict | None = None
        self.runtime_connected = False
        self.selected_data_category = "全部"
        self.selected_data_object_id: str | None = None
        self.selected_record_id: str | None = None

        self.path_var = tk.StringVar()
        self.engine_var = tk.StringVar(value="未加载")
        self.support_var = tk.StringVar(value="等待载入")
        self.run_status_var = tk.StringVar(value="未启动")
        self.translation_status_var = tk.StringVar(value="0 条")
        self.data_status_var = tk.StringVar(value="0 条")
        self.env_status_var = tk.StringVar(value="工具已就绪。选择或拖入 Game.exe 后开始。")
        self.project_name_var = tk.StringVar(value="选择游戏")
        self.project_path_var = tk.StringVar(value="请选择游戏的 Game.exe，或把 Game.exe 拖入窗口。")
        self.filter_var = tk.StringVar()
        self.translation_scope_var = tk.StringVar(value="全部文本")
        self.data_filter_var = tk.StringVar()
        self.save_slot_var = tk.StringVar()
        self.save_gold_var = tk.StringVar(value="0")
        self.save_item_filter_var = tk.StringVar()
        self.save_switch_filter_var = tk.StringVar()
        self.save_variable_filter_var = tk.StringVar()
        self.map_filter_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.translation_detail_var = tk.StringVar(value="选择一条文本后可在右侧编辑译文。")
        self.data_detail_var = tk.StringVar(value="选择一条数据后可在右侧进行修改。")
        self.save_status_var = tk.StringVar(value="尚未读取存档")
        self.map_status_var = tk.StringVar(value="尚未读取地图")
        self.runtime_status_var = tk.StringVar(value="实时桥接未连接")
        self.library_filter_var = tk.StringVar()
        self.library_note_var = tk.StringVar()
        self.library_tags_var = tk.StringVar()
        settings = self.workspace.load_settings()
        self.ai_provider_var = tk.StringVar(value=settings.get("ai_provider", "OpenAI"))
        self.ai_api_key_var = tk.StringVar(value=settings.get("ai_api_keys", {}).get(settings.get("ai_provider", "OpenAI"), settings.get("openai_api_key", "")))
        self.ai_model_var = tk.StringVar(value=settings.get("ai_model", "gpt-5.5"))
        self.ai_status_var = tk.StringVar(value="AI 翻译未开始")
        self.ai_progress_var = tk.DoubleVar(value=0)
        self.player_through_var = tk.BooleanVar(value=False)
        self.lock_hp_var = tk.BooleanVar(value=False)
        self.lock_mp_var = tk.BooleanVar(value=False)
        self.lock_tp_var = tk.BooleanVar(value=False)
        self.hp_value_var = tk.StringVar(value="9999")
        self.mp_value_var = tk.StringVar(value="9999")
        self.tp_value_var = tk.StringVar(value="100")

        self.nav_buttons: dict[str, tk.Button] = {}
        self._drop_callback = None
        self._old_wndproc = None

        self._configure_style()
        self._build_ui()
        self._enable_windows_file_drop()
        self._refresh_library()
        self._refresh_recent_tasks()
        self._show_section("dashboard")

        if initial_path:
            self.root.after(200, lambda: self.load_path(Path(initial_path)))

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        for candidate in ("vista", "clam", "default"):
            try:
                style.theme_use(candidate)
                break
            except tk.TclError:
                continue
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("Primary.TButton", padding=(8, 4), font=("Microsoft YaHei UI", 10, "bold"))

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=APP_BG)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        nav = tk.Frame(shell, bg=NAV_BG, width=250)
        nav.grid(row=0, column=0, sticky="nsw")
        nav.grid_propagate(False)
        self._build_nav(nav)

        main = tk.Frame(shell, bg=APP_BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        header = tk.Frame(main, bg=APP_BG, padx=24, pady=18)
        header.grid(row=0, column=0, sticky="ew")
        self._build_header(header)

        self.content = tk.Frame(main, bg=APP_BG)
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.dashboard_view = self._build_dashboard_view(self.content)
        self.translation_view = self._build_translation_view(self.content)
        self.data_view = self._build_data_view(self.content)
        self.save_view = self._build_save_view(self.content)
        self.map_view = self._build_map_view(self.content)
        self.tools_view = self._build_tools_view(self.content)

    def _build_nav(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent, bg=NAV_BG, padx=18, pady=20)
        top.pack(fill="x")
        tk.Label(top, text="本地化工作台", bg=NAV_BG, fg="white", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        tk.Label(top, text="管理单机游戏项目、翻译文本、编辑数据并保存备份。", bg=NAV_BG, fg="#b4c5df", justify="left", wraplength=200).pack(anchor="w", pady=(8, 0))

        menu = tk.Frame(parent, bg=NAV_BG, padx=12, pady=10)
        menu.pack(fill="x")
        for key, label in [
            ("dashboard", "游戏库"),
            ("translation", "翻译工作台"),
            ("data", "数据编辑器"),
            ("save", "存档修改"),
            ("maps", "地图查看"),
            ("tools", "环境与备份"),
        ]:
            btn = tk.Button(
                menu,
                text=label,
                anchor="w",
                relief="flat",
                bd=0,
                bg=NAV_BG,
                fg="white",
                activebackground=NAV_ACTIVE,
                activeforeground="white",
                font=("Microsoft YaHei UI", 11, "bold"),
                padx=16,
                pady=12,
                command=lambda item=key: self._show_section(item),
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        bottom = tk.Frame(parent, bg=NAV_BG, padx=18, pady=18)
        bottom.pack(side="bottom", fill="x")
        tk.Label(bottom, text="支持引擎", bg=NAV_BG, fg="#9eb4d3", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        tk.Label(bottom, text="RPG Maker MV/MZ\nRen'Py\nRPG Maker XP/VX/VX Ace", bg=NAV_BG, fg="#d7e2f1", justify="left").pack(anchor="w", pady=(8, 0))

    def _build_header(self, parent: tk.Frame) -> None:
        left = tk.Frame(parent, bg=APP_BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, textvariable=self.project_name_var, bg=APP_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 24, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.project_path_var, bg=APP_BG, fg=TEXT_MUTED, justify="left", wraplength=920).pack(anchor="w", pady=(6, 0))

        path_row = tk.Frame(left, bg=APP_BG)
        path_row.pack(fill="x", pady=(10, 0))
        tk.Label(path_row, text="入口路径", bg=APP_BG, fg=TEXT_MUTED).pack(side="left")
        ttk.Entry(path_row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(path_row, text="选择 Game.exe", command=self.select_project).pack(side="left")
        ttk.Button(path_row, text="载入", command=self.load_project).pack(side="left", padx=(8, 0))

        badges = tk.Frame(left, bg=APP_BG)
        badges.pack(anchor="w", pady=(10, 0))
        self._metric_badge(badges, "引擎", self.engine_var).pack(side="left")
        self._metric_badge(badges, "支持", self.support_var).pack(side="left", padx=8)
        self._metric_badge(badges, "运行", self.run_status_var).pack(side="left")

        right = tk.Frame(parent, bg=APP_BG)
        right.pack(side="right")
        ttk.Button(right, text="启动游戏", command=self.launch_current_game).pack(side="left", padx=(8, 0))

    def _metric_badge(self, parent: tk.Misc, title: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(parent, bg="#dbeafe", padx=10, pady=6)
        tk.Label(frame, text=title, bg="#dbeafe", fg=TEXT_MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
        tk.Label(frame, textvariable=variable, bg="#dbeafe", fg=ACCENT, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(8, 0))
        return frame

    def _build_dashboard_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        library = self._create_panel(frame)
        library.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        library.configure(width=460)
        library.grid_propagate(False)
        self._build_library_panel(library)

        overview = self._create_panel(frame)
        overview.grid(row=0, column=1, sticky="nsew")
        self._build_overview_panel(overview)
        return frame

    def _build_library_panel(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="游戏库", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")

        filter_row = tk.Frame(content, bg=PANEL_BG)
        filter_row.pack(fill="x", pady=(14, 10))
        ttk.Entry(filter_row, textvariable=self.library_filter_var).pack(side="left", fill="x", expand=True)
        self.library_filter_var.trace_add("write", lambda *_: self._refresh_library())
        ttk.Button(filter_row, text="加入当前", command=self.add_current_project_to_library).pack(side="left", padx=(8, 0))

        self.library_list = tk.Listbox(content, font=("Microsoft YaHei UI", 10), bd=0, highlightthickness=1, highlightbackground=BORDER, selectbackground=ACCENT, selectforeground="white")
        self.library_list.pack(fill="both", expand=True)
        self.library_list.bind("<<ListboxSelect>>", self._on_library_select)

        meta = tk.Frame(content, bg=PANEL_BG)
        meta.pack(fill="x", pady=(12, 0))
        tk.Label(meta, text="备注", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        ttk.Entry(meta, textvariable=self.library_note_var).pack(fill="x", pady=(4, 8))
        tk.Label(meta, text="标签（逗号分隔）", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        ttk.Entry(meta, textvariable=self.library_tags_var).pack(fill="x", pady=(4, 10))

        actions = tk.Frame(content, bg=PANEL_BG)
        actions.pack(fill="x")
        ttk.Button(actions, text="载入", command=self.load_selected_library_item).pack(side="left")
        ttk.Button(actions, text="保存信息", command=self.save_selected_library_meta).pack(side="left", padx=8)
        ttk.Button(actions, text="启动", command=self.launch_selected_library_item).pack(side="left")

        second = tk.Frame(content, bg=PANEL_BG)
        second.pack(fill="x", pady=(8, 0))
        ttk.Button(second, text="打开目录", command=self.open_selected_library_item).pack(side="left")
        ttk.Button(second, text="移除", command=self.remove_selected_library_item).pack(side="left", padx=8)

    def _build_overview_panel(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=18, pady=18)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="项目总览", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")

        cards = tk.Frame(content, bg=PANEL_BG)
        cards.pack(fill="x", pady=(16, 18))
        cards.grid_columnconfigure((0, 1, 2), weight=1)
        self._overview_metric(cards, 0, "引擎", self.engine_var, "#dbeafe", ACCENT)
        self._overview_metric(cards, 1, "翻译条目", self.translation_status_var, "#dbf5e8", SUCCESS)
        self._overview_metric(cards, 2, "数据条目", self.data_status_var, "#fff1d6", WARN)

        quick = tk.Frame(content, bg=PANEL_BG)
        quick.pack(fill="x")
        ttk.Button(quick, text="提取文本", command=self.extract_texts).pack(side="left")
        ttk.Button(quick, text="刷新数据", command=self.load_data_records).pack(side="left", padx=8)
        ttk.Button(quick, text="连接实时游戏", command=self.refresh_runtime_state).pack(side="left")
        ttk.Button(quick, text="全物品 99", command=self.quick_max_items).pack(side="left")
        ttk.Button(quick, text="启动游戏", command=self.launch_current_game).pack(side="left", padx=8)

        realtime = tk.LabelFrame(content, text="实时控制", bg=PANEL_BG, fg=TEXT_MAIN, padx=12, pady=10)
        realtime.pack(fill="x", pady=(14, 0))
        tk.Label(realtime, text="金币", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ttk.Entry(realtime, textvariable=self.save_gold_var, width=12).grid(row=0, column=1, sticky="w", padx=(8, 8))
        ttk.Button(realtime, text="应用金币", command=self.apply_save_gold).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(realtime, text="穿墙", variable=self.player_through_var, command=self.apply_player_through).grid(row=0, column=3, sticky="w", padx=(16, 0))
        ttk.Button(realtime, text="战斗胜利", command=lambda: self.runtime_battle_result("win")).grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Button(realtime, text="战斗失败", command=lambda: self.runtime_battle_result("lose")).grid(row=0, column=5, sticky="w", padx=(8, 0))
        for column, label, var, lock in ((0, "HP", self.hp_value_var, self.lock_hp_var), (2, "MP", self.mp_value_var, self.lock_mp_var), (4, "TP", self.tp_value_var, self.lock_tp_var)):
            tk.Label(realtime, text=label, bg=PANEL_BG, fg=TEXT_MUTED).grid(row=1, column=column, sticky="w", pady=(10, 0))
            ttk.Entry(realtime, textvariable=var, width=10).grid(row=1, column=column + 1, sticky="w", pady=(10, 0), padx=(8, 0))
            ttk.Checkbutton(realtime, text=f"锁定{label}", variable=lock, command=self.apply_actor_gauge_locks).grid(row=2, column=column, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(realtime, text="应用 HP/MP/TP 到当前角色", command=self.apply_actor_gauges).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        recent_wrap = tk.Frame(content, bg=PANEL_BG)
        recent_wrap.pack(fill="both", expand=True, pady=(18, 0))
        recent_wrap.grid_columnconfigure(0, weight=1)
        recent_wrap.grid_columnconfigure(1, weight=1)
        recent_wrap.grid_rowconfigure(1, weight=1)
        tk.Label(recent_wrap, text="最近任务", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(recent_wrap, text="当前状态", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.recent_task_list = tk.Listbox(recent_wrap, bd=0, highlightthickness=1, highlightbackground=BORDER)
        self.recent_task_list.grid(row=1, column=0, sticky="nsew")
        self.recent_task_list.bind("<Double-Button-1>", self._open_recent_task_project)

        self.status_text = tk.Text(recent_wrap, relief="flat", wrap="word", bg=PANEL_BG, fg=TEXT_MAIN)
        self.status_text.grid(row=1, column=1, sticky="nsew", padx=(16, 0))
        self._set_status_text("请选择 Game.exe 或将 Game.exe 拖入窗口。")

    def _overview_metric(self, parent: tk.Frame, column: int, title: str, variable: tk.StringVar, bg: str, fg: str) -> None:
        card = tk.Frame(parent, bg=bg, padx=14, pady=14)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        tk.Label(card, text=title, bg=bg, fg=TEXT_MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=bg, fg=fg, font=("Microsoft YaHei UI", 14, "bold"), justify="left", wraplength=220).pack(anchor="w", pady=(8, 0))

    def _build_translation_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=5)
        frame.grid_rowconfigure(0, weight=1)
        left = self._create_panel(frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = self._create_panel(frame)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_translation_list(left)
        self._build_translation_editor(right)
        return frame

    def _build_translation_list(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        head = tk.Frame(content, bg=PANEL_BG)
        head.pack(fill="x")
        tk.Label(head, text="翻译工作台", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ttk.Button(head, text="提取文本", command=self.extract_texts).pack(side="left", padx=(12, 0))
        ttk.Button(head, text="翻译选中", command=self.translate_selected_with_ai).pack(side="left", padx=6)
        ttk.Button(head, text="一键翻译全部", command=self.translate_with_ai).pack(side="left")
        ttk.Button(head, text="导出翻译包", command=self.export_pack).pack(side="left", padx=6)
        ttk.Button(head, text="导入翻译包", command=self.import_pack).pack(side="left")
        ttk.Button(head, text="加载翻译到当前游戏", command=self.load_runtime_translation, style="Primary.TButton").pack(side="right")
        ttk.Button(head, text="嵌入游戏", command=self.embed_translation_permanently).pack(side="right", padx=(0, 8))
        self._build_filter_row(content, self.filter_var, self._refresh_translation_tree)

        wrap = tk.Frame(content, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True)
        scope_row = tk.Frame(content, bg=PANEL_BG)
        scope_row.pack(fill="x", pady=(0, 10))
        tk.Label(scope_row, text="翻译范围", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        scope_box = ttk.Combobox(scope_row, textvariable=self.translation_scope_var, values=("仅对白/选项", "数据库名称/说明", "系统/插件文本", "全部文本"), state="readonly")
        scope_box.pack(side="left", padx=(8, 0))
        scope_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_translation_tree())

        columns = ("category", "file", "context", "source", "target")
        self.translation_tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="extended")
        for key, label, width in (("category", "类型", 90), ("file", "文件", 140), ("context", "上下文", 150), ("source", "原文", 320), ("target", "译文", 320)):
            self.translation_tree.heading(key, text=label)
            self.translation_tree.column(key, width=width, stretch=True)
        self._attach_tree_scrollbars(wrap, self.translation_tree)
        self.translation_tree.bind("<<TreeviewSelect>>", self._on_translation_select)
        self._set_translation_notice("请先选择或拖入 Game.exe。")

    def _build_translation_editor(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="译文编辑", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(content, textvariable=self.translation_detail_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=360).pack(fill="x", pady=(10, 14))
        ttk.Entry(content, textvariable=self.target_var).pack(fill="x")
        buttons = tk.Frame(content, bg=PANEL_BG)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="更新当前条目", command=self.update_translation_target, style="Primary.TButton").pack(side="left")
        ttk.Button(buttons, text="复制原文", command=self.copy_source_to_target).pack(side="left", padx=8)
        ttk.Button(buttons, text="清空", command=lambda: self.target_var.set("")).pack(side="left")

        ai = tk.LabelFrame(content, text="AI 翻译设置", bg=PANEL_BG, fg=TEXT_MAIN, padx=10, pady=10)
        ai.pack(fill="x", pady=(18, 0))
        tk.Label(ai, text="供应商", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        provider_box = ttk.Combobox(ai, textvariable=self.ai_provider_var, values=("OpenAI", "DeepSeek"), state="readonly")
        provider_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        provider_box.bind("<<ComboboxSelected>>", self._on_ai_provider_change)
        tk.Label(ai, text="API Key", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(ai, textvariable=self.ai_api_key_var, show="*").grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        tk.Label(ai, text="模型", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.ai_model_box = ttk.Combobox(ai, textvariable=self.ai_model_var, values=self._ai_model_options(), state="normal")
        self.ai_model_box.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(ai, text="保存设置", command=self.save_ai_settings).grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Button(ai, text="一键翻译全部", command=self.translate_with_ai, style="Primary.TButton").grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))
        self.ai_progress = ttk.Progressbar(ai, variable=self.ai_progress_var, maximum=100)
        self.ai_progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Label(ai, textvariable=self.ai_status_var, bg=PANEL_BG, fg=TEXT_MUTED, wraplength=340, justify="left").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ai.grid_columnconfigure(1, weight=1)

    def _build_data_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=2)
        frame.grid_columnconfigure(1, weight=5)
        frame.grid_rowconfigure(0, weight=1)
        left = self._create_panel(frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = self._create_panel(frame)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_data_list(left)
        self._build_data_editor(right)
        return frame

    def _build_data_list(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        head = tk.Frame(content, bg=PANEL_BG)
        head.pack(fill="x")
        tk.Label(head, text="数据编辑器", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ttk.Button(head, text="刷新数据项", command=self.load_data_records).pack(side="left", padx=(12, 0))
        ttk.Button(head, text="保存修改", command=self.save_selected_record, style="Primary.TButton").pack(side="right")
        self._build_filter_row(content, self.data_filter_var, self._refresh_data_tree)

        category_wrap = tk.Frame(content, bg=PANEL_BG)
        category_wrap.pack(fill="x", pady=(0, 10))
        tk.Label(category_wrap, text="分类", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        self.data_category_box = ttk.Combobox(category_wrap, state="readonly", values=("全部",))
        self.data_category_box.set("全部")
        self.data_category_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.data_category_box.bind("<<ComboboxSelected>>", self._on_data_category_change)

        wrap = tk.Frame(content, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True)
        columns = ("object", "count")
        self.data_tree = ttk.Treeview(wrap, columns=columns, show="headings")
        for key, label, width in (("object", "对象", 260), ("count", "字段数", 80)):
            self.data_tree.heading(key, text=label)
            self.data_tree.column(key, width=width, stretch=True)
        self._attach_tree_scrollbars(wrap, self.data_tree)
        self.data_tree.bind("<<TreeviewSelect>>", self._on_data_select)
        self._set_data_notice("请先选择或拖入 Game.exe。")

    def _build_data_editor(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="字段编辑", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(content, textvariable=self.data_detail_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=360).pack(fill="x", pady=(10, 14))
        prop_wrap = tk.Frame(content, bg=PANEL_BG)
        prop_wrap.pack(fill="both", expand=True)
        columns = ("field", "value")
        self.data_property_tree = ttk.Treeview(prop_wrap, columns=columns, show="headings", height=16)
        for key, label, width in (("field", "属性", 220), ("value", "值", 420)):
            self.data_property_tree.heading(key, text=label)
            self.data_property_tree.column(key, width=width, stretch=True)
        self._attach_tree_scrollbars(prop_wrap, self.data_property_tree)
        self.data_property_tree.bind("<<TreeviewSelect>>", self._on_data_property_select)

        edit = tk.Frame(content, bg=PANEL_BG)
        edit.pack(fill="x", pady=(12, 0))
        tk.Label(edit, text="当前字段值", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        self.data_text = tk.Text(edit, height=4, wrap="word", bd=1, relief="solid", highlightthickness=0, font=("Microsoft YaHei UI", 10))
        self.data_text.pack(fill="x", pady=(4, 0))

    def _build_save_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=2)
        frame.grid_columnconfigure(1, weight=5)
        frame.grid_rowconfigure(0, weight=1)
        left = self._create_panel(frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = self._create_panel(frame)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_save_left(left)
        self._build_save_right(right)
        return frame

    def _build_save_left(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="实时修改", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(content, textvariable=self.runtime_status_var, bg=PANEL_BG, fg=ACCENT, justify="left", wraplength=320).pack(fill="x", pady=(8, 0))
        tk.Label(content, textvariable=self.save_status_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=320).pack(fill="x", pady=(8, 12))
        row = tk.Frame(content, bg=PANEL_BG)
        row.pack(fill="x")
        self.save_slot_box = ttk.Combobox(row, textvariable=self.save_slot_var, state="readonly", values=())
        self.save_slot_box.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="刷新", command=self.refresh_save_slots).pack(side="left", padx=(8, 0))
        ttk.Button(content, text="读取当前存档", command=self.load_selected_save, style="Primary.TButton").pack(fill="x", pady=(12, 0))
        ttk.Button(content, text="保存当前存档", command=self.save_current_save).pack(fill="x", pady=(8, 0))
        ttk.Button(content, text="安装实时组件并连接", command=self.install_bridge_and_connect).pack(fill="x", pady=(12, 0))
        ttk.Button(content, text="刷新实时状态", command=self.refresh_runtime_state).pack(fill="x", pady=(8, 0))

        gold = tk.LabelFrame(content, text="常用修改", bg=PANEL_BG, fg=TEXT_MAIN, padx=10, pady=10)
        gold.pack(fill="x", pady=(18, 0))
        tk.Label(gold, text="金币", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ttk.Entry(gold, textvariable=self.save_gold_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(gold, text="应用金币", command=self.apply_save_gold).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(gold, text="999999", command=lambda: self.quick_set_gold(999999)).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))
        ttk.Button(gold, text="全物品/装备 99", command=self.quick_max_items).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(gold, text="穿墙", variable=self.player_through_var, command=self.apply_player_through).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        tk.Label(gold, text="实时模式需要先安装组件并重启游戏。离线存档编辑仍保留为备用。", bg=PANEL_BG, fg=TEXT_MUTED, wraplength=300, justify="left").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        gold.grid_columnconfigure(1, weight=1)

    def _build_save_right(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="存档内容", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        notebook = ttk.Notebook(content)
        notebook.pack(fill="both", expand=True, pady=(12, 0))
        self.save_items_tree = self._save_tab_tree(notebook, "物品/装备", ("kind", "id", "name", "count"), ("类型", "ID", "名称", "数量"), self._on_save_item_edit)
        self.save_actors_tree = self._save_tab_tree(notebook, "角色", ("id", "name", "level", "hp", "mp", "tp"), ("ID", "名称", "等级", "HP", "MP", "TP"), self._on_save_actor_edit)
        self.save_switches_tree = self._save_tab_tree(notebook, "开关", ("id", "name", "value"), ("ID", "名称", "值"), self._on_save_switch_edit)
        self.save_variables_tree = self._save_tab_tree(notebook, "变量", ("id", "name", "value"), ("ID", "名称", "值"), self._on_save_variable_edit)

    def _save_tab_tree(self, notebook: ttk.Notebook, title: str, columns: tuple[str, ...], labels: tuple[str, ...], callback) -> ttk.Treeview:
        frame = tk.Frame(notebook, bg=PANEL_BG, padx=8, pady=8)
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for key, label in zip(columns, labels):
            tree.heading(key, text=label)
            tree.column(key, width=120, stretch=True)
        self._attach_tree_scrollbars(frame, tree)
        tree.bind("<Double-Button-1>", callback)
        return tree

    def _build_map_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        head = self._create_panel(frame)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        row = tk.Frame(head, bg=PANEL_BG, padx=16, pady=16)
        row.pack(fill="x")
        tk.Label(row, text="地图查看", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ttk.Button(row, text="刷新地图", command=self.load_maps).pack(side="left", padx=(12, 0))
        tk.Label(row, textvariable=self.map_status_var, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=(12, 0))
        body = self._create_panel(frame)
        body.grid(row=1, column=0, sticky="nsew")
        content = tk.Frame(body, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        self._build_filter_row(content, self.map_filter_var, self._refresh_map_tree)
        wrap = tk.Frame(content, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True)
        columns = ("id", "name", "display", "size", "tileset", "events", "file")
        self.map_tree = ttk.Treeview(wrap, columns=columns, show="headings")
        for key, label, width in (("id", "ID", 70), ("name", "地图名", 180), ("display", "显示名", 180), ("size", "尺寸", 120), ("tileset", "图块集", 90), ("events", "事件数", 90), ("file", "文件", 120)):
            self.map_tree.heading(key, text=label)
            self.map_tree.column(key, width=width, stretch=True)
        self._attach_tree_scrollbars(wrap, self.map_tree)
        return frame

    def _build_filter_row(self, parent: tk.Frame, variable: tk.StringVar, callback) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(14, 10))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        variable.trace_add("write", lambda *_: callback())
        ttk.Button(row, text="清空筛选", command=lambda: variable.set("")).pack(side="left", padx=(8, 0))

    def _attach_tree_scrollbars(self, parent: tk.Frame, tree: ttk.Treeview) -> None:
        y = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

    def _build_tools_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_rowconfigure(0, weight=1)
        env = self._create_panel(frame)
        env.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        backups = self._create_panel(frame)
        backups.grid(row=0, column=1, sticky="nsew")
        self._build_env_panel(env)
        self._build_backup_panel(backups)
        return frame

    def _build_env_panel(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="环境与打包", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(content, textvariable=self.env_status_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=620).pack(fill="x", pady=(10, 14))
        ttk.Button(content, text="创建本地虚拟环境", command=self.prepare_local_env, style="Primary.TButton").pack(anchor="w")
        ttk.Button(content, text="打开项目目录", command=self.open_project_folder).pack(anchor="w", pady=(10, 0))
        ttk.Button(content, text="打开打包目录", command=self.open_dist_folder).pack(anchor="w", pady=(10, 0))
        ttk.Button(content, text="重新打包 exe", command=self.rebuild_release).pack(anchor="w", pady=(10, 0))
        self.env_console = tk.Text(content, height=18, wrap="word", bg="#0f172a", fg="#dbeafe", relief="flat")
        self.env_console.pack(fill="both", expand=True, pady=(16, 0))
        self.env_console.insert("1.0", "环境操作日志会显示在这里。\n")
        self.env_console.configure(state="disabled")

    def _build_backup_panel(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="备份中心", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        self.backup_list = tk.Listbox(content, bd=0, highlightthickness=1, highlightbackground=BORDER)
        self.backup_list.pack(fill="both", expand=True, pady=(14, 0))
        actions = tk.Frame(content, bg=PANEL_BG)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="刷新备份列表", command=self.refresh_backups).pack(side="left")
        ttk.Button(actions, text="打开备份目录", command=self.open_backup_folder).pack(side="left", padx=8)
        self.refresh_backups()

    def _create_panel(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL_BG, bd=1, relief="solid", highlightthickness=0)

    def _show_section(self, section: str) -> None:
        for key, btn in self.nav_buttons.items():
            btn.configure(bg=NAV_ACTIVE if key == section else NAV_BG)
        active_view = {
            "dashboard": self.dashboard_view,
            "translation": self.translation_view,
            "data": self.data_view,
            "save": self.save_view,
            "maps": self.map_view,
            "tools": self.tools_view,
        }[section]
        active_view.tkraise()
        self.content.update_idletasks()
        if section == "dashboard":
            if self.project:
                self._set_status_text(f"当前项目：{self.project.root}\n可直接切换到翻译工作台或数据编辑器。")
            else:
                self._set_status_text("请先选择 Game.exe，加载后会自动加入游戏库。")
        elif section == "translation":
            if not self.project:
                self._set_status_text("请先加载项目，再进入翻译工作台。")
            elif self._supports_full_editing(self.project):
                if not self.translation_entries:
                    self.extract_texts(silent=True)
                self._set_status_text(f"翻译工作台已打开，当前共有 {len(self.translation_entries)} 条可编辑文本。")
            else:
                self._set_status_text(f"{self.project.engine} 当前仅识别项目与启动入口，完整翻译待后续兼容。")
        elif section == "data":
            if not self.project:
                self._set_status_text("请先加载项目，再进入数据编辑器。")
            elif self._supports_full_editing(self.project):
                if not self.data_records:
                    self.load_data_records(silent=True)
                self._set_status_text(f"数据编辑器已打开，当前共有 {len(self.data_records)} 条可修改数据。")
            else:
                self._set_status_text(f"{self.project.engine} 当前仅识别项目与启动入口，完整数据编辑待后续兼容。")
        elif section == "save":
            if not self.project:
                self._set_status_text("请先加载项目，再进入存档修改。")
            else:
                self.refresh_save_slots(silent=True)
                self._set_status_text("存档修改已打开。请先在游戏内保存一次，再选择 file 存档读取。")
        elif section == "maps":
            if not self.project:
                self._set_status_text("请先加载项目，再查看地图。")
            else:
                self.load_maps(silent=True)
                self._set_status_text(f"地图查看已打开，当前读取到 {len(self.map_records)} 张地图。")
        elif section == "tools":
            self._set_status_text("环境与备份工具已打开。")

    def select_project(self) -> None:
        initial_dir = str(self._initial_game_picker_dir())
        path = filedialog.askopenfilename(
            title="选择或载入游戏 Game.exe",
            initialdir=initial_dir,
            initialfile="Game.exe",
            filetypes=[("游戏启动程序", "Game.exe"), ("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self.load_path(Path(path))

    def _initial_game_picker_dir(self) -> Path:
        raw_path = self.path_var.get().strip()
        if raw_path:
            candidate = Path(raw_path)
            if candidate.is_dir():
                return candidate
            if candidate.parent.exists():
                return candidate.parent
        if self.project and self.project.launcher_path:
            launcher_parent = Path(self.project.launcher_path).parent
            if launcher_parent.exists():
                return launcher_parent
        if self.project and self.project.root.exists():
            return self.project.root
        return Path.home()

    def load_project(self) -> None:
        raw_path = self.path_var.get().strip()
        if not raw_path:
            messagebox.showerror("错误", "请先选择 Game.exe。")
            return
        self.load_path(Path(raw_path))

    def load_path(self, path: Path) -> None:
        try:
            self.project = detect_project(path)
        except Exception as exc:
            messagebox.showerror("无法加载", str(exc))
            return
        if self.project.launcher_path:
            self.path_var.set(str(self.project.launcher_path))
        else:
            self.path_var.set(str(self.project.root))
        self._apply_project_state()
        self._show_section("dashboard")

    def _apply_project_state(self) -> None:
        if not self.project:
            return
        self.project_name_var.set(self.project.root.name)
        self.project_path_var.set(str(self.project.root))
        self.engine_var.set(self.project.engine)
        self.support_var.set(self._support_status_for(self.project))
        self.run_status_var.set("未启动")
        if self._supports_full_editing(self.project):
            self.extract_texts(silent=True)
            self.load_data_records(silent=True)
            self.refresh_save_slots(silent=True)
            self.load_maps(silent=True)
        else:
            self.translation_entries = []
            self.translation_map = {}
            self.data_records = []
            self.data_record_map = {}
            self.data_object_map = {}
            self.save_slots = []
            self.save_payload = None
            self.current_save_path = None
            self.map_records = []
            self.translation_status_var.set("暂不支持")
            self.data_status_var.set("暂不支持")
            self._set_translation_notice(f"{self.project.engine} 已识别，但暂未启用完整翻译。")
            self._set_data_notice(f"{self.project.engine} 已识别，但暂未启用完整数据编辑。")
            self._set_status_text(f"{self.project.engine} 已识别并加入游戏库；完整翻译和数据编辑会在后续扩展。")
        self.refresh_backups()
        self._touch_library_entry(self.project)
        self._append_recent_task("载入项目", self.project.root, self.project.engine)
        self.env_status_var.set(f"项目已加载：{self.project.root}")

    def extract_texts(self, silent: bool = False) -> None:
        if not self.project:
            if not silent:
                messagebox.showerror("错误", "请先加载项目。")
            self._set_translation_notice("请先选择或拖入 Game.exe。")
            return
        if not self._supports_full_editing(self.project):
            self.translation_status_var.set("暂不支持")
            self._set_translation_notice(f"{self.project.engine} 当前仅支持识别、入库和启动。")
            self._set_status_text(f"{self.project.engine} 暂未启用文本提取。")
            if not silent:
                messagebox.showinfo("提示", f"{self.project.engine} 当前仅支持识别、入库和启动。")
            return
        try:
            service = self._get_service()
            self.translation_entries = service.extract_translations()
        except Exception as exc:
            self.translation_entries = []
            self.translation_map = {}
            self.translation_status_var.set("提取失败")
            self._set_translation_notice(f"文本提取失败：{exc}")
            if not silent:
                messagebox.showerror("提取失败", str(exc))
            return
        self.translation_map = {entry.entry_id: entry for entry in self.translation_entries}
        self._load_project_translation_cache(silent=True)
        self.translation_status_var.set(f"{len(self.translation_entries)} 条")
        self._refresh_translation_tree()
        has_suspicious_text = self._has_suspicious_dialogue_text(self.translation_entries)
        if not self.translation_entries:
            self._set_translation_notice("没有提取到文本。可能是加密封包、非标准结构，或当前项目没有可识别文本。")
        elif has_suspicious_text:
            warning = "检测到部分对白疑似乱码。建议先从原版游戏或备份恢复 data 文件，再进行 AI 翻译，避免花费在错误源文本上。"
            self._set_translation_notice(warning)
            self._set_status_text(warning)
        self._append_recent_task("提取文本", self.project.root, self.project.engine)
        if not has_suspicious_text:
            self._set_status_text(f"已提取 {len(self.translation_entries)} 条文本。")
        self._save_project_translation_cache()

    @staticmethod
    def _has_suspicious_dialogue_text(entries: list[TranslationEntry]) -> bool:
        cjk_re = re.compile(r"[\u4e00-\u9fff]")
        kana_re = re.compile(r"[\u3040-\u30ff]")
        suspicious = 0
        checked = 0
        for entry in entries:
            if entry.category != "dialogue" or not entry.source.strip():
                continue
            text = entry.source.strip()
            cjk = len(cjk_re.findall(text))
            kana = len(kana_re.findall(text))
            if cjk + kana < 6:
                continue
            checked += 1
            if cjk > kana * 3 and kana <= 2:
                suspicious += 1
        return checked >= 3 and suspicious / checked >= 0.35

    def export_pack(self) -> None:
        if not self.project or not self.translation_entries:
            messagebox.showerror("错误", "没有可导出的翻译条目。")
            return
        path = filedialog.asksaveasfilename(title="导出翻译包", defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if path:
            export_translation_pack(Path(path), self.project.engine, self.translation_entries)
            self._append_recent_task("导出翻译包", self.project.root, self.project.engine)
            messagebox.showinfo("完成", f"已导出到:\n{path}")

    def import_pack(self) -> None:
        path = filedialog.askopenfilename(title="导入翻译包", filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        loaded = import_translation_pack(Path(path))
        for entry_id, imported in loaded.items():
            current = self.translation_map.get(entry_id)
            if current:
                current.target = imported.target
            else:
                self.translation_map[entry_id] = imported
        self.translation_entries = list(self.translation_map.values())
        self.translation_status_var.set(f"{len(self.translation_entries)} 条")
        self._refresh_translation_tree()
        self._save_project_translation_cache()
        if self.project:
            self._append_recent_task("导入翻译包", self.project.root, self.project.engine)
        messagebox.showinfo("完成", "翻译包已导入。")

    def apply_pack(self) -> None:
        self.embed_translation_permanently()

    def embed_translation_permanently(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        targets = [entry for entry in self.translation_map.values() if entry.target.strip()]
        if not targets:
            messagebox.showinfo("提示", "当前没有填写译文。请先手动编辑、导入翻译包，或使用 AI 一键翻译。")
            return
        service = self._get_service()
        if hasattr(service, "apply_translations"):
            try:
                updated = service.apply_translations(self.translation_map)
            except Exception as exc:
                messagebox.showerror("嵌入失败", str(exc))
                return
        else:
            messagebox.showinfo("提示", "当前引擎暂不支持嵌入翻译。")
            return
        self.refresh_backups()
        self._append_recent_task("嵌入翻译", self.project.root, self.project.engine)
        self._set_status_text(f"已将翻译嵌入游戏数据：{updated} 处。原文件已自动备份。")
        messagebox.showinfo("完成", f"已将翻译嵌入游戏数据：{updated} 处。\n原文件已自动备份。")

    def load_runtime_translation(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        targets = {entry.source: entry.target for entry in self.translation_map.values() if entry.source.strip() and entry.target.strip()}
        if not targets:
            messagebox.showinfo("提示", "当前没有可加载的译文。请先导入翻译包、手动编辑或使用 AI 翻译。")
            return
        try:
            result = self._runtime_request("POST", "/translation", {"enabled": True, "dict": targets})
        except Exception as exc:
            messagebox.showerror("加载失败", f"无法连接当前游戏实时组件：{exc}\n\n请先在“实时修改”页安装实时组件，然后重启游戏。")
            return
        self.runtime_connected = True
        self.runtime_status_var.set(f"实时翻译已加载：{result.get('count', len(targets))} 条")
        self._save_project_translation_cache()
        self._set_status_text("已把翻译表加载到当前运行中的游戏。新的文本绘制会使用译文；已绘制在屏幕上的旧文字可能需要刷新窗口/推进对话。")

    def launch_translated_runtime(self) -> None:
        self.load_runtime_translation()

    def save_ai_settings(self) -> None:
        settings = self.workspace.load_settings()
        provider = self.ai_provider_var.get().strip() or "OpenAI"
        keys = settings.get("ai_api_keys", {})
        if not isinstance(keys, dict):
            keys = {}
        keys[provider] = self.ai_api_key_var.get().strip()
        settings["ai_provider"] = provider
        settings["ai_api_keys"] = keys
        settings["ai_model"] = self.ai_model_var.get().strip() or self._default_ai_model(provider)
        self.workspace.save_settings(settings)
        self.ai_status_var.set("AI 设置已保存。")

    def _on_ai_provider_change(self, _event: object | None = None) -> None:
        provider = self.ai_provider_var.get().strip() or "OpenAI"
        settings = self.workspace.load_settings()
        keys = settings.get("ai_api_keys", {})
        self.ai_api_key_var.set(keys.get(provider, ""))
        if hasattr(self, "ai_model_box"):
            self.ai_model_box.configure(values=self._ai_model_options(provider))
        self.ai_model_var.set(self._default_ai_model(provider))
        self.ai_status_var.set(f"已切换到 {provider}。")

    def _ai_model_options(self, provider: str | None = None) -> tuple[str, ...]:
        provider = provider or self.ai_provider_var.get().strip() or "OpenAI"
        if provider == "DeepSeek":
            return ("deepseek-v4-flash", "deepseek-v4-pro")
        return ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini")

    def _default_ai_model(self, provider: str | None = None) -> str:
        provider = provider or self.ai_provider_var.get().strip() or "OpenAI"
        return "deepseek-v4-flash" if provider == "DeepSeek" else "gpt-5.5"

    def translate_with_ai(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        if not self.translation_entries:
            self.extract_texts(silent=True)
        pending = [entry for entry in self.translation_entries if self._translation_entry_in_scope(entry) and entry.source.strip() and not entry.target.strip()]
        self._start_ai_translation(pending, f"当前范围“{self.translation_scope_var.get()}”没有需要 AI 翻译的空译文。")

    def translate_selected_with_ai(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        pending = [entry for entry in self._selected_translation_entries() if entry.source.strip() and not entry.target.strip()]
        self._start_ai_translation(pending, "选中的文本都已翻译，或没有可翻译原文。")

    def _start_ai_translation(self, pending: list[TranslationEntry], empty_message: str) -> None:
        if not pending:
            messagebox.showinfo("提示", empty_message)
            return
        api_key = self.ai_api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("缺少 API Key", "请先在右侧 AI 翻译设置里输入 API Key。")
            return
        request_entries = self._unique_ai_requests(pending)
        self.save_ai_settings()
        self.ai_progress_var.set(0)
        saved = len(pending) - len(request_entries)
        suffix = f"，已合并 {saved} 条重复原文" if saved else ""
        self.ai_status_var.set(f"准备 AI 翻译：共 {len(pending)} 条，实际请求 {len(request_entries)} 条，每批 100 条{suffix}。")
        self._set_status_text(f"AI 翻译开始：共 {len(pending)} 条，实际请求 {len(request_entries)} 条，每批 100 条{suffix}。")
        provider = self.ai_provider_var.get().strip() or "OpenAI"
        model = self.ai_model_var.get().strip() or self._default_ai_model(provider)
        threading.Thread(target=self._ai_translate_all_worker, args=(pending, request_entries, api_key, model, provider), daemon=True).start()

    @staticmethod
    def _unique_ai_requests(entries: list[TranslationEntry]) -> list[TranslationEntry]:
        unique: list[TranslationEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = entry.source.strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(entry)
        return unique

    def _ai_translate_all_worker(self, pending_entries: list[TranslationEntry], request_entries: list[TranslationEntry], api_key: str, model: str, provider: str) -> None:
        total = len(request_entries)
        translated = 0
        pending_by_source: dict[str, list[TranslationEntry]] = {}
        for entry in pending_entries:
            pending_by_source.setdefault(entry.source.strip(), []).append(entry)
        try:
            for start in range(0, total, 100):
                batch = request_entries[start : start + 100]
                batch_index = start // 100 + 1
                batch_count = (total + 99) // 100
                self.root.after(0, lambda b=batch_index, c=batch_count: self.ai_status_var.set(f"正在翻译第 {b}/{c} 批，每批最多 100 条..."))
                translations = self._request_ai_translations(batch, api_key, model, provider)
                for entry in batch:
                    value = translations.get(entry.entry_id, "").strip()
                    if value:
                        for related in pending_by_source.get(entry.source.strip(), [entry]):
                            if not related.target.strip():
                                related.target = value
                                translated += 1
                progress = min(100, ((start + len(batch)) / total) * 100)
                self._save_project_translation_cache()
                self.root.after(0, lambda value=progress: self.ai_progress_var.set(value))
                self.root.after(0, self._refresh_translation_tree)
        except Exception as exc:
            self.root.after(0, lambda: self.ai_status_var.set(f"AI 翻译失败：{exc}"))
            self.root.after(0, lambda: messagebox.showerror("AI 翻译失败", str(exc)))
            return

        def finish() -> None:
            self.translation_map = {entry.entry_id: entry for entry in self.translation_entries}
            done = sum(1 for item in self.translation_entries if item.target.strip())
            self.translation_status_var.set(f"{len(self.translation_entries)} 条 / 已译 {done}")
            self._refresh_translation_tree()
            self.ai_progress_var.set(100)
            self.ai_status_var.set(f"一键翻译完成：新增 {translated} 条，实际请求 {total} 条，当前已译 {done}/{len(self.translation_entries)}。")
            self._save_project_translation_cache()
            if self.project:
                self._append_recent_task("AI 一键翻译", self.project.root, self.project.engine)
            self._set_status_text("AI 翻译完成，译文已自动保存到当前游戏目录内的工作文件夹。")
        self.root.after(0, finish)

    def _request_ai_translations(self, entries: list[TranslationEntry], api_key: str, model: str, provider: str) -> dict[str, str]:
        key_map = {str(index): entry.entry_id for index, entry in enumerate(entries, start=1)}
        system_prompt = "你是专业游戏本地化译者。将 RPG Maker/Ren'Py 游戏对白翻译成自然简体中文。保留控制符、变量占位符、转义符、颜色代码、换行标记、标点结构和人名格式。只输出 JSON 对象，键必须使用输入里的短编号 id，不要输出解释。"
        user_prompt = json.dumps(
            {
                "task": "translate_to_simplified_chinese",
                "format": {"id": "translated text"},
                "entries": [
                    {
                        "id": str(index),
                        "file": entry.file,
                        "context": entry.context,
                        "type": entry.category,
                        "source": entry.source,
                    }
                    for index, entry in enumerate(entries, start=1)
                ],
            },
            ensure_ascii=False,
        )
        if provider == "DeepSeek":
            raw = self._request_deepseek_translations(api_key, model, system_prompt, user_prompt)
        else:
            raw = self._request_openai_translations(api_key, model, system_prompt, user_prompt)
        return {key_map[key]: value for key, value in raw.items() if key in key_map and str(value).strip()}

    def _request_openai_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, str]:
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = self._extract_response_text(payload)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    def _request_deepseek_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, str]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("无法从 DeepSeek 响应中读取文本。")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _extract_response_text(payload: dict) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
        if chunks:
            return "\n".join(chunks)
        raise RuntimeError("无法从 OpenAI 响应中读取文本。")

    def update_translation_target(self) -> None:
        selection = self.translation_tree.selection()
        if not selection:
            messagebox.showerror("错误", "请先选择一条文本。")
            return
        if selection[0] == "__notice__":
            messagebox.showinfo("提示", "请先选择一条真实文本。")
            return
        entry = self.translation_map[selection[0]]
        entry.target = self.target_var.get()
        self.translation_tree.item(entry.entry_id, values=(self._translation_category_label(entry.category), entry.file, entry.context, entry.source, entry.target))
        self.translation_detail_var.set(f"{entry.file}\n{entry.context}\n原文：{entry.source}")
        self._save_project_translation_cache()

    def copy_source_to_target(self) -> None:
        selection = self.translation_tree.selection()
        if selection and selection[0] != "__notice__":
            self.target_var.set(self.translation_map[selection[0]].source)

    def _selected_translation_entries(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        for item_id in self.translation_tree.selection():
            if item_id == "__notice__":
                continue
            entry = self.translation_map.get(item_id)
            if entry:
                entries.append(entry)
        return entries

    def _project_workspace_dir(self) -> Path | None:
        if not self.project:
            return None
        work_dir = self.project.root / ".rpgrtl_workspace"
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    def _project_translation_cache_path(self) -> Path | None:
        work_dir = self._project_workspace_dir()
        return work_dir / "autosave_translation.json" if work_dir else None

    def _save_project_translation_cache(self) -> None:
        if not self.project or not self.translation_entries:
            return
        path = self._project_translation_cache_path()
        if not path:
            return
        try:
            export_translation_pack(path, self.project.engine, self.translation_entries)
        except Exception as exc:
            self.ai_status_var.set(f"自动保存翻译缓存失败：{exc}")

    def _load_project_translation_cache(self, silent: bool = True) -> None:
        path = self._project_translation_cache_path()
        if not path or not path.exists():
            return
        try:
            loaded = import_translation_pack(path)
        except Exception as exc:
            if not silent:
                messagebox.showerror("读取失败", f"无法读取自动翻译缓存：{exc}")
            return
        applied = 0
        for entry_id, imported in loaded.items():
            current = self.translation_map.get(entry_id)
            if current and imported.target.strip():
                current.target = imported.target
                applied += 1
        if applied:
            self.translation_status_var.set(f"{len(self.translation_entries)} 条 / 已载入缓存 {applied}")
            self.ai_status_var.set(f"已自动载入上次翻译缓存：{applied} 条。")

    def load_data_records(self, silent: bool = False) -> None:
        if not self.project:
            self.data_records = []
            self.data_record_map = {}
            self.data_object_map = {}
            self.data_status_var.set("0 条")
            self._set_data_notice("请先选择或拖入 Game.exe。")
            return
        if not self._supports_full_editing(self.project):
            self.data_records = []
            self.data_record_map = {}
            self.data_object_map = {}
            self.data_status_var.set("暂不支持")
            self._set_data_notice(f"{self.project.engine} 当前仅支持识别、入库和启动。")
            if not silent:
                messagebox.showinfo("提示", f"{self.project.engine} 当前仅支持识别、入库和启动。")
            return
        try:
            service = self._get_service()
            self.data_records = service.list_data_records() if hasattr(service, "list_data_records") else []
        except Exception as exc:
            self.data_records = []
            self.data_record_map = {}
            self.data_status_var.set("读取失败")
            self._set_data_notice(f"数据读取失败：{exc}")
            if not silent:
                messagebox.showerror("读取失败", str(exc))
            return
        self.data_record_map = {record.record_id: record for record in self.data_records}
        self.data_object_map = self._group_data_objects(self.data_records)
        self.data_status_var.set(f"{len(self.data_records)} 条")
        if any(record.category == "Items 物品" for record in self.data_records):
            self.selected_data_category = "Items 物品"
        self._refresh_data_categories()
        self._refresh_data_tree()
        if not self.data_records:
            self._set_data_notice("没有读取到可编辑数据。可能是加密封包、非标准结构，或当前项目没有可识别字段。")
        self._append_recent_task("刷新数据项", self.project.root, self.project.engine)
        self._set_status_text(f"已读取 {len(self.data_records)} 个可编辑数据项。")

    def save_selected_record(self) -> None:
        if not self.project or not self.selected_record_id:
            messagebox.showerror("错误", "请先选择一个可编辑数据项。")
            return
        record = self.data_record_map[self.selected_record_id]
        service = self._get_service()
        new_value = self.data_text.get("1.0", "end-1c")
        try:
            service.update_record(record, new_value)
        except Exception as exc:
            messagebox.showerror("保存失败", f"无法保存该字段：{exc}")
            return
        record.value = new_value
        if hasattr(self, "data_property_tree") and self.data_property_tree.exists(record.record_id):
            self.data_property_tree.item(record.record_id, values=(record.label, record.value))
        self.refresh_backups()
        self._append_recent_task("保存数据修改", self.project.root, self.project.engine)
        messagebox.showinfo("完成", "数据库字段已保存。\n注意：Actors.initialLevel 是新游戏/初始角色等级，不是当前游戏里的实时等级。当前等级请在“实时修改 > 角色”里双击角色修改。")

    def refresh_save_slots(self, silent: bool = False) -> None:
        if not self.project:
            self.save_slots = []
            self.save_slot_box.configure(values=())
            self.save_status_var.set("请先加载项目。")
            return
        try:
            service = self._get_service()
            self.save_slots = service.list_save_slots() if hasattr(service, "list_save_slots") else []
        except Exception as exc:
            self.save_slots = []
            self.save_status_var.set(f"读取存档失败：{exc}")
            if not silent:
                messagebox.showerror("读取存档失败", str(exc))
            return
        values = [f"{slot.slot_id}: {slot.path.name}  {slot.modified_at}" for slot in self.save_slots]
        self.save_slot_box.configure(values=values)
        if values and not self.save_slot_var.get():
            self.save_slot_var.set(values[0])
        if values:
            self.save_status_var.set(f"找到 {len(values)} 个游戏存档。")
        else:
            self.save_status_var.set("未找到 file*.rpgsave/rmmzsave。请先进入游戏保存一次。")

    def install_bridge_and_connect(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        service = self._get_service()
        if not hasattr(service, "install_runtime_bridge"):
            messagebox.showinfo("提示", "当前引擎暂不支持实时桥接。")
            return
        try:
            bridge_path = service.install_runtime_bridge()
        except Exception as exc:
            messagebox.showerror("安装失败", str(exc))
            return
        self.runtime_status_var.set("实时组件已安装。请重启游戏后点击刷新实时状态。")
        self._set_status_text(f"已安装实时组件：{bridge_path}\n请关闭并重新启动游戏，然后点击“刷新实时状态”。")
        messagebox.showinfo("完成", "实时组件已安装并启用。\n请重启游戏，让插件在游戏进程中加载。")

    def refresh_runtime_state(self, silent: bool = False) -> None:
        try:
            self.runtime_state = self._runtime_request("GET", "/state")
            self.runtime_connected = True
        except Exception as exc:
            self.runtime_connected = False
            self.runtime_status_var.set("实时桥接未连接")
            if not silent:
                messagebox.showinfo("未连接", f"无法连接当前游戏实时组件：{exc}\n\n请先安装实时组件并重启游戏。")
            return
        self._populate_runtime_views()
        state_map = self.runtime_state.get("map", {}) if self.runtime_state else {}
        self.runtime_status_var.set(f"已连接实时游戏：金币 {self.runtime_state.get('gold', 0)}，地图 {state_map.get('id', 0)} ({state_map.get('x', 0)}, {state_map.get('y', 0)})")
        self.map_status_var.set(f"当前地图：{state_map.get('id', 0)} {state_map.get('name', '')} ({state_map.get('x', 0)}, {state_map.get('y', 0)})")

    def _runtime_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"http://127.0.0.1:32179{path}"
        data = json.dumps(payload or {}).encode("utf-8") if method == "POST" else None
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(request, timeout=2) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok", True):
            raise RuntimeError(result.get("error", "runtime bridge error"))
        return result

    def _populate_runtime_views(self) -> None:
        if not self.runtime_state:
            return
        for tree in (self.save_items_tree, self.save_actors_tree, self.save_switches_tree, self.save_variables_tree):
            for item in tree.get_children():
                tree.delete(item)
        self.save_gold_var.set(str(self.runtime_state.get("gold", 0)))
        map_info = self.runtime_state.get("map", {})
        self.player_through_var.set(bool(map_info.get("through", False)))
        for kind in ("items", "weapons", "armors"):
            for item in self.runtime_state.get(kind, []):
                self.save_items_tree.insert("", "end", iid=f"{kind}:{item.get('id')}", values=(kind, item.get("id"), item.get("name", ""), item.get("count", 0)))
        for actor in self.runtime_state.get("actors", []):
            self.save_actors_tree.insert("", "end", iid=str(actor.get("id")), values=(actor.get("id"), actor.get("name", ""), actor.get("level", ""), actor.get("hp", ""), actor.get("mp", ""), actor.get("tp", "")))
        for switch in self.runtime_state.get("switches", []):
            self.save_switches_tree.insert("", "end", iid=str(switch.get("id")), values=(switch.get("id"), switch.get("name", ""), switch.get("value", False)))
        for variable in self.runtime_state.get("variables", []):
            self.save_variables_tree.insert("", "end", iid=str(variable.get("id")), values=(variable.get("id"), variable.get("name", ""), variable.get("value", 0)))

    def _runtime_set(self, payload: dict) -> bool:
        try:
            self.runtime_state = self._runtime_request("POST", "/set", payload)
            self.runtime_connected = True
            self._populate_runtime_views()
            return True
        except Exception as exc:
            self.runtime_connected = False
            self.runtime_status_var.set("实时桥接未连接")
            messagebox.showinfo("未连接", f"实时写入失败：{exc}\n\n请确认已安装实时组件并重启游戏。")
            return False

    def load_selected_save(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        if not self.save_slots:
            self.refresh_save_slots()
        slot = self._selected_save_slot()
        if not slot:
            messagebox.showinfo("提示", "没有可读取的游戏存档。请先进游戏保存一次，生成 file1.rmmzsave 之类的文件。")
            return
        try:
            service = self._get_service()
            self.save_payload = service.load_save(slot.path)
            self.current_save_path = slot.path
        except Exception as exc:
            messagebox.showerror("读取存档失败", str(exc))
            return
        self._refresh_save_views()
        self.save_status_var.set(f"已读取：{slot.path.name}")
        self._append_recent_task("读取存档", self.project.root, self.project.engine)
        self._set_status_text(f"已读取存档：{slot.path}\n修改后点击“保存当前存档”，游戏内重新读取该存档即可生效。")

    def save_current_save(self) -> None:
        if not self.project or not self.current_save_path or self.save_payload is None:
            messagebox.showerror("错误", "请先读取一个游戏存档。")
            return
        try:
            service = self._get_service()
            service.save_save(self.current_save_path, self.save_payload)
        except Exception as exc:
            messagebox.showerror("保存存档失败", str(exc))
            return
        self.refresh_backups()
        self.refresh_save_slots(silent=True)
        self.save_status_var.set(f"已保存：{self.current_save_path.name}")
        self._append_recent_task("保存存档修改", self.project.root, self.project.engine)
        messagebox.showinfo("完成", "存档已保存，并已自动备份原存档。请在游戏内重新读取该存档。")

    def apply_save_gold(self) -> None:
        if self._runtime_set({"gold": int(self.save_gold_var.get() or 0)}):
            return
        if not self._ensure_save_loaded():
            return
        service = self._get_service()
        service.set_save_gold(self.save_payload, int(self.save_gold_var.get() or 0))
        self._refresh_save_views()

    def quick_set_gold(self, amount: int) -> None:
        self.save_gold_var.set(str(amount))
        if self._runtime_set({"gold": amount}):
            return
        if not self._ensure_save_loaded():
            return
        self.apply_save_gold()
        self.save_current_save()

    def quick_max_items(self) -> None:
        if self.project and self.project.data_dir:
            payload = {"items": {}, "weapons": {}, "armors": {}}
            for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
                data = load_json(self.project.data_dir / file_name)
                for item in data:
                    if isinstance(item, dict) and item.get("id"):
                        payload[kind][str(item["id"])] = 99
            if self._runtime_set(payload):
                return
        if not self._ensure_save_loaded():
            return
        service = self._get_service()
        for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
            data = load_json(self.project.data_dir / file_name) if self.project and self.project.data_dir else []
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    service.set_save_item(self.save_payload, kind, int(item["id"]), 99)
        self._refresh_save_views()
        self.save_current_save()

    def _on_save_item_edit(self, _event: object | None = None) -> None:
        if not self._ensure_save_loaded():
            return
        selection = self.save_items_tree.selection()
        if not selection:
            return
        kind, item_id = selection[0].split(":")
        old = self.save_items_tree.item(selection[0], "values")[3]
        value = self._ask_value("修改数量", "请输入新的数量：", old)
        if value is None:
            return
        if self._runtime_set({kind: {str(item_id): int(value)}}):
            return
        self._get_service().set_save_item(self.save_payload, kind, int(item_id), int(value))
        self._refresh_save_views()

    def _on_save_actor_edit(self, _event: object | None = None) -> None:
        if not self._ensure_save_loaded():
            return
        selection = self.save_actors_tree.selection()
        if not selection:
            return
        actor_id = int(selection[0])
        values = self.save_actors_tree.item(selection[0], "values")
        old = values[2]
        value = self._ask_value("修改角色", "请输入等级，或输入 level=10,hp=999,mp=999,tp=100：", old)
        if value is None:
            return
        patch = self._parse_actor_patch(value)
        if self._runtime_set({"actors": {str(actor_id): patch}}):
            return
        self._get_service().set_save_actor_level(self.save_payload, actor_id, int(patch.get("level", old)))
        self._refresh_save_views()

    def _current_actor_id(self) -> int | None:
        selection = getattr(self, "save_actors_tree", None).selection() if hasattr(self, "save_actors_tree") else ()
        if selection:
            return int(selection[0])
        if self.runtime_state and self.runtime_state.get("actors"):
            return int(self.runtime_state["actors"][0].get("id"))
        return None

    def apply_actor_gauges(self) -> None:
        actor_id = self._current_actor_id()
        if actor_id is None:
            messagebox.showinfo("提示", "请先连接实时游戏并选择一个角色。")
            return
        patch = {
            "hp": int(self.hp_value_var.get() or 0),
            "mp": int(self.mp_value_var.get() or 0),
            "tp": int(self.tp_value_var.get() or 0),
        }
        self._runtime_set({"actors": {str(actor_id): patch}})

    def apply_actor_gauge_locks(self) -> None:
        actor_id = self._current_actor_id()
        if actor_id is None:
            return
        locks: dict[str, int] = {}
        if self.lock_hp_var.get():
            locks["hp"] = int(self.hp_value_var.get() or 0)
        if self.lock_mp_var.get():
            locks["mp"] = int(self.mp_value_var.get() or 0)
        if self.lock_tp_var.get():
            locks["tp"] = int(self.tp_value_var.get() or 0)
        self._runtime_set({"locks": {str(actor_id): locks}})

    def runtime_battle_result(self, result: str) -> None:
        self._runtime_set({"battle": result})

    def _on_save_switch_edit(self, _event: object | None = None) -> None:
        if not self._ensure_save_loaded():
            return
        selection = self.save_switches_tree.selection()
        if not selection:
            return
        switch_id = int(selection[0])
        old = self.save_switches_tree.item(selection[0], "values")[2]
        value = old not in {"True", "true", "1", "开启"}
        if self._runtime_set({"switches": {str(switch_id): value}}):
            return
        self._get_service().set_save_switch(self.save_payload, switch_id, value)
        self._refresh_save_views()

    def _on_save_variable_edit(self, _event: object | None = None) -> None:
        if not self._ensure_save_loaded():
            return
        selection = self.save_variables_tree.selection()
        if not selection:
            return
        variable_id = int(selection[0])
        old = self.save_variables_tree.item(selection[0], "values")[2]
        value = self._ask_value("修改变量", "请输入新的变量值：", old)
        if value is None:
            return
        if self._runtime_set({"variables": {str(variable_id): self._parse_runtime_value(value)}}):
            return
        self._get_service().set_save_variable(self.save_payload, variable_id, value)
        self._refresh_save_views()

    def apply_player_through(self) -> None:
        self._runtime_set({"player": {"through": self.player_through_var.get()}})

    def load_maps(self, silent: bool = False) -> None:
        if not self.project:
            self.map_records = []
            self._refresh_map_tree()
            return
        self.refresh_runtime_state(silent=True)
        try:
            service = self._get_service()
            self.map_records = service.list_maps() if hasattr(service, "list_maps") else []
        except Exception as exc:
            self.map_records = []
            self.map_status_var.set(f"地图读取失败：{exc}")
            if not silent:
                messagebox.showerror("地图读取失败", str(exc))
            return
        self.map_status_var.set(f"{len(self.map_records)} 张地图")
        if self.runtime_state and self.runtime_state.get("map"):
            current = self.runtime_state["map"]
            self.map_status_var.set(f"{len(self.map_records)} 张地图；当前角色在地图 {current.get('id', 0)} ({current.get('x', 0)}, {current.get('y', 0)})")
        self._refresh_map_tree()

    def _refresh_save_views(self) -> None:
        if self.save_payload is None or not self.project or not self.project.data_dir:
            return
        service = self._get_service()
        summary = service.save_summary(self.save_payload) if hasattr(service, "save_summary") else {}
        self.save_gold_var.set(str(summary.get("gold", 0)))
        self._populate_save_trees()

    def _populate_save_trees(self) -> None:
        for tree in (getattr(self, "save_items_tree", None), getattr(self, "save_actors_tree", None), getattr(self, "save_switches_tree", None), getattr(self, "save_variables_tree", None)):
            if tree:
                for item in tree.get_children():
                    tree.delete(item)
        if self.save_payload is None or not self.project or not self.project.data_dir:
            return
        data_dir = self.project.data_dir
        service = self._get_service()
        party = self.save_payload.get("party", {})
        items = (party.get("_items") or {}) if isinstance(party, dict) else {}
        weapons = (party.get("_weapons") or {}) if isinstance(party, dict) else {}
        armors = (party.get("_armors") or {}) if isinstance(party, dict) else {}
        for kind, container, file_name in (("items", items, "Items.json"), ("weapons", weapons, "Weapons.json"), ("armors", armors, "Armors.json")):
            db = {int(item["id"]): item for item in load_json(data_dir / file_name) if isinstance(item, dict) and item.get("id")}
            for key, value in sorted(container.items(), key=lambda kv: int(kv[0])):
                item = db.get(int(key))
                if not item:
                    continue
                name = item.get("name", "")
                self.save_items_tree.insert("", "end", iid=f"{kind}:{key}", values=(kind, key, name, value))
        actors = self.save_payload.get("actors", {})
        actor_data = actors.get("_data") if isinstance(actors, dict) else None
        if isinstance(actor_data, list):
            for actor_id, actor in enumerate(actor_data):
                if not isinstance(actor, dict) or actor_id == 0:
                    continue
                name = actor.get("_name") or ""
                level = actor.get("_level", 1)
                hp = actor.get("_hp", 0)
                mp = actor.get("_mp", 0)
                self.save_actors_tree.insert("", "end", iid=str(actor_id), values=(actor_id, name, level, hp, mp))
        switches = self.save_payload.get("switches", {})
        switch_data = switches.get("_data") if isinstance(switches, dict) else None
        if isinstance(switch_data, list):
            system = load_json(data_dir / "System.json")
            names = system.get("switches", []) if isinstance(system, dict) else []
            for switch_id, value in enumerate(switch_data):
                if switch_id == 0:
                    continue
                name = names[switch_id] if switch_id < len(names) else ""
                self.save_switches_tree.insert("", "end", iid=str(switch_id), values=(switch_id, name, value))
        variables = self.save_payload.get("variables", {})
        variable_data = variables.get("_data") if isinstance(variables, dict) else None
        if isinstance(variable_data, list):
            system = load_json(data_dir / "System.json")
            names = system.get("variables", []) if isinstance(system, dict) else []
            for variable_id, value in enumerate(variable_data):
                if variable_id == 0:
                    continue
                name = names[variable_id] if variable_id < len(names) else ""
                self.save_variables_tree.insert("", "end", iid=str(variable_id), values=(variable_id, name, value))
        self.save_status_var.set("存档内容已刷新。")

    def _refresh_map_tree(self) -> None:
        tree = getattr(self, "map_tree", None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        needle = self.map_filter_var.get().strip().lower()
        for record in self.map_records:
            haystack = f"{record.map_id} {record.name} {record.display_name} {record.file}".lower()
            if needle and needle not in haystack:
                continue
            tree.insert("", "end", iid=str(record.map_id), values=(record.map_id, record.name, record.display_name, f"{record.width}x{record.height}", record.tileset_id, record.event_count, record.file))

    def _selected_save_slot(self) -> SaveSlot | None:
        selected = self.save_slot_var.get().strip()
        if not selected:
            return self.save_slots[0] if self.save_slots else None
        prefix = selected.split(":", 1)[0].strip()
        if prefix.isdigit():
            slot_id = int(prefix)
            for slot in self.save_slots:
                if slot.slot_id == slot_id:
                    return slot
        return self.save_slots[0] if self.save_slots else None

    def _ensure_save_loaded(self) -> bool:
        if self.save_payload is None:
            messagebox.showinfo("提示", "请先读取一个游戏存档。")
            return False
        return True

    def _ask_value(self, title: str, prompt: str, initial: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text=prompt).pack(padx=16, pady=(16, 8))
        value = tk.StringVar(value=str(initial))
        entry = ttk.Entry(dialog, textvariable=value, width=36)
        entry.pack(padx=16, pady=(0, 16))
        result: list[str | None] = [None]
        def confirm() -> None:
            result[0] = value.get()
            dialog.destroy()
        ttk.Button(dialog, text="确定", command=confirm).pack(pady=(0, 16))
        entry.focus_set()
        self.root.wait_window(dialog)
        return result[0]

    @staticmethod
    def _parse_runtime_value(value: str) -> object:
        text = value.strip()
        if text.lower() in {"true", "false"}:
            return text.lower() == "true"
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return value

    @staticmethod
    def _parse_actor_patch(value: str) -> dict[str, int]:
        text = value.strip()
        if "=" not in text:
            return {"level": int(text)}
        patch: dict[str, int] = {}
        for part in text.split(","):
            if "=" not in part:
                continue
            key, raw = part.split("=", 1)
            key = key.strip().lower()
            if key in {"level", "hp", "mp", "tp"}:
                patch[key] = int(raw.strip())
        return patch or {"level": 1}

    def launch_current_game(self) -> None:
        if not self.project:
            raw_path = self.path_var.get().strip()
            if raw_path:
                self.load_path(Path(raw_path))
            if not self.project:
                messagebox.showerror("错误", "请先选择 Game.exe。")
                return
        launcher = self.project.launcher_path
        if not launcher or not launcher.exists():
            messagebox.showerror("错误", "当前项目未找到可启动的 Game.exe。")
            return
        self.game_process = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
        self.run_status_var.set("已启动")
        self._touch_library_entry(self.project)
        self._append_recent_task("启动游戏", self.project.root, self.project.engine)
        self._set_status_text(f"已启动游戏：{launcher.name}\n项目已自动加入游戏库。")
        self._refresh_library()
        self._show_section("dashboard")

    def prepare_local_env(self) -> None:
        project_root = self._project_root()
        venv_dir = project_root / ".venv"
        self._append_env_log(f"准备环境目录：{venv_dir}")
        try:
            if not venv_dir.exists():
                subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, cwd=project_root)
                self._append_env_log("已创建虚拟环境。")
            else:
                self._append_env_log("检测到现有虚拟环境，跳过创建。")
            python_exe = venv_dir / "Scripts" / "python.exe"
            subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], check=True, cwd=project_root)
            self._append_env_log("已升级虚拟环境中的 pip。")
        except Exception as exc:
            self._append_env_log(f"环境准备失败：{exc}")
            messagebox.showerror("失败", str(exc))

    def rebuild_release(self) -> None:
        script = self._project_root() / "build_release.ps1"
        try:
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True, cwd=self._project_root())
            self._append_env_log("打包完成。")
        except Exception as exc:
            self._append_env_log(f"打包失败：{exc}")
            messagebox.showerror("打包失败", str(exc))

    def add_current_project_to_library(self) -> None:
        if not self.project:
            raw_path = self.path_var.get().strip()
            if raw_path:
                self.load_path(Path(raw_path))
        if self.project:
            self._touch_library_entry(self.project)
            self._set_status_text("当前项目已加入游戏库。")

    def save_selected_library_meta(self) -> None:
        index = self._selected_library_index()
        if index is None:
            return
        entry = self._filtered_library()[index]
        for item in self.library_entries:
            if item.path == entry.path:
                item.note = self.library_note_var.get().strip()
                item.tags = [tag.strip() for tag in self.library_tags_var.get().split(",") if tag.strip()]
                break
        self.workspace.save_library(self.library_entries)
        self._refresh_library()

    def load_selected_library_item(self) -> None:
        index = self._selected_library_index()
        if index is not None:
            self.load_path(Path(self._filtered_library()[index].path))

    def remove_selected_library_item(self) -> None:
        index = self._selected_library_index()
        if index is None:
            return
        target = self._filtered_library()[index]
        self.library_entries = [entry for entry in self.library_entries if entry.path != target.path]
        self.workspace.save_library(self.library_entries)
        self._refresh_library()

    def open_selected_library_item(self) -> None:
        index = self._selected_library_index()
        if index is not None:
            os.startfile(self._filtered_library()[index].path)

    def launch_selected_library_item(self) -> None:
        index = self._selected_library_index()
        if index is not None:
            self._launch_library_entry(self._filtered_library()[index])

    def refresh_backups(self) -> None:
        self.backup_list.delete(0, "end")
        if not self.project:
            self.backup_list.insert("end", "载入项目后可查看 .rpgrtl_backup / .rpgrtl_workspace")
            return
        backup_root = self.project.root / ".rpgrtl_backup"
        workspace_root = self.project.root / ".rpgrtl_workspace"
        inserted = False
        for root in (backup_root, workspace_root):
            if not root.exists():
                continue
            for item in sorted(root.rglob("*")):
                self.backup_list.insert("end", str(item.relative_to(self.project.root)))
                inserted = True
        if not inserted:
            self.backup_list.insert("end", "当前项目暂无备份或工作文件")

    def open_backup_folder(self) -> None:
        if self.project:
            backup_root = self.project.root / ".rpgrtl_backup"
            backup_root.mkdir(parents=True, exist_ok=True)
            os.startfile(backup_root)

    def open_project_folder(self) -> None:
        os.startfile(self.project.root if self.project else self._project_root())

    def open_dist_folder(self) -> None:
        dist = self._project_root() / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        os.startfile(dist)

    def _append_env_log(self, text: str) -> None:
        self.env_console.configure(state="normal")
        self.env_console.insert("end", f"{text}\n")
        self.env_console.see("end")
        self.env_console.configure(state="disabled")

    def _get_service(self) -> RPGMakerService | RenPyService:
        if not self.project:
            raise ValueError("未加载项目。")
        if self.project.engine == "RPG Maker MV/MZ":
            return RPGMakerService(self.project)
        if self.project.engine == "Ren'Py":
            return RenPyService(self.project)
        raise ValueError("当前引擎暂未启用完整编辑。")

    def _supports_full_editing(self, project: ProjectInfo) -> bool:
        return project.engine in {"RPG Maker MV/MZ", "Ren'Py"}

    def _support_status_for(self, project: ProjectInfo) -> str:
        return "完整支持" if self._supports_full_editing(project) else "已识别，待扩展"

    def _refresh_translation_tree(self) -> None:
        needle = self.filter_var.get().strip().lower()
        for item in self.translation_tree.get_children():
            self.translation_tree.delete(item)
        inserted = 0
        for entry in self.translation_entries:
            if not self._translation_entry_in_scope(entry):
                continue
            haystack = f"{entry.file} {entry.context} {entry.source} {entry.target}".lower()
            if not needle or needle in haystack:
                self.translation_tree.insert("", "end", iid=entry.entry_id, values=(self._translation_category_label(entry.category), entry.file, entry.context, entry.source, entry.target))
                inserted += 1
        if not inserted and self.translation_entries:
            self._set_translation_notice("当前筛选条件下没有匹配文本。")

    def _translation_entry_in_scope(self, entry: TranslationEntry) -> bool:
        scope = self.translation_scope_var.get()
        if scope == "仅对白/选项":
            return entry.category == "dialogue"
        if scope == "数据库名称/说明":
            return entry.category == "database"
        if scope == "系统/插件文本":
            return entry.category in {"system", "plugin"}
        return True

    @staticmethod
    def _translation_category_label(category: str) -> str:
        return {
            "dialogue": "对白",
            "event": "事件",
            "database": "数据库",
            "system": "系统",
            "plugin": "插件",
        }.get(category, category or "文本")

    def _refresh_data_tree(self) -> None:
        needle = self.data_filter_var.get().strip().lower()
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        inserted = 0
        for object_id, records in self.data_object_map.items():
            if not records:
                continue
            first = records[0]
            if self.selected_data_category != "全部" and first.category != self.selected_data_category:
                continue
            haystack = f"{first.category} {first.object_label} {first.file} " + " ".join(f"{record.label} {record.value}" for record in records)
            haystack = haystack.lower()
            if not needle or needle in haystack:
                self.data_tree.insert("", "end", iid=object_id, values=(first.object_label or object_id, len(records)))
                inserted += 1
        if not inserted and self.data_records:
            self._set_data_notice("当前筛选条件下没有匹配数据。")

    def _refresh_data_categories(self) -> None:
        categories = ["全部"]
        for record in self.data_records:
            if record.category and record.category not in categories:
                categories.append(record.category)
        if hasattr(self, "data_category_box"):
            self.data_category_box.configure(values=tuple(categories))
            if self.selected_data_category not in categories:
                self.selected_data_category = "Items 物品" if "Items 物品" in categories else "全部"
                self.data_category_box.set(self.selected_data_category)

    def _on_data_category_change(self, _event: object) -> None:
        self.selected_data_category = self.data_category_box.get() or "全部"
        self._refresh_data_tree()
        self._clear_data_properties()
        count = sum(1 for record in self.data_records if self.selected_data_category == "全部" or record.category == self.selected_data_category)
        self.data_status_var.set(f"{count} 条 / {self.selected_data_category}")

    @staticmethod
    def _group_data_objects(records: list[DataRecord]) -> dict[str, list[DataRecord]]:
        grouped: dict[str, list[DataRecord]] = {}
        for record in records:
            key = record.object_id or record.record_id
            grouped.setdefault(key, []).append(record)
        return grouped

    def _clear_data_properties(self) -> None:
        self.selected_data_object_id = None
        self.selected_record_id = None
        if hasattr(self, "data_property_tree"):
            for item in self.data_property_tree.get_children():
                self.data_property_tree.delete(item)
        if hasattr(self, "data_text"):
            self.data_text.delete("1.0", "end")

    def _set_translation_notice(self, message: str) -> None:
        if not hasattr(self, "translation_tree"):
            return
        for item in self.translation_tree.get_children():
            self.translation_tree.delete(item)
        self.translation_tree.insert("", "end", iid="__notice__", values=("提示", "", "", message, ""))

    def _set_data_notice(self, message: str) -> None:
        if not hasattr(self, "data_tree"):
            return
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        self.data_tree.insert("", "end", iid="__notice__", values=(message, ""))

    def _refresh_library(self) -> None:
        self.library_list.delete(0, "end")
        for entry in self._filtered_library():
            tags = f" | {', '.join(entry.tags)}" if entry.tags else ""
            self.library_list.insert("end", f"{entry.name} [{entry.engine}]{tags}")

    def _refresh_recent_tasks(self) -> None:
        if hasattr(self, "recent_task_list"):
            self.recent_task_list.delete(0, "end")
            for task in self.recent_tasks[:20]:
                self.recent_task_list.insert("end", f"{task.created_at} | {task.action} | {task.title}")

    def _append_recent_task(self, action: str, project_path: Path, title: str) -> None:
        self.recent_tasks.insert(0, RecentTask(title=title, project_path=str(project_path), action=action, created_at=datetime.now().isoformat(timespec="seconds")))
        self.workspace.save_recent_tasks(self.recent_tasks)
        self._refresh_recent_tasks()

    def _launch_library_entry(self, entry: LibraryEntry) -> None:
        launcher = Path(entry.launcher_path) if entry.launcher_path else Path(entry.path) / "Game.exe"
        if not launcher.exists():
            messagebox.showerror("错误", "该项目没有找到可启动的 Game.exe。")
            return
        self.game_process = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
        self.run_status_var.set("已启动")
        self._append_recent_task("启动游戏", Path(entry.path), entry.engine)
        self._set_status_text(f"已启动游戏：{launcher.name}")
        self._show_section("dashboard")

    def _filtered_library(self) -> list[LibraryEntry]:
        needle = self.library_filter_var.get().strip().lower()
        entries = sorted(self.library_entries, key=lambda item: item.last_opened_at or item.added_at, reverse=True)
        if not needle:
            return entries
        return [entry for entry in entries if needle in f"{entry.name} {entry.path} {entry.engine} {entry.note} {' '.join(entry.tags or [])}".lower()]

    def _selected_library_index(self) -> int | None:
        selection = self.library_list.curselection()
        if not selection:
            messagebox.showerror("错误", "请先在游戏库中选择一个项目。")
            return None
        return selection[0]

    def _touch_library_entry(self, project: ProjectInfo) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        for entry in self.library_entries:
            if entry.path == str(project.root):
                entry.last_opened_at = now
                entry.engine = project.engine
                if project.launcher_path:
                    entry.launcher_path = str(project.launcher_path)
                self.workspace.save_library(self.library_entries)
                self._refresh_library()
                return
        self.library_entries.append(
            LibraryEntry(
                name=project.root.name,
                path=str(project.root),
                engine=project.engine,
                added_at=now,
                last_opened_at=now,
                launcher_path=str(project.launcher_path) if project.launcher_path else "",
                tags=[],
            )
        )
        self.workspace.save_library(self.library_entries)
        self._refresh_library()

    def _on_translation_select(self, _event: object) -> None:
        selection = self.translation_tree.selection()
        if selection:
            if selection[0] == "__notice__":
                return
            entry = self.translation_map[selection[0]]
            self.target_var.set(entry.target)
            self.translation_detail_var.set(f"{entry.file}\n{entry.context}\n原文：{entry.source}")

    def _on_data_select(self, _event: object) -> None:
        selection = self.data_tree.selection()
        if selection:
            if selection[0] == "__notice__":
                self._clear_data_properties()
                self.selected_record_id = None
                return
            self.selected_data_object_id = selection[0]
            records = self.data_object_map.get(self.selected_data_object_id, [])
            self.selected_record_id = None
            self.data_text.delete("1.0", "end")
            for item in self.data_property_tree.get_children():
                self.data_property_tree.delete(item)
            for record in records:
                self.data_property_tree.insert("", "end", iid=record.record_id, values=(record.label, record.value))
            if records:
                first = records[0]
                self.data_detail_var.set(f"{first.category}\n{first.object_label}\n请选择右侧属性进行编辑。")

    def _on_data_property_select(self, _event: object) -> None:
        selection = self.data_property_tree.selection()
        if not selection:
            return
        self.selected_record_id = selection[0]
        record = self.data_record_map[self.selected_record_id]
        self.data_text.delete("1.0", "end")
        self.data_text.insert("1.0", record.value)
        self.data_detail_var.set(f"{record.object_label}\n{record.location}\n字段：{record.label}")

    def _on_library_select(self, _event: object) -> None:
        selection = self.library_list.curselection()
        if selection:
            entry = self._filtered_library()[selection[0]]
            self.library_note_var.set(entry.note)
            self.library_tags_var.set(", ".join(entry.tags or []))

    def _open_recent_task_project(self, _event: object) -> None:
        selection = self.recent_task_list.curselection()
        if selection:
            task = self.recent_tasks[selection[0]]
            if Path(task.project_path).exists():
                self.path_var.set(task.project_path)

    def _set_status_text(self, text: str) -> None:
        if not hasattr(self, "status_text"):
            return
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", text)
        self.status_text.configure(state="disabled")

    def _enable_windows_file_drop(self) -> None:
        if os.name != "nt":
            return
        self.root.update_idletasks()
        hwnd = self.root.winfo_id()
        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32
        LONG_PTR = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
        user32.SetWindowLongPtrW.restype = LONG_PTR
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = LONG_PTR
        user32.CallWindowProcW.argtypes = [LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = LONG_PTR
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]
        shell32.DragFinish.restype = None
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragAcceptFiles.restype = None
        shell32.DragAcceptFiles(hwnd, True)
        WM_DROPFILES = 0x0233
        GWL_WNDPROC = -4
        WNDPROC = ctypes.WINFUNCTYPE(LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        self._old_wndproc = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)

        def wndproc(window, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                count = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                if count:
                    buf = ctypes.create_unicode_buffer(32768)
                    shell32.DragQueryFileW(wparam, 0, buf, len(buf))
                    self.root.after(0, lambda value=buf.value: self.load_path(Path(value)))
                shell32.DragFinish(wparam)
                return 0
            if self._old_wndproc:
                return user32.CallWindowProcW(self._old_wndproc, window, msg, wparam, lparam)
            return 0

        self._drop_callback = WNDPROC(wndproc)
        callback_ptr = ctypes.cast(self._drop_callback, ctypes.c_void_p).value
        self._old_wndproc = user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, LONG_PTR(callback_ptr))

    def _project_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]


def main(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    ToolkitApp(root, initial_path=initial_path)
    root.mainloop()

from __future__ import annotations

import concurrent.futures
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
import webbrowser
from json import JSONDecodeError
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .detectors import detect_project
from .models import DataRecord, MapDetail, MapRecord, ProjectInfo, SaveSlot, TranslationEntry
from .renpy import RenPyService
from .rpgmaker import RPGMakerService
from .storage import export_translation_pack, import_translation_pack, load_json
from .ui_layout import SplitPaneController
from .ui_theme import configure_app_style
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
TREE_RENDER_LIMIT = 1200
AI_PROVIDER_URLS = {
    "OpenAI": "https://platform.openai.com/api-keys",
    "Xiaomi Token Plan": "https://token-plan-sgp.xiaomimimo.com/",
    "DeepSeek": "https://platform.deepseek.com/api_keys",
    "Doubao": "https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-2-0-mini",
    "GLM": "https://z.ai/manage-apikey/apikey-list",
    "NVIDIA": "https://build.nvidia.com/",
    "百度翻译": "https://fanyi-api.baidu.com/manage/apiKey",
}


class ToolkitApp:
    def __init__(self, root: tk.Tk, initial_path: str | Path | None = None) -> None:
        self.root = root
        self.root.title("RPGRenPyLocalizer")
        try:
            self.root.tk.call("tk", "scaling", 1.08)
        except tk.TclError:
            pass
        self.root.geometry("1360x860")
        self.root.minsize(1180, 740)
        self.root.configure(bg=APP_BG)

        self.workspace = Workspace(self._project_root())
        self.library_entries: list[LibraryEntry] = self.workspace.load_library()
        self.recent_tasks: list[RecentTask] = self.workspace.load_recent_tasks()
        self.translation_memory: dict[str, str] = self.workspace.load_translation_memory()
        self._tm_dirty: bool = False
        self._project_tm_keys: set[str] = set()

        self.project: ProjectInfo | None = None
        self.game_process: subprocess.Popen[bytes] | None = None
        self.translation_entries: list[TranslationEntry] = []
        self.translation_map: dict[str, TranslationEntry] = {}
        self.translation_view_id_map: dict[str, str] = {}
        self.data_records: list[DataRecord] = []
        self.data_record_map: dict[str, DataRecord] = {}
        self.data_object_map: dict[str, list[DataRecord]] = {}
        self.save_slots: list[SaveSlot] = []
        self.save_payload: dict | None = None
        self.current_save_path: Path | None = None
        self.map_records: list[MapRecord] = []
        self.map_detail: MapDetail | None = None
        self.map_tile_size = 16
        self.map_selected_tile: tuple[int, int] | None = None
        self.runtime_state: dict | None = None
        self.runtime_connected = False
        self.runtime_bridge_root = ""
        self.runtime_bridge_pid: int | None = None
        self.current_section = "dashboard"
        self.selected_data_category = "全部"
        self.selected_data_object_id: str | None = None
        self.selected_record_id: str | None = None
        self.selected_data_runtime_item: tuple[str, int] | None = None
        self._auto_backup_after_id: str | None = None
        self._dashboard_split_controller: SplitPaneController | None = None
        self._dashboard_library_collapsed = False

        self.path_var = tk.StringVar()
        self.engine_var = tk.StringVar(value="未加载")
        self.support_var = tk.StringVar(value="等待载入")
        self.run_status_var = tk.StringVar(value="未启动")
        self.translation_status_var = tk.StringVar(value="0 条")
        self.data_status_var = tk.StringVar(value="0 条")
        self.env_status_var = tk.StringVar(value="工具已就绪。选择或拖入游戏 exe 后开始。")
        self.project_name_var = tk.StringVar(value="选择游戏")
        self.project_path_var = tk.StringVar(value="请选择游戏的 exe，或把 exe 拖入窗口。")
        self.filter_var = tk.StringVar()
        self.translation_scope_var = tk.StringVar(value="全部文本")
        self.translation_file_filter_var = tk.StringVar(value="全部文件")
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
        saved_provider = settings.get("ai_provider", "OpenAI")
        self.translation_channel_var = tk.StringVar(value="百度 API 翻译" if saved_provider == "百度翻译" else "AI 翻译")
        self.ai_provider_var = tk.StringVar(value=settings.get("ai_provider", "OpenAI"))
        self.ai_api_key_var = tk.StringVar(value=settings.get("ai_api_keys", {}).get(settings.get("ai_provider", "OpenAI"), settings.get("openai_api_key", "")))
        self.ai_base_url_var = tk.StringVar(value=settings.get("ai_base_urls", {}).get(settings.get("ai_provider", "OpenAI"), settings.get("ai_base_url", "")))
        self.xiaomi_plan_type_var = tk.StringVar(value=settings.get("xiaomi_plan_type", "Token Plan"))
        self.xiaomi_cluster_var = tk.StringVar(value=settings.get("xiaomi_cluster", "新加坡集群"))
        saved_model = settings.get("ai_model", self._default_ai_model(saved_provider))
        if saved_provider != "百度翻译" and saved_model not in self._ai_model_options(saved_provider):
            saved_model = self._default_ai_model(saved_provider)
        self.ai_model_var = tk.StringVar(value=saved_model)
        self.ai_parallel_provider_vars: dict[str, tk.BooleanVar] = {}
        self.ai_status_var = tk.StringVar(value="AI 翻译未开始")
        self.ai_progress_var = tk.DoubleVar(value=0)
        self.baidu_appid_var = tk.StringVar(value=settings.get("baidu_appid", ""))
        self.baidu_secret_var = tk.StringVar(value=settings.get("baidu_secret", ""))
        self.player_through_var = tk.BooleanVar(value=False)
        self.lock_hp_var = tk.BooleanVar(value=False)
        self.lock_mp_var = tk.BooleanVar(value=False)
        self.lock_tp_var = tk.BooleanVar(value=False)
        self.hp_value_var = tk.StringVar(value="9999")
        self.mp_value_var = tk.StringVar(value="9999")
        self.tp_value_var = tk.StringVar(value="100")
        self.game_speed_var = tk.StringVar(value="1")
        self.move_speed_var = tk.StringVar(value="4")
        self.battle_speed_var = tk.StringVar(value="1")
        self.exp_rate_var = tk.StringVar(value="1")
        self.item_amount_var = tk.StringVar(value="99")
        self.auto_save_interval_var = tk.StringVar(value="3")
        self.auto_backup_status_var = tk.StringVar(value="自动备份未开启")
        self.font_size_var = tk.StringVar(value="28")
        self.god_mode_var = tk.BooleanVar(value=False)
        self.auto_battle_var = tk.BooleanVar(value=False)
        self.unlock_cg_var = tk.BooleanVar(value=False)
        self.fps_boost_var = tk.BooleanVar(value=False)

        self.nav_buttons: dict[str, tk.Button] = {}
        self._drop_callback = None
        self._old_wndproc = None
        self._pending_drop_path: str | None = None
        self._filter_after_ids: dict[str, str] = {}
        self._runtime_auto_apply_after_ids: dict[str, str] = {}
        self._runtime_poll_after_id: str | None = None
        self._syncing_runtime_vars = False
        self._renpy_extract_poll_count = 0
        self._renpy_extracting = False
        self._renpy_extract_process: subprocess.Popen[bytes] | None = None
        self._renpy_extract_pid: int | None = None
        self._project_load_token = 0

        self._configure_style()
        self._build_ui()
        self._setup_runtime_auto_apply()
        self._enable_windows_file_drop()
        self.root.after(100, self._flush_pending_drop)
        self.root.after(80, self._refresh_library)
        self._refresh_recent_tasks()
        self._show_section("dashboard")

        if initial_path:
            self.root.after(200, lambda: self.load_path(Path(initial_path)))

    def _configure_style(self) -> None:
        configure_app_style(self.root, panel_bg=PANEL_BG, text_main=TEXT_MAIN, text_muted=TEXT_MUTED, accent=ACCENT)

    def _setup_runtime_auto_apply(self) -> None:
        for var in (
            self.save_gold_var,
            self.hp_value_var,
            self.mp_value_var,
            self.tp_value_var,
            self.game_speed_var,
            self.move_speed_var,
            self.battle_speed_var,
            self.exp_rate_var,
            self.auto_save_interval_var,
            self.font_size_var,
            self.item_amount_var,
        ):
            var.trace_add("write", lambda *_: self._schedule_auto_runtime_apply())

    def _schedule_auto_runtime_apply(self) -> None:
        if self._syncing_runtime_vars:
            return
        key = "runtime_auto_apply"
        after_id = self._runtime_auto_apply_after_ids.get(key)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._runtime_auto_apply_after_ids[key] = self.root.after(450, self._auto_apply_runtime_values)

    def _auto_apply_runtime_values(self) -> None:
        if not self.runtime_connected:
            self.refresh_runtime_state(silent=True)
        if not self.runtime_connected:
            return
        try:
            self._runtime_set(
                {
                    "gold": int(self.save_gold_var.get() or 0),
                    "options": {
                        "gameSpeed": self._clamped_float(self.game_speed_var.get(), 1, 16, 1),
                        "moveSpeed": self._clamped_float(self.move_speed_var.get(), 0, 6, 0),
                        "battleSpeed": self._clamped_float(self.battle_speed_var.get(), 1, 16, 1),
                        "autoSaveInterval": self._clamped_float(self.auto_save_interval_var.get(), 0, 999, 0) * 60,
                        "fontSize": self._clamped_float(self.font_size_var.get(), 0, 96, 0),
                    },
                    "actors": self._build_auto_actor_payload(),
                }
            )
        except Exception:
            pass

    def _build_auto_actor_payload(self) -> dict[str, dict[str, int]]:
        if not self.runtime_state:
            return {}
        actor = None
        selection = getattr(self, "save_actors_tree", None).selection() if hasattr(self, "save_actors_tree") else ()
        if selection:
            try:
                actor_id = int(selection[0])
            except ValueError:
                actor_id = 0
            for item in self.runtime_state.get("actors", []):
                if int(item.get("id") or 0) == actor_id:
                    actor = item
                    break
        if actor is None and self.runtime_state.get("actors"):
            actor = self.runtime_state["actors"][0]
        if not actor:
            return {}
        return {
            str(actor.get("id")): {
                "hp": int(self.hp_value_var.get() or actor.get("hp", 0)),
                "mp": int(self.mp_value_var.get() or actor.get("mp", 0)),
                "tp": int(self.tp_value_var.get() or actor.get("tp", 0)),
            }
        }

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
        self._section_views = {
            "dashboard": self.dashboard_view,
            "translation": self.translation_view,
            "data": self.data_view,
            "save": self.save_view,
            "maps": self.map_view,
            "tools": self.tools_view,
        }

    def _build_nav(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent, bg=NAV_BG, padx=18, pady=20)
        top.pack(fill="x")
        tk.Label(top, text="RPGRenPyLocalizer", bg=NAV_BG, fg="white", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
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
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=0)
        left = tk.Frame(parent, bg=APP_BG)
        left.grid(row=0, column=0, sticky="ew")
        left.grid_columnconfigure(0, weight=1)
        tk.Label(left, textvariable=self.project_name_var, bg=APP_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 24, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.project_path_var, bg=APP_BG, fg=TEXT_MUTED, justify="left", wraplength=920).pack(anchor="w", pady=(6, 0))

        path_row = tk.Frame(left, bg=APP_BG)
        path_row.pack(fill="x", pady=(10, 0))
        path_row.grid_columnconfigure(1, weight=1)
        tk.Label(path_row, text="入口路径", bg=APP_BG, fg=TEXT_MUTED).pack(side="left")
        ttk.Entry(path_row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(path_row, text="选择 exe", command=self.select_project).pack(side="left", padx=(0, 6))
        ttk.Button(path_row, text="载入", command=self.load_project).pack(side="left", padx=(6, 0))
        ttk.Button(path_row, text="启动游戏", command=self.launch_current_game, style="Primary.TButton").pack(side="left", padx=(6, 0))

        badges = tk.Frame(left, bg=APP_BG)
        badges.pack(anchor="w", pady=(10, 0))
        self._metric_badge(badges, "引擎", self.engine_var).pack(side="left")
        self._metric_badge(badges, "支持", self.support_var).pack(side="left", padx=8)
        self._metric_badge(badges, "运行", self.run_status_var).pack(side="left")

        # 全局活动指示条 — 在后台操作(载入/嵌入/翻译)时显示脉冲动画
        activity = tk.Frame(left, bg=APP_BG, height=6)
        activity.pack(fill="x", pady=(6, 0))
        activity.pack_forget()  # 默认隐藏
        self._activity_frame = activity
        self._activity_bar = ttk.Progressbar(
            activity, mode="indeterminate",
            length=200
        )
        self._activity_bar.pack(fill="x")
        self._activity_count = 0  # 嵌套计数，>0 时显示动画

    def _start_activity(self) -> None:
        """启动全局脉冲动画（线程安全）。嵌套计数，多次调用只显示一次。"""
        def _do():
            self._activity_count += 1
            if self._activity_count == 1:
                self._activity_frame.pack(fill="x", pady=(6, 0))
                self._activity_bar.start(15)  # 15ms 间隔脉冲
        self.root.after(0, _do)

    def _stop_activity(self) -> None:
        """停止全局脉冲动画（线程安全）。仅当所有调用者都停止后熄灭。"""
        def _do():
            self._activity_count = max(0, self._activity_count - 1)
            if self._activity_count == 0:
                self._activity_bar.stop()
                self._activity_frame.pack_forget()
        self.root.after(0, _do)

    def _metric_badge(self, parent: tk.Misc, title: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(parent, bg="#dbeafe", padx=10, pady=6)
        tk.Label(frame, text=title, bg="#dbeafe", fg=TEXT_MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
        tk.Label(frame, textvariable=variable, bg="#dbeafe", fg=ACCENT, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(8, 0))
        return frame

    def _build_dashboard_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        pane = ttk.PanedWindow(frame, orient="horizontal")
        pane.grid(row=0, column=0, sticky="nsew")

        library = self._create_panel(pane)
        library.configure(width=420)
        self._build_library_panel(library)
        overview = self._create_panel(pane)
        self._build_overview_panel(overview)
        pane.add(library, weight=1)
        pane.add(overview, weight=4)
        self._dashboard_split_controller = SplitPaneController(self.root, pane)
        return frame

    def _build_library_panel(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        header = tk.Frame(content, bg=PANEL_BG)
        header.pack(fill="x")
        tk.Label(header, text="游戏库", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ttk.Button(header, text="折叠", command=self.toggle_dashboard_library, style="Tool.TButton", width=8).pack(side="right")

        filter_row = tk.Frame(content, bg=PANEL_BG)
        filter_row.pack(fill="x", pady=(14, 10))
        ttk.Entry(filter_row, textvariable=self.library_filter_var).pack(side="left", fill="x", expand=True)
        self.library_filter_var.trace_add("write", lambda *_: self._refresh_library())
        ttk.Button(filter_row, text="加入当前", command=self.add_current_project_to_library, style="Primary.TButton", width=8).pack(side="left", padx=(6, 0))

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
        ttk.Button(actions, text="载入", command=self.load_selected_library_item, style="Primary.TButton", width=6).pack(side="left")
        ttk.Button(actions, text="保存信息", command=self.save_selected_library_meta, width=8).pack(side="left", padx=8)
        ttk.Button(actions, text="启动", command=self.launch_selected_library_item, width=6).pack(side="left", padx=(8, 0))

        second = tk.Frame(content, bg=PANEL_BG)
        second.pack(fill="x", pady=(8, 0))
        ttk.Button(second, text="打开目录", command=self.open_selected_library_item, width=8).pack(side="left", padx=(0, 6))
        ttk.Button(second, text="移除", command=self.remove_selected_library_item, width=6).pack(side="left")

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

        quick = tk.LabelFrame(content, text="主要操作", bg=PANEL_BG, fg=TEXT_MAIN, padx=12, pady=10)
        quick.pack(fill="x")
        quick.grid_columnconfigure((0, 1, 2), weight=1)
        ttk.Button(quick, text="翻译工作台", command=lambda: self._show_section("translation"), style="Primary.TButton").grid(row=0, column=0, sticky="ew")
        ttk.Button(quick, text="数据编辑器", command=lambda: self._show_section("data")).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(quick, text="连接实时游戏", command=self.refresh_runtime_state, style="Primary.TButton").grid(row=0, column=2, sticky="ew")

        realtime = tk.LabelFrame(content, text="实时控制", bg=PANEL_BG, fg=TEXT_MAIN, padx=14, pady=12)
        realtime.pack(fill="x", pady=(14, 0))
        realtime.grid_columnconfigure(0, weight=1, minsize=320)
        realtime.grid_columnconfigure(1, weight=1, minsize=320)

        core = tk.Frame(realtime, bg=PANEL_BG)
        core.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        tk.Label(core, text="基础", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        gold_row = tk.Frame(core, bg=PANEL_BG)
        gold_row.pack(anchor="w", pady=(6, 0))
        tk.Label(gold_row, text="金币", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        ttk.Entry(gold_row, textvariable=self.save_gold_var, width=14).pack(side="left", padx=(8, 0))
        flag_row = tk.Frame(core, bg=PANEL_BG)
        flag_row.pack(anchor="w", pady=(8, 0))
        for label, var, command in (
            ("穿墙", self.player_through_var, self.apply_player_through),
            ("上帝模式", self.god_mode_var, self.apply_runtime_options),
            ("自动战斗", self.auto_battle_var, self.apply_runtime_options),
            ("解锁 CG", self.unlock_cg_var, self.apply_runtime_options),
            ("FPS 优化", self.fps_boost_var, self.apply_runtime_options),
        ):
            ttk.Checkbutton(flag_row, text=label, variable=var, command=command, style="Compact.TCheckbutton").pack(side="left", padx=(0, 10))

        gauges = tk.Frame(realtime, bg=PANEL_BG)
        gauges.grid(row=0, column=1, sticky="nw")
        tk.Label(gauges, text="角色状态", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        gauge_row = tk.Frame(gauges, bg=PANEL_BG)
        gauge_row.pack(anchor="w", pady=(6, 0))
        for label, var, lock in (("HP", self.hp_value_var, self.lock_hp_var), ("MP", self.mp_value_var, self.lock_mp_var), ("TP", self.tp_value_var, self.lock_tp_var)):
            box = tk.Frame(gauge_row, bg=PANEL_BG)
            box.pack(side="left", padx=(0, 14))
            top = tk.Frame(box, bg=PANEL_BG)
            top.pack(anchor="w")
            tk.Label(top, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
            ttk.Entry(top, textvariable=var, width=8).pack(side="left", padx=(6, 0))
            ttk.Checkbutton(box, text=f"锁定{label}", variable=lock, command=self.apply_actor_gauge_locks, style="Compact.TCheckbutton").pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(realtime, bg=PANEL_BG)
        actions.grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
        for label, command, width in (
            ("全物品99", self.quick_max_items, 10),
            ("战斗胜利", lambda: self.runtime_battle_result("win"), 10),
            ("战斗失败", lambda: self.runtime_battle_result("lose"), 10),
            ("逃跑", lambda: self.runtime_battle_result("escape"), 8),
            ("鼠标瞬移", self.teleport_to_mouse, 10),
        ):
            ttk.Button(actions, text=label, command=command, style="Tool.TButton", width=width).pack(side="left", padx=(0, 8))

        tuning = tk.Frame(realtime, bg=PANEL_BG)
        tuning.grid(row=2, column=0, sticky="nw", pady=(12, 0), padx=(0, 16))
        tk.Label(tuning, text="倍率", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        for label, var in (("游戏", self.game_speed_var), ("移动", self.move_speed_var), ("战斗", self.battle_speed_var), ("经验", self.exp_rate_var)):
            box = tk.Frame(tuning, bg=PANEL_BG)
            box.pack(side="left", padx=(10, 0))
            tk.Label(box, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
            ttk.Entry(box, textvariable=var, width=5).pack(side="left", padx=(4, 0))

        utility = tk.Frame(realtime, bg=PANEL_BG)
        utility.grid(row=2, column=1, sticky="nw", pady=(12, 0))
        tk.Label(utility, text="实用", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        for label, var in (("自动备份", self.auto_save_interval_var), ("字体", self.font_size_var)):
            box = tk.Frame(utility, bg=PANEL_BG)
            box.pack(side="left", padx=(10, 0))
            tk.Label(box, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
            ttk.Entry(box, textvariable=var, width=5).pack(side="left", padx=(4, 0))
        ttk.Button(utility, text="经验倍率到全队", command=self.apply_exp_rate_to_party, style="Tool.TButton", width=14).pack(side="left", padx=(10, 0))

        recent_wrap = tk.Frame(content, bg=PANEL_BG)
        recent_wrap.pack(fill="both", expand=True, pady=(18, 0))
        recent_wrap.grid_columnconfigure(0, weight=1)
        recent_wrap.grid_columnconfigure(1, weight=1)
        recent_wrap.grid_rowconfigure(1, weight=1)
        tk.Label(recent_wrap, text="最近任务", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(recent_wrap, text="当前状态", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.recent_task_list = tk.Listbox(recent_wrap, bd=0, highlightthickness=1, highlightbackground=BORDER)
        self.recent_task_list.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.recent_task_list.bind("<Double-Button-1>", self._open_recent_task_project)

        self.status_text = tk.Text(recent_wrap, relief="flat", wrap="word", bg=PANEL_BG, fg=TEXT_MAIN)
        self.status_text.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self._set_status_text("请选择 exe 或将 exe 拖入窗口。")

    def _overview_metric(self, parent: tk.Frame, column: int, title: str, variable: tk.StringVar, bg: str, fg: str) -> None:
        card = tk.Frame(parent, bg=bg, padx=14, pady=14)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        tk.Label(card, text=title, bg=bg, fg=TEXT_MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=bg, fg=fg, font=("Microsoft YaHei UI", 14, "bold"), justify="left", wraplength=220).pack(anchor="w", pady=(8, 0))

    def _build_translation_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
        frame.grid_columnconfigure(0, weight=6)
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
        ttk.Button(head, text="提取文本", command=self.extract_texts).pack(side="left", padx=(6, 0))
        ttk.Button(head, text="翻译选中", command=self.translate_selected_with_ai).pack(side="left", padx=(6, 0))
        ttk.Button(head, text="一键翻译全部", command=self.translate_with_ai).pack(side="left", padx=(6, 0))
        ttk.Button(head, text="导出翻译包", command=self.export_pack).pack(side="left", padx=(6, 0))
        ttk.Button(head, text="导入翻译包", command=self.import_pack).pack(side="left", padx=(6, 0))
        ttk.Button(head, text="加载翻译到当前游戏", command=self.load_runtime_translation, style="Primary.TButton").pack(side="right", padx=(0, 6))
        self.embed_button = ttk.Button(head, text="嵌入游戏", command=self.embed_translation_permanently, style="Primary.TButton")
        self.embed_button.pack(side="right", padx=(0, 6))
        self._build_filter_row(content, self.filter_var, self._refresh_translation_tree)

        wrap = tk.Frame(content, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True)
        scope_row = tk.Frame(content, bg=PANEL_BG)
        scope_row.pack(fill="x", pady=(0, 10))
        tk.Label(scope_row, text="翻译范围", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        scope_box = ttk.Combobox(scope_row, textvariable=self.translation_scope_var, values=("仅对白/选项", "数据库名称/说明", "系统/插件文本", "全部文本"), state="readonly")
        scope_box.pack(side="left", padx=(8, 0))
        scope_box.bind("<<ComboboxSelected>>", self._on_translation_scope_change)
        tk.Label(scope_row, text="文件", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=(18, 0))
        self.translation_file_box = ttk.Combobox(scope_row, textvariable=self.translation_file_filter_var, values=("全部文件",), state="readonly", width=24)
        self.translation_file_box.pack(side="left", padx=(8, 0))
        self.translation_file_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_translation_tree())
        ttk.Button(scope_row, text="全选当前筛选", command=self.select_visible_translations).pack(side="left", padx=(6, 0))

        columns = ("category", "file", "context", "source", "target")
        self.translation_tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="extended")
        for key, label, width in (("category", "类型", 78), ("file", "文件", 120), ("context", "上下文", 135), ("source", "原文", 360), ("target", "译文", 360)):
            self.translation_tree.heading(key, text=label)
            self.translation_tree.column(key, width=width, stretch=True)
        self._attach_tree_scrollbars(wrap, self.translation_tree)
        self.translation_tree.bind("<<TreeviewSelect>>", self._on_translation_select)
        self._set_translation_notice("请先选择或拖入游戏 exe。")

    def _build_translation_editor(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=PANEL_BG, padx=16, pady=16)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="译文编辑", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(content, textvariable=self.translation_detail_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=480).pack(fill="x", pady=(10, 14))
        tk.Label(content, text="当前译文", bg=PANEL_BG, fg=TEXT_MUTED).pack(anchor="w")
        target_wrap = tk.Frame(content, bg=PANEL_BG)
        target_wrap.pack(fill="both", expand=True, pady=(4, 0))
        self.target_text = tk.Text(target_wrap, height=8, wrap="word", bd=1, relief="solid", highlightthickness=0, font=("Microsoft YaHei UI", 11), undo=True)
        target_scroll = ttk.Scrollbar(target_wrap, orient="vertical", command=self.target_text.yview)
        self.target_text.configure(yscrollcommand=target_scroll.set)
        self.target_text.grid(row=0, column=0, sticky="nsew")
        target_scroll.grid(row=0, column=1, sticky="ns")
        target_wrap.grid_rowconfigure(0, weight=1)
        target_wrap.grid_columnconfigure(0, weight=1)
        buttons = tk.Frame(content, bg=PANEL_BG)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="更新当前条目", command=self.update_translation_target, style="Primary.TButton").pack(side="left")
        ttk.Button(buttons, text="复制原文", command=self.copy_source_to_target).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="清空", command=self._clear_target_editor).pack(side="left", padx=(6, 0))

        ai = tk.LabelFrame(content, text="翻译服务", bg=PANEL_BG, fg=TEXT_MAIN, padx=10, pady=10)
        ai.pack(fill="x", pady=(18, 0))
        ai.grid_columnconfigure(1, weight=1)
        tk.Label(ai, text="翻译渠道", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        channel_box = ttk.Combobox(ai, textvariable=self.translation_channel_var, values=("AI 翻译", "百度 API 翻译"), state="readonly", width=18)
        channel_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        channel_box.bind("<<ComboboxSelected>>", self._on_translation_channel_change)

        self.ai_settings_frame = tk.Frame(ai, bg=PANEL_BG)
        self.ai_settings_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.ai_settings_frame.grid_columnconfigure(1, weight=1)
        tk.Label(self.ai_settings_frame, text="AI 厂商", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        provider_box = ttk.Combobox(self.ai_settings_frame, textvariable=self.ai_provider_var, values=("OpenAI", "Xiaomi Token Plan", "DeepSeek", "Doubao", "GLM", "NVIDIA"), state="readonly", width=20)
        provider_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        provider_box.bind("<<ComboboxSelected>>", self._on_ai_provider_change)
        self.ai_base_url_label = tk.Label(self.ai_settings_frame, text="Base URL", bg=PANEL_BG, fg=TEXT_MUTED)
        self.ai_base_url_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.ai_base_url_entry = ttk.Entry(self.ai_settings_frame, textvariable=self.ai_base_url_var)
        self.ai_base_url_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.xiaomi_plan_label = tk.Label(self.ai_settings_frame, text="小米类型", bg=PANEL_BG, fg=TEXT_MUTED)
        self.xiaomi_plan_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.xiaomi_plan_box = ttk.Combobox(self.ai_settings_frame, textvariable=self.xiaomi_plan_type_var, values=("Token Plan", "普通 API Key"), state="readonly", width=18)
        self.xiaomi_plan_box.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.xiaomi_plan_box.bind("<<ComboboxSelected>>", self._on_xiaomi_cluster_change)
        self.xiaomi_cluster_label = tk.Label(self.ai_settings_frame, text="小米集群", bg=PANEL_BG, fg=TEXT_MUTED)
        self.xiaomi_cluster_label.grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.xiaomi_cluster_box = ttk.Combobox(self.ai_settings_frame, textvariable=self.xiaomi_cluster_var, values=("中国集群", "新加坡集群", "欧洲集群"), state="readonly", width=18)
        self.xiaomi_cluster_box.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.xiaomi_cluster_box.bind("<<ComboboxSelected>>", self._on_xiaomi_cluster_change)
        self.ai_api_key_label = tk.Label(self.ai_settings_frame, text="API Key", bg=PANEL_BG, fg=TEXT_MUTED)
        self.ai_api_key_label.grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self.ai_settings_frame, textvariable=self.ai_api_key_var, show="*").grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.ai_model_box = ttk.Combobox(self.ai_settings_frame, textvariable=self.ai_model_var, values=self._ai_model_options(), state="normal", width=24)
        self.ai_model_label = tk.Label(self.ai_settings_frame, text="模型", bg=PANEL_BG, fg=TEXT_MUTED)
        self.ai_model_label.grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.ai_model_box.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        tk.Label(self.ai_settings_frame, text="并行厂商", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=6, column=0, sticky="nw", pady=(8, 0))
        self.ai_parallel_frame = tk.Frame(self.ai_settings_frame, bg=PANEL_BG)
        self.ai_parallel_frame.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.ai_parallel_hint_var = tk.StringVar(value="")
        self.ai_parallel_hint = tk.Label(self.ai_settings_frame, textvariable=self.ai_parallel_hint_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=360)
        self.ai_parallel_hint.grid(row=7, column=1, sticky="ew", padx=(8, 0))
        self._refresh_parallel_provider_checks()

        self.baidu_settings_frame = tk.Frame(ai, bg=PANEL_BG)
        self.baidu_settings_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.baidu_settings_frame.grid_columnconfigure(1, weight=1)
        tk.Label(self.baidu_settings_frame, text="百度 AppID", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.baidu_settings_frame, textvariable=self.baidu_appid_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        tk.Label(self.baidu_settings_frame, text="百度 Secret", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self.baidu_settings_frame, textvariable=self.baidu_secret_var, show="*").grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        action_row = tk.Frame(ai, bg=PANEL_BG)
        action_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        action_row.grid_columnconfigure((0, 1), weight=1)
        self.ai_provider_link = ttk.Button(action_row, text="打开 API 页面", command=self.open_ai_provider_page)
        self.ai_provider_link.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(action_row, text="保存设置", command=self.save_ai_settings).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(ai, text="一键翻译全部", command=self.translate_with_ai, style="Primary.TButton").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.ai_progress = ttk.Progressbar(ai, variable=self.ai_progress_var, maximum=100)
        self.ai_progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Label(ai, textvariable=self.ai_status_var, bg=PANEL_BG, fg=TEXT_MUTED, wraplength=340, justify="left").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._refresh_translation_channel_ui()
        self._refresh_ai_base_url_visibility(self.ai_provider_var.get().strip() or "OpenAI")

    def _build_data_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
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
        columns = ("object", "count", "owned")
        self.data_tree = ttk.Treeview(wrap, columns=columns, show="headings")
        for key, label, width in (("object", "对象", 260), ("count", "字段数", 72), ("owned", "持有", 72)):
            self.data_tree.heading(key, text=label)
            self.data_tree.column(key, width=width, stretch=(key == "object"))
        self._attach_tree_scrollbars(wrap, self.data_tree)
        self.data_tree.bind("<<TreeviewSelect>>", self._on_data_select)
        self._set_data_notice("请先选择或拖入游戏 exe。")

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
        runtime_row = tk.Frame(content, bg=PANEL_BG)
        runtime_row.pack(fill="x", pady=(10, 0))
        tk.Label(runtime_row, text="当前持有数量", bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
        self.data_runtime_count_var = tk.StringVar(value="")
        ttk.Entry(runtime_row, textvariable=self.data_runtime_count_var, width=10).pack(side="left", padx=(8, 6))
        ttk.Button(runtime_row, text="应用到当前游戏", command=self.apply_data_runtime_item_count, style="Tool.TButton").pack(side="left")

    def _build_save_view(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=APP_BG)
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
        ttk.Button(content, text="保存当前存档", command=self.save_current_save, style="Primary.TButton").pack(fill="x", pady=(8, 0))
        backup_row = tk.Frame(content, bg=PANEL_BG)
        backup_row.pack(fill="x", pady=(8, 0))
        ttk.Button(backup_row, text="开启自动备份", command=self.toggle_auto_backup, style="Primary.TButton").pack(side="left", fill="x", expand=True)
        ttk.Button(backup_row, text="立即备份", command=self.create_manual_save_backup).pack(side="left", padx=(8, 0))
        tk.Label(content, textvariable=self.auto_backup_status_var, bg=PANEL_BG, fg=TEXT_MUTED, justify="left", wraplength=320).pack(fill="x", pady=(6, 0))
        ttk.Button(content, text="安装实时组件并连接", command=self.install_bridge_and_connect, style="Primary.TButton").pack(fill="x", pady=(12, 0))
        ttk.Button(content, text="刷新实时状态", command=self.refresh_runtime_state).pack(fill="x", pady=(8, 0))

        gold = tk.LabelFrame(content, text="常用修改", bg=PANEL_BG, fg=TEXT_MAIN, padx=10, pady=10)
        gold.pack(fill="x", pady=(18, 0))
        tk.Label(gold, text="金币", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ttk.Entry(gold, textvariable=self.save_gold_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(gold, text="999999", command=lambda: self.quick_set_gold(999999)).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        tk.Label(gold, text="批量物品数量", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(gold, textvariable=self.item_amount_var).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(gold, text="全物品/装备", command=self.quick_max_items).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(gold, text="穿墙", variable=self.player_through_var, command=self.apply_player_through).grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(gold, text="上帝模式", variable=self.god_mode_var, command=self.apply_runtime_options).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Checkbutton(gold, text="自动战斗", variable=self.auto_battle_var, command=self.apply_runtime_options).grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(gold, text="解锁 CG", variable=self.unlock_cg_var, command=self.apply_runtime_options).grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(gold, text="战斗胜利", command=lambda: self.runtime_battle_result("win")).grid(row=6, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(gold, text="逃跑", command=lambda: self.runtime_battle_result("escape")).grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        tk.Label(gold, text="游戏/战斗/移动倍率", bg=PANEL_BG, fg=TEXT_MUTED).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        speed_row = tk.Frame(gold, bg=PANEL_BG)
        speed_row.grid(row=8, column=0, columnspan=2, sticky="ew")
        for label, var in (("游戏", self.game_speed_var), ("移动", self.move_speed_var), ("战斗", self.battle_speed_var)):
            tk.Label(speed_row, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
            ttk.Entry(speed_row, textvariable=var, width=4).pack(side="left", padx=(4, 8))
        utility_row = tk.Frame(gold, bg=PANEL_BG)
        utility_row.grid(row=10, column=0, columnspan=2, sticky="ew")
        for label, var in (("经验", self.exp_rate_var), ("自动保存", self.auto_save_interval_var), ("字体", self.font_size_var)):
            tk.Label(utility_row, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left")
            ttk.Entry(utility_row, textvariable=var, width=5).pack(side="left", padx=(4, 8))
        ttk.Button(gold, text="经验倍率到全队", command=self.apply_exp_rate_to_party).grid(row=11, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        tk.Label(gold, text="修改金币、倍率、字体等数值后会自动应用；物品数量请在右侧列表双击修改。", bg=PANEL_BG, fg=TEXT_MUTED, wraplength=300, justify="left").grid(row=12, column=0, columnspan=2, sticky="ew", pady=(10, 0))
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
        frame.grid_columnconfigure(0, weight=7)
        frame.grid_columnconfigure(1, weight=3)
        frame.grid_rowconfigure(1, weight=1)
        head = self._create_panel(frame)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        row = tk.Frame(head, bg=PANEL_BG, padx=16, pady=16)
        row.pack(fill="x")
        tk.Label(row, text="地图查看", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ttk.Button(row, text="刷新地图", command=self.load_maps).pack(side="left", padx=(12, 0))
        tk.Label(row, textvariable=self.map_status_var, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=(12, 0))
        left = self._create_panel(frame)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        right = self._create_panel(frame)
        right.grid(row=1, column=1, sticky="nsew")
        left_content = tk.Frame(left, bg=PANEL_BG, padx=16, pady=16)
        left_content.pack(fill="both", expand=True)
        self.map_detail_var = tk.StringVar(value="选择一张地图查看细节。")
        tk.Label(left_content, textvariable=self.map_detail_var, bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 12, "bold"), justify="left").pack(anchor="w")
        legend = tk.Frame(left_content, bg=PANEL_BG)
        legend.pack(fill="x", pady=(8, 0))
        for color, label in (("#d9ead3", "可走"), ("#4b5563", "墙"), ("#f6d365", "事件"), ("#65c7f7", "传送"), ("#ff5a5f", "玩家"), ("#ffffff", "选中")):
            item = tk.Frame(legend, bg=PANEL_BG)
            item.pack(side="left", padx=(0, 12))
            tk.Label(item, text="  ", bg=color, relief="solid", bd=1).pack(side="left")
            tk.Label(item, text=label, bg=PANEL_BG, fg=TEXT_MUTED).pack(side="left", padx=(4, 0))
        canvas_wrap = tk.Frame(left_content, bg=PANEL_BG)
        canvas_wrap.pack(fill="both", expand=True, pady=(12, 0))
        self.map_canvas = tk.Canvas(canvas_wrap, bg="#101820", highlightthickness=1, highlightbackground=BORDER)
        self.map_canvas.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.map_canvas.yview)
        x = ttk.Scrollbar(canvas_wrap, orient="horizontal", command=self.map_canvas.xview)
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.map_canvas.configure(xscrollcommand=x.set, yscrollcommand=y.set)
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)
        self.map_canvas.bind("<Button-1>", self._on_map_canvas_click)

        right_content = tk.Frame(right, bg=PANEL_BG, padx=16, pady=16)
        right_content.pack(fill="both", expand=True)
        tk.Label(right_content, text="地图与事件", bg=PANEL_BG, fg=TEXT_MAIN, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        self._build_filter_row(right_content, self.map_filter_var, self._refresh_map_tree)
        wrap = tk.Frame(right_content, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True)
        columns = ("id", "name", "display", "size", "tileset", "events", "file")
        self.map_tree = ttk.Treeview(wrap, columns=columns, show="headings")
        for key, label, width in (("id", "ID", 48), ("name", "地图名", 120), ("display", "显示名", 120), ("size", "尺寸", 70), ("tileset", "图块", 54), ("events", "EV", 48), ("file", "文件", 90)):
            self.map_tree.heading(key, text=label)
            self.map_tree.column(key, width=width, stretch=(key in {"name", "display", "file"}))
        self._attach_tree_scrollbars(wrap, self.map_tree)
        self.map_tree.bind("<<TreeviewSelect>>", self._on_map_select)
        self.map_tile_detail = tk.Text(right_content, height=12, wrap="word", bd=1, relief="solid", highlightthickness=0, font=("Microsoft YaHei UI", 10))
        self.map_tile_detail.pack(fill="x", pady=(12, 0))
        self.map_switch_actions = tk.Frame(right_content, bg=PANEL_BG)
        self.map_switch_actions.pack(fill="x", pady=(8, 0))
        return frame

    def _build_filter_row(self, parent: tk.Frame, variable: tk.StringVar, callback) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=(14, 10))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        variable.trace_add("write", lambda *_: self._debounced_filter(variable, callback))
        ttk.Button(row, text="清空筛选", command=lambda: variable.set("")).pack(side="left", padx=(8, 0))

    def _debounced_filter(self, variable: tk.StringVar, callback) -> None:
        key = str(variable)
        after_id = self._filter_after_ids.get(key)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._filter_after_ids[key] = self.root.after(180, callback)

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
        ttk.Button(actions, text="刷新备份列表", command=self.refresh_backups, style="Primary.TButton").pack(side="left")
        ttk.Button(actions, text="打开备份目录", command=self.open_backup_folder).pack(side="left", padx=8)
        self.refresh_backups()

    def _create_panel(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL_BG, bd=1, relief="solid", highlightthickness=0)

    def _show_section(self, section: str) -> None:
        self.current_section = section
        for key, btn in self.nav_buttons.items():
            btn.configure(bg=NAV_ACTIVE if key == section else NAV_BG)
        for key, view in self._section_views.items():
            if key == section:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_remove()
        if section == "dashboard":
            if self.project:
                self._set_status_text(f"当前项目：{self.project.root}\n可直接切换到翻译工作台或数据编辑器。")
            else:
                self._set_status_text("请先选择游戏 exe，加载后会自动加入游戏库。")
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
            elif self.project.engine != "RPG Maker MV/MZ":
                self._show_section("translation")
                self._set_status_text("Ren'Py 项目已隐藏 RPG Maker 实时作弊菜单；当前可使用翻译工作台。")
            else:
                self.refresh_save_slots(silent=True)
                self._set_status_text("存档修改已打开。请先在游戏内保存一次，再选择 file 存档读取。")
        elif section == "maps":
            if not self.project:
                self._set_status_text("请先加载项目，再查看地图。")
            elif self.project.engine != "RPG Maker MV/MZ":
                self._show_section("translation")
                self._set_status_text("Ren'Py 项目已隐藏 RPG Maker 地图查看；当前可使用翻译工作台。")
            else:
                self.load_maps(silent=True)
                self._set_status_text(f"地图查看已打开，当前读取到 {len(self.map_records)} 张地图。")
                self._start_runtime_map_poll()
        elif section == "tools":
            self._set_status_text("环境与备份工具已打开。")

    def select_project(self) -> None:
        initial_dir = str(self._initial_game_picker_dir())
        path = filedialog.askopenfilename(
            title="选择或载入游戏 exe",
            initialdir=initial_dir,
            filetypes=[("可执行文件", "*.exe"), ("Game.exe", "Game.exe"), ("所有文件", "*.*")],
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
            messagebox.showerror("错误", "请先选择 exe。")
            return
        self.load_path(Path(raw_path))

    def load_path(self, path: Path) -> None:
        self._project_load_token += 1
        token = self._project_load_token
        self.project = None
        self.env_status_var.set("正在识别游戏项目...")
        self.run_status_var.set("识别中")
        self._set_status_text(f"正在识别项目：{path}")
        self._start_activity()
        threading.Thread(target=self._detect_project_worker, args=(path, token), daemon=True).start()

    def _detect_project_worker(self, path: Path, token: int) -> None:
        try:
            project = detect_project(path)
        except Exception as exc:
            self.root.after(0, lambda err=exc, t=token: self._handle_project_load_error(err, t))
            return
        self.root.after(0, lambda p=project, t=token: self._apply_detected_project(p, t))

    def _handle_project_load_error(self, exc: Exception, token: int) -> None:
        if token != self._project_load_token:
            return
        self.env_status_var.set("项目加载失败")
        self.run_status_var.set("未启动")
        self._set_status_text(f"项目识别失败：{exc}")
        self._stop_activity()
        messagebox.showerror("无法加载", str(exc))

    def _apply_detected_project(self, project: ProjectInfo, token: int) -> None:
        if token != self._project_load_token:
            return
        self._stop_activity()
        self.project = project
        if self.project.launcher_path:
            self.path_var.set(str(self.project.launcher_path))
        else:
            self.path_var.set(str(self.project.root))
        self._apply_project_state()
        self._show_section("dashboard")

    def _apply_project_state(self) -> None:
        if not self.project:
            return
        self._load_project_tm()
        self.project_name_var.set(self.project.root.name)
        self.project_path_var.set(str(self.project.root))
        self.engine_var.set(self.project.engine)
        self.support_var.set(self._support_status_for(self.project))
        self.run_status_var.set("未启动")
        self._refresh_engine_specific_navigation()
        if self._supports_full_editing(self.project):
            self.translation_status_var.set("待加载")
            self.data_status_var.set("待加载")
            self.save_status_var.set("待刷新")
            self.map_status_var.set("待刷新")
            self.root.after(120, lambda: self._prepare_and_extract_texts())
            self.root.after(260, lambda: self.load_data_records(silent=True))
            self.root.after(420, lambda: self.refresh_save_slots(silent=True))
        else:
            self.translation_entries = []
            self.translation_map = {}
            self.translation_view_id_map = {}
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

    def _refresh_engine_specific_navigation(self) -> None:
        is_rpgmaker = bool(self.project and self.project.engine == "RPG Maker MV/MZ")
        for key in ("save", "maps"):
            button = self.nav_buttons.get(key)
            if button:
                if is_rpgmaker:
                    button.pack(fill="x", pady=4)
                else:
                    button.pack_forget()
        if not is_rpgmaker and self.project:
            self.save_status_var.set("Ren'Py 不显示 RPG Maker 实时作弊菜单")
            self.map_status_var.set("Ren'Py 不显示 RPG Maker 地图查看")
            self._set_status_text(f"{self.project.engine} 已识别并加入游戏库；完整翻译和数据编辑会在后续扩展。")
        self.refresh_backups()
        self._touch_library_entry(self.project)
        self._append_recent_task("载入项目", self.project.root, self.project.engine)
        self.env_status_var.set(f"项目已加载：{self.project.root}")
        if not self._renpy_extracting:
            self.ai_progress_var.set(0)
            self.ai_status_var.set("AI 翻译未开始")

    def _prepare_and_extract_texts(self) -> None:
        if not self.project or self.project.engine != "Ren'Py":
            self.extract_texts(silent=True)
            return
        service = self._get_service()
        if hasattr(service, "prepare_source_tree"):
            self.ai_progress_var.set(8)
            self.ai_status_var.set("Ren'Py 正在准备资源树：解包/反编译游戏脚本……")
            self._set_status_text("Ren'Py 正在准备资源树：会先尝试解包 RPA、反编译 RPYC，再提取文本。")
            threading.Thread(target=self._run_prepare_and_extract, args=(service,), daemon=True).start()
            return
        self.extract_texts(silent=True)

    def _run_prepare_and_extract(self, service: RenPyService) -> None:
        try:
            stats = service.prepare_source_tree()
        except Exception as exc:
            self.root.after(0, lambda err=exc: self._finish_prepare_and_extract(None, err))
            return
        self.root.after(0, lambda s=stats: self._finish_prepare_and_extract(s, None))

    def _finish_prepare_and_extract(self, stats: dict | None, error: Exception | None) -> None:
        if error is not None:
            self._set_status_text(f"Ren'Py 资源准备失败：{error}")
            self.extract_texts(silent=True)
            return
        stats = stats or {}
        self._set_status_text(
            f"Ren'Py 资源准备完成：rpy={stats.get('rpy', 0)}，rpyc={stats.get('rpyc', 0)}，rpa={stats.get('rpa', 0)}。\n"
            "正在继续提取文本……"
        )
        self.ai_status_var.set("Ren'Py 资源准备完成，正在提取文本……")
        self.extract_texts(silent=True)

    def extract_texts(self, silent: bool = False, allow_runtime_extract: bool = True) -> None:
        if not self.project:
            if not silent:
                messagebox.showerror("错误", "请先加载项目。")
            self._set_translation_notice("请先选择或拖入游戏 exe。")
            return
        if not self._supports_full_editing(self.project):
            self.translation_status_var.set("暂不支持")
            self._set_translation_notice(f"{self.project.engine} 当前仅支持识别、入库和启动。")
            self._set_status_text(f"{self.project.engine} 暂未启用文本提取。")
            if not silent:
                messagebox.showinfo("提示", f"{self.project.engine} 当前仅支持识别、入库和启动。")
            return
        project = self.project
        self.translation_status_var.set("提取中...")
        self._set_status_text("正在后台提取文本，界面可继续操作。")
        self._start_activity()
        threading.Thread(target=self._extract_texts_worker, args=(project, silent, allow_runtime_extract), daemon=True).start()

    def _extract_texts_worker(self, project: ProjectInfo, silent: bool, allow_runtime_extract: bool) -> None:
        try:
            service = self._service_for_project(project)
            entries = service.extract_translations()
        except Exception as exc:
            self.root.after(0, lambda err=exc, s=silent: self._handle_extract_texts_error(err, s))
            return
        self.root.after(0, lambda e=entries, svc=service, s=silent, a=allow_runtime_extract: self._finish_extract_texts(e, svc, s, a))

    def _handle_extract_texts_error(self, exc: Exception, silent: bool) -> None:
        self.translation_entries = []
        self.translation_map = {}
        self.translation_view_id_map = {}
        self.translation_status_var.set("提取失败")
        self._set_translation_notice(f"文本提取失败：{exc}")
        self._stop_activity()
        if not silent:
            messagebox.showerror("提取失败", str(exc))

    def _finish_extract_texts(self, entries: list[TranslationEntry], service: object, silent: bool, allow_runtime_extract: bool) -> None:
        if not self.project:
            return
        self._stop_activity()
        self.translation_entries = entries
        self.translation_map = {entry.entry_id: entry for entry in self.translation_entries}
        self._load_project_translation_cache(silent=True)
        self.translation_status_var.set(f"{len(self.translation_entries)} 条")
        if self.project.engine == "Ren'Py":
            self.translation_scope_var.set("全部文本")
        self._refresh_translation_file_filter()
        self._refresh_translation_tree()
        should_runtime_extract = (
            allow_runtime_extract
            and self.project.engine == "Ren'Py"
            and hasattr(service, "can_runtime_extract")
            and service.can_runtime_extract()
            and hasattr(service, "runtime_export_path")
            and not service.runtime_export_path().exists()
        )
        if should_runtime_extract:
            self._start_renpy_runtime_extraction(service, auto_trigger=True)
            return
        has_suspicious_text = self._has_suspicious_dialogue_text(self.translation_entries)
        if not self.translation_entries:
            self._set_translation_notice("没有提取到文本。可能是加密封包、非标准结构，或当前项目没有可识别文本。")
        elif has_suspicious_text:
            warning = "检测到部分对白疑似乱码。建议先从原版游戏或备份恢复 data 文件，再进行 AI 翻译，避免花费在错误源文本上。"
            self.translation_detail_var.set(warning)
            self._set_status_text(warning)
        self._append_recent_task("提取文本", self.project.root, self.project.engine)
        if not has_suspicious_text:
            self._set_status_text(f"已提取 {len(self.translation_entries)} 条文本。")
        self._save_project_translation_cache()

    def _start_renpy_runtime_extraction(self, service: RenPyService, auto_trigger: bool = False) -> None:
        if self._renpy_extracting:
            self._set_status_text("Ren'Py 深度提取已经在进行中，请在窗口选择器中刷新并确认真正的游戏窗口。")
            return
        try:
            extractor = service.install_runtime_extractor(clear_cache=True)
        except Exception as exc:
            self._set_status_text(f"Ren'Py 深度提取脚本安装失败：{exc}")
            return
        notice = (
            "当前 Ren'Py 游戏将自动执行深度提取：已安装脚本并启动一次游戏，让引擎导出编译脚本文本。"
            if auto_trigger
            else "已安装 Ren'Py 深度提取脚本，正在启动游戏一次让引擎导出编译脚本文本。"
        )
        self._set_translation_notice(notice)
        self._renpy_extracting = True
        self.ai_progress_var.set(5)
        self.ai_status_var.set("Ren'Py 深度提取准备中：正在启动游戏，请在窗口选择器中确认真正的游戏窗口。")
        self._set_status_text(
            f"已安装 Ren'Py 深度提取脚本：{extractor.name}\n"
            "正在启动游戏并打开窗口选择器。请等游戏真正进入主窗口后，点击刷新并确认选择。"
        )
        if not self._choose_or_start_renpy_extract_target():
            self._renpy_extracting = False
            return

    def _choose_or_start_renpy_extract_target(self) -> bool:
        launcher = self._resolve_current_launcher()
        if launcher:
            try:
                self._renpy_extract_process = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
                self._renpy_extract_pid = self._renpy_extract_process.pid
                self.run_status_var.set("已启动")
                self._set_status_text(
                    f"已启动游戏用于文本提取：{launcher.name}\n"
                    "窗口选择器已经打开。等加载动画结束、真正游戏窗口出现后，点击刷新并确认选择。"
                )
            except Exception as exc:
                self._set_status_text(f"Ren'Py 深度提取需要启动游戏，但启动失败：{exc}")
                return False
        else:
            self._set_status_text("未找到可启动的游戏 exe。请先手动打开游戏，再在窗口选择器中刷新并选择真正游戏窗口。")
        selected = self._ask_window_selection()
        if selected:
            self._renpy_extract_pid = selected.get("pid")
            self._set_status_text(f"已选择游戏窗口：{selected.get('title', '')}\n现在开始等待 Ren'Py 导出游戏文本。")
            self._begin_renpy_extract_wait()
            return True
        self._renpy_extracting = False
        self._close_renpy_extract_process()
        self._set_status_text("已取消窗口选择，暂不开始深度提取。可在翻译工作台点击“提取文本”重新开始。")
        return False

    def _begin_renpy_extract_wait(self) -> None:
        self._renpy_extracting = True
        self._renpy_extract_poll_count = 0
        self.ai_progress_var.set(12)
        self.ai_status_var.set("Ren'Py 深度提取中：已确认游戏窗口，正在等待引擎导出文本……")
        self.root.after(300, self._renpy_extract_pulse)
        self.root.after(500, self._poll_renpy_runtime_extraction)

    def _renpy_extract_pulse(self) -> None:
        if not self._renpy_extracting:
            return
        current = float(self.ai_progress_var.get() or 0)
        if current < 92:
            self.ai_progress_var.set(min(92, current + 3))
        if self._renpy_extracting:
            self.root.after(300, self._renpy_extract_pulse)

    def _poll_renpy_runtime_extraction(self) -> None:
        if not self.project or self.project.engine != "Ren'Py":
            return
        service = RenPyService(self.project)
        output = service.runtime_export_path()
        if output.exists():
            self._renpy_extracting = False
            self.ai_progress_var.set(100)
            self.ai_status_var.set("Ren'Py 深度提取完成，正在刷新列表……")
            self._set_status_text("Ren'Py 深度提取完成，正在刷新文本列表。")
            self._close_renpy_extract_process()
            self.extract_texts(silent=True, allow_runtime_extract=False)
            self.ai_progress_var.set(0)
            self.ai_status_var.set("AI 翻译未开始")
            return
        self._renpy_extract_poll_count += 1
        if self._renpy_extract_poll_count <= 60:
            self.root.after(1000, self._poll_renpy_runtime_extraction)
            return
        self._renpy_extracting = False
        self._close_renpy_extract_process()
        self.ai_progress_var.set(0)
        self.ai_status_var.set("AI 翻译未开始")
        self._set_status_text(
            "Ren'Py 深度提取暂未检测到导出结果。请确认游戏是否成功启动到标题画面；"
            "之后可回到翻译工作台点击“提取文本”重试。"
        )

    def _resolve_current_launcher(self) -> Path | None:
        if self.project and self.project.launcher_path and self.project.launcher_path.exists():
            return self.project.launcher_path
        raw_path = self.path_var.get().strip()
        if raw_path:
            path = Path(raw_path)
            if path.is_file() and path.suffix.lower() == ".exe":
                return path
        if self.project and self.project.root.exists():
            game_exe = self.project.root / "Game.exe"
            if game_exe.exists():
                return game_exe
            for candidate in sorted(self.project.root.glob("*.exe")):
                if candidate.name.lower() != "rpgrenpylocalizer.exe":
                    return candidate
        return None

    def _close_renpy_extract_process(self) -> None:
        proc = self._renpy_extract_process
        selected_pid = self._renpy_extract_pid
        self._renpy_extract_process = None
        self._renpy_extract_pid = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                self.root.after(1500, lambda p=proc: p.kill() if p.poll() is None else None)
            except Exception:
                pass
        if selected_pid and (not proc or selected_pid != proc.pid):
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                subprocess.run(
                    ["taskkill", "/PID", str(selected_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    check=False,
                )
            except Exception:
                pass

    def _list_candidate_game_windows(self) -> list[dict]:
        if os.name != "nt" or not self.project:
            return []
        user32 = ctypes.windll.user32
        items: list[dict] = []
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title or "RPGRenPyLocalizer" in title:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            path = self._process_path(int(pid.value))
            process_name = Path(path).name.lower() if path else ""
            if process_name in {"cmd.exe", "powershell.exe", "windowsterminal.exe", "conhost.exe"}:
                return True
            items.append({"hwnd": hwnd, "pid": int(pid.value), "title": title, "path": path})
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return items

    @staticmethod
    def _process_path(pid: int) -> str:
        try:
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return ""
            try:
                buffer = ctypes.create_unicode_buffer(260)
                size = wintypes.DWORD(len(buffer))
                if psapi.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    return buffer.value
                return ""
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ""

    def _ask_window_selection(self) -> dict | None:
        windows = self._list_candidate_game_windows()
        dialog = tk.Toplevel(self.root)
        dialog.title("选择 Ren'Py 游戏窗口")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=PANEL_BG)
        dialog.geometry("620x320")
        tk.Label(
            dialog,
            text="游戏正在启动。等真正的游戏窗口出现后点“刷新窗口”，选中它，再确认开始提取文本。",
            bg=PANEL_BG,
            fg=TEXT_MAIN,
            font=("Microsoft YaHei UI", 11, "bold"),
            wraplength=580,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(14, 8))
        listbox = tk.Listbox(dialog, height=9)
        listbox.pack(fill="both", expand=True, padx=14)
        result: dict | None = {}

        def refresh() -> None:
            listbox.delete(0, "end")
            current = self._list_candidate_game_windows()
            windows[:] = current
            for item in current:
                display = f"{item.get('title', '')}  | PID {item.get('pid', '')}  | {Path(item.get('path', '')).name}"
                listbox.insert("end", display)
            if current:
                listbox.selection_clear(0, "end")
                listbox.selection_set(0)

        def choose() -> None:
            nonlocal result
            selection = listbox.curselection()
            result = windows[selection[0]] if selection else None
            dialog.destroy()

        def skip() -> None:
            nonlocal result
            result = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", skip)
        buttons = tk.Frame(dialog, bg=PANEL_BG)
        buttons.pack(fill="x", padx=14, pady=12)
        ttk.Button(buttons, text="确认选择并开始提取", command=choose, style="Primary.TButton").pack(side="left")
        ttk.Button(buttons, text="刷新窗口", command=refresh).pack(side="left", padx=8)
        ttk.Button(buttons, text="取消", command=skip).pack(side="left", padx=8)
        refresh()
        self.root.wait_window(dialog)
        return result

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
        self._refresh_translation_file_filter()
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
        project = self.project
        if self._has_risky_system_plugin_targets():
            ok = messagebox.askyesno(
                "高风险嵌入提示",
                "当前译文包含 RPG Maker 的系统/插件文本。\n\n"
                "这类文本可能包含脚本、插件参数或引擎关键字段，嵌入后有概率导致游戏启动失败。\n"
                "本工具会自动跳过系统/插件文本，只嵌入对白、选项和普通数据库文本。\n\n仍要继续嵌入吗？",
            )
            if not ok:
                return
        if not messagebox.askyesno(
            "嵌入游戏",
            "嵌入游戏需要较长时间，并会写入游戏数据文件。\n\n"
            "处理期间请勿在此界面进行其他操作，也不要同时启动/关闭游戏。\n\n确认开始吗？",
        ):
            return
        self.ai_progress_var.set(5)
        self.ai_status_var.set("正在准备后台嵌入翻译，请稍候...")
        self._set_status_text("正在后台准备翻译快照并写入游戏。嵌入期间请勿在此界面进行其他操作。")
        if hasattr(self, "embed_button"):
            self.embed_button.configure(state="disabled")
        self._start_activity()
        threading.Thread(target=self._embed_translation_worker, args=(project,), daemon=True).start()
        return

    def _embed_translation_worker(self, project: ProjectInfo) -> None:
        try:
            service = self._service_for_project(project)
            if not hasattr(service, "apply_translations"):
                self.root.after(0, lambda: messagebox.showinfo("提示", "当前引擎暂不支持嵌入翻译。"))
                self.root.after(0, lambda: self.ai_progress_var.set(0))
                self.root.after(0, self._stop_activity)
                return
            translations = {
                entry_id: entry
                for entry_id, entry in self.translation_map.items()
                if entry.target.strip() and entry.category not in {"system", "plugin"}
            }
            if not translations:
                self.root.after(0, lambda: messagebox.showinfo("提示", "当前没有填写译文。请先手动编辑、导入翻译包，或使用 AI 一键翻译。"))
                self.root.after(0, lambda: self.ai_progress_var.set(0))
                self.root.after(0, self._stop_activity)
                return
            count = len(translations)
            self.root.after(0, lambda c=count: self.ai_status_var.set(f"正在嵌入翻译：{c} 条，即将开始..."))
            self.root.after(0, lambda: self.ai_progress_var.set(10))
            time.sleep(0)
            # 分阶段进度更新（service.apply_translations 内部不自报进度时由外层兜底）
            self.root.after(0, lambda c=count: self.ai_status_var.set(f"正在嵌入翻译：{c} 条，正在写入文件..."))
            self.root.after(0, lambda: self.ai_progress_var.set(30))
            time.sleep(0)
            start = time.time()
            updated = service.apply_translations(translations)
            elapsed = time.time() - start
            self.root.after(0, lambda u=updated, e=elapsed: self.ai_status_var.set(f"嵌入完成：{u} 处（耗时 {e:.1f} 秒）"))
            self.root.after(0, lambda: self.ai_progress_var.set(90))
        except Exception as exc:
            self.root.after(0, lambda err=exc: self._handle_embed_translation_error(err))
            return
        self.root.after(0, self._stop_activity)
        self.root.after(0, lambda count=updated, p=project: self._finish_embed_translation(count, p))

    def _handle_embed_translation_error(self, exc: Exception) -> None:
        self.ai_progress_var.set(0)
        self.ai_status_var.set("嵌入翻译失败")
        if hasattr(self, "embed_button"):
            self.embed_button.configure(state="normal")
        self._stop_activity()
        messagebox.showerror("嵌入失败", str(exc))

    def _finish_embed_translation(self, updated: int, project: ProjectInfo) -> None:
        if not self.project or self.project.root != project.root:
            return
        self.ai_progress_var.set(100)
        self.ai_status_var.set(f"嵌入完成：{updated} 处")
        if hasattr(self, "embed_button"):
            self.embed_button.configure(state="normal")
        self.root.after(500, self.refresh_backups)
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
        if self.project.engine == "Ren'Py":
            self._load_renpy_runtime_translation()
            return
        try:
            self._ensure_runtime_bridge_matches_project()
            result = self._runtime_request("POST", "/translation", {"enabled": True, "dict": targets}, timeout=8.0)
        except Exception as exc:
            messagebox.showerror("加载失败", self._runtime_error_message(exc))
            return
        self.runtime_connected = True
        self.runtime_status_var.set(f"实时翻译已加载：{result.get('count', len(targets))} 条")
        self._save_project_translation_cache()
        self._set_status_text("已把翻译表加载到当前运行中的游戏。新的文本绘制会使用译文；已绘制在屏幕上的旧文字可能需要刷新窗口/推进对话。")

    def launch_translated_runtime(self) -> None:
        self.load_runtime_translation()

    def _load_renpy_runtime_translation(self) -> None:
        service = self._get_service()
        if not hasattr(service, "build_runtime_translation_patch"):
            messagebox.showinfo("提示", "当前 Ren'Py 项目暂不支持运行时翻译补丁。")
            return
        try:
            patch_path, count = service.build_runtime_translation_patch(self.translation_map)
        except Exception as exc:
            messagebox.showerror("加载失败", f"生成 Ren'Py 临时翻译补丁失败：{exc}")
            return
        self._save_project_translation_cache()
        self._append_recent_task("加载运行时翻译", self.project.root, self.project.engine)
        self._set_status_text(f"已生成 Ren'Py 临时翻译补丁：{patch_path.name}，共 {count} 条。\n正在启动游戏，启动后的文本会优先显示译文。")
        self.launch_current_game()
        messagebox.showinfo(
            "已启动游戏",
            f"已为 Ren'Py 生成临时翻译补丁并启动游戏：{count} 条。\n\n"
            "这是临时加载方案；删除 game 目录中的 zz_rpgrtl_runtime_translation.rpy 后，游戏会恢复原文。",
        )

    def save_ai_settings(self) -> None:
        settings = self.workspace.load_settings()
        provider = "百度翻译" if self._using_baidu_channel() else (self.ai_provider_var.get().strip() or "OpenAI")
        keys = settings.get("ai_api_keys", {})
        if not isinstance(keys, dict):
            keys = {}
        keys[provider] = self.ai_api_key_var.get().strip()
        base_urls = settings.get("ai_base_urls", {})
        if not isinstance(base_urls, dict):
            base_urls = {}
        base_urls[provider] = self.ai_base_url_var.get().strip()
        settings["ai_provider"] = provider
        settings["ai_api_keys"] = keys
        settings["ai_base_urls"] = base_urls
        if provider == "百度翻译":
            settings["ai_model"] = "无需模型"
        else:
            model = self.ai_model_var.get().strip() or self._default_ai_model(provider)
            if provider == "Xiaomi Token Plan":
                model = self._normalize_xiaomi_model(model)
                self.ai_model_var.set(model)
            if provider == "Doubao":
                model = self._normalize_doubao_model(model)
                self.ai_model_var.set(model)
            settings["ai_model"] = model
            models = settings.get("ai_models", {})
            if not isinstance(models, dict):
                models = {}
            models[provider] = model
            settings["ai_models"] = models
        settings["baidu_appid"] = self.baidu_appid_var.get().strip()
        settings["baidu_secret"] = self.baidu_secret_var.get().strip()
        settings["xiaomi_plan_type"] = self.xiaomi_plan_type_var.get().strip() or "Token Plan"
        settings["xiaomi_cluster"] = self.xiaomi_cluster_var.get().strip() or "新加坡集群"
        settings["ai_parallel_providers"] = self._selected_parallel_providers()
        self.workspace.save_settings(settings)
        self._refresh_parallel_provider_checks()
        self.ai_status_var.set("翻译设置已保存。")

    def _on_translation_channel_change(self, _event: object | None = None) -> None:
        self._refresh_translation_channel_ui()
        channel = self.translation_channel_var.get()
        self.ai_status_var.set(f"已切换到 {channel}。")

    def _using_baidu_channel(self) -> bool:
        return self.translation_channel_var.get() == "百度 API 翻译"

    def _selected_parallel_providers(self) -> list[str]:
        return [provider for provider, var in self.ai_parallel_provider_vars.items() if var.get()]

    def _refresh_parallel_provider_checks(self) -> None:
        if not hasattr(self, "ai_parallel_frame"):
            return
        settings = self.workspace.load_settings()
        keys = settings.get("ai_api_keys", {})
        if not isinstance(keys, dict):
            keys = {}
        saved = settings.get("ai_parallel_providers", [])
        if isinstance(saved, str):
            selected = {name.strip() for name in re.split(r"[,，;；\s]+", saved) if name.strip()}
        elif isinstance(saved, list):
            selected = {str(name).strip() for name in saved if str(name).strip()}
        else:
            selected = set()
        current_provider = self.ai_provider_var.get().strip() or "OpenAI"
        current_key = self.ai_api_key_var.get().strip()
        configured = [
            provider
            for provider in ("OpenAI", "Xiaomi Token Plan", "DeepSeek", "Doubao", "GLM", "NVIDIA")
            if (provider == current_provider and current_key) or str(keys.get(provider, "")).strip()
        ]
        for child in self.ai_parallel_frame.winfo_children():
            child.destroy()
        self.ai_parallel_provider_vars = {}
        if not configured:
            self.ai_parallel_hint_var.set("保存至少一个 AI 厂商的 API Key 后，这里会显示可并行选择的厂商。")
            return
        for index, provider in enumerate(configured):
            var = tk.BooleanVar(value=(provider in selected) or (not selected and provider == current_provider))
            self.ai_parallel_provider_vars[provider] = var
            ttk.Checkbutton(self.ai_parallel_frame, text=provider, variable=var).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 12), pady=(0, 4))
        self.ai_parallel_hint_var.set("只显示已保存 API Key 的厂商；勾选多个后会按批次并行分配。")

    def _refresh_translation_channel_ui(self) -> None:
        if not hasattr(self, "ai_settings_frame") or not hasattr(self, "baidu_settings_frame"):
            return
        if self._using_baidu_channel():
            self.ai_settings_frame.grid_remove()
            self.baidu_settings_frame.grid()
            self.ai_provider_link.configure(text=self._provider_link_label("百度翻译"))
        else:
            self.baidu_settings_frame.grid_remove()
            self.ai_settings_frame.grid()
            self.ai_provider_link.configure(text=self._provider_link_label(self.ai_provider_var.get().strip() or "OpenAI"))

    def _on_ai_provider_change(self, _event: object | None = None) -> None:
        provider = self.ai_provider_var.get().strip() or "OpenAI"
        settings = self.workspace.load_settings()
        keys = settings.get("ai_api_keys", {})
        self.ai_api_key_var.set(keys.get(provider, ""))
        base_urls = settings.get("ai_base_urls", {})
        if not isinstance(base_urls, dict):
            base_urls = {}
        self.ai_base_url_var.set(base_urls.get(provider, self._default_ai_base_url(provider)))
        self.baidu_appid_var.set(settings.get("baidu_appid", ""))
        self.baidu_secret_var.set(settings.get("baidu_secret", ""))
        models = settings.get("ai_models", {})
        if not isinstance(models, dict):
            models = {}
        if hasattr(self, "ai_model_box"):
            self.ai_model_box.configure(values=self._ai_model_options(provider))
        if provider == "百度翻译":
            self.ai_model_var.set("无需模型")
            if hasattr(self, "ai_model_box"):
                self.ai_model_box.configure(state="disabled")
        else:
            if hasattr(self, "ai_model_box"):
                self.ai_model_box.configure(state="normal")
            model = str(models.get(provider, self._default_ai_model(provider)))
            if provider == "Xiaomi Token Plan":
                model = self._normalize_xiaomi_model(model)
            self.ai_model_var.set(model)
        if hasattr(self, "ai_provider_link") and not self._using_baidu_channel():
            self.ai_provider_link.configure(text=self._provider_link_label(provider))
        self._refresh_ai_base_url_visibility(provider)
        if provider == "Xiaomi Token Plan" and (not self.ai_base_url_var.get().strip() or "token-plan-" in self.ai_base_url_var.get().strip()):
            self.ai_base_url_var.set(self._default_ai_base_url(provider))
        self._refresh_parallel_provider_checks()
        self.ai_status_var.set(f"已切换到 {provider}。")

    def _on_xiaomi_cluster_change(self, _event: object | None = None) -> None:
        if self.ai_provider_var.get().strip() == "Xiaomi Token Plan":
            self.ai_base_url_var.set(self._default_ai_base_url("Xiaomi Token Plan"))
            self.ai_status_var.set(
                f"已切换小米 {self.xiaomi_plan_type_var.get()} / {self.xiaomi_cluster_var.get()}。"
                "中国集群可能受账号注册地限制，不通时建议用新加坡集群。"
            )

    def _ai_model_options(self, provider: str | None = None) -> tuple[str, ...]:
        provider = provider or self.ai_provider_var.get().strip() or "OpenAI"
        if provider == "DeepSeek":
            return ("deepseek-v4-flash", "deepseek-v4-pro")
        if provider == "Xiaomi Token Plan":
            return ("mimo-v2.5-pro", "mimo-v2.5", "mimo-v2-pro", "mimo-v2-omni", "mimo-v2.5-tts")
        if provider == "Doubao":
            return ("doubao-seed-2-0-mini-260215", "doubao-seed-2-0-lite-260215", "doubao-seed-2-0-pro-260215")
        if provider == "GLM":
            return ("glm-4.5", "glm-4.5-air", "glm-4.5-flash")
        if provider == "NVIDIA":
            return ("minimaxai/minimax-m2.7",)
        return ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini")

    def _default_ai_model(self, provider: str | None = None) -> str:
        provider = provider or self.ai_provider_var.get().strip() or "OpenAI"
        if provider == "DeepSeek":
            return "deepseek-v4-flash"
        if provider == "Xiaomi Token Plan":
            return "mimo-v2.5-pro"
        if provider == "Doubao":
            return "doubao-seed-2-0-mini-260215"
        if provider == "GLM":
            return "glm-4.5"
        if provider == "NVIDIA":
            return "minimaxai/minimax-m2.7"
        return "gpt-5.5"

    @staticmethod
    def _xiaomi_cluster_base_url(cluster: str, protocol: str = "openai") -> str:
        hosts = {
            "中国集群": "token-plan-cn.xiaomimimo.com",
            "新加坡集群": "token-plan-sgp.xiaomimimo.com",
            "欧洲集群": "token-plan-ams.xiaomimimo.com",
        }
        host = hosts.get(cluster, hosts["新加坡集群"])
        suffix = "anthropic" if protocol == "anthropic" else "v1"
        return f"https://{host}/{suffix}"

    def _default_ai_base_url(self, provider: str | None = None) -> str:
        if provider == "Xiaomi Token Plan":
            return self._xiaomi_cluster_base_url(self.xiaomi_cluster_var.get().strip() or "新加坡集群", "openai")
        if provider == "NVIDIA":
            return "https://integrate.api.nvidia.com/v1"
        return ""

    def _refresh_ai_base_url_visibility(self, provider: str | None = None) -> None:
        provider = provider or self.ai_provider_var.get().strip() or "OpenAI"
        if not hasattr(self, "ai_base_url_label") or not hasattr(self, "ai_base_url_entry"):
            return
        if provider in {"NVIDIA", "Xiaomi Token Plan"}:
            self.ai_base_url_label.grid()
            self.ai_base_url_entry.grid()
            if provider == "Xiaomi Token Plan":
                self.xiaomi_plan_label.grid()
                self.xiaomi_plan_box.grid()
                self.xiaomi_cluster_label.grid()
                self.xiaomi_cluster_box.grid()
            elif hasattr(self, "xiaomi_plan_label"):
                self.xiaomi_plan_label.grid_remove()
                self.xiaomi_plan_box.grid_remove()
                self.xiaomi_cluster_label.grid_remove()
                self.xiaomi_cluster_box.grid_remove()
            if not self.ai_base_url_var.get().strip():
                self.ai_base_url_var.set(self._default_ai_base_url(provider))
        else:
            self.ai_base_url_label.grid_remove()
            self.ai_base_url_entry.grid_remove()
            if hasattr(self, "xiaomi_plan_label"):
                self.xiaomi_plan_label.grid_remove()
                self.xiaomi_plan_box.grid_remove()
                self.xiaomi_cluster_label.grid_remove()
                self.xiaomi_cluster_box.grid_remove()

    def _provider_link_label(self, provider: str) -> str:
        return f"打开 {provider} API 页面"

    def open_ai_provider_page(self) -> None:
        provider = "百度翻译" if self._using_baidu_channel() else (self.ai_provider_var.get().strip() or "OpenAI")
        url = AI_PROVIDER_URLS.get(provider)
        if not url:
            messagebox.showinfo("提示", f"{provider} 暂时没有配置官网跳转地址。")
            return
        webbrowser.open(url)

    def translate_with_ai(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        if not self.translation_entries:
            self.extract_texts(silent=True)
        base_pending = [
            entry
            for entry in self.translation_entries
            if self._translation_entry_visible(entry) and entry.source.strip() and not entry.target.strip()
        ]
        pending = [entry for entry in base_pending if self._is_likely_dialogue_text(entry)]
        skipped_non_dialogue = len(base_pending) - len(pending)
        empty_message = f"当前范围“{self.translation_scope_var.get()}”没有需要 AI 翻译的空译文。"
        if skipped_non_dialogue:
            empty_message += f"\n已自动跳过 {skipped_non_dialogue} 条非对白或异常文本。"
        self._start_ai_translation(pending, empty_message, skipped_non_dialogue=skipped_non_dialogue)

    def translate_selected_with_ai(self) -> None:
        if not self.project:
            messagebox.showerror("错误", "请先加载项目。")
            return
        base_pending = [
            entry
            for entry in self._selected_translation_entries()
            if entry.source.strip() and not entry.target.strip()
        ]
        pending = [entry for entry in base_pending if self._is_likely_dialogue_text(entry)]
        skipped_non_dialogue = len(base_pending) - len(pending)
        empty_message = "选中的文本都已翻译，或没有可翻译原文。"
        if skipped_non_dialogue:
            empty_message += f"\n已自动跳过 {skipped_non_dialogue} 条非对白或异常文本。"
        self._start_ai_translation(pending, empty_message, skipped_non_dialogue=skipped_non_dialogue)

    def _start_ai_translation(self, pending: list[TranslationEntry], empty_message: str, skipped_non_dialogue: int = 0) -> None:
        if not pending:
            messagebox.showinfo("提示", empty_message)
            return
        self._start_activity()
        cache_hits = self._apply_translation_memory(pending)
        request_entries = self._unique_ai_requests([entry for entry in pending if not entry.target.strip()])
        if not request_entries:
            self._save_project_translation_cache()
            self._refresh_translation_tree()
            done = sum(1 for item in self.translation_entries if item.target.strip())
            self.translation_status_var.set(f"{len(self.translation_entries)} 条 / 已译 {done}")
            messagebox.showinfo("提示", f"当前需要翻译的文本都已从全局缓存命中：{cache_hits} 条。")
            return
        self.save_ai_settings()
        self.ai_progress_var.set(0)
        saved = len(pending) - len(request_entries)
        suffix_parts = []
        if saved:
            suffix_parts.append(f"已合并 {saved} 条重复原文")
        if cache_hits:
            suffix_parts.append(f"全局缓存命中 {cache_hits} 条")
        if skipped_non_dialogue:
            suffix_parts.append(f"已跳过 {skipped_non_dialogue} 条非对白/异常文本")
        suffix = f"，{'，'.join(suffix_parts)}" if suffix_parts else ""
        self.ai_status_var.set(f"准备 AI 翻译：共 {len(pending)} 条，实际请求 {len(request_entries)} 条，动态编排批次{suffix}。")
        self._set_status_text(f"AI 翻译开始：共 {len(pending)} 条，实际请求 {len(request_entries)} 条，动态编排批次{suffix}。")
        provider = "百度翻译" if self._using_baidu_channel() else (self.ai_provider_var.get().strip() or "OpenAI")
        model = self.ai_model_var.get().strip() or self._default_ai_model(provider)
        if provider == "百度翻译":
            appid = self.baidu_appid_var.get().strip()
            secret = self.baidu_secret_var.get().strip()
            if not appid or not secret:
                messagebox.showerror("缺少百度翻译参数", "请先填写百度翻译的 AppID 和 Secret Key。")
                return
            threading.Thread(target=self._baidu_translate_all_worker, args=(pending, request_entries, appid, secret), daemon=True).start()
            return
        api_key = self.ai_api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("缺少 API Key", "请先在右侧 AI 翻译设置里输入 API Key。")
            return
        provider_configs = self._active_ai_provider_configs(provider, api_key, model)
        if not provider_configs:
            messagebox.showerror("缺少 API Key", "并行厂商都没有可用 API Key。请先分别选择厂商并保存 API Key。")
            return
        providers_text = "、".join(config["provider"] for config in provider_configs)
        self.ai_status_var.set(f"准备并行翻译：{providers_text}，共 {len(request_entries)} 条。")
        threading.Thread(target=self._ai_translate_all_worker, args=(pending, request_entries, provider_configs), daemon=True).start()

    @staticmethod
    def _normalize_cache_key(source: str, category: str = "") -> str:
        """归一化缓存键：小写、统一空白。
        menu/system/ui 类文本额外去掉首尾标点并加前缀做上下文分片。
        对白类文本保留所有标点，因为问号/感叹号/省略号影响翻译语义。"""
        normalized = source.strip().lower()
        normalized = re.sub(r'\s+', ' ', normalized)
        if category and category in ("menu", "system", "ui"):
            normalized = normalized.strip('.,!?;:\'"。，！？；：、""''·…—·')
            return f"[{category}]{normalized}"
        return normalized

    def _apply_translation_memory(self, entries: list[TranslationEntry]) -> int:
        hits = 0
        for entry in entries:
            if entry.target.strip():
                continue
            # 1. 精确匹配（兼容旧缓存格式）
            cached = self.translation_memory.get(entry.source.strip(), "").strip()
            if cached:
                entry.target = cached
                hits += 1
                continue
            # 2. 归一化匹配
            norm_key = self._normalize_cache_key(entry.source, entry.category)
            if norm_key != entry.source.strip():
                cached = self.translation_memory.get(norm_key, "").strip()
                if cached:
                    entry.target = cached
                    hits += 1
                    continue
            # 3. 模糊匹配（短文本编辑距离 ≤ 1，主要针对 UI/系统文本的微小差异）
            fuzzy = self._fuzzy_match_short_text(entry.source.strip())
            if fuzzy:
                entry.target = fuzzy
                hits += 1
        return hits

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """编辑距离，仅在短字符串下使用。"""
        n, m = len(s1), len(s2)
        if abs(n - m) > 1:
            return abs(n - m)
        prev = list(range(m + 1))
        for i in range(1, n + 1):
            curr = [i] + [0] * m
            for j in range(1, m + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            prev = curr
        return prev[m]

    def _fuzzy_match_short_text(self, source: str, max_distance: int = 1) -> str | None:
        """对短文本（≤20 字符）做编辑距离容错匹配。"""
        source = source.strip()
        if not source or len(source) > 20:
            return None
        # 只检查长度差 ≤ 1 的缓存键
        source_lower = source.lower()
        for cached_source, cached_target in self.translation_memory.items():
            if abs(len(cached_source) - len(source)) > 1:
                continue
            if cached_source == source:
                continue
            if self._edit_distance(source_lower, cached_source.lower()) <= max_distance:
                return cached_target
        return None

    def _remember_translations(self, entries: list[TranslationEntry]) -> int:
        added = 0
        for entry in entries:
            source = entry.source.strip()
            target = entry.target.strip()
            if not source or not target:
                continue
            norm_key = self._normalize_cache_key(source, entry.category)
            if self.translation_memory.get(norm_key) != target:
                self.translation_memory[norm_key] = target
                self._project_tm_keys.add(norm_key)
                added += 1
                self._tm_dirty = True
        return added

    def _load_project_tm(self) -> None:
        """载入项目级翻译记忆，叠加到全局缓存之上。"""
        if not self.project:
            return
        project_tm = self.workspace.load_project_translation_memory(self.project.root)
        if not project_tm:
            return
        overlap = 0
        for key, target in project_tm.items():
            if self.translation_memory.get(key) != target:
                self.translation_memory[key] = target
                self._project_tm_keys.add(key)
                overlap += 1
        if overlap:
            self.ai_status_var.set(f"已叠加项目级翻译缓存：{overlap} 条")

    def _flush_translation_memory(self) -> None:
        """延迟持久化 — 只在有脏数据时一次性写盘。
        同时写全局缓存和项目级缓存，实现项目隔离。"""
        if self._tm_dirty:
            self.workspace.save_translation_memory(self.translation_memory)
            if self.project:
                project_tm = {k: self.translation_memory[k] for k in self._project_tm_keys if k in self.translation_memory}
                self.workspace.save_project_translation_memory(self.project.root, project_tm)
            self._tm_dirty = False

    def _unique_ai_requests(self, entries: list[TranslationEntry]) -> list[TranslationEntry]:
        """去重：使用归一化后的缓存键去重，避免 'Hello!' 和 'hello ！' 重复请求。"""
        unique: list[TranslationEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = self._normalize_cache_key(entry.source, entry.category)
            if key and key not in seen:
                seen.add(key)
                unique.append(entry)
        return unique

    @staticmethod
    def _estimate_entry_tokens(entry: TranslationEntry) -> int:
        """估算单条文本的 token 消耗。
        中文约 1.8 token/字，英文约 0.3 token/字符，
        外加 JSON 结构开销 ~15 token/条。"""
        text = entry.source
        cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other = len(text) - cjk
        return int(cjk * 1.8 + other * 0.3) + 15

    def _build_token_aware_batches(self, entries: list[TranslationEntry], max_tokens: int = 3500) -> list[list[TranslationEntry]]:
        """按 token 数动态编排批次。
        短文本自动合并到更大的批，长文本单独成批。"""
        if not entries:
            return []
        batches: list[list[TranslationEntry]] = []
        current: list[TranslationEntry] = []
        current_tokens = 0
        for entry in entries:
            tokens = self._estimate_entry_tokens(entry)
            # 单条超过 max_tokens 的仍单独成批（让 LLM 处理长文本）
            if tokens >= max_tokens:
                if current:
                    batches.append(current)
                    current, current_tokens = [], 0
                batches.append([entry])
                continue
            if current_tokens + tokens > max_tokens and current:
                batches.append(current)
                current, current_tokens = [], 0
            current.append(entry)
            current_tokens += tokens
        if current:
            batches.append(current)
        return batches

    def _active_ai_provider_configs(self, current_provider: str, current_api_key: str, current_model: str) -> list[dict[str, str]]:
        settings = self.workspace.load_settings()
        keys = settings.get("ai_api_keys", {})
        models = settings.get("ai_models", {})
        base_urls = settings.get("ai_base_urls", {})
        if not isinstance(keys, dict):
            keys = {}
        if not isinstance(models, dict):
            models = {}
        if not isinstance(base_urls, dict):
            base_urls = {}
        requested = self._selected_parallel_providers()
        if not requested:
            requested = [current_provider]
        configs: list[dict[str, str]] = []
        seen: set[str] = set()
        for provider in requested:
            if provider == "百度翻译" or provider in seen:
                continue
            seen.add(provider)
            api_key = current_api_key if provider == current_provider else str(keys.get(provider, "")).strip()
            if not api_key:
                continue
            model = current_model if provider == current_provider else str(models.get(provider, self._default_ai_model(provider))).strip()
            configs.append(
                {
                    "provider": provider,
                    "api_key": api_key,
                    "model": model or self._default_ai_model(provider),
                    "base_url": str(base_urls.get(provider, self._default_ai_base_url(provider))).strip(),
                }
            )
        return configs

    def _ai_translate_all_worker(self, pending_entries: list[TranslationEntry], request_entries: list[TranslationEntry], provider_configs: list[dict[str, str]]) -> None:
        total = len(request_entries)
        translated = 0
        completed = 0
        pending_by_source: dict[str, list[TranslationEntry]] = {}
        for entry in pending_entries:
            pending_by_source.setdefault(entry.source.strip(), []).append(entry)

        def apply_batch(batch: list[TranslationEntry], translations: dict[str, str]) -> int:
            count = 0
            for entry in batch:
                value = translations.get(entry.entry_id, "").strip()
                if value:
                    for related in pending_by_source.get(entry.source.strip(), [entry]):
                        if not related.target.strip():
                            related.target = value
                            count += 1
                    # 使用归一化键写入，与 _remember_translations 保持一致
                    norm_key = self._normalize_cache_key(entry.source, entry.category)
                    self.translation_memory[norm_key] = value
                    self._project_tm_keys.add(norm_key)
                    self._tm_dirty = True
            return count

        try:
            batches = self._build_token_aware_batches(request_entries)
            max_workers = min(4, max(1, len(batches)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self._request_ai_translations, batch, config["api_key"], config["model"], config["provider"], config.get("base_url", "")): (index + 1, len(batches), batch, config)
                    for index, batch in enumerate(batches)
                    for config in (provider_configs[index % len(provider_configs)],)
                }
                for future in concurrent.futures.as_completed(future_map):
                    batch_index, batch_count, batch, config = future_map[future]
                    provider_name = config["provider"]
                    self.root.after(0, lambda b=batch_index, c=batch_count, p=provider_name: self.ai_status_var.set(f"{p} 正在翻译第 {b}/{c} 批..."))
                    try:
                        translations = future.result()
                    except Exception as exc:
                        self.root.after(0, lambda b=batch_index, c=batch_count, p=provider_name, e=exc: self.ai_status_var.set(f"{p} 第 {b}/{c} 批失败，正在拆分重试：{e}"))
                        translations = self._retry_ai_batch(batch, config)
                    translated += apply_batch(batch, translations)
                    completed += len(batch)
                    progress = min(100, (completed / total) * 100)
                    self._save_project_translation_cache()
                    self.root.after(0, lambda value=progress: self.ai_progress_var.set(value))
                    self.root.after(0, self._refresh_translation_tree)
        except Exception as exc:
            self.root.after(0, lambda: self.ai_status_var.set(f"AI 翻译失败：{exc}"))
            self.root.after(0, lambda: messagebox.showerror("AI 翻译失败", str(exc)))
            self._stop_activity()
            return

        def finish() -> None:
            self.translation_map = {entry.entry_id: entry for entry in self.translation_entries}
            done = sum(1 for item in self.translation_entries if item.target.strip())
            self.translation_status_var.set(f"{len(self.translation_entries)} 条 / 已译 {done}")
            self._stop_activity()
            remembered = self._remember_translations(self.translation_entries)
            self._flush_translation_memory()
            self._refresh_translation_tree()
            self.ai_progress_var.set(100)
            self.ai_status_var.set(f"一键翻译完成：新增 {translated} 条，实际请求 {total} 条，缓存更新 {remembered} 条，当前已译 {done}/{len(self.translation_entries)}。")
            self._save_project_translation_cache()
            if self.project:
                self._append_recent_task("AI 一键翻译", self.project.root, self.project.engine)
            self._set_status_text("AI 翻译完成，译文已自动保存到当前游戏目录内的工作文件夹。")
        self.root.after(0, finish)

    def _retry_ai_batch(self, batch: list[TranslationEntry], config: dict[str, str]) -> dict[str, str]:
        if not batch:
            return {}
        if len(batch) <= 10:
            try:
                return self._request_ai_translations(batch, config["api_key"], config["model"], config["provider"], config.get("base_url", ""))
            except Exception:
                return {}
        mid = len(batch) // 2
        result: dict[str, str] = {}
        result.update(self._retry_ai_batch(batch[:mid], config))
        result.update(self._retry_ai_batch(batch[mid:], config))
        return result

    def _baidu_translate_all_worker(self, pending_entries: list[TranslationEntry], request_entries: list[TranslationEntry], appid: str, secret: str) -> None:
        total = len(request_entries)
        translated = 0
        completed = 0
        pending_by_source: dict[str, list[TranslationEntry]] = {}
        for entry in pending_entries:
            pending_by_source.setdefault(entry.source.strip(), []).append(entry)

        try:
            batches = [request_entries[start : start + 100] for start in range(0, total, 100)]
            max_workers = min(3, max(1, len(batches)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self._request_baidu_translations, batch, appid, secret): (index + 1, len(batches), batch)
                    for index, batch in enumerate(batches)
                }
                for future in concurrent.futures.as_completed(future_map):
                    batch_index, batch_count, batch = future_map[future]
                    self.root.after(0, lambda b=batch_index, c=batch_count: self.ai_status_var.set(f"正在使用百度翻译，第 {b}/{c} 批，每批最多 100 条..."))
                    try:
                        translations = future.result()
                    except Exception as exc:
                        self.root.after(0, lambda b=batch_index, c=batch_count, e=exc: self.ai_status_var.set(f"百度第 {b}/{c} 批失败，正在跳过：{e}"))
                        translations = {}
                    for entry in batch:
                        value = translations.get(entry.entry_id, "").strip()
                        if value:
                            for related in pending_by_source.get(entry.source.strip(), [entry]):
                                if not related.target.strip():
                                    related.target = value
                                    translated += 1
                            self.translation_memory[entry.source.strip()] = value
                    completed += len(batch)
                    progress = min(100, (completed / total) * 100)
                    self._save_project_translation_cache()
                    self.root.after(0, lambda value=progress: self.ai_progress_var.set(value))
                    self.root.after(0, self._refresh_translation_tree)
        except Exception as exc:
            self.root.after(0, lambda: self.ai_status_var.set(f"百度翻译失败：{exc}"))
            self.root.after(0, lambda: messagebox.showerror("百度翻译失败", str(exc)))
            self._stop_activity()
            return

        def finish() -> None:
            self.translation_map = {entry.entry_id: entry for entry in self.translation_entries}
            done = sum(1 for item in self.translation_entries if item.target.strip())
            self.translation_status_var.set(f"{len(self.translation_entries)} 条 / 已译 {done}")
            self._stop_activity()
            remembered = self._remember_translations(self.translation_entries)
            self._flush_translation_memory()
            self._refresh_translation_tree()
            self.ai_progress_var.set(100)
            self.ai_status_var.set(f"百度翻译完成：新增 {translated} 条，实际请求 {total} 条，缓存更新 {remembered} 条，当前已译 {done}/{len(self.translation_entries)}。")
            self._save_project_translation_cache()
            if self.project:
                self._append_recent_task("百度翻译", self.project.root, self.project.engine)
            self._set_status_text("百度翻译完成，译文已自动保存到当前游戏目录内的工作文件夹。")
        self.root.after(0, finish)

    def _request_ai_translations(self, entries: list[TranslationEntry], api_key: str, model: str, provider: str, base_url: str = "") -> dict[str, str]:
        key_map = {str(index): entry.entry_id for index, entry in enumerate(entries, start=1)}
        system_prompt = (
            "你是专业游戏本地化译者。只翻译真正的游戏对白、台词、选项、菜单说明或叙述文本。"
            "如果输入更像文件路径、图片名、资源名、URL、脚本代码、变量名、乱码、纯符号串、调试信息或其他非对白内容，"
            "请在对应 id 的值里返回空字符串，表示跳过，不要改写。"
            "保留控制符、变量占位符、转义符、颜色代码、换行标记和人名格式。"
            "只输出合法 JSON 对象，例如 {\"1\":\"译文\",\"2\":\"\"}。"
            "JSON 语法必须使用英文双引号、英文冒号和英文逗号；不要使用中文引号、中文冒号、书名号、数组外壳、Markdown 或解释。"
        )
        user_prompt = json.dumps(
            {
                "task": "translate_to_simplified_chinese",
                "rule": "only_translate_dialogue_like_text; return empty string for non-dialogue or garbled content",
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
        elif provider == "Xiaomi Token Plan":
            raw = self._request_xiaomi_token_plan_translations(api_key, self._normalize_xiaomi_model(model), system_prompt, user_prompt, base_url)
        elif provider == "Doubao":
            raw = self._request_doubao_translations(api_key, self._normalize_doubao_model(model), system_prompt, user_prompt)
        elif provider == "GLM":
            raw = self._request_glm_translations(api_key, model, system_prompt, user_prompt)
        elif provider == "NVIDIA":
            raw = self._request_nvidia_translations(api_key, model, system_prompt, user_prompt, base_url)
        else:
            raw = self._request_openai_translations(api_key, model, system_prompt, user_prompt)
        result: dict[str, str] = {}
        for key, value in raw.items():
            if key not in key_map:
                continue
            text = str(value).strip()
            if not text:
                continue
            source_entry = entries[int(key) - 1] if key.isdigit() and 1 <= int(key) <= len(entries) else None
            if source_entry and not self._is_likely_dialogue_text(source_entry):
                continue
            if self._looks_like_non_dialogue_translation(text):
                continue
            result[key_map[key]] = text
        return result

    @staticmethod
    def _looks_like_non_dialogue_translation(text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return True
        if any(token in lowered for token in (".png", ".jpg", ".jpeg", ".webp", ".ogg", ".wav", ".mp3", ".json", ".rpyc", ".rpa", ".exe", "http://", "https://")):
            return True
        if re.fullmatch(r"[\W_]+", lowered):
            return True
        return False

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
        parsed = self._load_llm_json(text, "OpenAI")
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
        parsed = self._load_llm_json(text, "DeepSeek")
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    def _request_doubao_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, str]:
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
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
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
            if exc.code == 404 and "InvalidEndpointOrModel.NotFound" in detail:
                detail += (
                    "\n\n提示：火山方舟 API 需要使用已开通的可调用模型 ID 或推理接入点 ID。"
                    "如果你刚才填的是控制台模型详情 ID，请改用 doubao-seed-2-0-mini-260215，"
                    "或在方舟控制台开通/创建对应推理接入点后填写接入点 ID。"
                )
            raise RuntimeError(f"Doubao API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("无法从 Doubao 响应中读取文本。")
        parsed = self._load_llm_json(text, "Doubao")
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _normalize_doubao_model(model: str) -> str:
        aliases = {
            "doubao-seed-2-0-mini": "doubao-seed-2-0-mini-260215",
            "doubao-seed-2-0-lite": "doubao-seed-2-0-lite-260215",
            "doubao-seed-2-0-pro": "doubao-seed-2-0-pro-260215",
        }
        return aliases.get(model.strip(), model.strip())

    def _request_glm_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, str]:
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
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
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
            raise RuntimeError(f"GLM API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("无法从 GLM 响应中读取文本。")
        parsed = self._load_llm_json(text, "GLM")
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    def _request_nvidia_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str, base_url: str = "") -> dict[str, str]:
        endpoint = self._nvidia_chat_completions_url(base_url)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 1,
            "top_p": 0.95,
            "max_tokens": 8192,
            "stream": False,
        }
        request = urllib.request.Request(
            endpoint,
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
            raise RuntimeError(f"NVIDIA API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("无法从 NVIDIA 响应中读取文本。")
        parsed = self._load_llm_json(text, "NVIDIA")
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    def _request_xiaomi_token_plan_translations(self, api_key: str, model: str, system_prompt: str, user_prompt: str, base_url: str = "") -> dict[str, str]:
        endpoint = self._chat_completions_url(base_url or self._default_ai_base_url("Xiaomi Token Plan"))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "top_p": 0.95,
            "max_tokens": 8192,
            "stream": False,
        }
        try:
            return self._request_xiaomi_chat_payload(endpoint, api_key, payload)
        except RuntimeError as exc:
            if "400" not in str(exc) and "response_format" not in str(exc):
                raise
            fallback_payload = dict(payload)
            fallback_payload.pop("response_format", None)
            return self._request_xiaomi_chat_payload(endpoint, api_key, fallback_payload)

    def _request_xiaomi_chat_payload(self, endpoint: str, api_key: str, payload: dict) -> dict[str, str]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Xiaomi Token Plan API 返回错误：{exc.code}\n{detail}") from exc
        payload = json.loads(raw)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("无法从 Xiaomi Token Plan 响应中读取文本。")
        parsed = self._load_llm_json(text, "Xiaomi Token Plan")
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 返回内容不是 JSON 对象。")
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _normalize_xiaomi_model(model: str) -> str:
        aliases = {
            "MiMo-V2.5-Pro": "mimo-v2.5-pro",
            "MiMo-V2.5": "mimo-v2.5",
            "MiMo-V2-Pro": "mimo-v2-pro",
            "MiMo-V2-Omni": "mimo-v2-omni",
            "MiMo-V2.5-TTS": "mimo-v2.5-tts",
            "mimo-v2.5-tts-voiceclone": "mimo-v2.5-tts",
            "mimo-v2.5-tts-voicedesign": "mimo-v2.5-tts",
        }
        return aliases.get(model.strip(), model.strip())

    def _nvidia_chat_completions_url(self, base_url: str = "") -> str:
        base_url = base_url.strip() or self.ai_base_url_var.get().strip() or self._default_ai_base_url("NVIDIA")
        return self._chat_completions_url(base_url)

    @staticmethod
    def _chat_completions_url(base_url: str = "") -> str:
        base_url = base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _request_baidu_translations(self, entries: list[TranslationEntry], appid: str, secret: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for index, entry in enumerate(entries, start=1):
            query = entry.source.strip()
            salt = str(int(datetime.utcnow().timestamp() * 1000))
            sign = hashlib.md5(f"{appid}{query}{salt}{secret}".encode("utf-8")).hexdigest()
            params = urllib.parse.urlencode(
                {
                    "q": query,
                    "from": "auto",
                    "to": "zh",
                    "appid": appid,
                    "salt": salt,
                    "sign": sign,
                }
            )
            request = urllib.request.Request(f"https://fanyi-api.baidu.com/api/trans/vip/translate?{params}", method="GET")
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"百度翻译返回错误：{exc.code}\n{detail}") from exc
            payload = json.loads(raw)
            if "error_code" in payload:
                raise RuntimeError(f"百度翻译错误：{payload.get('error_code')} {payload.get('error_msg', '')}")
            items = payload.get("trans_result", [])
            if items:
                result[str(index)] = items[0].get("dst", "")
        return result

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

    @staticmethod
    def _load_llm_json(text: str, provider: str) -> dict:
        candidate = text.strip()
        if not candidate:
            raise RuntimeError(f"{provider} 没有返回可解析内容。")
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate).strip()
        try:
            parsed = json.loads(candidate)
        except JSONDecodeError as exc:
            extracted = ToolkitApp._extract_json_object(candidate)
            if extracted is None:
                repaired = ToolkitApp._parse_llm_loose_json(candidate)
                if repaired:
                    return repaired
                raise RuntimeError(f"{provider} 返回的不是有效 JSON：{exc}\n原始内容前 400 字符：{candidate[:400]}") from exc
            try:
                parsed = json.loads(extracted)
            except JSONDecodeError as inner_exc:
                repaired = ToolkitApp._parse_llm_loose_json(extracted) or ToolkitApp._parse_llm_loose_json(candidate)
                if repaired:
                    return repaired
                raise RuntimeError(f"{provider} 返回了疑似 JSON，但仍无法解析：{inner_exc}\n原始内容前 400 字符：{candidate[:400]}") from inner_exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{provider} 返回内容不是 JSON 对象。")
        return parsed

    @staticmethod
    def _parse_llm_loose_json(text: str) -> dict[str, str]:
        normalized = (
            text.strip()
            .replace("```json", "")
            .replace("```", "")
            .replace("【", "{")
            .replace("】", "}")
            .replace("：", ":")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", '"')
            .replace("’", '"')
            .replace("❤", "\\u2764")
        )
        result: dict[str, str] = {}
        for raw_line in normalized.splitlines():
            line = raw_line.strip().strip(",，{}[]")
            if not line:
                continue
            match = re.match(r'^"?(\d+)[^:]*:\s*"?(.*?)"?\s*[,，]?$', line)
            if not match:
                match = re.match(r'^"?(\d+)(?:["\'*:\s]+)+(.*?)"?\s*[,，]?$', line)
            if match:
                value = match.group(2).strip().strip('",，')
                if value:
                    result[match.group(1)] = value.replace("\\u2764", "❤")
        repaired = ToolkitApp._repair_loose_json_object(normalized.replace("，", ","))
        result.update({key: value for key, value in repaired.items() if key not in result})
        return result

    @staticmethod
    def _repair_loose_json_object(text: str) -> dict[str, str]:
        body = text.strip()
        start = body.find("{")
        end = body.rfind("}")
        if start >= 0 and end > start:
            body = body[start + 1 : end]
        entries: list[str] = []
        current: list[str] = []
        in_string = False
        escaped = False
        for char in body:
            if escaped:
                current.append(char)
                escaped = False
                continue
            if char == "\\":
                current.append(char)
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                current.append(char)
                continue
            if char == "," and not in_string:
                item = "".join(current).strip()
                if item:
                    entries.append(item)
                current = []
                continue
            current.append(char)
        item = "".join(current).strip()
        if item:
            entries.append(item)

        result: dict[str, str] = {}
        for entry in entries:
            match = re.match(r'^"?(\d+)[^0-9":,]*"?\s*:\s*(.*)$', entry.strip())
            if not match:
                continue
            key = match.group(1)
            value = match.group(2).strip().strip(",")
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            value = value.strip()
            if value:
                result[key] = value.replace("\\u2764", "❤")
        return result

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        return text[start : end + 1]

    def update_translation_target(self) -> None:
        selection = self.translation_tree.selection()
        if not selection:
            messagebox.showerror("错误", "请先选择一条文本。")
            return
        if selection[0] == "__notice__":
            messagebox.showinfo("提示", "请先选择一条真实文本。")
            return
        entry_id = self.translation_view_id_map.get(selection[0], selection[0])
        entry = self.translation_map[entry_id]
        entry.target = self._target_editor_value()
        self.target_var.set(entry.target)
        self.translation_tree.item(selection[0], values=(self._translation_category_label(entry.category), entry.file, entry.context, entry.source, entry.target))
        self.translation_detail_var.set(f"{entry.file}\n{entry.context}\n原文：{entry.source}")
        self._save_project_translation_cache()

    def copy_source_to_target(self) -> None:
        selection = self.translation_tree.selection()
        if selection and selection[0] != "__notice__":
            entry_id = self.translation_view_id_map.get(selection[0], selection[0])
            self._set_target_editor(self.translation_map[entry_id].source)

    def _set_target_editor(self, value: str) -> None:
        self.target_var.set(value)
        if hasattr(self, "target_text"):
            self.target_text.delete("1.0", "end")
            self.target_text.insert("1.0", value)

    def _target_editor_value(self) -> str:
        if hasattr(self, "target_text"):
            return self.target_text.get("1.0", "end-1c")
        return self.target_var.get()

    def _clear_target_editor(self) -> None:
        self._set_target_editor("")

    def _selected_translation_entries(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        for item_id in self.translation_tree.selection():
            if item_id == "__notice__":
                continue
            entry_id = self.translation_view_id_map.get(item_id, item_id)
            entry = self.translation_map.get(entry_id)
            if entry:
                entries.append(entry)
        return entries

    def select_visible_translations(self) -> None:
        item_ids = [item_id for item_id in self.translation_tree.get_children() if item_id != "__notice__"]
        if not item_ids:
            messagebox.showinfo("提示", "当前筛选条件下没有可选择的文本。")
            return
        self.translation_tree.selection_set(item_ids)
        self.translation_tree.focus(item_ids[0])
        self.translation_tree.see(item_ids[0])
        self.translation_detail_var.set(f"已选择当前显示的 {len(item_ids)} 条文本。可点击“翻译选中”只翻译这些条目。")

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
            self._set_data_notice("请先选择或拖入游戏 exe。")
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
        project = self.project
        self.data_status_var.set("读取中...")
        threading.Thread(target=self._load_data_records_worker, args=(project, silent), daemon=True).start()

    def _load_data_records_worker(self, project: ProjectInfo, silent: bool) -> None:
        try:
            service = self._service_for_project(project)
            records = service.list_data_records() if hasattr(service, "list_data_records") else []
        except Exception as exc:
            self.root.after(0, lambda err=exc, s=silent: self._handle_data_records_error(err, s))
            return
        self.root.after(0, lambda r=records, p=project: self._finish_load_data_records(r, p))

    def _handle_data_records_error(self, exc: Exception, silent: bool) -> None:
        self.data_records = []
        self.data_record_map = {}
        self.data_object_map = {}
        self.data_status_var.set("读取失败")
        self._set_data_notice(f"数据读取失败：{exc}")
        if not silent:
            messagebox.showerror("读取失败", str(exc))

    def _finish_load_data_records(self, records: list[DataRecord], project: ProjectInfo) -> None:
        if not self.project or self.project.root != project.root:
            return
        self.data_records = records
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
        project = self.project
        self.save_status_var.set("正在扫描存档...")
        threading.Thread(target=self._refresh_save_slots_worker, args=(project, silent), daemon=True).start()

    def _refresh_save_slots_worker(self, project: ProjectInfo, silent: bool) -> None:
        try:
            service = self._service_for_project(project)
            slots = service.list_save_slots() if hasattr(service, "list_save_slots") else []
        except Exception as exc:
            self.root.after(0, lambda err=exc, s=silent: self._handle_save_slots_error(err, s))
            return
        self.root.after(0, lambda s=slots, p=project: self._finish_refresh_save_slots(s, p))

    def _handle_save_slots_error(self, exc: Exception, silent: bool) -> None:
        self.save_slots = []
        self.save_status_var.set(f"读取存档失败：{exc}")
        if not silent:
            messagebox.showerror("读取存档失败", str(exc))

    def _finish_refresh_save_slots(self, slots: list[SaveSlot], project: ProjectInfo) -> None:
        if not self.project or self.project.root != project.root:
            return
        self.save_slots = slots
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
            self._ensure_runtime_bridge_matches_project()
            self.runtime_state = self._runtime_request("GET", "/state", timeout=4.5)
            self.runtime_connected = True
        except Exception as exc:
            self.runtime_connected = False
            self.runtime_status_var.set("实时桥接未连接")
            if not silent:
                messagebox.showinfo("未连接", self._runtime_error_message(exc))
            return
        self._populate_runtime_views()
        state_map = self.runtime_state.get("map", {}) if self.runtime_state else {}
        self.runtime_status_var.set(f"已连接实时游戏：金币 {self.runtime_state.get('gold', 0)}，地图 {state_map.get('id', 0)} ({state_map.get('x', 0)}, {state_map.get('y', 0)})")
        self.map_status_var.set(f"当前地图：{state_map.get('id', 0)} {state_map.get('name', '')} ({state_map.get('x', 0)}, {state_map.get('y', 0)})")
        self._sync_map_view_to_runtime()
        self._start_runtime_map_poll()

    def _start_runtime_map_poll(self) -> None:
        if self._runtime_poll_after_id:
            try:
                self.root.after_cancel(self._runtime_poll_after_id)
            except tk.TclError:
                pass
        self._runtime_poll_after_id = self.root.after(1200, self._poll_runtime_map_state)

    def _poll_runtime_map_state(self) -> None:
        self._runtime_poll_after_id = None
        if self.current_section == "maps" and self.runtime_connected:
            try:
                state = self._runtime_request("GET", "/state", timeout=2.5)
            except Exception:
                self._runtime_poll_after_id = self.root.after(2200, self._poll_runtime_map_state)
                return
            self.runtime_state = state
            self._populate_runtime_views()
            self._sync_map_view_to_runtime()
        self._runtime_poll_after_id = self.root.after(2200, self._poll_runtime_map_state)

    def _runtime_request(self, method: str, path: str, payload: dict | None = None, timeout: float = 3.5) -> dict:
        url = f"http://127.0.0.1:32179{path}"
        data = json.dumps(payload or {}).encode("utf-8") if method == "POST" else None
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
        last_error: Exception | None = None
        for current_timeout in (min(1.5, timeout), timeout):
            try:
                with urllib.request.urlopen(request, timeout=current_timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except Exception as exc:
                last_error = exc
                time.sleep(0.12)
        else:
            raise last_error or RuntimeError("runtime bridge timeout")
        if not result.get("ok", True):
            raise RuntimeError(result.get("error", "runtime bridge error"))
        return result

    def _ensure_runtime_bridge_matches_project(self) -> None:
        if not self.project or self.project.engine != "RPG Maker MV/MZ":
            return
        info = self._runtime_request("GET", "/ping", timeout=2.5)
        root = str(info.get("root") or "")
        self.runtime_bridge_root = root
        try:
            self.runtime_bridge_pid = int(info.get("pid") or 0) or None
        except (TypeError, ValueError):
            self.runtime_bridge_pid = None
        if not root:
            return
        try:
            bridge_root = Path(root).resolve()
            project_root = self.project.root.resolve()
            candidates = {project_root}
            if self.project.game_dir:
                candidates.add(self.project.game_dir.resolve())
            if self.project.data_dir:
                candidates.add(self.project.data_dir.resolve().parent)
        except Exception:
            return
        bridge_text = os.path.normcase(str(bridge_root))
        for candidate in candidates:
            candidate_text = os.path.normcase(str(candidate))
            if bridge_text == candidate_text or bridge_text.startswith(candidate_text + os.sep):
                return
        pid_text = f"（PID {self.runtime_bridge_pid}）" if self.runtime_bridge_pid else ""
        raise RuntimeError(f"实时端口被其他游戏占用{pid_text}：{bridge_root}\n当前项目：{project_root}")

    @staticmethod
    def _runtime_error_message(exc: Exception) -> str:
        text = str(exc)
        if "timed out" in text.lower():
            return (
                f"无法连接当前游戏实时组件：{exc}\n\n"
                "这通常是游戏还没完全进入地图、旧游戏实例占用了实时端口，或实时插件正在启动但还没响应。\n"
                "请先等游戏进入可操作画面；如果仍失败，请关闭旧的 RPG Maker 游戏窗口，再从本工具重新启动当前游戏。"
            )
        if "其他游戏占用" in text:
            return f"{text}\n\n请关闭旧游戏窗口，然后重新从本工具启动当前游戏。"
        return f"无法连接当前游戏实时组件：{exc}\n\n请先安装实时组件并重启游戏。"

    def _populate_runtime_views(self) -> None:
        if not self.runtime_state:
            return
        self._syncing_runtime_vars = True
        try:
            for tree in (self.save_items_tree, self.save_actors_tree, self.save_switches_tree, self.save_variables_tree):
                for item in tree.get_children():
                    tree.delete(item)
            self.save_gold_var.set(str(self.runtime_state.get("gold", 0)))
            map_info = self.runtime_state.get("map", {})
            self.player_through_var.set(bool(map_info.get("through", False)))
            options = self.runtime_state.get("options", {})
            if isinstance(options, dict):
                self.game_speed_var.set(str(options.get("gameSpeed", self.game_speed_var.get())))
                self.move_speed_var.set(str(options.get("moveSpeed", self.move_speed_var.get())))
                self.battle_speed_var.set(str(options.get("battleSpeed", self.battle_speed_var.get())))
                self.auto_save_interval_var.set(str(options.get("autoSaveInterval", self.auto_save_interval_var.get())))
                self.font_size_var.set(str(options.get("fontSize", self.font_size_var.get())))
                self.god_mode_var.set(bool(options.get("godMode", False)))
                self.auto_battle_var.set(bool(options.get("autoBattle", False)))
                self.unlock_cg_var.set(bool(options.get("unlockCg", False)))
                self.fps_boost_var.set(bool(options.get("fpsBoost", False)))
            if self.project and self.project.data_dir:
                runtime_counts = self._runtime_item_count_map()
                for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
                    db = load_json(self.project.data_dir / file_name)
                    if not isinstance(db, list):
                        continue
                    for item in db:
                        if not isinstance(item, dict) or not item.get("id"):
                            continue
                        item_id = int(item["id"])
                        self.save_items_tree.insert("", "end", iid=f"rt:{kind}:{item_id}", values=(kind, item_id, item.get("name", ""), runtime_counts.get((kind, item_id), 0)))
            else:
                for kind in ("items", "weapons", "armors"):
                    for item in self.runtime_state.get(kind, []):
                        self.save_items_tree.insert("", "end", iid=f"rt:{kind}:{item.get('id')}", values=(kind, item.get("id"), item.get("name", ""), item.get("count", 0)))
            for actor in self.runtime_state.get("actors", []):
                self.save_actors_tree.insert("", "end", iid=str(actor.get("id")), values=(actor.get("id"), actor.get("name", ""), actor.get("level", ""), actor.get("hp", ""), actor.get("mp", ""), actor.get("tp", "")))
            for switch in self.runtime_state.get("switches", []):
                self.save_switches_tree.insert("", "end", iid=str(switch.get("id")), values=(switch.get("id"), switch.get("name", ""), switch.get("value", False)))
            for variable in self.runtime_state.get("variables", []):
                self.save_variables_tree.insert("", "end", iid=str(variable.get("id")), values=(variable.get("id"), variable.get("name", ""), variable.get("value", 0)))
        finally:
            self._syncing_runtime_vars = False

    def _runtime_set(self, payload: dict) -> bool:
        try:
            self._ensure_runtime_bridge_matches_project()
            self.runtime_state = self._runtime_request("POST", "/set", payload, timeout=4.5)
            self.runtime_connected = True
            self._populate_runtime_views()
            return True
        except Exception as exc:
            self.runtime_connected = False
            self.runtime_status_var.set("实时桥接未连接")
            messagebox.showinfo("未连接", f"实时写入失败：\n\n{self._runtime_error_message(exc)}")
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

    def create_manual_save_backup(self) -> None:
        copied = self._backup_current_save("manual")
        if copied:
            self.auto_backup_status_var.set(f"已备份：{copied.name}")
            self.refresh_backups()
            self._set_status_text(f"已备份当前存档到：{copied}")

    def toggle_auto_backup(self) -> None:
        if self._auto_backup_after_id:
            try:
                self.root.after_cancel(self._auto_backup_after_id)
            except tk.TclError:
                pass
            self._auto_backup_after_id = None
            self.auto_backup_status_var.set("自动备份已关闭")
            return
        self._schedule_save_auto_backup(run_now=True)

    def _schedule_save_auto_backup(self, run_now: bool = False) -> None:
        try:
            minutes = max(1, int(float(self.auto_save_interval_var.get() or 3)))
        except ValueError:
            minutes = 3
        if run_now:
            copied = self._backup_current_save("auto")
            if copied:
                self.auto_backup_status_var.set(f"自动备份已开启：每 {minutes} 分钟，最近 {copied.name}")
            else:
                self.auto_backup_status_var.set(f"自动备份已开启：每 {minutes} 分钟，等待可用存档")
        self._auto_backup_after_id = self.root.after(minutes * 60 * 1000, self._run_scheduled_save_backup)

    def _run_scheduled_save_backup(self) -> None:
        self._auto_backup_after_id = None
        copied = self._backup_current_save("auto")
        try:
            minutes = max(1, int(float(self.auto_save_interval_var.get() or 3)))
        except ValueError:
            minutes = 3
        if copied:
            self.auto_backup_status_var.set(f"自动备份运行中：每 {minutes} 分钟，最近 {copied.name}")
            self.refresh_backups()
        else:
            self.auto_backup_status_var.set(f"自动备份运行中：每 {minutes} 分钟，未找到可备份存档")
        self._schedule_save_auto_backup(run_now=False)

    def _backup_current_save(self, mode: str) -> Path | None:
        if not self.project:
            messagebox.showinfo("提示", "请先加载 RPG Maker 项目。")
            return None
        slot = self._selected_save_slot()
        save_path = self.current_save_path or (slot.path if slot else None)
        if not save_path or not save_path.exists():
            messagebox.showinfo("提示", "没有找到可备份的当前存档。请先选择或读取一个存档。")
            return None
        backup_dir = self.project.root / ".rpgrtl_backup" / ("save_auto" if mode == "auto" else "save_manual")
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"{save_path.name}.{stamp}.bak"
        shutil.copy2(save_path, target)
        return target

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
            amount = int(self.item_amount_var.get() or 99)
            for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
                data = load_json(self.project.data_dir / file_name)
                for item in data:
                    if isinstance(item, dict) and item.get("id"):
                        payload[kind][str(item["id"])] = amount
            if self._runtime_set(payload):
                return
        if not self._ensure_save_loaded():
            return
        service = self._get_service()
        for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
            data = load_json(self.project.data_dir / file_name) if self.project and self.project.data_dir else []
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    service.set_save_item(self.save_payload, kind, int(item["id"]), int(self.item_amount_var.get() or 99))
        self._refresh_save_views()
        self.save_current_save()

    def _on_save_item_edit(self, _event: object | None = None) -> None:
        selection = self.save_items_tree.selection()
        if not selection:
            return
        parts = selection[0].split(":")
        if len(parts) == 3 and parts[0] == "rt":
            _, kind, item_id = parts
        else:
            kind, item_id = parts[:2]
        old = self.save_items_tree.item(selection[0], "values")[3]
        value = self._ask_value("修改数量", "请输入新的数量：", old)
        if value is None:
            return
        if self._runtime_set({kind: {str(item_id): int(value)}}):
            return
        if not self._ensure_save_loaded():
            return
        self._get_service().set_save_item(self.save_payload, kind, int(item_id), int(value))
        self._refresh_save_views()

    def apply_data_runtime_item_count(self) -> None:
        if not self.selected_data_runtime_item:
            messagebox.showinfo("提示", "请在数据编辑器里选择 Items / Weapons / Armors 条目。")
            return
        try:
            value = int(self.data_runtime_count_var.get() or 0)
        except ValueError:
            messagebox.showerror("错误", "持有数量必须是整数。")
            return
        kind, item_id = self.selected_data_runtime_item
        if self._runtime_set({kind: {str(item_id): value}}):
            self._refresh_data_tree()
            self._set_status_text(f"已把当前游戏中的 {kind} #{item_id} 数量改为 {value}。")

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

    def apply_runtime_options(self) -> None:
        payload = {
            "options": {
                "gameSpeed": self._clamped_float(self.game_speed_var.get(), 1, 16, 1),
                "moveSpeed": self._clamped_float(self.move_speed_var.get(), 0, 6, 0),
                "battleSpeed": self._clamped_float(self.battle_speed_var.get(), 1, 16, 1),
                "autoBattle": self.auto_battle_var.get(),
                "godMode": self.god_mode_var.get(),
                "autoSaveInterval": self._clamped_float(self.auto_save_interval_var.get(), 0, 999, 0) * 60,
                "unlockCg": self.unlock_cg_var.get(),
                "fontSize": self._clamped_float(self.font_size_var.get(), 0, 96, 0),
                "fpsBoost": self.fps_boost_var.get(),
            }
        }
        self._runtime_set(payload)

    def apply_exp_rate_to_party(self) -> None:
        if not self.runtime_state or not self.runtime_state.get("actors"):
            self.refresh_runtime_state(silent=True)
            if not self.runtime_state:
                return
        rate = self._clamped_float(self.exp_rate_var.get(), 0, 999, 1)
        actors: dict[str, dict[str, int]] = {}
        for actor in self.runtime_state.get("actors", []):
            actor_id = actor.get("id")
            exp = actor.get("exp")
            if actor_id and exp is not None:
                actors[str(actor_id)] = {"exp": int(float(exp) * rate)}
        if actors:
            self._runtime_set({"actors": actors})

    def teleport_to_mouse(self) -> None:
        self._runtime_set({"player": {"teleport": {"x": "mouse", "y": "mouse"}}})

    @staticmethod
    def _clamped_float(value: str, minimum: float, maximum: float, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, min(maximum, number))

    def _on_save_switch_edit(self, _event: object | None = None) -> None:
        selection = self.save_switches_tree.selection()
        if not selection:
            return
        switch_id = int(selection[0])
        old = self.save_switches_tree.item(selection[0], "values")[2]
        value = old not in {"True", "true", "1", "开启"}
        if self._runtime_set({"switches": {str(switch_id): value}}):
            return
        if not self._ensure_save_loaded():
            return
        self._get_service().set_save_switch(self.save_payload, switch_id, value)
        self._refresh_save_views()

    def _on_save_variable_edit(self, _event: object | None = None) -> None:
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
        if not self._ensure_save_loaded():
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
        self._select_current_or_first_map()

    def _refresh_save_views(self) -> None:
        if self.save_payload is None or not self.project or not self.project.data_dir:
            return
        service = self._get_service()
        summary = service.save_summary(self.save_payload) if hasattr(service, "save_summary") else {}
        self.save_gold_var.set(str(summary.get("gold", 0)))
        self._populate_save_trees()

    def _runtime_item_count_map(self) -> dict[tuple[str, int], int]:
        counts: dict[tuple[str, int], int] = {}
        if not self.runtime_state:
            return counts
        for kind in ("items", "weapons", "armors"):
            for item in self.runtime_state.get(kind, []):
                try:
                    counts[(kind, int(item.get("id") or 0))] = int(item.get("count", 0) or 0)
                except Exception:
                    continue
        return counts

    @staticmethod
    def _data_runtime_item_key(records: list[DataRecord]) -> tuple[str, int] | None:
        if not records:
            return None
        first = records[0]
        kind_map = {
            "Items.json": "items",
            "Weapons.json": "weapons",
            "Armors.json": "armors",
        }
        kind = kind_map.get(first.file)
        if not kind:
            return None
        try:
            item_id = int(first.object_id.rsplit(":", 1)[-1])
        except (TypeError, ValueError):
            return None
        return kind, item_id

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
        if self.runtime_state:
            runtime_counts = self._runtime_item_count_map()
            for kind, file_name in (("items", "Items.json"), ("weapons", "Weapons.json"), ("armors", "Armors.json")):
                db = load_json(data_dir / file_name)
                if not isinstance(db, list):
                    continue
                for item in db:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    item_id = int(item["id"])
                    self.save_items_tree.insert("", "end", iid=f"rt:{kind}:{item_id}", values=(kind, item_id, item.get("name", ""), runtime_counts.get((kind, item_id), 0)))
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

    def _select_current_or_first_map(self) -> None:
        tree = getattr(self, "map_tree", None)
        if not tree or not self.map_records:
            return
        current_id = 0
        if self.runtime_state and self.runtime_state.get("map"):
            current_id = int(self.runtime_state["map"].get("id") or 0)
        target = str(current_id) if current_id else str(self.map_records[0].map_id)
        if not tree.exists(target):
            target = str(self.map_records[0].map_id)
        tree.selection_set(target)
        tree.focus(target)
        tree.see(target)
        self._load_map_detail(int(target))

    def _sync_map_view_to_runtime(self) -> None:
        if not self.runtime_state:
            return
        state_map = self.runtime_state.get("map", {})
        map_id = int(state_map.get("id") or 0)
        if not map_id:
            return
        tree = getattr(self, "map_tree", None)
        if tree and tree.exists(str(map_id)) and tree.selection() != (str(map_id),):
            tree.selection_set(str(map_id))
            tree.focus(str(map_id))
            tree.see(str(map_id))
        if self.map_detail and self.map_detail.record.map_id == map_id:
            self.map_detail_var.set(
                f"{self.map_detail.record.map_id}: {self.map_detail.record.name} / {self.map_detail.record.display_name} | "
                f"{self.map_detail.record.width}x{self.map_detail.record.height} | 事件 {len(self.map_detail.events)} | "
                f"玩家当前位置 ({state_map.get('x', 0)}, {state_map.get('y', 0)})"
            )
            self._draw_map_canvas()
        elif tree and tree.exists(str(map_id)) and self.map_detail and self.map_detail.record.map_id != map_id:
            self._load_map_detail(map_id)

    def _on_map_select(self, _event: object | None = None) -> None:
        tree = getattr(self, "map_tree", None)
        if not tree:
            return
        selection = tree.selection()
        if selection:
            self._load_map_detail(int(selection[0]))

    def _load_map_detail(self, map_id: int) -> None:
        if not self.project or self.project.engine != "RPG Maker MV/MZ":
            return
        service = self._get_service()
        if not hasattr(service, "map_detail"):
            return
        try:
            self.map_detail = service.map_detail(map_id)
        except Exception as exc:
            self.map_detail = None
            self.map_detail_var.set(f"地图详情读取失败：{exc}")
            return
        record = self.map_detail.record
        current = self.runtime_state.get("map", {}) if self.runtime_state else {}
        suffix = ""
        if int(current.get("id") or 0) == map_id:
            suffix = f" | 玩家当前位置 ({current.get('x', 0)}, {current.get('y', 0)})"
        self.map_detail_var.set(f"{record.map_id}: {record.name} / {record.display_name} | {record.width}x{record.height} | 事件 {len(self.map_detail.events)}{suffix}")
        self._draw_map_canvas()
        if int(current.get("id") or 0) == map_id:
            start_x = int(current.get("x") or 0)
            start_y = int(current.get("y") or 0)
        else:
            start_x, start_y = 0, 0
        self._show_map_tile_detail(start_x, start_y)

    def _draw_map_canvas(self) -> None:
        canvas = getattr(self, "map_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        detail = self.map_detail
        if not detail:
            return
        width = max(1, detail.record.width)
        height = max(1, detail.record.height)
        tile = max(8, min(24, int(640 / max(width, height, 1))))
        self.map_tile_size = tile
        event_positions = {(event.x, event.y) for event in detail.events}
        transfer_positions = {(event.x, event.y) for event in detail.events if event.transfers}
        tile_map = {(item.x, item.y): item for item in detail.tiles}
        current = self.runtime_state.get("map", {}) if self.runtime_state else {}
        current_pos = (int(current.get("x") or -1), int(current.get("y") or -1)) if int(current.get("id") or 0) == detail.record.map_id else None
        for y in range(height):
            for x in range(width):
                item = tile_map.get((x, y))
                color = "#d9ead3" if not item or item.passable else "#4b5563"
                if (x, y) in event_positions:
                    color = "#f6d365"
                if (x, y) in transfer_positions:
                    color = "#65c7f7"
                if current_pos == (x, y):
                    color = "#ff5a5f"
                x1 = x * tile
                y1 = y * tile
                canvas.create_rectangle(x1, y1, x1 + tile, y1 + tile, fill=color, outline="#1f2937")
                if detail.record.width <= 64 and detail.record.height <= 64:
                    if (x, y) in transfer_positions:
                        canvas.create_text(x1 + tile / 2, y1 + tile / 2, text="T", fill="#063970", font=("Segoe UI", max(7, tile // 2), "bold"))
                    elif (x, y) in event_positions:
                        canvas.create_text(x1 + tile / 2, y1 + tile / 2, text="E", fill="#563a00", font=("Segoe UI", max(7, tile // 2), "bold"))
                    elif current_pos == (x, y):
                        canvas.create_text(x1 + tile / 2, y1 + tile / 2, text="P", fill="#ffffff", font=("Segoe UI", max(7, tile // 2), "bold"))
        if self.map_selected_tile:
            sx, sy = self.map_selected_tile
            if 0 <= sx < width and 0 <= sy < height:
                x1 = sx * tile
                y1 = sy * tile
                canvas.create_rectangle(x1 + 1, y1 + 1, x1 + tile - 1, y1 + tile - 1, outline="#ffffff", width=3)
        canvas.configure(scrollregion=(0, 0, width * tile, height * tile))

    def _on_map_canvas_click(self, event: tk.Event) -> None:
        detail = self.map_detail
        if not detail:
            return
        canvas = self.map_canvas
        x = int(canvas.canvasx(event.x) // self.map_tile_size)
        y = int(canvas.canvasy(event.y) // self.map_tile_size)
        if 0 <= x < detail.record.width and 0 <= y < detail.record.height:
            self._show_map_tile_detail(x, y)

    def _show_map_tile_detail(self, x: int, y: int) -> None:
        text = getattr(self, "map_tile_detail", None)
        if not text:
            return
        text.configure(state="normal")
        text.delete("1.0", "end")
        detail = self.map_detail
        if not detail:
            text.configure(state="disabled")
            return
        self.map_selected_tile = (x, y)
        self._draw_map_canvas()
        tile = next((item for item in detail.tiles if item.x == x and item.y == y), None)
        self._clear_map_switch_actions()
        switch_ids: set[int] = set()
        lines = [
            f"坐标 ({x}, {y})",
            f"通行：{'可走' if not tile or tile.passable else '墙/不可通行'}",
            f"格子内容：事件 {tile.event_count if tile else 0} 个，传送 {tile.transfer_count if tile else 0} 个",
        ]
        events = [event for event in detail.events if event.x == x and event.y == y]
        if not events:
            lines.append("事件：无")
        for event in events:
            lines.append("")
            lines.append(f"EV{event.event_id:03d}: {event.name}（{event.command_count} 行，{event.page_count} 页）")
            self._add_map_event_detail_action(event)
            for condition in event.conditions:
                lines.append(f"触发条件：{condition}")
                if condition not in switch_ids:
                    self._add_map_condition_action(condition)
                    match = re.search(r"开关\s+(\d+)\s+ON", condition)
                    if match:
                        switch_ids.add(int(match.group(1)))
            for transfer in event.transfers:
                lines.append(f"传送：{transfer}")
            for command in event.commands:
                lines.append(f"命令：{command}")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def _clear_map_switch_actions(self) -> None:
        frame = getattr(self, "map_switch_actions", None)
        if not frame:
            return
        for child in frame.winfo_children():
            child.destroy()

    def _add_map_condition_action(self, condition: str) -> None:
        frame = getattr(self, "map_switch_actions", None)
        if not frame:
            return
        match = re.search(r"开关\s+(\d+)\s+ON", condition)
        if not match:
            return
        switch_id = int(match.group(1))
        current = self._runtime_switch_value(switch_id)
        name = self._runtime_switch_name(switch_id)
        label = f"{name}: {'ON' if current else 'OFF'}"
        ttk.Button(frame, text=label, command=lambda sid=switch_id: self._toggle_map_switch(sid)).pack(side="left", padx=(0, 8), pady=(0, 6))

    def _add_map_event_detail_action(self, event: MapEventInfo) -> None:
        frame = getattr(self, "map_switch_actions", None)
        if not frame:
            return
        ttk.Button(frame, text=f"查看 EV{event.event_id:03d}", command=lambda e=event: self._show_map_event_detail_dialog(e)).pack(side="left", padx=(0, 8), pady=(0, 6))

    def _show_map_event_detail_dialog(self, event: MapEventInfo) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"EV{event.event_id:03d} {event.name}")
        dialog.transient(self.root)
        dialog.geometry("560x420")
        content = tk.Text(dialog, wrap="word", font=("Microsoft YaHei UI", 10))
        scroll = ttk.Scrollbar(dialog, orient="vertical", command=content.yview)
        content.configure(yscrollcommand=scroll.set)
        content.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        lines = [
            f"EV{event.event_id:03d}: {event.name}",
            f"坐标：({event.x}, {event.y})",
            f"事件页：{event.page_count}",
            f"命令行：{event.command_count}",
            "",
            "触发条件：",
            *(event.conditions or ["无"]),
            "",
            "传送：",
            *(event.transfers or ["无"]),
            "",
            "命令摘要：",
            *(event.commands or ["无"]),
        ]
        content.insert("1.0", "\n".join(lines))
        content.configure(state="disabled")

    def _runtime_switch_value(self, switch_id: int) -> bool:
        if not self.runtime_state:
            return False
        for item in self.runtime_state.get("switches", []):
            try:
                if int(item.get("id") or 0) == switch_id:
                    return bool(item.get("value"))
            except Exception:
                continue
        return False

    def _runtime_switch_name(self, switch_id: int) -> str:
        if self.runtime_state:
            for item in self.runtime_state.get("switches", []):
                try:
                    if int(item.get("id") or 0) == switch_id:
                        name = str(item.get("name") or "").strip()
                        return f"开关 {switch_id} {name}" if name else f"开关 {switch_id}"
                except Exception:
                    continue
        return f"开关 {switch_id}"

    def _toggle_map_switch(self, switch_id: int) -> None:
        value = not self._runtime_switch_value(switch_id)
        if self._runtime_set({"switches": {str(switch_id): value}}):
            if self.map_selected_tile:
                self._show_map_tile_detail(*self.map_selected_tile)

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
                messagebox.showerror("错误", "请先选择游戏 exe。")
                return
        launcher = self.project.launcher_path
        if not launcher or not launcher.exists():
            fallback = Path(self.path_var.get().strip()) if self.path_var.get().strip() else None
            if fallback and fallback.is_file() and fallback.suffix.lower() == ".exe" and fallback.exists():
                launcher = fallback
                self.project.launcher_path = fallback
            elif self.project and self.project.root.exists():
                guess = self.project.root / "Game.exe"
                if guess.exists():
                    launcher = guess
                    self.project.launcher_path = guess
                else:
                    for candidate in sorted(self.project.root.glob("*.exe")):
                        launcher = candidate
                        self.project.launcher_path = candidate
                        break
        if not launcher or not launcher.exists():
            messagebox.showerror("错误", "当前项目未找到可启动的 exe。")
            return
        if self.project.engine == "RPG Maker MV/MZ":
            try:
                service = self._get_service()
                if hasattr(service, "install_runtime_bridge"):
                    service.install_runtime_bridge()
                    self.runtime_status_var.set("实时组件已安装，正在随游戏启动自动连接...")
            except Exception as exc:
                self.runtime_status_var.set(f"实时组件安装失败：{exc}")
        self.game_process = subprocess.Popen([str(launcher)], cwd=str(launcher.parent))
        self.run_status_var.set("已启动")
        self._touch_library_entry(self.project)
        self._append_recent_task("启动游戏", self.project.root, self.project.engine)
        self._set_status_text(f"已启动游戏：{launcher.name}\n项目已自动加入游戏库。")
        self._refresh_library()
        for delay in (1800, 3600, 6000, 9000, 13000):
            self.root.after(delay, lambda: self.refresh_runtime_state(silent=True))
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
        return self._service_for_project(self.project)

    @staticmethod
    def _service_for_project(project: ProjectInfo) -> RPGMakerService | RenPyService:
        if project.engine == "RPG Maker MV/MZ":
            return RPGMakerService(project)
        if project.engine == "Ren'Py":
            return RenPyService(project)
        raise ValueError("当前引擎暂未启用完整编辑。")

    def _supports_full_editing(self, project: ProjectInfo) -> bool:
        return project.engine in {"RPG Maker MV/MZ", "Ren'Py"}

    def _support_status_for(self, project: ProjectInfo) -> str:
        return "完整支持" if self._supports_full_editing(project) else "已识别，待扩展"

    def _refresh_translation_tree(self) -> None:
        needle = self.filter_var.get().strip().lower()
        if self.translation_entries:
            self.translation_detail_var.set("选择一条文本后可在右侧编辑译文。")
        for item in self.translation_tree.get_children():
            self.translation_tree.delete(item)
        self.translation_view_id_map = {}
        inserted = 0
        matched = 0
        for index, entry in enumerate(self.translation_entries):
            if not self._translation_entry_visible(entry):
                continue
            haystack = f"{entry.file} {entry.context} {entry.source} {entry.target}".lower()
            if not needle or needle in haystack:
                matched += 1
                if inserted < TREE_RENDER_LIMIT:
                    view_id = f"row_{index}"
                    self.translation_view_id_map[view_id] = entry.entry_id
                    self.translation_tree.insert("", "end", iid=view_id, values=(self._translation_category_label(entry.category), entry.file, entry.context, entry.source, entry.target))
                    inserted += 1
        if not inserted and self.translation_entries:
            self._set_translation_notice("当前筛选条件下没有匹配文本。")
        elif matched > TREE_RENDER_LIMIT:
            self.translation_detail_var.set(f"当前匹配 {matched} 条，已先显示前 {inserted} 条。可输入关键词缩小范围，界面会更流畅。")

    def _refresh_translation_file_filter(self) -> None:
        files = sorted({entry.file for entry in self.translation_entries if entry.file})
        values = ("全部文件", *files)
        if hasattr(self, "translation_file_box"):
            self.translation_file_box.configure(values=values)
            widest = max((len(item) for item in values), default=4)
            width = max(18, min(52, widest + 2))
            self.translation_file_box.configure(width=width)
        if self.translation_file_filter_var.get() not in values:
            self.translation_file_filter_var.set("全部文件")

    def _translation_entry_visible(self, entry: TranslationEntry) -> bool:
        if not self._translation_entry_in_scope(entry):
            return False
        selected_file = self.translation_file_filter_var.get().strip()
        if selected_file and selected_file != "全部文件" and entry.file != selected_file:
            return False
        return True

    def _on_translation_scope_change(self, _event: object | None = None) -> None:
        if self.translation_scope_var.get() in {"系统/插件文本", "全部文本"} and self.project and self.project.engine == "RPG Maker MV/MZ":
            messagebox.showwarning(
                "高风险翻译范围",
                "系统/插件文本通常包含脚本、插件参数、引擎关键字段。\n\n"
                "误翻译或嵌入后可能导致游戏启动失败。建议只翻译对白/选项，除非你明确知道这些字段可以改。",
            )
        self._refresh_translation_tree()

    def _has_risky_system_plugin_targets(self) -> bool:
        if not self.project or self.project.engine != "RPG Maker MV/MZ":
            return False
        return any(entry.target.strip() and entry.category in {"system", "plugin"} for entry in self.translation_map.values())

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

    @staticmethod
    def _looks_already_chinese(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        cjk = sum(1 for char in stripped if "\u4e00" <= char <= "\u9fff")
        kana = sum(1 for char in stripped if "\u3040" <= char <= "\u30ff")
        latin = sum(1 for char in stripped if "a" <= char.lower() <= "z")
        meaningful = cjk + kana + latin
        if meaningful == 0:
            return False
        return cjk >= 2 and kana == 0 and (cjk / meaningful >= 0.5 or cjk >= latin)

    @staticmethod
    def _is_likely_dialogue_text(entry: TranslationEntry) -> bool:
        text = entry.source.strip()
        if not text:
            return False
        lowered = text.lower()
        if any(token in lowered for token in (".png", ".jpg", ".jpeg", ".webp", ".webm", ".ogg", ".mp3", ".wav", ".mp4", ".json", ".rpyc", ".rpa", ".exe", "http://", "https://", "www.")):
            return False
        if "\\" in text or "/" in text:
            if re.search(r"[a-zA-Z]:\\|\\\\|/|\\.", text):
                return False
        if len(text) < 2:
            return False
        if re.fullmatch(r"[\W_]+", text):
            return False
        if entry.category != "dialogue" and len(text) < 3:
            return False
        if text.count("{") != text.count("}") or text.count("[") != text.count("]"):
            return False
        if not any("\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or ch.isalpha() for ch in text):
            return False
        return True

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
                runtime_key = self._data_runtime_item_key(records)
                owned = ""
                if runtime_key:
                    owned = str(self._runtime_item_count_map().get(runtime_key, 0)) if self.runtime_state else "未连接"
                self.data_tree.insert("", "end", iid=object_id, values=(first.object_label or object_id, len(records), owned))
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
        self.selected_data_runtime_item = None
        if hasattr(self, "data_property_tree"):
            for item in self.data_property_tree.get_children():
                self.data_property_tree.delete(item)
        if hasattr(self, "data_text"):
            self.data_text.delete("1.0", "end")
        if hasattr(self, "data_runtime_count_var"):
            self.data_runtime_count_var.set("")

    def _set_translation_notice(self, message: str) -> None:
        if not hasattr(self, "translation_tree"):
            return
        self.translation_view_id_map = {}
        for item in self.translation_tree.get_children():
            self.translation_tree.delete(item)
        self.translation_tree.insert("", "end", iid="__notice__", values=("提示", "", "", message, ""))

    def _set_data_notice(self, message: str) -> None:
        if not hasattr(self, "data_tree"):
            return
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        self.data_tree.insert("", "end", iid="__notice__", values=(message, "", ""))

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
            messagebox.showerror("错误", "该项目没有找到可启动的 exe。")
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
            entry_id = self.translation_view_id_map.get(selection[0], selection[0])
            entry = self.translation_map[entry_id]
            self._set_target_editor(entry.target)
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
            self.selected_data_runtime_item = self._data_runtime_item_key(records)
            self.data_text.delete("1.0", "end")
            if hasattr(self, "data_runtime_count_var"):
                if self.selected_data_runtime_item:
                    current = self._runtime_item_count_map().get(self.selected_data_runtime_item, 0) if self.runtime_state else ""
                    self.data_runtime_count_var.set(str(current))
                else:
                    self.data_runtime_count_var.set("")
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
                    self._pending_drop_path = buf.value
                shell32.DragFinish(wparam)
                return 0
            if self._old_wndproc:
                return user32.CallWindowProcW(self._old_wndproc, window, msg, wparam, lparam)
            return 0

        self._drop_callback = WNDPROC(wndproc)
        callback_ptr = ctypes.cast(self._drop_callback, ctypes.c_void_p).value
        self._old_wndproc = user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, LONG_PTR(callback_ptr))

    def _flush_pending_drop(self) -> None:
        if self._pending_drop_path:
            path = self._pending_drop_path
            self._pending_drop_path = None
            self.load_path(Path(path))
        self.root.after(100, self._flush_pending_drop)

    def _project_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]


def main(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    ToolkitApp(root, initial_path=initial_path)
    root.mainloop()

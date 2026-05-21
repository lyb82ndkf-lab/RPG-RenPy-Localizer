from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from toolkit.app import main as app_main


if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"


class BootstrapWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("工具启动器")
        self.root.geometry("640x360")
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="正在检查运行环境...")
        self.detail_var = tk.StringVar(value="这一步会尽量自动完成，不需要你手动配置。")

        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="RPG Maker / Ren'Py 本地化工具箱", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, textvariable=self.status_var, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(18, 6))
        ttk.Label(frame, textvariable=self.detail_var, wraplength=580).pack(anchor="w")

        self.log = tk.Text(frame, height=10, wrap="word", bg="#0f172a", fg="#dbeafe", relief="flat")
        self.log.pack(fill="both", expand=True, pady=(18, 0))
        self.log.insert("1.0", "启动器已就绪。\n")
        self.log.configure(state="disabled")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text="自动准备环境并启动", command=self.prepare_and_run).pack(side="left")
        ttk.Button(btns, text="直接启动", command=self.launch_app).pack(side="left", padx=8)
        self.root.after(250, self._auto_boot)

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def prepare_and_run(self) -> None:
        try:
            if not VENV_DIR.exists():
                self.status_var.set("正在创建虚拟环境...")
                self._append(f"创建虚拟环境: {VENV_DIR}")
                subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, cwd=PROJECT_ROOT)
            else:
                self._append("检测到现有虚拟环境。")

            self.status_var.set("正在更新虚拟环境基础组件...")
            if VENV_PYTHON.exists():
                subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=True, cwd=PROJECT_ROOT)
                self._append("已升级虚拟环境中的 pip。")
                self.detail_var.set("环境已准备完成。当前 GUI 采用标准库 tkinter，可直接进入主工具。")
            else:
                self._append("未找到虚拟环境 python.exe，跳过 pip 升级。")

            self.status_var.set("环境准备完成")
            self._append("准备完成，进入主界面。")
            self.launch_app()
        except Exception as exc:
            self._append(f"环境准备失败: {exc}")
            messagebox.showerror("启动失败", str(exc))

    def _auto_boot(self) -> None:
        if VENV_DIR.exists() and VENV_PYTHON.exists():
            self.status_var.set("环境已就绪，正在自动启动...")
            self.detail_var.set("已检测到可用环境，自动进入主界面。")
            self._append("检测到环境已就绪，自动启动主工具。")
            self.root.after(250, self.launch_app)
            return
        self.prepare_and_run()

    def launch_app(self) -> None:
        self.root.destroy()
        app_main(initial_path=_initial_path_from_argv())


def _initial_path_from_argv() -> str | None:
    if len(sys.argv) < 2:
        return None
    candidate = Path(sys.argv[1]).expanduser()
    return str(candidate) if candidate.exists() else None


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    for candidate in ("vista", "clam", "default"):
        try:
            style.theme_use(candidate)
            break
        except tk.TclError:
            continue
    BootstrapWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()

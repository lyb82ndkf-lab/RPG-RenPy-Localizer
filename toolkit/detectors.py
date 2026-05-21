from __future__ import annotations

from pathlib import Path

from .models import ProjectInfo


def detect_project(path: str | Path) -> ProjectInfo:
    root = Path(path).expanduser().resolve()
    if root.is_file():
        root = root.parent

    game_exe = root / "Game.exe"
    rpg_data = root / "data"
    rpg_www_data = root / "www" / "data"
    renpy_game = root / "game"

    if rpg_data.is_dir() and (rpg_data / "System.json").is_file():
        return ProjectInfo(
            engine="RPG Maker MV/MZ",
            root=root,
            game_dir=root,
            launcher_path=game_exe if game_exe.exists() else None,
            data_dir=rpg_data,
        )

    if rpg_www_data.is_dir() and (rpg_www_data / "System.json").is_file():
        return ProjectInfo(
            engine="RPG Maker MV/MZ",
            root=root,
            game_dir=root / "www",
            launcher_path=game_exe if game_exe.exists() else None,
            data_dir=rpg_www_data,
        )

    if renpy_game.is_dir() and any(renpy_game.rglob("*.rpy")):
        return ProjectInfo(
            engine="Ren'Py",
            root=root,
            game_dir=renpy_game,
            launcher_path=game_exe if game_exe.exists() else None,
            scripts_dir=renpy_game,
        )

    if list(root.glob("*.rxproj")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker XP",
            root=root,
            game_dir=root,
            launcher_path=game_exe if game_exe.exists() else None,
        )

    if list(root.glob("*.rvproj")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX",
            root=root,
            game_dir=root,
            launcher_path=game_exe if game_exe.exists() else None,
        )

    if list(root.glob("*.rvproj2")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX Ace",
            root=root,
            game_dir=root,
            launcher_path=game_exe if game_exe.exists() else None,
        )

    raise ValueError(
        "未识别到受支持项目。当前优先支持 RPG Maker MV/MZ 与 Ren'Py，"
        "并可识别 RPG Maker XP/VX/VX Ace 的项目目录用于游戏库与启动。"
    )

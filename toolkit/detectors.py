from __future__ import annotations

from pathlib import Path

from .models import ProjectInfo


def detect_project(path: str | Path) -> ProjectInfo:
    selected = Path(path).expanduser().resolve()
    selected_launcher = selected if selected.is_file() and selected.suffix.lower() == ".exe" else None
    root = selected
    if root.is_file():
        root = root.parent

    if root.name.lower() == "game" and root.is_dir():
        renpy_game = root
        renpy_root = root.parent
        if any(renpy_game.rglob("*.rpy")) or any(renpy_game.rglob("*.rpyc")) or any(renpy_game.rglob("*.rpa")):
            launcher = selected_launcher or _find_launcher(renpy_root)
            return ProjectInfo(
                engine="Ren'Py",
                root=renpy_root,
                game_dir=renpy_game,
                launcher_path=launcher,
                scripts_dir=renpy_game,
            )

    game_exe = root / "Game.exe"
    launcher = selected_launcher or (game_exe if game_exe.exists() else _find_launcher(root))
    rpg_data = root / "data"
    rpg_www_data = root / "www" / "data"
    renpy_game = root / "game"

    if rpg_data.is_dir() and (rpg_data / "System.json").is_file():
        return ProjectInfo(
            engine="RPG Maker MV/MZ",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=rpg_data,
        )

    if rpg_www_data.is_dir() and (rpg_www_data / "System.json").is_file():
        return ProjectInfo(
            engine="RPG Maker MV/MZ",
            root=root,
            game_dir=root / "www",
            launcher_path=launcher,
            data_dir=rpg_www_data,
        )

    if renpy_game.is_dir() and (any(renpy_game.rglob("*.rpy")) or any(renpy_game.rglob("*.rpyc")) or any(renpy_game.rglob("*.rpa"))):
        return ProjectInfo(
            engine="Ren'Py",
            root=root,
            game_dir=renpy_game,
            launcher_path=launcher,
            scripts_dir=renpy_game,
        )

    if list(root.glob("*.rxproj")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker XP",
            root=root,
            game_dir=root,
            launcher_path=launcher,
        )

    if list(root.glob("*.rvproj")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX",
            root=root,
            game_dir=root,
            launcher_path=launcher,
        )

    if list(root.glob("*.rvproj2")) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX Ace",
            root=root,
            game_dir=root,
            launcher_path=launcher,
        )

    raise ValueError(
        "未识别到受支持项目。当前优先支持 RPG Maker MV/MZ 与 Ren'Py，"
        "并可识别 RPG Maker XP/VX/VX Ace 的项目目录用于游戏库与启动。"
    )


def _find_launcher(root: Path) -> Path | None:
    for candidate in sorted(root.glob("*.exe")):
        if candidate.name.lower() not in {"rpgrenpylocalizer.exe", "python.exe", "pythonw.exe"}:
            return candidate
    return None

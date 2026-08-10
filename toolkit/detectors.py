from __future__ import annotations

from pathlib import Path
import os

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
    launcher = selected_launcher or (game_exe if game_exe.exists() else find_launcher(root))
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

    # Unknown games remain importable for the read-only Agent workbench.
    return ProjectInfo(engine=detect_engine(root), root=root, game_dir=root, launcher_path=launcher)

def detect_engine(root: str | Path) -> str:
    """Identify common non-Ren'Py/non-RPG Maker runtimes from file signals."""
    root = Path(root)
    if root.is_file():
        root = root.parent
    names: set[str] = set()
    relative_paths: set[str] = set()
    count = 0
    try:
        for current, dirnames, filenames in os.walk(root):
            depth = len(Path(current).relative_to(root).parts)
            if depth > 4:
                dirnames[:] = []
                continue
            dirnames[:] = [name for name in dirnames if name not in {".git", ".rpgrtl_workspace", ".rpgrtl_backup", "node_modules"}]
            for filename in filenames:
                names.add(filename.lower())
                relative_paths.add(str((Path(current) / filename).relative_to(root)).replace("\\", "/").lower())
                count += 1
                if count >= 8000:
                    break
            if count >= 8000:
                break
    except OSError:
        pass
    if "unityplayer.dll" in names or any("_data/managed/unityengine" in p or "_data/globalgamemanagers" in p for p in relative_paths):
        return "Unity"
    if {"unrealengine.exe", "ue4game.exe", "ue5game.exe"} & names or any(name.endswith((".pak", ".locres")) for name in names) or any("engine/binaries" in p for p in relative_paths):
        return "Unreal Engine 4/5"
    if "project.godot" in names or any(name.endswith(".pck") for name in names):
        return "Godot"
    if "wolfdatalock.json" in names or any(name.endswith(".wolfx") for name in names) or "mtool_game.exe" in names or any("data/basicdata" in p and p.endswith(".dat") for p in relative_paths):
        return "Wolf RPG Editor"
    if "electron.exe" in names or "resources/app.asar" in relative_paths:
        return "Electron/Web"
    if any(name.endswith(".exe") for name in names):
        return "Generic Windows Game"
    return "Unknown"


def find_launcher(root: str | Path, preferred_name: str | None = None) -> Path | None:
    root = Path(root)
    if not root.is_dir():
        return None
    blocked = {
        "rpgrenpylocalizer.exe",
        "rpgrtl-api.exe",
        "python.exe",
        "pythonw.exe",
        "unins000.exe",
        "uninstall.exe",
        "uninstaller.exe",
        "crashreporter.exe",
        "notification_helper.exe",
    }
    candidates = [candidate for candidate in sorted(root.glob("*.exe")) if candidate.name.lower() not in blocked]
    if not candidates:
        return None
    if preferred_name:
        preferred = next((candidate for candidate in candidates if candidate.name.lower() == preferred_name.lower()), None)
        if preferred:
            return preferred
    game = next((candidate for candidate in candidates if candidate.name.lower() == "game.exe"), None)
    if game:
        return game
    nw = [candidate for candidate in candidates if candidate.name.lower() == "nw.exe"]
    non_nw = [candidate for candidate in candidates if candidate not in nw]
    return non_nw[0] if non_nw else candidates[0]


def _find_launcher(root: Path) -> Path | None:
    return find_launcher(root)

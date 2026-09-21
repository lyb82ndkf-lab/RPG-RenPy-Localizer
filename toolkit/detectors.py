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

    # RPG Maker 2000/2003 (the pre-RGSS binary format) does not have a
    # project file or JSON data directory.  Its reliable on-disk signals are
    # RPG_RT.exe/RPG_RT.ini plus the LDB/LMT/LMU database/map files.  Detect it
    # before the generic fallback so the Agent can choose a binary extractor
    # instead of scanning unrelated text files.
    legacy_rpg = (
        (root / "RPG_RT.exe").is_file()
        or (root / "RPG_RT.ini").is_file()
        or bool(list(root.glob("*.ldb")))
        or bool(list(root.glob("*.lmt")))
        or bool(list(root.glob("*.lmu")))
    )
    if legacy_rpg:
        legacy_launcher = selected_launcher or (root / "RPG_RT.exe" if (root / "RPG_RT.exe").is_file() else launcher)
        return ProjectInfo(
            engine="RPG Maker 2000/2003",
            root=root,
            game_dir=root,
            launcher_path=legacy_launcher,
            data_dir=root,
        )

    if renpy_game.is_dir() and (any(renpy_game.rglob("*.rpy")) or any(renpy_game.rglob("*.rpyc")) or any(renpy_game.rglob("*.rpa"))):
        return ProjectInfo(
            engine="Ren'Py",
            root=root,
            game_dir=renpy_game,
            launcher_path=launcher,
            scripts_dir=renpy_game,
        )

    if (list(root.glob("*.rxproj")) or (root / "Data" / "Scripts.rxdata").is_file() or (root / "Data" / "System.rxdata").is_file() or any(f.name.lower().startswith("rgss10") and f.name.lower().endswith(".dll") for f in root.glob("*.dll"))) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker XP",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "Data",
        )

    if (list(root.glob("*.rvproj")) or (root / "Data" / "Scripts.rvdata").is_file() or (root / "Data" / "System.rvdata").is_file() or any(f.name.lower().startswith("rgss20") and f.name.lower().endswith(".dll") for f in root.glob("*.dll"))) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "Data",
        )

    if (list(root.glob("*.rvproj2")) or (root / "Data" / "Scripts.rvdata2").is_file() or (root / "Data" / "System.rvdata2").is_file() or any(f.name.lower().startswith("rgss30") and f.name.lower().endswith(".dll") for f in root.glob("*.dll"))) and (root / "Data").is_dir():
        return ProjectInfo(
            engine="RPG Maker VX Ace",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "Data",
        )

    if (root / "Data.dts").is_file() or ((root / "Script").is_dir() and (root / "Plugin").is_dir()):
        return ProjectInfo(
            engine="SRPG Studio",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "Plugin" if (root / "Plugin").is_dir() else root,
        )

    # RPG Developer Bakin
    if (
        (root / "data" / "bakinplayer.exe").is_file()
        or (root / "data" / "bakinengine.dll").is_file()
        or (root / "bakinplayer.exe").is_file()
        or (root / "bakinengine.dll").is_file()
        or ((root / "data").is_dir() and any(f.suffix.lower() == ".rbpack" for f in (root / "data").glob("*.rbpack")))
    ):
        return ProjectInfo(
            engine="RPG Developer Bakin",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "data" if (root / "data").is_dir() else root,
        )

    # TyranoBuilder / TyranoScript
    if (
        (root / "tyrano" / "tyrano.js").is_file()
        or (root / "tyrano").is_dir()
        or ((root / "data" / "scenario").is_dir() and any((root / "data" / "scenario").glob("*.ks")) and not any(root.glob("*.xp3")) and not (root / "krkr.exe").is_file())
    ):
        return ProjectInfo(
            engine="TyranoBuilder",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "data" if (root / "data").is_dir() else root,
            scripts_dir=root / "data" / "scenario" if (root / "data" / "scenario").is_dir() else None,
        )

    # Pixel Game Maker MV (Action Game Maker / Agtk)
    if (root / "agtk.exe").is_file() or (root / "player.exe").is_file() and any("agtk" in f.name.lower() for f in root.glob("*.dll")):
        return ProjectInfo(
            engine="Pixel Game Maker MV",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root / "data" if (root / "data").is_dir() else root,
        )

    # Smile Game Builder (SGB)
    if (root / "game.kmy").is_file() or ((root / "kmyCore.dll").is_file() and not (root / "data" / "bakinplayer.exe").is_file()):
        return ProjectInfo(
            engine="Smile Game Builder",
            root=root,
            game_dir=root,
            launcher_path=launcher,
            data_dir=root,
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
    if (
        "wolfdatalock.json" in names
        or any(name.endswith(".wolfx") for name in names)
        or "mtool_game.exe" in names
        or any("data/basicdata" in p and p.endswith(".dat") for p in relative_paths)
        or any(p.startswith("data/mapdata/") and p.endswith(".mps") for p in relative_paths)
    ):
        return "Wolf RPG Editor"
    if (
        {"rpg_rt.exe", "rpg_rt.ini"} & names
        or any(name.endswith(('.ldb', '.lmt', '.lmu')) for name in names)
    ):
        return "RPG Maker 2000/2003"
    if "data.dts" in names or any("plugin/" in p and p.endswith(".js") for p in relative_paths) or ("script" in names and "plugin" in names):
        return "SRPG Studio"
    if any(name.startswith("rgss30") and name.endswith(".dll") for name in names) or any(p.endswith(".rvdata2") for p in relative_paths):
        return "RPG Maker VX Ace"
    if any(name.startswith("rgss20") and name.endswith(".dll") for name in names) or any(p.endswith(".rvdata") for p in relative_paths):
        return "RPG Maker VX"
    if any(name.startswith("rgss10") and name.endswith(".dll") for name in names) or any(p.endswith(".rxdata") for p in relative_paths):
        return "RPG Maker XP"
    if (
        "bakinplayer.exe" in names
        or "bakinengine.dll" in names
        or any(name.endswith(".rbpack") for name in names)
        or "sharpkmycore.dll" in names
    ):
        return "RPG Developer Bakin"
    if "tyrano.js" in names or any("tyrano/" in p for p in relative_paths):
        return "TyranoBuilder"
    if "agtk.exe" in names or any("agtk" in name for name in names):
        return "Pixel Game Maker MV"
    if "game.kmy" in names or ("kmycore.dll" in names and "bakinengine.dll" not in names):
        return "Smile Game Builder"
    if "electron.exe" in names or "resources/app.asar" in relative_paths:
        return "Electron/Web"
    # Common visual-novel runtime signals.  Kirikiri/KAG uses XP3 archives
    # and .ks/.tjs scenarios; NScripter/ONScripter uses nscript.dat or .sar.
    # This deliberately stays after the more specific engines above.
    if (
        {"krkr.exe", "krkrz.exe", "tvpwin.exe", "onscripter.exe", "onscripter-en.exe", "nscript.dat"} & names
        or any(name.endswith((".xp3", ".sar")) for name in names)
        or any(path.endswith((".ks", ".tjs", ".spt", ".mes")) for path in relative_paths)
    ):
        return "Visual Novel / Galgame"
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

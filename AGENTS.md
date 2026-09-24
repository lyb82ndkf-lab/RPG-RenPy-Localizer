# AGENTS.md

Windows monorepo for **RPGRenPyLocalizer** (PC desktop v3.4.0 + Android shell). Prefer executable sources (`package.json`, build scripts, `toolkit/`) over README prose when they disagree.

## Architecture (what an agent would miss)

- **PC desktop (primary product)**: Electron shell + Vue 3 renderer + Python local HTTP API.
  - Electron main: `electron/main.js` (spawns backend; IPC; packaged path resolution).
  - Renderer: `electron/renderer/src/` (mostly `App.vue` + `main.js`); Vite config: `electron/renderer/vite.config.mjs`; build output: `electron/renderer/dist/`.
  - Python backend package: `toolkit/` — real entry `toolkit/api/server.py` (`ToolkitApi`, stdlib `ThreadingHTTPServer`). Packaged entry: `api_server_entry.py` → PyInstaller `rpgrtl-api`.
  - Domain modules: `toolkit/rpgmaker.py`, `toolkit/renpy.py`, `toolkit/unknown_game.py` (multi-engine extract/write-back), `toolkit/workspace.py`, `toolkit/storage.py`, `toolkit/memory_editor.py`.
- **Legacy PC UI still present**: `main.py` / `launcher.py` → `toolkit/app.py` (Tkinter). Do not treat as the shipping path; Electron is.
- **Android**: official shell is `android_app/shell` (Kotlin/Compose + Winlator-derived native libs). Mobile WebUI source is `android_app/mobile_ui_src` (Vite Vue); built assets land in `android_app/mobile_ui` and are synced into shell assets by `build_all.ps1`.
- **Not official / ignore for builds**: `AndroidAPP/` (legacy UniApp, H5 chain broken per `android_app/VALIDATION.md`), `android_offline`, `winlator-main/`, `mtool/` (large local refs), root `*.kt` dumps (`extracted_1109.kt`, `cleaned.kt`, `git_ver.kt`), stale `main.js` / `RPGRenPyLocalizer.spec` at repo root.
- No CI workflows, no lint/typecheck configs, no monorepo workspace tooling. Tests live only under `tests/` (stdlib `unittest` style; pytest also collects them).

## Commands (Windows / PowerShell)

### PC desktop

```powershell
# One-time
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyinstaller
npm install

# Dev (builds renderer then launches Electron; auto-starts Python API)
npm run build:renderer
npm start

# Full Windows installer + portable (PyInstaller backend → electron-builder)
powershell -ExecutionPolicy Bypass -File .\build_electron_release.ps1
# Variants: -SkipNpmInstall, -DirOnly (directory pack only)

# Or npm-only after backend is already packaged under build/electron-backend/
npm run dist        # nsis + portable → release-electron/
npm run pack        # win dir only
npm run portable    # portable exe only

# Backend alone (Electron also does this with --port 0)
python -m toolkit.api.server --port 0
```

Version numbers for desktop releases come from root `package.json` (`build.productName`, scripts). Do not bump only in docs.

### Tests

```powershell
# All backend tests (documented verified command)
python -m pytest tests -q

# Single file
python -m pytest tests/test_renpy_live_bridge.py -q
# or
python -m unittest tests.test_renpy_live_bridge
```

No separate lint/typecheck step exists; there is nothing to run in that order beyond tests.

### Android

```powershell
# Official one-shot (build mobile UI → sync assets → Gradle → archive)
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Debug   # or without -Debug for release

# Shell-only APK + verify_apk.ps1
cd android_app\shell
.\build_apk.ps1
# Device smoke:
.\install_and_smoke.ps1
```

Mobile UI rebuild (required before Android packaging if UI changed):

```powershell
cd android_app\mobile_ui_src
npm run build          # outDir: ../mobile_ui
```

`build_all.ps1` copies `android_app/mobile_ui` → `android_app/shell/app/src/main/assets/mobile_ui`. Prefer editing `mobile_ui_src`, not the synced snapshot.

## Environment quirks (will fail without these)

- Scripts hardcode **machine paths**: Python `C:\Users\Administrator\...\Python312\python.exe`, `D:\java\jdk-17` (`build_apk.ps1`) vs `D:\java\jdk-21` (`build_all.ps1`), `D:\Android SDK`, `D:\gradle-9.5.1`. Adjust if missing; they are intentional for this host.
- Android needs `android_app/shell/local.properties` with `sdk.dir=...` (copy from root `local.properties.template` for signing keys; `local.properties` is gitignored).
- No root `requirements.txt` / `pyproject.toml`. Python deps: PyInstaller (+ optional `unrpa`/`unrpyc` via `build_release.ps1`). Prefer whatever Python the Electron/build scripts resolve (`.venv` or system 3.12).
- Electron packaging expects backend already at `build/electron-backend/rpgrtl-api` (created by `build_electron_release.ps1`); `npm run dist` alone will not rebuild the Python backend.

## Domain rules (do not “fix” casually)

- **Safe translation surface**: RPG Maker UI/workbench exposes `database` / `dialogue` (and carefully gated `system`); high-risk `event` / `script` categories must not enter normal batch translate/write-back. Constants: `SAFE_TRANSLATION_CATEGORIES`, `DATABASE_TEXT_FIELDS` in `toolkit/rpgmaker.py`.
- **AI batch protocol is `entry_id` JSON**, not positional arrays (see README). Always match on `entry_id` when writing translations back.
- **Write-back is non-destructive by design**: work under `<game>\.rpgrtl_workspace\` / `.rpgrtl_backup\`; never overwrite the user’s original game files in place.
- Control/placeholder tokens (`\N[1]`, `{player}`, `${value}`, `%s`, HTML/engine tags) must be preserved — see `TRANSLATION_TEMPLATE_TOKEN` in `toolkit/api/server.py` and `toolkit/core/control_codes.py`.
- AI keys live in `%APPDATA%\RPGRenPyLocalizer\settings.json` only — never commit, log, or paste keys.

## Repo hygiene

- Gitignored local/tool noise: `opencode.json`, `.claude/`, `.codex/`, `.reasonix/`, `release-electron/`, `node_modules/`, build trees, `winlator-main/`, `mtool/`.
- Prefer small, verified diffs. There is no formatter/linter to run; correctness is checked by `python -m pytest tests -q` for Python and by successful `build:renderer` / packaging scripts for frontends.
- User-facing docs (Chinese): `README.md`, `ELECTRON_README.md`, `android_app/README.md`, `android_app/VALIDATION.md` (source of truth for what Android build steps were actually verified on this machine).

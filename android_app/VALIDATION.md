# Android / Winlator validation status

This document is intentionally strict: an item is marked verified only when it was actually run on this machine or on a connected Android device.

## Official Android deliverable

- Official shell: `android_app/shell`
- Packaged mobile UI snapshot: `android_app/mobile_ui`
- Debug APK: `android_app/shell/app/build/outputs/apk/debug/app-debug.apk`

`AndroidAPP/AndroidAPP` is currently only a legacy UniApp source snapshot. Its H5 build chain is not considered verified, because `npx vite build` fails with the local HBuilderX / Vue dependency set. Do not claim UniApp source rebuilds are working until that command is fixed and rerun successfully.

`android_offline` is a failed legacy experiment and is not part of the official deliverable. Deletion was attempted only after path verification, but the local tool policy blocked recursive removal; therefore it remains on disk and must be ignored by official builds.

## Verified on this machine

Date: 2026-07-21

1. `android_app/shell/build_apk.ps1`
   - Result: passed.
   - The script now fails if Gradle exits non-zero or if the APK is missing.
   - The script runs `tools/verify_apk.ps1` after building.

2. `android_app/shell/tools/verify_apk.ps1`
   - Result: passed.
   - Verifies the APK contains the required Winlator-derived arm64 engine libraries:
     - `libwinlator.so`
     - `libvirglrenderer.so`
     - `libvortekrenderer.so`
     - `libgladiorenderer.so`
     - `libmidihandler.so`
     - `libfile_redirect_hook.so`
     - `libgsl_alloc_hook.so`
     - `libhook_impl.so`
     - `libmain_hook.so`
   - Verifies the packaged mobile UI asset graph is closed and has no stale hashed assets.
   - Verifies packaged JS includes the expected mobile navigation / settings / translation bridge strings.
   - Verifies at least two packaged touchscreen control profiles exist and each contains controls.

3. `python -m pytest tests -q`
   - Result: passed, 24 tests.
   - Covers the Python-side RPG Maker and RenPy live bridge tests that the mobile bridge is intended to reuse conceptually.

4. `D:\gradle-9.5.1\bin\gradle.bat --no-daemon testDebugUnitTest`
   - Result: passed.
   - There are no Android unit test classes yet, but the task recompiles Kotlin/Java and catches compile-time breakage.

## Not yet verified

The following items require a real connected Android device or emulator with suitable GPU / storage access and cannot be honestly marked complete in the current environment:

- Install the APK through ADB.
- Launch the app on Android and confirm the WebView UI renders.
- Select and start a real RPG Maker or RenPy Windows game through the Winlator engine.
- Confirm the in-game top-right tool window appears over an active game.
- Confirm the packaged default virtual key profiles render and work in the game.
- Confirm user-created/customized key profiles persist across app restarts.
- Confirm live translation and data modification work against an active running game.

## Required real-device command sequence

Preferred smoke script:

```powershell
cd android_app/shell
.\install_and_smoke.ps1
```

Manual equivalent:

```powershell
cd android_app/shell
.\build_apk.ps1
adb devices
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell monkey -p com.rpgrtl.shell 1
adb logcat -c
# Run a real game manually, then capture logs if anything fails:
adb logcat -d > android-device-run.log
```

Only after the real-device checks above pass should the overall mobile goal be marked complete.

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "android_app/shell/app/src/main/assets/rpgmaker/rpgrtl_runtime.js"
BRIDGE = ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/rpgmaker/RpgMakerNativeBridge.kt"
ACTIVITY = ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/rpgmaker/RpgMakerWebViewActivity.kt"
GAMEPAD = ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/rpgmaker/VirtualGamepadView.kt"
FLOATING = ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/rpgmaker/InGameFloatingButton.kt"
DASHBOARD_HTML = ROOT / "android_app/shell/app/src/main/assets/mtool/mtool_overlay.html"
DASHBOARD_CSS = ROOT / "android_app/shell/app/src/main/assets/mtool/mtool_overlay.css"
DASHBOARD_JS = ROOT / "android_app/shell/app/src/main/assets/mtool/mtool_overlay.js"
WINE_ACTIVITY = ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/wine/WineDisplayActivity.kt"
MANIFEST = ROOT / "android_app/shell/app/src/main/AndroidManifest.xml"


def test_android_rpgmaker_runtime_components_are_wired():
    for path in [RUNTIME, BRIDGE, GAMEPAD, FLOATING, DASHBOARD_HTML, DASHBOARD_CSS, DASHBOARD_JS, WINE_ACTIVITY]:
        assert path.is_file(), path

    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "fun saveFileExists" in bridge
    assert "fun loadSaveData" in bridge
    assert "fun saveSaveData" in bridge
    assert "fun removeSaveFile" in bridge
    assert "canonicalFile" in bridge

    activity = ACTIVITY.read_text(encoding="utf-8")
    assert 'addJavascriptInterface(RpgMakerNativeBridge' in activity
    assert "shouldInterceptRequest" in activity
    assert "rpgrtl_runtime.js" in activity
    assert "VirtualGamepadView" in activity
    assert "InGameFloatingButton" in activity
    assert "injectDashboard" in activity
    assert "mtool_overlay.js" in activity
    assert "showTrainerDialog" not in activity

    wine_activity = WINE_ACTIVITY.read_text(encoding="utf-8")
    assert "showInGameTrainerDialog" not in wine_activity
    assert '"data", "trainer" -> openToolPage("trainer")' in wine_activity

    dashboard_html = DASHBOARD_HTML.read_text(encoding="utf-8")
    dashboard_css = DASHBOARD_CSS.read_text(encoding="utf-8")
    dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "RPGRenPyLocalizer" in dashboard_html
    assert "RPGRenPy live console" not in dashboard_html
    assert "backdrop-filter" not in dashboard_css
    assert "box-shadow" not in dashboard_css
    assert "touch-action:pan-y" in dashboard_css.replace(" ", "")
    assert "-webkit-overflow-scrolling:touch" in dashboard_css.replace(" ", "")
    assert "主页控制台" not in dashboard
    assert "LIVE CONTROL" not in dashboard
    assert "mt-kpi" not in dashboard
    for tab in ["主页", "物品", "防具", "武器", "开关", "变量", "角色", "地图", "公共事件", "数据修改", "翻译", "MCenter", "数据锁定", "地图Ex", "按键设定"]:
        assert tab in dashboard


def test_runtime_script_maps_mv_and_mz_saves_to_physical_bridge(tmp_path: Path):
    assert RUNTIME.is_file()
    harness = tmp_path / "runtime_harness.js"
    harness.write_text(
        r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(__RUNTIME__, 'utf8');
function bridgeStore() {
  const files = Object.create(null);
  return { files, bridge: {
    saveSaveData(name, data) { files[name] = String(data); return true; },
    loadSaveData(name) { return Object.prototype.hasOwnProperty.call(files, name) ? files[name] : ''; },
    saveFileExists(name) { return Object.prototype.hasOwnProperty.call(files, name); },
    removeSaveFile(name) { const found = Object.prototype.hasOwnProperty.call(files, name); delete files[name]; return found; },
    getTranslationMap() { return '{}'; }
  }};
}
(async () => {
  const mvStore = bridgeStore();
  const mv = { console, RPGRTLBridge: mvStore.bridge, StorageManager: {
    isLocalMode() { return false; }, saveToLocalFile() { throw new Error('old MV save path called'); },
    loadFromLocalFile() { throw new Error('old MV load path called'); }, localFileExists() { return false; }, removeLocalFile() {}
  }};
  mv.window = mv; vm.createContext(mv); vm.runInContext(source, mv);
  if (!mv.StorageManager.isLocalMode()) process.exit(10);
  mv.StorageManager.saveToLocalFile(1, 'mv-payload');
  if (mvStore.files['file1.rpgsave'] !== 'mv-payload') process.exit(11);
  if (mv.StorageManager.loadFromLocalFile(1) !== 'mv-payload') process.exit(12);
  if (!mv.StorageManager.localFileExists(1)) process.exit(13);
  mv.StorageManager.removeLocalFile(1);
  if (mv.StorageManager.localFileExists(1)) process.exit(14);

  const mzStore = bridgeStore();
  const mz = { console, Promise, RPGRTLBridge: mzStore.bridge, StorageManager: {
    isLocalMode() { return false; }, saveObject() {}, objectToJson() {}, saveZip() { throw new Error('old MZ save path called'); },
    loadZip() { throw new Error('old MZ load path called'); }, exists() { return false; }, remove() {}
  }};
  mz.window = mz; vm.createContext(mz); vm.runInContext(source, mz);
  await mz.StorageManager.saveZip('file2', 'mz-payload');
  if (mzStore.files['file2.rmmzsave'] !== 'mz-payload') process.exit(20);
  if ((await mz.StorageManager.loadZip('file2')) !== 'mz-payload') process.exit(21);
  if (!mz.StorageManager.exists('file2')) process.exit(22);
  await mz.StorageManager.remove('file2');
  if (mz.StorageManager.exists('file2')) process.exit(23);
  if (!mz.__RPGRTL_TRAINER || typeof mz.__RPGRTL_TRAINER.teleport !== 'function') process.exit(24);
  process.stdout.write('android rpgmaker runtime ok\n');
})().catch(error => { console.error(error); process.exit(99); });
""".replace("__RUNTIME__", json.dumps(str(RUNTIME))),
        encoding="utf-8",
    )
    result = subprocess.run(["node", str(harness)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "android rpgmaker runtime ok" in result.stdout



def test_mobile_touch_cutout_and_portrait_guards():
    css = DASHBOARD_CSS.read_text(encoding="utf-8").replace(" ", "")
    activity = ACTIVITY.read_text(encoding="utf-8")
    main_screen = (ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/ui/MainScreen.kt").read_text(encoding="utf-8")
    main_activity = (ROOT / "android_app/shell/app/src/main/java/com/rpgrtl/shell/MainActivity.kt").read_text(encoding="utf-8")

    assert "safe-area-inset-top" in css
    assert "safe-area-inset-right" in css
    assert "safe-area-inset-bottom" in css
    assert "@media(orientation:portrait)" in css
    assert ".mt-control-editor{height:auto" in css
    assert ".mt-detail{height:auto;overflow:visible" in css
    assert "min-height:28px" in css

    assert "LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES" in activity
    assert "SCREEN_ORIENTATION_SENSOR_LANDSCAPE" in activity
    assert "viewport-fit=cover" in activity
    assert "getInsetsIgnoringVisibility" in activity
    assert "setSafeInsets" in activity
    assert "contentWindowInsets = WindowInsets(0, 0, 0, 0)" in main_screen
    assert "LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES" in main_activity
    manifest = MANIFEST.read_text(encoding="utf-8")
    rpg_activity = manifest.split('<activity\n            android:name=".rpgmaker.RpgMakerWebViewActivity"', 1)[1].split("</activity>", 1)[0]
    assert 'android:screenOrientation="sensorLandscape"' in rpg_activity

def test_dashboard_blocks_touch_events_from_reaching_game_canvas():
    dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
    css = DASHBOARD_CSS.read_text(encoding="utf-8").replace(" ", "")
    for event_name in ["touchstart", "touchmove", "touchend", "pointerdown", "pointerup", "mousedown", "mouseup", "click"]:
        assert event_name in dashboard
    assert "stopPropagation" in dashboard
    assert "pointer-events:auto" in css
    assert "min-width:100vw" in css
    assert "min-height:100vh" in css

def test_native_overlay_is_moved_behind_dashboard_while_open():
    activity = ACTIVITY.read_text(encoding="utf-8")
    assert "onDashboardVisibilityChanged(true)" in activity
    assert "webView?.bringToFront()" in activity
    assert "virtualGamepad?.bringToFront()" in activity
    assert "floatingButton?.bringToFront()" in activity
    assert "virtualGamepad?.visibility = View.GONE" in activity
    assert "floatingButton?.visibility = View.GONE" in activity
    assert "floatingButton?.visibility = View.VISIBLE" in activity



def test_map_ex_debugger_and_composite_gamepad_are_bundled():
    dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
    dashboard_css = DASHBOARD_CSS.read_text(encoding="utf-8")
    gamepad = GAMEPAD.read_text(encoding="utf-8")

    # Map EX: browse external maps, inspect overlapping events, edit conditions,
    # and explicitly run a selected event page instead of teleporting on canvas tap.
    for marker in [
        "mt-mapex-map-select",
        "loadMapExData",
        "eventsAtMapExTile",
        "toggle-map-switch",
        "toggle-map-self-switch",
        "satisfy-map-variable",
        "execute-map-event",
        "formatEventCommand",
    ]:
        assert marker in dashboard

    # Input studio: a real composite joystick profile, presets and touch key picker.
    for marker in [
        'type:"joystick"',
        "joystickMode",
        "apply-control-preset",
        "openKeyPicker",
        "mt-keypicker-modal",
        "mt-keypicker-gamepad",
    ]:
        assert marker in dashboard
    for marker in [
        "JoystickView",
        'type == "joystick"',
        "dispatchJoystickDirection",
        "MouseEvent",
    ]:
        assert marker in gamepad

    assert ".mt-mapex-layout" in dashboard_css
    assert ".mt-keypicker-modal" in dashboard_css
    assert ".mt-editor-joystick" in dashboard_css


def test_gamepad_editor_persists_live_layout_and_uses_dark_simulator():
    dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
    dashboard_css = DASHBOARD_CSS.read_text(encoding="utf-8")
    gamepad = GAMEPAD.read_text(encoding="utf-8")
    activity = ACTIVITY.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")

    for marker in [
        "syncSelectedControlFromEditor",
        "updateControlPreview",
        "setupJoystickDemo",
        "mt-control-screen-grid",
        "mt-joystick-demo",
        "mt-control-save-state",
        'bg:"#18232d"',
    ]:
        assert marker in dashboard
    for marker in [
        ".mt-control-screen-grid",
        ".mt-joystick-demo",
        ".mt-joy-direction",
        ".mt-control-safe-frame",
    ]:
        assert marker in dashboard_css
    assert "DARK_BUTTON_COLOR" in gamepad
    assert "DARK_JOYSTICK_COLOR" in gamepad
    assert '.commit()' in bridge
    assert 'gamepad.applyProfile(savedProfile)' in activity

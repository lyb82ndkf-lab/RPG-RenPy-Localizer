from __future__ import annotations

import json
import re
import shutil
import time
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import DataRecord, MapDetail, MapEventInfo, MapRecord, MapTileInfo, ProjectInfo, SaveSlot, TranslationEntry
from .storage import load_json, save_json


TEXT_FILES = [
    "Actors.json",
    "Armors.json",
    "Classes.json",
    "Enemies.json",
    "Items.json",
    "MapInfos.json",
    "Skills.json",
    "States.json",
    "Weapons.json",
    "System.json",
    "CommonEvents.json",
]

EDITABLE_DB_FILES = {
    "Actors.json",
    "Armors.json",
    "Classes.json",
    "Enemies.json",
    "Items.json",
    "Skills.json",
    "States.json",
    "Weapons.json",
    "System.json",
    "MapInfos.json",
    "CommonEvents.json",
}

SKIP_DATA_KEYS = {"note", "traits", "effects"}
RUNTIME_BRIDGE_NAME = "RPGRenPyBridge"
RUNTIME_BRIDGE_PORT = 32179

RUNTIME_BRIDGE_SOURCE = r"""/*:
 * @target MV MZ
 * @plugindesc Local runtime bridge for single-player RPG Maker tools.
 * @author RPGRenPyLocalizer
 *
 * @help
 * Runs a localhost-only HTTP bridge so the desktop tool can inspect and modify
 * the current single-player game state. Do not use this with online games.
 */
(() => {
  "use strict";
  if (window.RPGRenPyBridge && window.RPGRenPyBridge.started) return;
  if (typeof require !== "function") return;

  const http = require("http");
  const PORT = 32179;
  const HOST = "127.0.0.1";
  const bridge = window.RPGRenPyBridge = window.RPGRenPyBridge || {};
  bridge.started = true;
  bridge.enabled = true;
  bridge.root = process.cwd ? process.cwd() : "";
  bridge.translationEnabled = false;
  bridge.translations = bridge.translations || {};
  bridge.locks = bridge.locks || {};
  bridge.options = bridge.options || {
    gameSpeed: 1,
    moveSpeed: 0,
    battleSpeed: 1,
    autoBattle: false,
    godMode: false,
    autoSaveInterval: 0,
    unlockCg: false,
    fontSize: 0,
    fpsBoost: false
  };
  bridge.lastAutoSaveAt = bridge.lastAutoSaveAt || 0;

  function clamp(value, min, max, fallback) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.max(min, Math.min(max, number));
  }

  function json(res, status, payload) {
    const body = JSON.stringify(payload);
    res.writeHead(status, {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "http://127.0.0.1",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type"
    });
    res.end(body);
  }

  function readBody(req) {
    return new Promise(resolve => {
      let body = "";
      req.on("data", chunk => body += chunk);
      req.on("end", () => {
        try { resolve(body ? JSON.parse(body) : {}); }
        catch (_e) { resolve({}); }
      });
    });
  }

  function translate(text) {
    if (!bridge.translationEnabled || text == null) return text;
    const raw = String(text);
    return bridge.translations[raw] || bridge.translations[raw.trim()] || raw;
  }

  function collectContainer(container, database) {
    const result = [];
    if (!container || !database) return result;
    for (const id of Object.keys(container)) {
      const item = database[Number(id)];
      if (item) result.push({ id: Number(id), name: item.name || "", count: container[id] || 0 });
    }
    return result;
  }

  function state() {
    const mapId = window.$gameMap ? $gameMap.mapId() : 0;
    const mapInfo = window.$dataMapInfos && $dataMapInfos[mapId] ? $dataMapInfos[mapId] : null;
    const party = window.$gameParty;
    const actors = [];
    if (window.$gameActors && $gameActors._data) {
      for (let i = 1; i < $gameActors._data.length; i++) {
        const actor = $gameActors._data[i];
        if (actor) actors.push({
          id: i,
          name: actor.name ? actor.name() : actor._name,
          level: actor._level,
          hp: actor._hp,
          mhp: actor.mhp || 0,
          mp: actor._mp,
          mmp: actor.mmp || 0,
          tp: actor._tp || 0,
          atk: actor.atk || 0,
          def: actor.def || 0,
          mat: actor.mat || 0,
          mdf: actor.mdf || 0,
          agi: actor.agi || 0,
          luk: actor.luk || 0,
          exp: actor.currentExp ? actor.currentExp() : null
        });
      }
    }
    const switches = [];
    if (window.$dataSystem && window.$gameSwitches) {
      for (let i = 1; i < ($dataSystem.switches || []).length; i++) {
        switches.push({ id: i, name: $dataSystem.switches[i] || "", value: !!$gameSwitches.value(i) });
      }
    }
    const variables = [];
    if (window.$dataSystem && window.$gameVariables) {
      for (let i = 1; i < ($dataSystem.variables || []).length; i++) {
        variables.push({ id: i, name: $dataSystem.variables[i] || "", value: $gameVariables.value(i) });
      }
    }
    return {
      ok: true,
      gold: party ? party.gold() : 0,
      steps: party ? party.steps() : 0,
      items: party ? collectContainer(party._items, window.$dataItems) : [],
      weapons: party ? collectContainer(party._weapons, window.$dataWeapons) : [],
      armors: party ? collectContainer(party._armors, window.$dataArmors) : [],
      actors,
      switches,
      variables,
      map: {
        id: mapId,
        name: mapInfo ? mapInfo.name : "",
        displayName: window.$dataMap ? ($dataMap.displayName || "") : "",
        x: window.$gamePlayer ? $gamePlayer.x : 0,
        y: window.$gamePlayer ? $gamePlayer.y : 0,
        through: window.$gamePlayer ? $gamePlayer.isThrough() : false
      },
      options: bridge.options,
      translationEnabled: bridge.translationEnabled
    };
  }

  function apply(payload) {
    if (window.$gameParty && payload.gold !== undefined) $gameParty._gold = Math.max(0, Math.min(Number(payload.gold) || 0, 99999999));
    const applyItems = (kind, database) => {
      if (!window.$gameParty || !payload[kind]) return;
      const container = kind === "items" ? $gameParty._items : kind === "weapons" ? $gameParty._weapons : $gameParty._armors;
      for (const [id, value] of Object.entries(payload[kind])) {
        const amount = Math.max(0, Number(value) || 0);
        if (amount <= 0) delete container[id]; else container[id] = amount;
      }
    };
    applyItems("items", window.$dataItems);
    applyItems("weapons", window.$dataWeapons);
    applyItems("armors", window.$dataArmors);
    if (window.$gameSwitches && payload.switches) for (const [id, value] of Object.entries(payload.switches)) $gameSwitches.setValue(Number(id), !!value);
    if (window.$gameVariables && payload.variables) for (const [id, value] of Object.entries(payload.variables)) $gameVariables.setValue(Number(id), value);
    if (window.$gameActors && payload.actors) {
      for (const [id, patch] of Object.entries(payload.actors)) {
        const actor = $gameActors.actor(Number(id));
        if (!actor || !patch) continue;
        if (patch.level !== undefined && actor.changeLevel) actor.changeLevel(Number(patch.level), false);
        if (patch.exp !== undefined && actor.changeExp) actor.changeExp(Number(patch.exp) || 0, false);
        if (patch.hp !== undefined) actor._hp = Number(patch.hp) || 0;
        if (patch.mp !== undefined) actor._mp = Number(patch.mp) || 0;
        if (patch.tp !== undefined) actor._tp = Number(patch.tp) || 0;
        const paramMap = { mhp: 0, mmp: 1, atk: 2, def: 3, mat: 4, mdf: 5, agi: 6, luk: 7 };
        for (const [key, paramId] of Object.entries(paramMap)) {
          if (patch[key] !== undefined && actor.addParam) {
            const target = Number(patch[key]) || 0;
            const current = actor[key] || 0;
            actor.addParam(paramId, target - current);
          }
        }
      }
    }
    if (payload.options) {
      const options = payload.options;
      if (options.gameSpeed !== undefined) bridge.options.gameSpeed = clamp(options.gameSpeed, 1, 16, 1);
      if (options.moveSpeed !== undefined) bridge.options.moveSpeed = clamp(options.moveSpeed, 0, 6, 0);
      if (options.battleSpeed !== undefined) bridge.options.battleSpeed = clamp(options.battleSpeed, 1, 16, 1);
      if (options.autoBattle !== undefined) bridge.options.autoBattle = !!options.autoBattle;
      if (options.godMode !== undefined) bridge.options.godMode = !!options.godMode;
      if (options.autoSaveInterval !== undefined) bridge.options.autoSaveInterval = Math.max(0, Number(options.autoSaveInterval) || 0);
      if (options.unlockCg !== undefined) bridge.options.unlockCg = !!options.unlockCg;
      if (options.fontSize !== undefined) bridge.options.fontSize = Math.max(0, Number(options.fontSize) || 0);
      if (options.fpsBoost !== undefined) bridge.options.fpsBoost = !!options.fpsBoost;
      if (bridge.options.unlockCg && window.$gameSystem) {
        $gameSystem._cgUnlocked = true;
        $gameSystem._galleryUnlocked = true;
        $gameSystem._unlockedCg = $gameSystem._unlockedCg || {};
        for (let i = 1; i <= 999; i++) $gameSystem._unlockedCg[i] = true;
      }
      if (window.Graphics && bridge.options.fpsBoost) {
        try { Graphics._maxFps = 60; } catch (_e) {}
      }
    }
    if (payload.locks) bridge.locks = payload.locks;
    if (payload.battle === "win" && window.BattleManager) BattleManager.processVictory();
    if (payload.battle === "lose" && window.BattleManager) BattleManager.processDefeat();
    if (payload.battle === "escape" && window.BattleManager) BattleManager.processEscape();
    if (window.$gamePlayer && payload.player && payload.player.through !== undefined) $gamePlayer.setThrough(!!payload.player.through);
    if (window.$gamePlayer && payload.player && payload.player.teleport && window.$gameMap) {
      const toMapX = value => value === "mouse" && window.TouchInput ? $gameMap.canvasToMapX(TouchInput.x) : Number(value);
      const toMapY = value => value === "mouse" && window.TouchInput ? $gameMap.canvasToMapY(TouchInput.y) : Number(value);
      const x = Number.isFinite(toMapX(payload.player.teleport.x)) ? toMapX(payload.player.teleport.x) : $gamePlayer.x;
      const y = Number.isFinite(toMapY(payload.player.teleport.y)) ? toMapY(payload.player.teleport.y) : $gamePlayer.y;
      $gamePlayer.reserveTransfer($gameMap.mapId(), x, y, $gamePlayer.direction(), 0);
    }
    if (window.$gameMap) $gameMap.requestRefresh();
  }

  const _battlerRefresh = Game_BattlerBase.prototype.refresh;
  Game_BattlerBase.prototype.refresh = function() {
    _battlerRefresh.call(this);
    applyLock(this);
  };

  function applyLock(battler) {
    if (!battler || !battler.isActor || !battler.isActor()) return;
    const id = battler.actorId();
    const lock = bridge.locks[String(id)] || {};
    if (lock.hp !== undefined) battler._hp = Number(lock.hp) || 0;
    if (lock.mp !== undefined) battler._mp = Number(lock.mp) || 0;
    if (lock.tp !== undefined) battler._tp = Number(lock.tp) || 0;
    if (bridge.options.godMode) {
      battler._hp = Math.max(1, battler.mhp || battler._hp || 1);
      battler._mp = battler.mmp || battler._mp || 0;
      battler._tp = 100;
    }
  }

  const _playerRealMoveSpeed = Game_Player.prototype.realMoveSpeed;
  Game_Player.prototype.realMoveSpeed = function() {
    const base = _playerRealMoveSpeed.call(this);
    return bridge.options.moveSpeed > 0 ? bridge.options.moveSpeed : base;
  };

  const _battleManagerUpdate = BattleManager.update;
  BattleManager.update = function(timeActive) {
    const count = Math.max(1, Math.floor(bridge.options.battleSpeed || 1));
    for (let i = 0; i < count; i++) _battleManagerUpdate.call(this, timeActive);
  };

  const _sceneMapUpdate = Scene_Map.prototype.update;
  Scene_Map.prototype.update = function() {
    const ctrlBoost = !!(window.Input && Input.isPressed && Input.isPressed("control"));
    const speed = Math.max(Number(bridge.options.gameSpeed || 1), ctrlBoost ? 2 : 1);
    const count = Math.max(1, Math.floor(speed));
    for (let i = 0; i < count; i++) _sceneMapUpdate.call(this);
    if (window.$gameParty) $gameParty.members().forEach(applyLock);
    if (bridge.options.autoSaveInterval > 0 && window.DataManager) {
      const now = Date.now();
      if (now - bridge.lastAutoSaveAt >= bridge.options.autoSaveInterval * 1000) {
        bridge.lastAutoSaveAt = now;
        try { DataManager.saveGame(1); } catch (_e) {}
      }
    }
  };

  const _sceneBattleUpdate = Scene_Battle.prototype.update;
  Scene_Battle.prototype.update = function() {
    _sceneBattleUpdate.call(this);
    if (window.$gameParty) $gameParty.members().forEach(applyLock);
    if (bridge.options.autoBattle && window.BattleManager && BattleManager.inputting && BattleManager.inputting()) {
      try {
        if (window.$gameParty) {
          $gameParty.members().forEach(actor => {
            if (actor && actor.makeAutoBattleActions) actor.makeAutoBattleActions();
          });
        }
        BattleManager.startTurn();
      } catch (_e) {}
    }
  };

  const _bitmapInitialize = Bitmap.prototype.initialize;
  Bitmap.prototype.initialize = function(width, height) {
    _bitmapInitialize.call(this, width, height);
    if (bridge.options.fontSize > 0) this.fontSize = bridge.options.fontSize;
  };

  const _convert = Window_Base.prototype.convertEscapeCharacters;
  Window_Base.prototype.convertEscapeCharacters = function(text) {
    return _convert.call(this, translate(text));
  };
  const _drawText = Bitmap.prototype.drawText;
  Bitmap.prototype.drawText = function(text, x, y, maxWidth, lineHeight, align) {
    return _drawText.call(this, translate(text), x, y, maxWidth, lineHeight, align);
  };

  bridge.server = http.createServer(async (req, res) => {
    if (req.method === "OPTIONS") return json(res, 200, { ok: true });
    try {
      if (req.url === "/ping") return json(res, 200, { ok: true, name: "RPGRenPyBridge", root: bridge.root, pid: process.pid });
      if (req.url === "/state") return json(res, 200, state());
      if (req.url === "/set" && req.method === "POST") {
        apply(await readBody(req));
        return json(res, 200, state());
      }
      if (req.url === "/translation" && req.method === "POST") {
        const payload = await readBody(req);
        bridge.translations = payload.dict || {};
        bridge.translationEnabled = payload.enabled !== false;
        if (SceneManager && SceneManager._scene && SceneManager._scene.refresh) SceneManager._scene.refresh();
        return json(res, 200, { ok: true, count: Object.keys(bridge.translations).length });
      }
      json(res, 404, { ok: false, error: "not found" });
    } catch (e) {
      json(res, 500, { ok: false, error: String(e && e.stack || e) });
    }
  });
  bridge.server.on("error", e => {
    bridge.lastError = String(e && e.stack || e);
    bridge.started = false;
  });
  bridge.server.listen(PORT, HOST, () => {
    bridge.started = true;
    bridge.lastError = "";
  });
})();
"""

CATEGORY_LABELS = {
    "Actors.json": "Actors 角色",
    "Armors.json": "Armors 防具",
    "Classes.json": "Classes 职业",
    "Enemies.json": "Enemies 敌人",
    "Items.json": "Items 物品",
    "Skills.json": "Skills 技能",
    "States.json": "States 状态",
    "System.json": "System 系统",
    "Weapons.json": "Weapons 武器",
    "MapInfos.json": "MapInfos 地图",
    "CommonEvents.json": "CommonEvents 公共事件",
}


@dataclass(slots=True)
class JsonDocument:
    path: Path
    data: Any


class RPGMakerService:
    def __init__(self, project: ProjectInfo) -> None:
        if not project.data_dir:
            raise ValueError("RPG Maker 项目缺少 data 目录。")
        self.project = project
        self.data_dir = project.data_dir

    def extract_translations(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        for json_path in sorted(self.data_dir.glob("*.json")):
            if json_path.name not in TEXT_FILES and not json_path.stem.startswith("Map"):
                continue
            data = load_json(json_path)
            entries.extend(self._extract_from_json(json_path.name, data))
        return entries

    def list_data_records(self) -> list[DataRecord]:
        records: list[DataRecord] = []
        for json_path in sorted(self.data_dir.glob("*.json")):
            if json_path.name not in EDITABLE_DB_FILES and not json_path.stem.startswith("Map"):
                continue
            data = load_json(json_path)
            if json_path.name == "System.json":
                for key in ("gameTitle", "currencyUnit"):
                    value = data.get(key)
                    if isinstance(value, str):
                        records.append(
                            DataRecord(
                                record_id=f"{json_path.name}:{key}",
                                label=key,
                                value=value,
                                file=json_path.name,
                                category=self._category_for(json_path.name),
                                object_id=f"{json_path.name}:system",
                                object_label="系统",
                                location=key,
                                json_path=[key],
                            )
                        )
                for group in ("elements", "equipTypes", "skillTypes", "weaponTypes", "armorTypes"):
                    group_values = data.get(group)
                    if isinstance(group_values, list):
                        for index, value in enumerate(group_values):
                            if isinstance(value, str) and value.strip():
                                records.append(
                                    DataRecord(
                                        record_id=f"{json_path.name}:{group}:{index}",
                                        label=f"{group}[{index}]",
                                        value=value,
                                        file=json_path.name,
                                        category=self._category_for(json_path.name),
                                        object_id=f"{json_path.name}:{group}",
                                        object_label=group,
                                        location=f"{group}/{index}",
                                        json_path=[group, index],
                                    )
                                )
                continue

            if json_path.name == "MapInfos.json":
                for index, item in enumerate(data):
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        records.append(
                            DataRecord(
                                record_id=f"{json_path.name}:{index}:name",
                                label=f"map {index} name",
                                value=name,
                                file=json_path.name,
                                category=self._category_for(json_path.name),
                                object_id=f"{json_path.name}:{index}",
                                object_label=f"地图 {index}: {name}",
                                location=f"{index}/name",
                                json_path=[index, "name"],
                            )
                        )
                continue

            if json_path.name == "CommonEvents.json":
                records.extend(self._list_event_records(json_path.name, data))
                continue

            if json_path.stem.startswith("Map"):
                records.extend(self._list_event_records(json_path.name, data))
                continue

            records.extend(self._list_database_records(json_path.name, data))
        return records

    def apply_translations(self, translations: dict[str, TranslationEntry]) -> int:
        self._backup_tree()
        updated = 0
        for index, json_path in enumerate(sorted(self.data_dir.glob("*.json"))):
            if json_path.name not in TEXT_FILES and not json_path.stem.startswith("Map"):
                continue
            if index % 5 == 0:
                time.sleep(0)
            data = load_json(json_path)
            changed = self._apply_to_json(json_path.name, data, translations)
            if changed:
                save_json(json_path, data)
                updated += changed
        return updated

    def build_translation_patch(self, translations: dict[str, TranslationEntry]) -> tuple[Path, int]:
        patch_root = self.project.root / ".rpgrtl_workspace" / "runtime_patch"
        updated = 0
        changed_files: list[tuple[Path, Any]] = []
        for json_path in sorted(self.data_dir.glob("*.json")):
            if json_path.name not in TEXT_FILES and not json_path.stem.startswith("Map"):
                continue
            data = load_json(json_path)
            changed = self._apply_to_json(json_path.name, data, translations)
            if changed:
                changed_files.append((json_path, data))
                updated += changed
        if updated == 0:
            return patch_root, 0

        if patch_root.exists():
            shutil.rmtree(patch_root)
        patch_data_dir = patch_root / self.data_dir.relative_to(self.project.root)
        patch_data_dir.mkdir(parents=True, exist_ok=True)
        for json_path, data in changed_files:
            save_json(patch_data_dir / json_path.name, data)
        manifest = patch_root / "README.txt"
        manifest.write_text(
            "这是当前项目的临时翻译补丁目录，原游戏文件未被替换。\n"
            "如果需要测试补丁，请关闭游戏后把本目录中的 data/www/data 文件复制覆盖到游戏对应目录；\n"
            "删除补丁目录后，原游戏仍保持未翻译状态。\n",
            encoding="utf-8",
        )
        return patch_root, updated

    def build_runtime_copy(self, translations: dict[str, TranslationEntry]) -> tuple[Path, Path | None, int]:
        patch_root, updated = self.build_translation_patch(translations)
        return patch_root, None, updated

    def _copy_tree_contents(self, source: Path, target: Path) -> None:
        for item in source.iterdir():
            if item.name == "README.txt":
                continue
            destination = target / item.name
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                self._copy_tree_contents(item, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

    def update_record(self, record: DataRecord, new_value: str) -> None:
        self._backup_tree()
        json_path = self.data_dir / record.file
        data = load_json(json_path)
        target = data
        for segment in record.json_path[:-1]:
            target = target[segment]
        old_value = target[record.json_path[-1]]
        target[record.json_path[-1]] = self._coerce_value(new_value, old_value)
        save_json(json_path, data)

    def install_runtime_bridge(self) -> Path:
        plugins_dir = self.project.root / "js" / "plugins"
        if not plugins_dir.is_dir():
            raise RuntimeError("未找到 js/plugins 目录，当前项目可能不是标准 RPG Maker MV/MZ 结构。")
        bridge_path = plugins_dir / f"{RUNTIME_BRIDGE_NAME}.js"
        bridge_path.write_text(RUNTIME_BRIDGE_SOURCE, encoding="utf-8", newline="\n")
        plugins_js = self.project.root / "js" / "plugins.js"
        self._enable_plugin(plugins_js, RUNTIME_BRIDGE_NAME)
        return bridge_path

    def uninstall_runtime_bridge(self) -> None:
        plugins_js = self.project.root / "js" / "plugins.js"
        self._disable_plugin(plugins_js, RUNTIME_BRIDGE_NAME)

    def _enable_plugin(self, plugins_js: Path, plugin_name: str) -> None:
        plugins = self._load_plugins_js(plugins_js)
        for plugin in plugins:
            if plugin.get("name") == plugin_name:
                plugin["status"] = True
                break
        else:
            plugins.append({"name": plugin_name, "status": True, "description": "Local runtime bridge", "parameters": {}})
        self._save_plugins_js(plugins_js, plugins)

    def _disable_plugin(self, plugins_js: Path, plugin_name: str) -> None:
        plugins = [plugin for plugin in self._load_plugins_js(plugins_js) if plugin.get("name") != plugin_name]
        self._save_plugins_js(plugins_js, plugins)

    @staticmethod
    def _load_plugins_js(plugins_js: Path) -> list[dict[str, Any]]:
        if not plugins_js.exists():
            return []
        text = plugins_js.read_text(encoding="utf-8-sig")
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < start:
            return []
        raw = text[start : end + 1]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _save_plugins_js(plugins_js: Path, plugins: list[dict[str, Any]]) -> None:
        body = json.dumps(plugins, ensure_ascii=False, indent=2)
        plugins_js.write_text("// Generated by RPG Maker.\n// Do not edit this file directly.\nvar $plugins =\n" + body + ";\n", encoding="utf-8", newline="\n")

    def list_save_slots(self) -> list[SaveSlot]:
        save_dir = self.project.root / "save"
        if not save_dir.is_dir():
            return []
        slots: list[SaveSlot] = []
        for path in sorted(save_dir.glob("*.*save")):
            match = re.match(r"file(\d+)\.(rpgsave|rmmzsave)$", path.name, re.IGNORECASE)
            if not match:
                continue
            slot_id = int(match.group(1))
            modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            slots.append(SaveSlot(slot_id=slot_id, label=f"存档 {slot_id}", path=path, modified_at=modified))
        return slots

    def load_save(self, save_path: Path) -> dict[str, Any]:
        raw = save_path.read_bytes().decode("utf-8", errors="surrogateescape")
        data = raw.encode("latin1", errors="ignore")
        text = zlib.decompress(data).decode("utf-8")
        return json.loads(text)

    def save_save(self, save_path: Path, payload: dict[str, Any]) -> None:
        self._backup_save(save_path)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        zipped = zlib.compress(text.encode("utf-8"), level=1)
        save_path.write_bytes(zipped.decode("latin1").encode("utf-8"))

    def save_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        party = payload.get("party", {})
        switches = payload.get("switches", {})
        variables = payload.get("variables", {})
        actors = payload.get("actors", {})
        return {
            "gold": party.get("_gold", 0),
            "steps": party.get("_steps", 0),
            "actor_count": len((actors.get("_data") or [])) if isinstance(actors, dict) else 0,
            "switch_count": len((switches.get("_data") or [])) if isinstance(switches, dict) else 0,
            "variable_count": len((variables.get("_data") or [])) if isinstance(variables, dict) else 0,
        }

    def set_save_gold(self, payload: dict[str, Any], value: int) -> None:
        party = payload.setdefault("party", {})
        party["_gold"] = max(0, min(int(value), 99999999))

    def set_save_item(self, payload: dict[str, Any], kind: str, item_id: int, value: int) -> None:
        key = {"items": "_items", "weapons": "_weapons", "armors": "_armors"}[kind]
        party = payload.setdefault("party", {})
        container = party.setdefault(key, {})
        amount = max(0, int(value))
        if amount == 0:
            container.pop(str(item_id), None)
        else:
            container[str(item_id)] = amount

    def set_save_actor_level(self, payload: dict[str, Any], actor_id: int, value: int) -> None:
        actors = payload.setdefault("actors", {}).setdefault("_data", [])
        if actor_id >= len(actors) or not isinstance(actors[actor_id], dict):
            return
        actors[actor_id]["_level"] = max(1, int(value))

    def set_save_switch(self, payload: dict[str, Any], switch_id: int, value: bool) -> None:
        data = payload.setdefault("switches", {}).setdefault("_data", [])
        self._ensure_list_size(data, switch_id)
        data[switch_id] = bool(value)

    def set_save_variable(self, payload: dict[str, Any], variable_id: int, value: Any) -> None:
        data = payload.setdefault("variables", {}).setdefault("_data", [])
        self._ensure_list_size(data, variable_id)
        data[variable_id] = self._parse_variable_value(value)

    def list_maps(self) -> list[MapRecord]:
        info_path = self.data_dir / "MapInfos.json"
        infos = load_json(info_path) if info_path.exists() else []
        maps: list[MapRecord] = []
        for index, info in enumerate(infos):
            if not isinstance(info, dict):
                continue
            map_id = int(info.get("id") or index)
            file_name = f"Map{map_id:03d}.json"
            map_path = self.data_dir / file_name
            display_name = ""
            width = height = tileset_id = event_count = 0
            if map_path.exists():
                data = load_json(map_path)
                display_name = str(data.get("displayName") or "")
                width = int(data.get("width") or 0)
                height = int(data.get("height") or 0)
                tileset_id = int(data.get("tilesetId") or 0)
                events = data.get("events") or []
                if isinstance(events, list):
                    event_count = sum(1 for item in events if item)
            maps.append(
                MapRecord(
                    map_id=map_id,
                    name=str(info.get("name") or f"Map {map_id}"),
                    display_name=display_name,
                    file=file_name,
                    width=width,
                    height=height,
                    tileset_id=tileset_id,
                    event_count=event_count,
                )
            )
        return maps

    def map_detail(self, map_id: int) -> MapDetail:
        records = {record.map_id: record for record in self.list_maps()}
        record = records.get(map_id)
        if not record:
            record = MapRecord(map_id=map_id, name=f"Map {map_id}", display_name="", file=f"Map{map_id:03d}.json")
        map_path = self.data_dir / record.file
        data = load_json(map_path) if map_path.exists() else {}
        width = int(data.get("width") or record.width or 0)
        height = int(data.get("height") or record.height or 0)
        record.width = width
        record.height = height
        record.display_name = str(data.get("displayName") or record.display_name)
        record.tileset_id = int(data.get("tilesetId") or record.tileset_id or 0)

        passable = self._map_passability(data, width, height, record.tileset_id)
        events = self._map_events(data)
        event_count: dict[tuple[int, int], int] = {}
        transfer_count: dict[tuple[int, int], int] = {}
        for event in events:
            key = (event.x, event.y)
            event_count[key] = event_count.get(key, 0) + 1
            if event.transfers:
                transfer_count[key] = transfer_count.get(key, 0) + len(event.transfers)
        tiles = [
            MapTileInfo(
                x=x,
                y=y,
                passable=passable.get((x, y), True),
                event_count=event_count.get((x, y), 0),
                transfer_count=transfer_count.get((x, y), 0),
            )
            for y in range(height)
            for x in range(width)
        ]
        return MapDetail(record=record, tiles=tiles, events=events)

    def _map_passability(self, data: dict[str, Any], width: int, height: int, tileset_id: int) -> dict[tuple[int, int], bool]:
        tilesets = load_json(self.data_dir / "Tilesets.json") if (self.data_dir / "Tilesets.json").exists() else []
        flags: list[int] = []
        if isinstance(tilesets, list) and 0 <= tileset_id < len(tilesets) and isinstance(tilesets[tileset_id], dict):
            raw_flags = tilesets[tileset_id].get("flags") or []
            if isinstance(raw_flags, list):
                flags = [int(item or 0) for item in raw_flags]
        raw = data.get("data") or []
        layers = 6
        result: dict[tuple[int, int], bool] = {}
        for y in range(height):
            for x in range(width):
                blocked = False
                for z in range(min(layers, max(1, len(raw) // max(1, width * height)))):
                    index = (z * height + y) * width + x
                    tile_id = int(raw[index] or 0) if index < len(raw) else 0
                    if tile_id <= 0 or tile_id >= len(flags):
                        continue
                    flag = flags[tile_id]
                    if flag & 0x10:
                        continue
                    if flag & 0x0F == 0x0F:
                        blocked = True
                        break
                result[(x, y)] = not blocked
        return result

    def _map_events(self, data: dict[str, Any]) -> list[MapEventInfo]:
        result: list[MapEventInfo] = []
        events = data.get("events") or []
        if not isinstance(events, list):
            return result
        for fallback_id, raw_event in enumerate(events):
            if not isinstance(raw_event, dict):
                continue
            event_id = int(raw_event.get("id") or fallback_id)
            pages = raw_event.get("pages") or []
            conditions: list[str] = []
            transfers: list[str] = []
            commands_summary: list[str] = []
            command_count = 0
            if isinstance(pages, list):
                for page_index, page in enumerate(pages, start=1):
                    if not isinstance(page, dict):
                        continue
                    conditions.extend(self._event_page_conditions(page_index, page.get("conditions") or {}))
                    commands = page.get("list") or []
                    if isinstance(commands, list):
                        command_count += len(commands)
                        commands_summary.extend(self._event_command_summary(commands))
                        transfers.extend(self._event_transfers(commands))
            result.append(
                MapEventInfo(
                    event_id=event_id,
                    name=str(raw_event.get("name") or f"Event {event_id}"),
                    x=int(raw_event.get("x") or 0),
                    y=int(raw_event.get("y") or 0),
                    page_count=len(pages) if isinstance(pages, list) else 0,
                    command_count=command_count,
                    conditions=conditions,
                    transfers=transfers,
                    commands=commands_summary,
                )
            )
        return result

    @staticmethod
    def _event_page_conditions(page_index: int, conditions: dict[str, Any]) -> list[str]:
        result: list[str] = []
        if conditions.get("switch1Valid"):
            result.append(f"页{page_index}: 开关 {conditions.get('switch1Id')} ON")
        if conditions.get("switch2Valid"):
            result.append(f"页{page_index}: 开关 {conditions.get('switch2Id')} ON")
        if conditions.get("variableValid"):
            result.append(f"页{page_index}: 变量 {conditions.get('variableId')} >= {conditions.get('variableValue')}")
        if conditions.get("selfSwitchValid"):
            result.append(f"页{page_index}: 独立开关 {conditions.get('selfSwitchCh')} ON")
        if conditions.get("itemValid"):
            result.append(f"页{page_index}: 持有物品 {conditions.get('itemId')}")
        if conditions.get("actorValid"):
            result.append(f"页{page_index}: 队伍含角色 {conditions.get('actorId')}")
        if not result:
            result.append(f"页{page_index}: 无触发条件")
        return result

    @staticmethod
    def _event_transfers(commands: list[Any]) -> list[str]:
        transfers: list[str] = []
        for command in commands:
            if not isinstance(command, dict):
                continue
            if command.get("code") != 201:
                continue
            params = command.get("parameters") or []
            if len(params) >= 5:
                transfers.append(f"传送到地图 {params[1]} ({params[2]}, {params[3]})")
        return transfers

    @staticmethod
    def _event_command_summary(commands: list[Any]) -> list[str]:
        summary: list[str] = []
        for command in commands:
            if not isinstance(command, dict):
                continue
            code = command.get("code")
            params = command.get("parameters") or []
            if code == 101 and len(params) > 4 and isinstance(params[4], str):
                summary.append(f"对话：{params[4][:32]}")
            elif code in {401, 405} and params and isinstance(params[0], str):
                summary.append(f"对话：{params[0][:32]}")
            elif code == 121 and len(params) >= 3:
                summary.append(f"开关：{params[0]}-{params[1]}")
            elif code == 122 and len(params) >= 5:
                summary.append(f"变量：{params[0]}-{params[1]}")
            elif code == 201 and len(params) >= 5:
                summary.append(f"传送：地图 {params[1]} ({params[2]}, {params[3]})")
            elif code == 230:
                summary.append("等待")
            elif code == 355:
                summary.append("脚本")
        return summary[:12]

    def _backup_save(self, save_path: Path) -> None:
        if not save_path.exists():
            return
        backup_dir = self.project.root / ".rpgrtl_backup" / "save"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(save_path, backup_dir / f"{save_path.name}.{stamp}.bak")

    @staticmethod
    def _ensure_list_size(values: list[Any], index: int) -> None:
        while len(values) <= index:
            values.append(None)

    @staticmethod
    def _parse_variable_value(value: Any) -> Any:
        if isinstance(value, str):
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
        return value

    def _list_database_records(self, file_name: str, data: Any) -> list[DataRecord]:
        records: list[DataRecord] = []

        def add(path: list[str | int], value: Any) -> None:
            if isinstance(value, str) and not value.strip():
                return
            records.append(
                DataRecord(
                    record_id=f"{file_name}::" + "/".join(map(str, path)),
                    label=" / ".join(map(str, path[1:] if path and isinstance(path[0], int) else path)),
                    value=self._display_value(value),
                    file=file_name,
                    category=self._category_for(file_name),
                    object_id=self._object_id_for(file_name, path, data),
                    object_label=self._object_label_for(file_name, path, data),
                    location="/".join(map(str, path)),
                    json_path=path,
                )
            )

        def visit(node: Any, path: list[str | int]) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in SKIP_DATA_KEYS:
                        continue
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        add(path + [key], value)
                    elif isinstance(value, dict):
                        visit(value, path + [key])
                    elif isinstance(value, list) and key in {"params", "expParams", "learnings"}:
                        visit(value, path + [key])
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    if item is None:
                        continue
                    if isinstance(item, (str, int, float, bool)):
                        add(path + [index], item)
                    elif isinstance(item, (dict, list)):
                        visit(item, path + [index])

        visit(data, [])
        return records

    def _backup_tree(self) -> None:
        backup_root = self.project.root / ".rpgrtl_backup" / "data"
        if backup_root.exists():
            return
        shutil.copytree(self.data_dir, backup_root)

    def _list_event_records(self, file_name: str, data: Any) -> list[DataRecord]:
        records: list[DataRecord] = []

        def add(path: list[str | int], label: str, value: str) -> None:
            records.append(
                DataRecord(
                    record_id=f"{file_name}::" + "/".join(map(str, path)),
                    label=label,
                    value=value,
                    file=file_name,
                    category=self._category_for(file_name),
                    object_id=self._object_id_for(file_name, path, data),
                    object_label=self._object_label_for(file_name, path, data),
                    location="/".join(map(str, path)),
                    json_path=path,
                )
            )

        def scan_command(command: dict[str, Any], base_path: list[str | int]) -> None:
            code = command.get("code")
            params = command.get("parameters")
            if not isinstance(params, list):
                return
            if code in {401, 405, 355, 655} and params and isinstance(params[0], str) and params[0].strip():
                add(base_path + ["parameters", 0], f"event {code}", params[0])
            elif code == 101 and len(params) > 4 and isinstance(params[4], str) and params[4].strip():
                add(base_path + ["parameters", 4], "speaker name", params[4])
            elif code == 102 and params and isinstance(params[0], list):
                for index, option in enumerate(params[0]):
                    if isinstance(option, str) and option.strip():
                        add(base_path + ["parameters", 0, index], f"choice {index}", option)
            elif code == 402 and len(params) > 1 and isinstance(params[1], str) and params[1].strip():
                add(base_path + ["parameters", 1], "choice branch", params[1])
            elif code == 122 and len(params) > 4 and isinstance(params[4], str):
                raw = params[4]
                if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                    body = raw[1:-1]
                    if body.strip():
                        add(base_path + ["parameters", 4], "script string", body)

        def visit(node: Any, path: list[str | int]) -> None:
            if isinstance(node, dict):
                if "code" in node and "parameters" in node:
                    scan_command(node, path)
                for key, value in node.items():
                    visit(value, path + [key])
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    visit(item, path + [index])

        visit(data, [])
        return records

    def _extract_from_json(self, file_name: str, data: Any) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []

        def visit(node: Any, path: list[str | int]) -> None:
            if isinstance(node, dict):
                if "code" in node and "parameters" in node:
                    entries.extend(self._extract_event_command(file_name, node, path))
                for key, value in node.items():
                    if key in {
                        "name",
                        "description",
                        "profile",
                        "nickname",
                        "message1",
                        "message2",
                        "message3",
                        "message4",
                        "displayName",
                        "gameTitle",
                        "currencyUnit",
                    } and isinstance(value, str) and value.strip():
                        entries.append(
                            TranslationEntry(
                                entry_id=self._make_entry_id(file_name, path + [key]),
                                source=value,
                                file=file_name,
                                context=" / ".join(map(str, path + [key])),
                                category=self._translation_category(file_name, key),
                            )
                        )
                    visit(value, path + [key])
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    visit(item, path + [index])

        visit(data, [])
        return self._deduplicate(entries)

    def _extract_event_command(
        self, file_name: str, command: dict[str, Any], path: list[str | int]
    ) -> list[TranslationEntry]:
        code = command.get("code")
        params = command.get("parameters")
        results: list[TranslationEntry] = []
        if not isinstance(params, list):
            return results

        def add(idx: int, text: str) -> None:
            if text.strip():
                results.append(
                    TranslationEntry(
                        entry_id=self._make_entry_id(file_name, path + ["parameters", idx]),
                        source=text,
                        file=file_name,
                        context=f"event code {code}",
                        category=self._event_translation_category(code),
                    )
                )

        if code in {401, 405, 355, 655} and params:
            if isinstance(params[0], str):
                add(0, params[0])
        elif code == 101 and len(params) > 4 and isinstance(params[4], str):
            add(4, params[4])
        elif code == 102 and params and isinstance(params[0], list):
            for index, option in enumerate(params[0]):
                if isinstance(option, str):
                    add(index, option)
        elif code == 402 and len(params) > 1 and isinstance(params[1], str):
            add(1, params[1])
        elif code == 122 and len(params) > 4 and isinstance(params[4], str):
            raw = params[4]
            if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                add(4, raw[1:-1])
        elif code == 356 and params and isinstance(params[0], str):
            add(0, params[0])
        elif code == 357 and len(params) > 3:
            self._extract_any_strings(file_name, params[3], path + ["parameters", 3], results, f"plugin {params[0]}")

        return results

    def _extract_any_strings(
        self,
        file_name: str,
        node: Any,
        path: list[str | int],
        results: list[TranslationEntry],
        context: str,
    ) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                self._extract_any_strings(file_name, value, path + [key], results, context)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._extract_any_strings(file_name, value, path + [index], results, context)
        elif isinstance(node, str) and node.strip():
            results.append(
                TranslationEntry(
                    entry_id=self._make_entry_id(file_name, path),
                    source=node,
                    file=file_name,
                    context=context,
                    category="plugin",
                )
            )

    def _apply_to_json(
        self, file_name: str, data: Any, translations: dict[str, TranslationEntry]
    ) -> int:
        changed = 0

        def resolve(entry_id: str, original: str) -> str:
            entry = translations.get(entry_id)
            if entry and entry.target.strip():
                return entry.target
            for candidate in translations.values():
                if candidate.source == original and candidate.target.strip():
                    return candidate.target
            return original

        def visit(node: Any, path: list[str | int]) -> None:
            nonlocal changed
            if isinstance(node, dict):
                if "code" in node and "parameters" in node:
                    changed += self._apply_event_command(file_name, node, path, resolve)
                for key, value in node.items():
                    if key in {
                        "name",
                        "description",
                        "profile",
                        "nickname",
                        "message1",
                        "message2",
                        "message3",
                        "message4",
                        "displayName",
                        "gameTitle",
                        "currencyUnit",
                    } and isinstance(value, str):
                        entry_id = self._make_entry_id(file_name, path + [key])
                        translated = resolve(entry_id, value)
                        if translated != value:
                            node[key] = translated
                            changed += 1
                    visit(value, path + [key])
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    visit(item, path + [index])

        visit(data, [])
        return changed

    def _apply_event_command(
        self,
        file_name: str,
        command: dict[str, Any],
        path: list[str | int],
        resolve: Any,
    ) -> int:
        code = command.get("code")
        params = command.get("parameters")
        if not isinstance(params, list):
            return 0

        changed = 0
        if code in {401, 405, 355, 655} and params and isinstance(params[0], str):
            entry_id = self._make_entry_id(file_name, path + ["parameters", 0])
            new_text = resolve(entry_id, params[0])
            if new_text != params[0]:
                params[0] = new_text
                changed += 1
        elif code == 101 and len(params) > 4 and isinstance(params[4], str):
            entry_id = self._make_entry_id(file_name, path + ["parameters", 4])
            new_text = resolve(entry_id, params[4])
            if new_text != params[4]:
                params[4] = new_text
                changed += 1
        elif code == 102 and params and isinstance(params[0], list):
            for index, option in enumerate(params[0]):
                if isinstance(option, str):
                    entry_id = self._make_entry_id(file_name, path + ["parameters", index])
                    new_text = resolve(entry_id, option)
                    if new_text != option:
                        params[0][index] = new_text
                        changed += 1
        elif code == 402 and len(params) > 1 and isinstance(params[1], str):
            entry_id = self._make_entry_id(file_name, path + ["parameters", 1])
            new_text = resolve(entry_id, params[1])
            if new_text != params[1]:
                params[1] = new_text
                changed += 1
        elif code == 122 and len(params) > 4 and isinstance(params[4], str):
            raw = params[4]
            if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
                body = raw[1:-1]
                entry_id = self._make_entry_id(file_name, path + ["parameters", 4])
                new_text = resolve(entry_id, body)
                if new_text != body:
                    params[4] = f"'{new_text}'"
                    changed += 1
        elif code == 356 and params and isinstance(params[0], str):
            entry_id = self._make_entry_id(file_name, path + ["parameters", 0])
            new_text = resolve(entry_id, params[0])
            if new_text != params[0]:
                params[0] = new_text
                changed += 1
        elif code == 357 and len(params) > 3:
            changed += self._apply_any_strings(file_name, params[3], path + ["parameters", 3], resolve)
        return changed

    def _apply_any_strings(
        self,
        file_name: str,
        node: Any,
        path: list[str | int],
        resolve: Any,
    ) -> int:
        changed = 0
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    entry_id = self._make_entry_id(file_name, path + [key])
                    new_text = resolve(entry_id, value)
                    if new_text != value:
                        node[key] = new_text
                        changed += 1
                else:
                    changed += self._apply_any_strings(file_name, value, path + [key], resolve)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, str):
                    entry_id = self._make_entry_id(file_name, path + [index])
                    new_text = resolve(entry_id, value)
                    if new_text != value:
                        node[index] = new_text
                        changed += 1
                else:
                    changed += self._apply_any_strings(file_name, value, path + [index], resolve)
        return changed

    @staticmethod
    def _make_entry_id(file_name: str, path: list[str | int]) -> str:
        return f"{file_name}::" + "/".join(map(str, path))

    @staticmethod
    def _category_for(file_name: str) -> str:
        if file_name == "MapInfos.json":
            return CATEGORY_LABELS.get(file_name, "MapInfos 地图")
        if file_name.startswith("Map") and file_name.endswith(".json"):
            return "Maps 地图事件"
        return CATEGORY_LABELS.get(file_name, file_name.removesuffix(".json"))

    @staticmethod
    def _translation_category(file_name: str, key: str) -> str:
        if file_name == "MapInfos.json":
            return "database"
        if file_name.startswith("Map"):
            if key in {"name", "displayName"}:
                return "event"
            return "dialogue"
        if file_name == "CommonEvents.json":
            return "dialogue"
        if file_name == "System.json":
            return "system"
        return "database"

    @staticmethod
    def _event_translation_category(code: Any) -> str:
        if code in {401, 405, 101, 102, 402, 403}:
            return "dialogue"
        if code in {355, 655, 356, 357}:
            return "plugin"
        return "event"

    @staticmethod
    def _object_id_for(file_name: str, path: list[str | int], root: Any) -> str:
        if path and isinstance(path[0], int):
            return f"{file_name}:{path[0]}"
        return f"{file_name}:root"

    @staticmethod
    def _object_label_for(file_name: str, path: list[str | int], root: Any) -> str:
        if path and isinstance(path[0], int):
            index = path[0]
            name = ""
            try:
                item = root[index]
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("nickname") or item.get("displayName")
                    if isinstance(candidate, str) and candidate.strip():
                        name = candidate.strip()
            except Exception:
                name = ""
            base = file_name.removesuffix(".json")
            return f"{base} {index}" + (f": {name}" if name else "")
        return file_name.removesuffix(".json")

    @staticmethod
    def _display_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    @staticmethod
    def _coerce_value(value: str, old_value: Any) -> Any:
        text = value.strip()
        if isinstance(old_value, bool):
            return text.lower() in {"1", "true", "yes", "y", "on", "是"}
        if isinstance(old_value, int) and not isinstance(old_value, bool):
            return int(text)
        if isinstance(old_value, float):
            return float(text)
        if old_value is None and text.lower() == "null":
            return None
        return value

    @staticmethod
    def _deduplicate(entries: list[TranslationEntry]) -> list[TranslationEntry]:
        unique: dict[str, TranslationEntry] = {}
        for entry in entries:
            unique[entry.entry_id] = entry
        return list(unique.values())

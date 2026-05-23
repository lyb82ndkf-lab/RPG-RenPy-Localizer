(function () {
  'use strict';
  if (window.RPGCHEAT && window.RPGCHEAT.__version === 2) return;

  var state = window.__rpgrtlCheatState || {
    noclip: false,
    clickWarp: false,
    godMode: false,
    hpLock: false,
    mpLock: false,
    tpLock: false,
    hpValue: 9999,
    mpValue: 9999,
    tpValue: 100,
    speed: 1,
    battleSpeed: 1,
    expRate: 1,
    original: {},
    timers: {}
  };
  window.__rpgrtlCheatState = state;

  function ok(data) {
    return JSON.stringify(Object.assign({ ok: true }, data || {}));
  }

  function fail(error) {
    return JSON.stringify({ ok: false, error: String(error && error.message ? error.message : error) });
  }

  function bool(value) {
    return value === true || value === 'true' || value === '1' || value === 1 || value === 'on';
  }

  function enabledValue(value) {
    return !(value === false || value === 'false' || value === '0' || value === 0 || value === 'off');
  }

  function num(value, fallback) {
    var n = Number(value);
    return isFinite(n) ? n : fallback;
  }

  function ready() {
    return !!(window.$gameParty || window.DataManager || window.SceneManager);
  }

  function partyMembers() {
    return window.$gameParty && $gameParty.members ? $gameParty.members() : [];
  }

  function troopMembers() {
    return window.$gameTroop && $gameTroop.members ? $gameTroop.members() : [];
  }

  function firstActor() {
    var list = partyMembers();
    return list && list.length ? list[0] : null;
  }

  function setHp(actor, value) {
    if (!actor) return;
    if (actor.setHp) actor.setHp(value);
    else actor._hp = value;
  }

  function setMp(actor, value) {
    if (!actor) return;
    if (actor.setMp) actor.setMp(value);
    else actor._mp = value;
  }

  function setTp(actor, value) {
    if (!actor) return;
    if (actor.setTp) actor.setTp(value);
    else actor._tp = value;
  }

  function recoverAll() {
    partyMembers().forEach(function (actor) {
      if (actor.recoverAll) actor.recoverAll();
      else {
        setHp(actor, actor.mhp || actor._mhp || 9999);
        setMp(actor, actor.mmp || actor._mmp || 9999);
        setTp(actor, 100);
      }
    });
  }

  function patchLocks() {
    if (!window.Scene_Map || Scene_Map.prototype.__rpgrtlLockPatch) return;
    Scene_Map.prototype.__rpgrtlLockPatch = true;
    state.original.sceneMapUpdateForLock = Scene_Map.prototype.update;
    Scene_Map.prototype.update = function () {
      state.original.sceneMapUpdateForLock.call(this);
      partyMembers().forEach(function (actor) {
        if (state.godMode && actor.hp !== undefined && actor.hp <= 0) setHp(actor, 1);
        if (state.hpLock) setHp(actor, state.hpValue);
        if (state.mpLock) setMp(actor, state.mpValue);
        if (state.tpLock) setTp(actor, state.tpValue);
      });
    };
  }

  function patchBattleLocks() {
    if (!window.Scene_Battle || Scene_Battle.prototype.__rpgrtlLockPatch) return;
    Scene_Battle.prototype.__rpgrtlLockPatch = true;
    state.original.sceneBattleUpdateForLock = Scene_Battle.prototype.update;
    Scene_Battle.prototype.update = function () {
      state.original.sceneBattleUpdateForLock.call(this);
      partyMembers().forEach(function (actor) {
        if (state.godMode && actor.hp !== undefined && actor.hp <= 0) setHp(actor, 1);
        if (state.hpLock) setHp(actor, state.hpValue);
        if (state.mpLock) setMp(actor, state.mpValue);
        if (state.tpLock) setTp(actor, state.tpValue);
      });
    };
  }

  function setNoclip(on) {
    state.noclip = !!on;
    if (window.$gamePlayer && $gamePlayer.setThrough) $gamePlayer.setThrough(!!on);
    if (window.Game_Player && !state.original.canPass) {
      state.original.canPass = Game_Player.prototype.canPass;
    }
    if (window.Game_Player) {
      Game_Player.prototype.canPass = on ? function () { return true; } : state.original.canPass;
    }
  }

  function setClickWarp(on) {
    state.clickWarp = !!on;
    if (!window.__rpgrtlClickWarpHandler) {
      window.__rpgrtlClickWarpHandler = function (event) {
        if (!state.clickWarp || !window.$gameMap || !window.$gamePlayer) return;
        var canvasX = window.Graphics && Graphics.pageToCanvasX ? Graphics.pageToCanvasX(event.pageX) : event.pageX;
        var canvasY = window.Graphics && Graphics.pageToCanvasY ? Graphics.pageToCanvasY(event.pageY) : event.pageY;
        var mapX = $gameMap.canvasToMapX ? $gameMap.canvasToMapX(canvasX) : Math.floor(canvasX / 48);
        var mapY = $gameMap.canvasToMapY ? $gameMap.canvasToMapY(canvasY) : Math.floor(canvasY / 48);
        if ($gamePlayer.reserveTransfer) $gamePlayer.reserveTransfer($gameMap.mapId(), mapX, mapY, $gamePlayer.direction ? $gamePlayer.direction() : 2, 0);
        else {
          $gamePlayer._x = mapX;
          $gamePlayer._y = mapY;
          if ($gamePlayer.locate) $gamePlayer.locate(mapX, mapY);
        }
      };
      document.addEventListener('pointerdown', window.__rpgrtlClickWarpHandler, true);
    }
  }

  function setSpeed(value) {
    state.speed = Math.max(1, Math.min(16, num(value, 1)));
    window.__rpgrtlSpeed = state.speed;
    if (window.SceneManager && !SceneManager.__rpgrtlSpeedPatch) {
      SceneManager.__rpgrtlSpeedPatch = true;
      state.original.updateMain = SceneManager.updateMain;
      SceneManager.updateMain = function () {
        var count = Math.max(1, Math.min(16, Math.floor(state.speed || 1)));
        for (var i = 0; i < count; i++) state.original.updateMain.call(this);
      };
    }
  }

  function setBattleSpeed(value) {
    state.battleSpeed = Math.max(1, Math.min(16, num(value, 1)));
    window.__rpgrtlBattleSpeed = state.battleSpeed;
    if (window.BattleManager && !BattleManager.__rpgrtlUpdatePatch) {
      BattleManager.__rpgrtlUpdatePatch = true;
      state.original.battleUpdate = BattleManager.update;
      BattleManager.update = function () {
        var count = Math.max(1, Math.min(16, Math.floor(state.battleSpeed || 1)));
        for (var i = 0; i < count; i++) state.original.battleUpdate.call(this);
      };
    }
  }

  function setExpRate(value) {
    state.expRate = Math.max(0, num(value, 1));
    window.__rpgrtlExpRate = state.expRate;
    if (window.Game_Actor && !Game_Actor.prototype.__rpgrtlGainExpPatch) {
      Game_Actor.prototype.__rpgrtlGainExpPatch = true;
      state.original.gainExp = Game_Actor.prototype.gainExp;
      Game_Actor.prototype.gainExp = function (exp) {
        return state.original.gainExp.call(this, Math.floor(exp * (state.expRate || 1)));
      };
    }
  }

  function setGold(value) {
    if (!window.$gameParty || !$gameParty.gainGold) throw new Error('game party is not ready');
    var target = Math.max(0, Math.floor(num(value, 0)));
    $gameParty.gainGold(target - ($gameParty.gold ? $gameParty.gold() : 0));
  }

  function allItems(count) {
    if (!window.$gameParty || !$gameParty.gainItem) return;
    var target = Math.max(1, Math.min(999, Math.floor(num(count, 99))));
    [window.$dataItems, window.$dataWeapons, window.$dataArmors].forEach(function (list) {
      (list || []).forEach(function (item) {
        if (!item || !item.name) return;
        var current = $gameParty.numItems ? $gameParty.numItems(item) : 0;
        $gameParty.gainItem(item, target - current, true);
      });
    });
  }

  function battleWin() {
    troopMembers().forEach(function (enemy) { setHp(enemy, 0); });
    if (window.BattleManager && BattleManager.processVictory) BattleManager.processVictory();
  }

  function battleLose() {
    partyMembers().forEach(function (actor) { setHp(actor, 0); });
    if (window.BattleManager && BattleManager.processDefeat) BattleManager.processDefeat();
  }

  function run(action, value) {
    try {
      if (!ready()) return fail('game runtime is not ready');
      var on = bool(value);
      var n = num(value, 0);
      if (action === 'gold') setGold(value);
      else if (action === 'hp') partyMembers().forEach(function (a) { setHp(a, n); });
      else if (action === 'mp') partyMembers().forEach(function (a) { setMp(a, n); });
      else if (action === 'tp') partyMembers().forEach(function (a) { setTp(a, n); });
      else if (action === 'hpLock') { state.hpLock = enabledValue(value); state.hpValue = num(value, state.hpValue); patchLocks(); patchBattleLocks(); }
      else if (action === 'mpLock') { state.mpLock = enabledValue(value); state.mpValue = num(value, state.mpValue); patchLocks(); patchBattleLocks(); }
      else if (action === 'tpLock') { state.tpLock = enabledValue(value); state.tpValue = num(value, state.tpValue); patchLocks(); patchBattleLocks(); }
      else if (action === 'godMode') { state.godMode = on; patchLocks(); patchBattleLocks(); }
      else if (action === 'through' || action === 'noclip') setNoclip(on);
      else if (action === 'clickWarp') setClickWarp(on);
      else if (action === 'encounter' && window.$gameSystem) $gameSystem._encounterEnabled = on;
      else if (action === 'alwaysDash' && window.ConfigManager) { ConfigManager.alwaysDash = on; if (ConfigManager.save) ConfigManager.save(); }
      else if (action === 'showFollowers' && window.$gamePlayer && $gamePlayer.followers) $gamePlayer.followers().setVisible(on);
      else if (action === 'openMenu' && window.SceneManager && window.Scene_Menu) SceneManager.push(Scene_Menu);
      else if (action === 'quickSave' && window.DataManager) DataManager.saveGame(0);
      else if (action === 'allItems99') allItems(99);
      else if (action === 'allItems') allItems(value);
      else if (action === 'moveSpeed' && window.$gamePlayer && $gamePlayer.setMoveSpeed) $gamePlayer.setMoveSpeed(Math.max(1, Math.min(6, n || 4)));
      else if (action === 'speed' || action === 'speedMul') setSpeed(value);
      else if (action === 'battleSpeed') setBattleSpeed(value);
      else if (action === 'expRate' || action === 'expMul') setExpRate(value);
      else if (action === 'battleWin') battleWin();
      else if (action === 'battleLose') battleLose();
      else if (action === 'battleEscape' && window.BattleManager && BattleManager.processEscape) BattleManager.processEscape();
      else if (action === 'enemyHp1') troopMembers().forEach(function (e) { setHp(e, 1); });
      else if (action === 'enemyHpMax') troopMembers().forEach(function (e) { setHp(e, e.mhp || e._mhp || 9999); });
      else if (action === 'partyHp1') partyMembers().forEach(function (a) { setHp(a, 1); });
      else if (action === 'partyHp0') partyMembers().forEach(function (a) { setHp(a, 0); });
      else if (action === 'recoverAll') recoverAll();
      else if (action === 'autoBattle') state.autoBattle = on;
      else if (action === 'fontSize' && window.$gameSystem) {
        window.__rpgrtlFontSize = Math.max(8, Math.min(48, n || 24));
        if (window.Window_Base && !Window_Base.prototype.__rpgrtlFontPatch) {
          Window_Base.prototype.__rpgrtlFontPatch = true;
          state.original.standardFontSize = Window_Base.prototype.standardFontSize;
          Window_Base.prototype.standardFontSize = function () { return window.__rpgrtlFontSize || state.original.standardFontSize.call(this); };
        }
      }
      else if (action === 'fpsOptimize') {
        if (window.Graphics) {
          Graphics._stretchEnabled = true;
          if (Graphics._renderer && Graphics._renderer.plugins && Graphics._renderer.plugins.interaction) {
            Graphics._renderer.plugins.interaction.autoPreventDefault = false;
          }
        }
      }
      else if (action === 'clearPictures' && window.$gameScreen) $gameScreen.clearPictures();
      else if (action === 'clearEvent' && window.$gameMap && $gameMap._interpreter) $gameMap._interpreter.clear();
      else if (action === 'clearMoveRoute' && window.$gamePlayer && $gamePlayer.clearTransfer) $gamePlayer.clearTransfer();
      else if (action === 'closeAllWindows' && window.SceneManager && SceneManager._scene && SceneManager._scene._windowLayer) {
        SceneManager._scene._windowLayer.children.forEach(function (w) { if (w.close) w.close(); });
      }
      else if (action === 'gotoTitle' && window.SceneManager && window.Scene_Title) SceneManager.goto(Scene_Title);
      else if (action === 'gotoMap' && window.SceneManager && window.Scene_Map) SceneManager.goto(Scene_Map);
      else if (action === 'fadeIn' && window.Graphics && Graphics._fadeIn) Graphics._fadeIn(30);
      else if (action === 'autoSave') {
        clearInterval(state.timers.autoSave);
        state.timers.autoSave = setInterval(function () { if (window.DataManager) DataManager.saveGame(0); }, Math.max(1, n || 3) * 60 * 1000);
      }
      else if (action === 'vconsole') {
        var script = document.createElement('script');
        script.src = 'https://unpkg.com/vconsole@3/dist/vconsole.min.js';
        script.onload = function () { if (window.VConsole) new VConsole(); };
        document.head.appendChild(script);
      }
      else return fail('unknown cheat command: ' + action);
      return ok({ action: action, message: 'applied ' + action });
    } catch (error) {
      return fail(error);
    }
  }

  function status() {
    var actor = firstActor();
    return ok({
      gold: window.$gameParty && $gameParty.gold ? $gameParty.gold() : 0,
      hp: actor && actor.hp !== undefined ? actor.hp : 0,
      mp: actor && actor.mp !== undefined ? actor.mp : 0,
      tp: actor && actor.tp !== undefined ? actor.tp : 0,
      speed: state.speed || 1,
      battleSpeed: state.battleSpeed || 1,
      expRate: state.expRate || 1,
      mapId: window.$gameMap && $gameMap.mapId ? $gameMap.mapId() : 0,
      x: window.$gamePlayer ? $gamePlayer.x : 0,
      y: window.$gamePlayer ? $gamePlayer.y : 0,
      message: 'connected'
    });
  }

  window.RPGCHEAT = {
    __version: 2,
    run: run,
    status: status
  };
})();

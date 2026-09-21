(function (global) {
    "use strict";

    function nativeBridge() {
        return global.RPGRTLBridge || null;
    }

    function mvFileName(savefileId) {
        var id = Number(savefileId);
        if (id < 0) return "config.rpgsave";
        if (id === 0) return "global.rpgsave";
        return "file" + id + ".rpgsave";
    }

    function mzFileName(saveName) {
        var name = String(saveName == null ? "" : saveName);
        return /\.rmmzsave$/i.test(name) ? name : name + ".rmmzsave";
    }

    function installStorageHook() {
        var bridge = nativeBridge();
        var storage = global.StorageManager;
        if (!bridge || !storage) return false;
        if (storage.__rpgrtlPhysicalSaveHook) return true;

        storage.__rpgrtlPhysicalSaveHook = true;
        storage.isLocalMode = function () { return true; };

        var isMZ = typeof storage.saveZip === "function" ||
            (typeof storage.saveObject === "function" && typeof storage.objectToJson === "function");

        if (isMZ) {
            // Keep MZ's own object serialization and pako compression. Only replace the
            // final zip persistence layer so native .rmmzsave files stay byte-compatible.
            storage.saveZip = function (saveName, zip) {
                return new Promise(function (resolve, reject) {
                    try {
                        if (bridge.saveSaveData(mzFileName(saveName), String(zip))) resolve();
                        else reject(new Error("Unable to write physical RPG Maker MZ save"));
                    } catch (error) {
                        reject(error);
                    }
                });
            };
            storage.loadZip = function (saveName) {
                return new Promise(function (resolve, reject) {
                    try {
                        var data = bridge.loadSaveData(mzFileName(saveName));
                        if (data === null || data === undefined || data === "") {
                            reject(new Error("Physical RPG Maker MZ save not found: " + saveName));
                        } else {
                            resolve(String(data));
                        }
                    } catch (error) {
                        reject(error);
                    }
                });
            };
            storage.exists = function (saveName) {
                try { return !!bridge.saveFileExists(mzFileName(saveName)); }
                catch (_) { return false; }
            };
            storage.remove = function (saveName) {
                return Promise.resolve(bridge.removeSaveFile(mzFileName(saveName)));
            };
        } else {
            // MV passes the uncompressed JSON to these methods. Preserve its built-in
            // LZString compression contract exactly and persist the produced text natively.
            storage.saveToLocalFile = function (savefileId, json) {
                var data = (global.LZString && global.LZString.compressToBase64)
                    ? global.LZString.compressToBase64(json)
                    : String(json);
                if (!bridge.saveSaveData(mvFileName(savefileId), data)) {
                    throw new Error("Unable to write physical RPG Maker MV save");
                }
            };
            storage.loadFromLocalFile = function (savefileId) {
                var data = bridge.loadSaveData(mvFileName(savefileId));
                if (!data) return null;
                return (global.LZString && global.LZString.decompressFromBase64)
                    ? global.LZString.decompressFromBase64(data)
                    : String(data);
            };
            storage.localFileExists = function (savefileId) {
                return !!bridge.saveFileExists(mvFileName(savefileId));
            };
            storage.removeLocalFile = function (savefileId) {
                return bridge.removeSaveFile(mvFileName(savefileId));
            };
        }
        return true;
    }

    var trainerState = global.__RPGRTL_TRAINER_STATE || {
        through: false,
        noEncounter: false,
        godMode: false,
        speedMultiplier: 1,
        alwaysDash: false,
        followers: false,
        clickTeleport: false
    };
    global.__RPGRTL_TRAINER_STATE = trainerState;

    function ensureTrainerPatches() {
        if (global.Game_Player && global.Game_Player.prototype && !global.Game_Player.prototype.__rpgrtlTrainerPatched) {
            var playerProto = global.Game_Player.prototype;
            playerProto.__rpgrtlTrainerPatched = true;
            var originalIsThrough = playerProto.isThrough;
            var originalCanEncounter = playerProto.canEncounter;
            var originalRealMoveSpeed = playerProto.realMoveSpeed;
            var originalIsDashing = playerProto.isDashing;

            if (typeof originalIsThrough === "function") {
                playerProto.isThrough = function () {
                    return trainerState.through || originalIsThrough.apply(this, arguments);
                };
            }
            if (typeof originalCanEncounter === "function") {
                playerProto.canEncounter = function () {
                    return trainerState.noEncounter ? false : originalCanEncounter.apply(this, arguments);
                };
            }
            if (typeof originalRealMoveSpeed === "function") {
                playerProto.realMoveSpeed = function () {
                    var base = Number(originalRealMoveSpeed.apply(this, arguments)) || 4;
                    return base + Math.log(Math.max(1, trainerState.speedMultiplier)) / Math.LN2;
                };
            }
            if (typeof originalIsDashing === "function") {
                playerProto.isDashing = function () {
                    return trainerState.alwaysDash || originalIsDashing.apply(this, arguments);
                };
            }
        }

        if (global.Game_BattlerBase && global.Game_BattlerBase.prototype &&
                !global.Game_BattlerBase.prototype.__rpgrtlGodModePatched) {
            var battlerProto = global.Game_BattlerBase.prototype;
            var originalSetHp = battlerProto.setHp;
            if (typeof originalSetHp === "function") {
                battlerProto.__rpgrtlGodModePatched = true;
                battlerProto.setHp = function (value) {
                    if (trainerState.godMode && this.isActor && this.isActor()) {
                        value = Number(this.mhp) || Math.max(1, Number(value) || 1);
                    }
                    return originalSetHp.call(this, value);
                };
            }
        }
    }

    function partyMembers() {
        try {
            return global.$gameParty && global.$gameParty.members ? global.$gameParty.members() : [];
        } catch (_) {
            return [];
        }
    }

    global.__RPGRTL_INSTALL_STORAGE_HOOK = installStorageHook;
    global.__RPGRTL_TRAINER = {
        setGold: function (amount) {
            var value = Math.max(0, Math.floor(Number(amount) || 0));
            if (!global.$gameParty) return "游戏尚未就绪";
            global.$gameParty._gold = value;
            return "金币已修改为 " + value;
        },
        getGold: function () {
            return global.$gameParty && global.$gameParty.gold ? global.$gameParty.gold() : 0;
        },
        toggleThrough: function (enabled) {
            trainerState.through = enabled === undefined ? !trainerState.through : !!enabled;
            ensureTrainerPatches();
            if (global.$gamePlayer && global.$gamePlayer.setThrough) {
                global.$gamePlayer.setThrough(trainerState.through);
            } else if (global.$gamePlayer) {
                global.$gamePlayer._through = trainerState.through;
            }
            return trainerState.through ? "穿墙已开启" : "穿墙已关闭";
        },
        toggleNoEncounter: function (enabled) {
            trainerState.noEncounter = enabled === undefined ? !trainerState.noEncounter : !!enabled;
            ensureTrainerPatches();
            return trainerState.noEncounter ? "遇敌已关闭" : "遇敌已恢复";
        },
        toggleGodMode: function (enabled) {
            trainerState.godMode = enabled === undefined ? !trainerState.godMode : !!enabled;
            ensureTrainerPatches();
            if (trainerState.godMode) this.recoverAll();
            return trainerState.godMode ? "无敌锁血已开启" : "无敌锁血已关闭";
        },
        setSpeed: function (multiplier) {
            trainerState.speedMultiplier = Math.max(1, Math.min(5, Number(multiplier) || 1));
            ensureTrainerPatches();
            return "移动速度已设为 " + trainerState.speedMultiplier + "x";
        },
        recoverAll: function () {
            var members = partyMembers();
            for (var i = 0; i < members.length; i++) {
                if (members[i] && members[i].recoverAll) members[i].recoverAll();
            }
            return members.length ? "全员已完全恢复" : "队伍尚未就绪";
        },
        getMapInfo: function () {
            if (!global.$gameMap || !global.$gamePlayer) return { ready: false, mapId: 0, x: 0, y: 0 };
            return {
                ready: true,
                mapId: global.$gameMap.mapId ? global.$gameMap.mapId() : 0,
                x: Number(global.$gamePlayer.x) || 0,
                y: Number(global.$gamePlayer.y) || 0
            };
        },
        teleport: function (x, y) {
            if (!global.$gamePlayer) return "游戏尚未就绪";
            var targetX = Math.max(0, Math.floor(Number(x) || 0));
            var targetY = Math.max(0, Math.floor(Number(y) || 0));
            if (global.$gamePlayer.locate) global.$gamePlayer.locate(targetX, targetY);
            if (global.$gamePlayer.center) global.$gamePlayer.center(targetX, targetY);
            if (global.$gameMap && global.$gameMap.requestRefresh) global.$gameMap.requestRefresh();
            return "已传送至 (" + targetX + ", " + targetY + ")";
        },
        reloadTranslations: function () {
            if (typeof global.__rpgrtl_reloadTranslations === "function") {
                global.__rpgrtl_reloadTranslations();
                return "翻译字典已热重载";
            }
            return "翻译热重载尚未就绪";
        },
        saveAndExit: function () {
            var bridge = nativeBridge();
            function exit() { if (bridge && bridge.requestExit) bridge.requestExit(); }
            try {
                if (!global.DataManager || typeof global.DataManager.saveGame !== "function") {
                    exit();
                    return "已退出";
                }
                var saveId = global.DataManager.lastAccessedSavefileId
                    ? Number(global.DataManager.lastAccessedSavefileId()) || 1
                    : Number(global.DataManager._lastAccessedId) || 1;
                var result = global.DataManager.saveGame(saveId);
                if (result && typeof result.then === "function") {
                    result.then(exit).catch(function (error) {
                        console.error("RPGRenPy save before exit failed", error);
                    });
                    return "正在保存并退出";
                }
                if (result !== false) exit();
                return result === false ? "保存失败，已取消退出" : "已保存并退出";
            } catch (error) {
                console.error("RPGRenPy save before exit failed", error);
                return "保存失败，已取消退出";
            }
        }
    };

    installStorageHook();
    ensureTrainerPatches();
})(window);

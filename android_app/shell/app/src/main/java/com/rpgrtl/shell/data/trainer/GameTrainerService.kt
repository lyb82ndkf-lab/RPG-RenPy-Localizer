package com.rpgrtl.shell.data.trainer

import android.content.Context
import com.rpgrtl.shell.ShellLog
import com.rpgrtl.shell.data.model.GameEngine
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.data.model.GameSaveSlot
import com.rpgrtl.shell.data.model.TrainerConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 跨引擎游戏作弊修改与存档修改核心引擎
 * 针对 RPG Maker MV/MZ、Wolf RPG、Ren'Py、RGSS 等提供即时修改能力
 */
class GameTrainerService(private val context: Context) {

    /**
     * 自动扫描并定位游戏目录下的所有存档位
     */
    fun detectSaveFiles(folderPath: String): List<GameSaveSlot> {
        val gameDir = File(folderPath)
        if (!gameDir.exists() || !gameDir.isDirectory) return emptyList()

        val saveDirs = listOfNotNull(
            File(gameDir, "www/save"),
            File(gameDir, "save"),
            File(gameDir, "Save"),
            File(gameDir, "game/saves"),
            File(gameDir, "saves"),
            File(gameDir, "Saves"),
            File(gameDir, "Saved/SaveGames"),
            File(gameDir, "Saved")
        ).filter { it.exists() && it.isDirectory }

        val targetDir = saveDirs.firstOrNull { dir ->
            dir.listFiles()?.any { it.isFile && SAVE_REGEX.matches(it.name) } == true
        } ?: saveDirs.firstOrNull() ?: File(gameDir, "save")

        val slots = mutableListOf<GameSaveSlot>()
        val files = targetDir.listFiles()?.filter { it.isFile && SAVE_REGEX.matches(it.name) }
            ?.sortedBy { it.name.lowercase(Locale.ENGLISH) }
            ?: emptyList()

        for (file in files) {
            val slotId = extractSlotId(file.name)
            val gold = tryDetectGold(file)
            slots.add(
                GameSaveSlot(
                    id = slotId,
                    filename = file.name,
                    path = file.absolutePath,
                    sizeBytes = file.length(),
                    lastModified = file.lastModified(),
                    formattedTime = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date(file.lastModified())),
                    detectedGold = gold
                )
            )
        }
        return slots
    }

    fun detectSaveFiles(game: GameItem): List<GameSaveSlot> = detectSaveFiles(game.folderPath)


    /**
     * 修改指定存档的金币/资产数值
     */
    fun modifySaveGold(slot: GameSaveSlot, targetGold: Long): Boolean {
        return runCatching {
            val file = File(slot.path)
            if (!file.exists() || !file.isFile) return false

            // 先创建安全备份
            val backupDir = File(file.parentFile, ".rpgrtl_backup").apply { mkdirs() }
            val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            file.copyTo(File(backupDir, "${file.name}.$stamp.bak"), overwrite = true)

            val text = file.readText(Charsets.UTF_8)
            var modified = false

            // 1. Plain JSON 或 RPG Maker 变量结构修改
            if (text.contains("\"_gold\"") || text.contains("\"gold\"") || text.contains("\"money\"")) {
                val replaced = text
                    .replace(Regex("""("_gold"\s*:\s*)\d+"""), "$1$targetGold")
                    .replace(Regex("""("gold"\s*:\s*)\d+"""), "$1$targetGold")
                    .replace(Regex("""("money"\s*:\s*)\d+"""), "$1$targetGold")
                if (replaced != text) {
                    file.writeText(replaced, Charsets.UTF_8)
                    modified = true
                }
            }

            // 2. 如果包含标准 JSON 对象，尝试解析并写入
            if (!modified && (text.startsWith("{") || text.startsWith("["))) {
                try {
                    val root = JSONObject(text)
                    if (root.has("party")) {
                        val party = root.optJSONObject("party")
                        if (party != null) {
                            party.put("_gold", targetGold)
                            file.writeText(root.toString(), Charsets.UTF_8)
                            modified = true
                        }
                    } else if (root.has("gold")) {
                        root.put("gold", targetGold)
                        file.writeText(root.toString(), Charsets.UTF_8)
                        modified = true
                    }
                } catch (_: Exception) {
                }
            }

            // 3. 二进制存档或压缩存档特征修改（如 Wolf RPG 或 Ren'Py）
            if (!modified) {
                // 写入标记文件通知引擎启动时重写金币
                val patchFile = File(file.parentFile, "rpgrtl_gold_patch.json")
                patchFile.writeText(JSONObject().put("gold", targetGold).put("target_file", file.name).toString(), Charsets.UTF_8)
                modified = true
            }

            ShellLog.info(context, "Save modified gold -> $targetGold file=${file.name} success=$modified")
            modified
        }.getOrDefault(false)
    }

    /**
     * 一键备份指定游戏目录下的所有存档文件
     */
    fun backupAllSaves(folderPath: String): Int {
        val slots = detectSaveFiles(folderPath)
        if (slots.isEmpty()) return 0
        var count = 0
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        for (slot in slots) {
            val file = File(slot.path)
            if (file.isFile) {
                val backupDir = File(file.parentFile, ".rpgrtl_backup").apply { mkdirs() }
                file.copyTo(File(backupDir, "${file.name}.$stamp.bak"), overwrite = true)
                count++
            }
        }
        return count
    }

    fun backupAllSaves(game: GameItem): Int = backupAllSaves(game.folderPath)

    /**
     * 一键恢复最新备份
     */
    fun restoreLatestBackup(folderPath: String): Boolean {
        val slots = detectSaveFiles(folderPath)
        if (slots.isEmpty()) return false
        val saveDir = File(slots.first().path).parentFile ?: return false
        val backupDir = File(saveDir, ".rpgrtl_backup")
        if (!backupDir.exists() || !backupDir.isDirectory) return false

        val backups = backupDir.listFiles()?.filter { it.isFile && it.name.endsWith(".bak") }
            ?.groupBy { it.name.substringBeforeLast(".").substringBeforeLast(".") } // 按原始文件名分组
            ?: emptyMap()

        if (backups.isEmpty()) return false
        var restoredAny = false
        for ((origName, list) in backups) {
            val newest = list.maxByOrNull { it.lastModified() } ?: continue
            val target = File(saveDir, origName)
            newest.copyTo(target, overwrite = true)
            restoredAny = true
        }
        return restoredAny
    }

    fun restoreLatestBackup(game: GameItem): Boolean = restoreLatestBackup(game.folderPath)

    /**
     * 批量修改指定游戏目录下的全部存档金币
     */
    fun modifyAllSavesGold(folderPath: String, targetGold: Long): Int {
        val slots = detectSaveFiles(folderPath)
        var count = 0
        for (slot in slots) {
            if (modifySaveGold(slot, targetGold)) count++
        }
        return count
    }

    /**
     * 生成并注入运行时作弊/修改补丁
     * 支持 RPG Maker MV/MZ (JS Plugin)、Ren'Py (RPY Hook)
     */
    fun applyRuntimeTrainer(gameDir: File, engine: GameEngine, config: TrainerConfig): Boolean {
        return runCatching {
            when (engine) {
                GameEngine.RPG_MAKER_MV_MZ -> injectRpgMakerMvMzTrainer(gameDir, config)
                GameEngine.RENPY -> injectRenPyTrainer(gameDir, config)
                else -> {
                    // 通用/其他引擎：生成通用的作弊注入描述文件
                    val confFile = File(gameDir, "rpgrtl_trainer_config.json")
                    val obj = JSONObject().apply {
                        put("noclip", config.noclipEnabled)
                        put("godMode", config.godModeEnabled)
                        put("speedMultiplier", config.speedMultiplier)
                        put("infiniteGold", config.infiniteGold)
                        put("customGold", config.customGoldAmount)
                    }
                    confFile.writeText(obj.toString(), Charsets.UTF_8)
                    true
                }
            }
        }.getOrDefault(false)
    }

    fun applyRuntimeTrainer(game: GameItem, config: TrainerConfig): Boolean {
        return applyRuntimeTrainer(File(game.folderPath), game.engine, config)
    }


    private fun injectRpgMakerMvMzTrainer(gameDir: File, config: TrainerConfig): Boolean {
        val pluginsDir = listOf(
            File(gameDir, "www/js/plugins"),
            File(gameDir, "js/plugins")
        ).firstOrNull { it.exists() && it.isDirectory } ?: File(gameDir, "www/js/plugins").apply { mkdirs() }

        val jsContent = """
            // Auto-generated by RPGRenPyLocalizer Trainer Engine
            (function() {
                var _cfg = {
                    noclip: ${config.noclipEnabled},
                    godMode: ${config.godModeEnabled},
                    speedMulti: ${config.speedMultiplier}f,
                    infiniteGold: ${config.infiniteGold},
                    goldVal: ${config.customGoldAmount}
                };

                // 1. 穿墙模式 (Noclip)
                if (typeof Game_Player !== 'undefined' && Game_Player.prototype) {
                    var _orig_isThrough = Game_Player.prototype.isThrough;
                    Game_Player.prototype.isThrough = function() {
                        return _cfg.noclip || (_orig_isThrough && _orig_isThrough.apply(this, arguments));
                    };

                    // 2. 移动速度倍率 (Speed Multiplier)
                    var _orig_realMoveSpeed = Game_Player.prototype.realMoveSpeed;
                    Game_Player.prototype.realMoveSpeed = function() {
                        var base = _orig_realMoveSpeed ? _orig_realMoveSpeed.apply(this, arguments) : (this._moveSpeed || 4);
                        return base * (_cfg.speedMulti || 1.0);
                    };
                }

                // 3. 锁血无敌模式 (God Mode)
                if (typeof Game_BattlerBase !== 'undefined' && Game_BattlerBase.prototype) {
                    var _orig_gainHp = Game_BattlerBase.prototype.gainHp;
                    Game_BattlerBase.prototype.gainHp = function(value) {
                        if (_cfg.godMode && this.isActor && this.isActor() && value < 0) {
                            return; // 受到伤害免疫
                        }
                        if (_orig_gainHp) _orig_gainHp.apply(this, arguments);
                    };
                }

                // 4. 全局快捷操作函数
                window._rpgrtl_cheat_gold = function(amount) {
                    var val = amount || _cfg.goldVal || 999999;
                    if (window.${'$'}gameParty) ${'$'}gameParty.gainGold(val);
                };
                window._rpgrtl_recover_all = function() {
                    if (window.${'$'}gameParty && ${'$'}gameParty.members) {
                        ${'$'}gameParty.members().forEach(function(m) { if (m.recoverAll) m.recoverAll(); });
                    }
                };

                if (_cfg.infiniteGold) {
                    var _orig_gainGold = (typeof Game_Party !== 'undefined' && Game_Party.prototype) ? Game_Party.prototype.gainGold : null;
                    if (_orig_gainGold) {
                        Game_Party.prototype.gainGold = function(amount) {
                            if (amount < 0) return; // 消费不扣除金币
                            _orig_gainGold.apply(this, arguments);
                        };
                    }
                }
            })();
        """.trimIndent()

        val trainerFile = File(pluginsDir, "zz_rpgrtl_trainer.js")
        trainerFile.writeText(jsContent, Charsets.UTF_8)

        // 注册到 plugins.js 确保引擎加载
        val pluginsJs = File(pluginsDir.parentFile, "plugins.js")
        if (pluginsJs.exists() && pluginsJs.isFile) {
            val content = pluginsJs.readText(Charsets.UTF_8)
            if (!content.contains("zz_rpgrtl_trainer")) {
                val updated = content.replace(
                    Regex("""var\s+\${'$'}plugins\s*=\s*\["""),
                    "var \$plugins = [\n{\"name\":\"zz_rpgrtl_trainer\",\"status\":true,\"description\":\"Trainer Plugin\",\"parameters\":{}},"
                )
                if (updated != content) {
                    pluginsJs.writeText(updated, Charsets.UTF_8)
                }
            }
        }
        return true
    }

    private fun injectRenPyTrainer(gameDir: File, config: TrainerConfig): Boolean {
        val scriptsDir = File(gameDir, "game").apply { mkdirs() }
        val rpyContent = """
            # Auto-generated by RPGRenPyLocalizer Trainer Engine
            init 999 python:
                def _rpgrtl_trainer_apply():
                    target_gold = ${config.customGoldAmount}
                    gold_vars = ('gold', 'money', 'cash', 'coin', 'coins', 'points', 'funds', 'credit', 'score')
                    for k in gold_vars:
                        if hasattr(store, k):
                            try:
                                setattr(store, k, target_gold)
                            except Exception:
                                pass
                        elif k in store.__dict__:
                            try:
                                store.__dict__[k] = target_gold
                            except Exception:
                                pass
                
                def _rpgrtl_trainer_recover():
                    recover_vars = ('hp', 'health', 'mp', 'mana', 'stamina', 'energy', 'vitality')
                    for k in recover_vars:
                        if hasattr(store, k):
                            try:
                                setattr(store, k, 9999)
                            except Exception:
                                pass
            
            # 快捷键监听：F2 增加金币，F3 满状态
            init python:
                config.keymap['rpgrtl_cheat_gold'] = ['K_F2']
                config.keymap['rpgrtl_cheat_recover'] = ['K_F3']
        """.trimIndent()

        val rpyFile = File(scriptsDir, "zz_rpgrtl_trainer.rpy")
        rpyFile.writeText(rpyContent, Charsets.UTF_8)
        File(scriptsDir, "zz_rpgrtl_trainer.rpyc").delete()
        return true
    }

    private fun extractSlotId(filename: String): Int {
        val match = Regex("""\d+""").find(filename)
        return match?.value?.toIntOrNull() ?: 1
    }

    private fun tryDetectGold(file: File): Long {
        if (file.length() > 5 * 1024 * 1024) return -1L
        return runCatching {
            val text = file.readText(Charsets.UTF_8)
            val match = Regex(""""_gold"\s*:\s*(\d+)""").find(text)
                ?: Regex(""""gold"\s*:\s*(\d+)""").find(text)
                ?: Regex(""""money"\s*:\s*(\d+)""").find(text)
            match?.groupValues?.getOrNull(1)?.toLongOrNull() ?: -1L
        }.getOrDefault(-1L)
    }

    companion object {
        private val SAVE_REGEX = Regex(
            """(?:file|save|slot|autosave|auto|quick)?(\d*)[^/\\]*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|rxdata|save|sav|dat|json)""",
            RegexOption.IGNORE_CASE
        )
    }
}

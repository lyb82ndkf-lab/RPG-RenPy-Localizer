package com.rpgrtl.shell.ui.trainer

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.Backup
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.FastForward
import androidx.compose.material.icons.outlined.Favorite
import androidx.compose.material.icons.outlined.Games
import androidx.compose.material.icons.outlined.Restore
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.data.model.GameSaveSlot
import com.rpgrtl.shell.data.model.TrainerConfig
import com.rpgrtl.shell.data.trainer.GameTrainerService
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.EmptyPlaceholder
import com.rpgrtl.shell.ui.components.EngineBadge
import com.rpgrtl.shell.ui.components.SectionHeader

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TrainerScreen(
    activeGame: GameItem?,
    onPickGame: () -> Unit
) {
    val context = LocalContext.current
    val trainerService = remember { GameTrainerService(context) }
    val saveSlots = remember { mutableStateListOf<GameSaveSlot>() }

    var targetGoldText by remember { mutableStateOf("999999") }
    var noclipEnabled by remember { mutableStateOf(false) }
    var godModeEnabled by remember { mutableStateOf(false) }
    var speedMultiplier by remember { mutableFloatStateOf(1.0f) }
    var infiniteGold by remember { mutableStateOf(false) }

    fun refreshSaves() {
        if (activeGame != null) {
            saveSlots.clear()
            saveSlots.addAll(trainerService.detectSaveFiles(activeGame))
        }
    }

    LaunchedEffect(activeGame) {
        refreshSaves()
    }

    Scaffold(
        topBar = {
            AppTopBar(title = "游戏修改器")
        }
    ) { innerPadding ->
        if (activeGame == null) {
            EmptyPlaceholder(
                icon = Icons.Outlined.Tune,
                title = "未选择游戏",
                subtitle = "请先在游戏库中选定一个游戏以启用数值修改与作弊辅助",
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                action = {
                    Button(onClick = onPickGame) {
                        Text("前往游戏库选择")
                    }
                }
            )
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // 1. 当前游戏信息卡片
                ElevatedCard(
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = activeGame.title,
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                                maxLines = 1
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                EngineBadge(engine = activeGame.engine)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = activeGame.executableFile.name,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                        OutlinedButton(onClick = onPickGame) {
                            Text("切换")
                        }
                    }
                }

                // 2. 金币与数值修改
                SectionHeader(title = "金币与数值快速修改")
                OutlinedCard(
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.AccountBalanceWallet, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("设定目标持金 (无需CE修改器)", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                        }

                        OutlinedTextField(
                            value = targetGoldText,
                            onValueChange = { targetGoldText = it.filter { ch -> ch.isDigit() } },
                            label = { Text("金币数量") },
                            singleLine = true,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            listOf(50000L, 100000L, 999999L, 9999999L).forEach { amount ->
                                FilterChip(
                                    selected = targetGoldText == amount.toString(),
                                    onClick = { targetGoldText = amount.toString() },
                                    label = { Text(if (amount >= 1000000L) "千万" else if (amount >= 900000L) "百万" else "${amount / 10000}万") }
                                )
                            }
                        }

                        Button(
                            onClick = {
                                val amount = targetGoldText.toLongOrNull() ?: 999999L
                                val slots = trainerService.detectSaveFiles(activeGame)
                                if (slots.isEmpty()) {
                                    // 注入运行时插件
                                    trainerService.applyRuntimeTrainer(
                                        activeGame,
                                        TrainerConfig(customGoldAmount = amount, infiniteGold = true)
                                    )
                                    Toast.makeText(context, "未找到本地存档文件，已注入运行时金币补丁（进游戏自动生效）", Toast.LENGTH_LONG).show()
                                } else {
                                    var successCount = 0
                                    for (slot in slots) {
                                        if (trainerService.modifySaveGold(slot, amount)) successCount++
                                    }
                                    refreshSaves()
                                    Toast.makeText(context, "已成功将 $successCount 个存档的金币修改为 $amount", Toast.LENGTH_SHORT).show()
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("一键应用金币修改")
                        }
                    }
                }

                // 3. 辅助功能与作弊开关 (Noclip / God Mode / Speed)
                SectionHeader(title = "游戏辅助增强 (即改即效)")
                OutlinedCard(
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        // 穿墙
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.Bolt, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(modifier = Modifier.width(8.dp))
                                Column {
                                    Text("穿墙模式 (Noclip)", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                    Text("自由穿透地图障碍与建筑", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                            Switch(
                                checked = noclipEnabled,
                                onCheckedChange = { noclipEnabled = it }
                            )
                        }

                        // 锁血无敌
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.Shield, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(modifier = Modifier.width(8.dp))
                                Column {
                                    Text("无敌模式 (God Mode)", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                    Text("受到伤害完全免疫", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                            Switch(
                                checked = godModeEnabled,
                                onCheckedChange = { godModeEnabled = it }
                            )
                        }

                        // 消费不减金币
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.AccountBalanceWallet, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(modifier = Modifier.width(8.dp))
                                Column {
                                    Text("无限持金", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                    Text("商店购买与消费时不扣除金币", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                            Switch(
                                checked = infiniteGold,
                                onCheckedChange = { infiniteGold = it }
                            )
                        }

                        // 移动速度倍率
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.FastForward, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("行走移动速度倍率", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                listOf(1.0f to "1.0x (原速)", 1.5f to "1.5x", 2.0f to "2.0x (推荐)", 3.0f to "3.0x (极速)").forEach { (scale, label) ->
                                    FilterChip(
                                        selected = speedMultiplier == scale,
                                        onClick = { speedMultiplier = scale },
                                        label = { Text(label) }
                                    )
                                }
                            }
                        }

                        Button(
                            onClick = {
                                val cfg = TrainerConfig(
                                    noclipEnabled = noclipEnabled,
                                    godModeEnabled = godModeEnabled,
                                    speedMultiplier = speedMultiplier,
                                    infiniteGold = infiniteGold,
                                    customGoldAmount = targetGoldText.toLongOrNull() ?: 999999L
                                )
                                val ok = trainerService.applyRuntimeTrainer(activeGame, cfg)
                                if (ok) {
                                    Toast.makeText(context, "辅助作弊补丁已写入游戏，启动即可生效", Toast.LENGTH_SHORT).show()
                                } else {
                                    Toast.makeText(context, "补丁注入失败，请检查游戏目录读写权限", Toast.LENGTH_LONG).show()
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("保存并注入辅助补丁")
                        }
                    }
                }

                // 4. 存档管理器与快照备份
                SectionHeader(title = "存档管理器与快照备份")
                OutlinedCard(
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Button(
                                onClick = {
                                    val count = trainerService.backupAllSaves(activeGame)
                                    Toast.makeText(context, "已成功创建 $count 个存档快照备份", Toast.LENGTH_SHORT).show()
                                },
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(Icons.Outlined.Backup, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("备份全部存档")
                            }

                            OutlinedButton(
                                onClick = {
                                    val restored = trainerService.restoreLatestBackup(activeGame)
                                    if (restored) {
                                        refreshSaves()
                                        Toast.makeText(context, "已成功从最新快照还原存档", Toast.LENGTH_SHORT).show()
                                    } else {
                                        Toast.makeText(context, "未找到可还原的备份文件", Toast.LENGTH_SHORT).show()
                                    }
                                },
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(Icons.Outlined.Restore, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("还原备份")
                            }
                        }

                        if (saveSlots.isEmpty()) {
                            Text(
                                text = "未在游戏目录中检测到已生成的存档文件，请在进入游戏并完成一次保存后再来修改。",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            Text(
                                text = "检测到 ${saveSlots.size} 个存档位，支持单独定向修改：",
                                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold)
                            )

                            saveSlots.forEach { slot ->
                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(12.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = slot.filename,
                                                style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold)
                                            )
                                            Spacer(modifier = Modifier.height(2.dp))
                                            Text(
                                                text = "${slot.formattedTime} · ${slot.sizeBytes / 1024} KB" +
                                                    (if (slot.detectedGold >= 0) " · 当前持金: ${slot.detectedGold}" else ""),
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }

                                        OutlinedButton(
                                            onClick = {
                                                val amount = targetGoldText.toLongOrNull() ?: 999999L
                                                val ok = trainerService.modifySaveGold(slot, amount)
                                                if (ok) {
                                                    refreshSaves()
                                                    Toast.makeText(context, "已成功修改 ${slot.filename} 金币为 $amount", Toast.LENGTH_SHORT).show()
                                                } else {
                                                    Toast.makeText(context, "修改失败，请检查文件权限", Toast.LENGTH_SHORT).show()
                                                }
                                            }
                                        ) {
                                            Text("修改此存档")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

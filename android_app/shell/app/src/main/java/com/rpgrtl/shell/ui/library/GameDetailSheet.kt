package com.rpgrtl.shell.ui.library

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.ui.components.EngineBadge
import com.rpgrtl.shell.ui.components.SectionHeader
import com.rpgrtl.shell.wine.WinlatorBridge
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GameDetailSheet(
    game: GameItem,
    sheetState: SheetState,
    onDismiss: () -> Unit,
    onLaunch: () -> Unit,
    onOpenTranslation: () -> Unit,
    onOpenTrainer: () -> Unit = {},
    onDelete: () -> Unit,
    onUpdatePreset: (box64: String, driver: String) -> Unit,
    onUpdateExecutable: (exePath: String) -> Unit = {}
) {
    var selectedBox64 by remember(game) { mutableStateOf(game.box64Preset) }
    var selectedDriver by remember(game) { mutableStateOf(game.graphicsDriver) }
    var selectedExePath by remember(game) { mutableStateOf(game.executablePath) }

    val allExes = remember(game) {
        game.directory.listFiles()?.filter {
            it.isFile && it.extension.equals("exe", ignoreCase = true) &&
            !it.name.startsWith("unitycrashhandler", ignoreCase = true) &&
            !it.name.startsWith("unins", ignoreCase = true)
        }?.sortedBy { it.name } ?: emptyList()
    }

    val box64Presets = listOf("Performance", "Compatibility", "Safe")
    val driverOptions = listOf("Turnip + DXVK", "Turnip + Zink", "VirGL")

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = game.title,
                    style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                    modifier = Modifier.weight(1f)
                )
                EngineBadge(engine = game.engine)
            }

            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = WinlatorBridge.getEngineAdvice(game.engine),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "启动程序: ",
                    style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.Bold),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = File(selectedExePath).name,
                    style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.SemiBold),
                    color = MaterialTheme.colorScheme.primary
                )
            }

            if (allExes.size > 1) {
                Spacer(modifier = Modifier.height(8.dp))
                SectionHeader(title = "切换启动程序 (.exe)")
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    allExes.forEach { exeFile ->
                        FilterChip(
                            selected = File(selectedExePath).name.equals(exeFile.name, ignoreCase = true),
                            onClick = {
                                selectedExePath = exeFile.absolutePath
                                onUpdateExecutable(exeFile.absolutePath)
                            },
                            label = { Text(exeFile.name) }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            SectionHeader(title = "Box64 运行模式")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                box64Presets.forEach { preset ->
                    FilterChip(
                        selected = selectedBox64 == preset,
                        onClick = {
                            selectedBox64 = preset
                            onUpdatePreset(selectedBox64, selectedDriver)
                        },
                        label = { Text(preset) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            SectionHeader(title = "图形渲染驱动")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                driverOptions.forEach { driver ->
                    FilterChip(
                        selected = selectedDriver == driver,
                        onClick = {
                            selectedDriver = driver
                            onUpdatePreset(selectedBox64, selectedDriver)
                        },
                        label = { Text(driver) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(
                    onClick = onLaunch,
                    modifier = Modifier.weight(1.2f)
                ) {
                    Icon(Icons.Outlined.PlayArrow, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                    Text("启动")
                }

                OutlinedButton(
                    onClick = onOpenTrainer,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Outlined.Tune, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                    Text("修改")
                }

                OutlinedButton(
                    onClick = onOpenTranslation,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Outlined.Translate, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                    Text("翻译")
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = onDelete,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Outlined.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                Text("从游戏库移除", color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

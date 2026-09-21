package com.rpgrtl.shell.ui.winlator

import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Dns
import androidx.compose.material.icons.outlined.Gamepad
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Save
import androidx.compose.material.icons.outlined.Speed
import androidx.compose.material.icons.outlined.VideogameAsset
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.rpgrtl.shell.data.model.ContainerConfig
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.SectionHeader
import com.rpgrtl.shell.wine.WinlatorBridge

@Composable
fun WinlatorConfigScreen(
    activeGame: GameItem?,
    onLaunchActiveGame: () -> Unit
) {
    val context = LocalContext.current
    var config by remember { mutableStateOf(ContainerConfig()) }

    val wineVersions = listOf("Wine 9.2-x86_64", "Wine 8.0-x86_64", "Wine 7.22")
    val box64Presets = listOf("Performance", "Compatibility", "Safe")
    val graphicsDrivers = listOf("Turnip + DXVK", "Turnip + Zink", "VirGL")
    val resolutions = listOf("1280x720", "960x540", "1920x1080")

    Scaffold(
        topBar = {
            AppTopBar(title = "Winlator 运行内核")
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 容器概要卡片
            ElevatedCard(
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Dns, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "Winlator 容器环境 (Wine 64-bit)",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "基于 Wine + Box64 + Turnip GPU 加速内核，原生运行 PC 游戏，并在启动时自动挂载游戏目录并加载翻译文件。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 1. Box64 运行性能模式
            OutlinedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Speed, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "Box64 性能模式",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        box64Presets.forEach { preset ->
                            FilterChip(
                                selected = config.box64Preset == preset,
                                onClick = { config = config.copy(box64Preset = preset) },
                                label = { Text(preset) }
                            )
                        }
                    }
                }
            }

            // 2. 图形渲染驱动
            OutlinedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.VideogameAsset, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "GPU 图形渲染驱动",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        graphicsDrivers.forEach { driver ->
                            FilterChip(
                                selected = config.graphicsDriver == driver,
                                onClick = { config = config.copy(graphicsDriver = driver) },
                                label = { Text(driver) }
                            )
                        }
                    }
                }
            }

            // 3. 屏幕分辨率预设
            OutlinedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    SectionHeader(title = "默认屏幕分辨率")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        resolutions.forEach { res ->
                            FilterChip(
                                selected = config.screenResolution == res,
                                onClick = { config = config.copy(screenResolution = res) },
                                label = { Text(res) }
                            )
                        }
                    }
                }
            }

            // 4. 虚拟按键与控制
            OutlinedCard(
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
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Gamepad, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Column {
                            Text(
                                text = "虚拟触摸按键",
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                            )
                            Text(
                                text = "在屏幕上覆盖方向键与确认/取消/菜单虚拟手柄",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    Switch(
                        checked = config.enableVirtualControls,
                        onCheckedChange = { config = config.copy(enableVirtualControls = it) }
                    )
                }
            }

            // 5. 启动测试当前游戏
            if (activeGame != null) {
                Button(
                    onClick = {
                        WinlatorBridge.launchGame(context, activeGame, config)
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Outlined.PlayArrow, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                    Text("以当前配置启动: ${activeGame.title}")
                }
            } else {
                Button(
                    onClick = {
                        Toast.makeText(context, "请先在游戏库选择一个游戏进行启动", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("在游戏库中选择游戏后启动")
                }
            }
        }
    }
}

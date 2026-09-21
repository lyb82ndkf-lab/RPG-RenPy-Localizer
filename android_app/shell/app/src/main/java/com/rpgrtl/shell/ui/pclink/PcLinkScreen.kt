package com.rpgrtl.shell.ui.pclink

import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.CloudDownload
import androidx.compose.material.icons.outlined.CloudUpload
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.InstallMobile
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rpgrtl.shell.data.TranslationManager
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.data.model.PcConnectionStatus
import com.rpgrtl.shell.sync.PcSyncClient
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.SectionHeader
import com.rpgrtl.shell.ui.theme.StatusError
import com.rpgrtl.shell.ui.theme.StatusSuccess
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun PcLinkScreen(
    activeGame: GameItem?,
    onPickGame: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val syncClient = remember { PcSyncClient() }

    var host by remember { mutableStateOf("192.168.1.100") }
    var port by remember { mutableStateOf("35420") }
    var isConnecting by remember { mutableStateOf(false) }
    var isSyncing by remember { mutableStateOf(false) }
    var connectionStatus by remember { mutableStateOf(PcConnectionStatus()) }
    var syncLog by remember { mutableStateOf("尚未进行同步操作") }

    Scaffold(
        topBar = {
            AppTopBar(title = "PC 翻译联动")
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
            // PC 连接参数配置卡片
            ElevatedCard(
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.Computer, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text(
                                text = "局域网 PC 连接配置",
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                            )
                        }

                        if (connectionStatus.isConnected) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.CheckCircle, contentDescription = null, tint = StatusSuccess, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                                Text("已连接", color = StatusSuccess, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                            }
                        } else {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                                Text("未连接", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        OutlinedTextField(
                            value = host,
                            onValueChange = { host = it },
                            label = { Text("PC 端 IP 地址") },
                            placeholder = { Text("例如 192.168.1.100") },
                            singleLine = true,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.weight(2f)
                        )

                        OutlinedTextField(
                            value = port,
                            onValueChange = { port = it },
                            label = { Text("端口") },
                            placeholder = { Text("35420") },
                            singleLine = true,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Button(
                        onClick = {
                            val portInt = port.toIntOrNull() ?: 35420
                            isConnecting = true
                            scope.launch {
                                val result = syncClient.checkConnection(host.trim(), portInt)
                                isConnecting = false
                                result.fold(
                                    onSuccess = { status ->
                                        connectionStatus = status
                                        syncLog = "成功连接至 PC 端：${status.pcProjectTitle} (${status.pcProjectEngine})"
                                        Toast.makeText(context, "连接成功！", Toast.LENGTH_SHORT).show()
                                    },
                                    onFailure = { err ->
                                        connectionStatus = connectionStatus.copy(isConnected = false, statusMessage = err.message ?: "连接失败")
                                        syncLog = "连接失败: ${err.message}"
                                        Toast.makeText(context, "连接失败: ${err.message}", Toast.LENGTH_LONG).show()
                                    }
                                )
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !isConnecting
                    ) {
                        if (isConnecting) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("正在连接...")
                        } else {
                            Icon(Icons.Outlined.Wifi, contentDescription = null)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("测试并连接 PC 端服务")
                        }
                    }
                }
            }

            // PC 端当前游戏信息展示
            if (connectionStatus.isConnected) {
                OutlinedCard(
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                    ) {
                        SectionHeader(title = "PC 端当前项目")
                        Text(
                            text = connectionStatus.pcProjectTitle.ifBlank { "未载入游戏" },
                            style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold)
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "引擎: ${connectionStatus.pcProjectEngine} · 词条数: ${connectionStatus.pcTranslationCount}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            // 联动操作区
            SectionHeader(title = "双向同步操作")

            // 1. 从 PC 拉取翻译
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
                        Icon(Icons.Outlined.CloudDownload, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "从 PC 端拉取翻译 (Pull)",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "拉取 PC 端当前的全部翻译条目，直接更新到手机当前游戏的 翻译文件.json。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Button(
                        onClick = {
                            if (activeGame == null) {
                                Toast.makeText(context, "请先在游戏库选择对应游戏", Toast.LENGTH_SHORT).show()
                                return@Button
                            }
                            val portInt = port.toIntOrNull() ?: 35420
                            val destFile = TranslationManager.getDefaultTranslationFile(File(activeGame.folderPath))
                            isSyncing = true
                            scope.launch {
                                val result = syncClient.pullTranslationsFromPc(host.trim(), portInt, destFile)
                                isSyncing = false
                                result.fold(
                                    onSuccess = { items ->
                                        syncLog = "成功从 PC 端拉取 ${items.size} 条翻译，已存入 ${destFile.name}"
                                        Toast.makeText(context, "同步成功！拉取 ${items.size} 条", Toast.LENGTH_SHORT).show()
                                    },
                                    onFailure = { err ->
                                        syncLog = "拉取失败: ${err.message}"
                                        Toast.makeText(context, "拉取失败: ${err.message}", Toast.LENGTH_LONG).show()
                                    }
                                )
                            }
                        },
                        enabled = connectionStatus.isConnected && !isSyncing,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Outlined.CloudDownload, contentDescription = null)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text("一键拉取到手机")
                    }
                }
            }

            // 2. 推送翻译到 PC
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
                        Icon(Icons.Outlined.CloudUpload, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "推送手机翻译至 PC (Push)",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "将手机端修改和保存的翻译条目同步更新回 PC 端 RPGRenPyLocalizer。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedButton(
                        onClick = {
                            if (activeGame == null) {
                                Toast.makeText(context, "请先在游戏库选择对应游戏", Toast.LENGTH_SHORT).show()
                                return@OutlinedButton
                            }
                            val transFile = TranslationManager.findTranslationFile(File(activeGame.folderPath))
                            if (transFile == null || !transFile.exists()) {
                                Toast.makeText(context, "未找到本地翻译文件", Toast.LENGTH_SHORT).show()
                                return@OutlinedButton
                            }
                            val items = TranslationManager.loadTranslations(transFile)
                            val portInt = port.toIntOrNull() ?: 35420
                            isSyncing = true
                            scope.launch {
                                val result = syncClient.pushTranslationsToPc(host.trim(), portInt, items)
                                isSyncing = false
                                result.fold(
                                    onSuccess = { count ->
                                        syncLog = "成功推送 $count 条翻译至 PC 端！"
                                        Toast.makeText(context, "推送成功！已同步 $count 条", Toast.LENGTH_SHORT).show()
                                    },
                                    onFailure = { err ->
                                        syncLog = "推送失败: ${err.message}"
                                        Toast.makeText(context, "推送失败: ${err.message}", Toast.LENGTH_LONG).show()
                                    }
                                )
                            }
                        },
                        enabled = connectionStatus.isConnected && !isSyncing,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Outlined.CloudUpload, contentDescription = null)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text("推送到 PC 端")
                    }
                }
            }

            // 3. 一键无线部署即玩补丁
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
                        Icon(Icons.Outlined.InstallMobile, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "无线请求生成即玩补丁",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "请求 PC 端自动根据游戏引擎构建全套注入补丁（Hook DLL 与加载脚本）。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedButton(
                        onClick = {
                            val portInt = port.toIntOrNull() ?: 35420
                            val targetPath = activeGame?.folderPath ?: ""
                            isSyncing = true
                            scope.launch {
                                val result = syncClient.requestPcGeneratePatch(host.trim(), portInt, targetPath)
                                isSyncing = false
                                result.fold(
                                    onSuccess = {
                                        syncLog = "PC 端补丁生成指令已执行！"
                                        Toast.makeText(context, "补丁生成完成", Toast.LENGTH_SHORT).show()
                                    },
                                    onFailure = { err ->
                                        syncLog = "补丁生成失败: ${err.message}"
                                        Toast.makeText(context, "失败: ${err.message}", Toast.LENGTH_LONG).show()
                                    }
                                )
                            }
                        },
                        enabled = connectionStatus.isConnected && !isSyncing,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("请求生成并注入补丁")
                    }
                }
            }

            // 同步日志展示
            ElevatedCard(
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp)
                ) {
                    Text(
                        text = "同步状态记录",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = syncLog,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}

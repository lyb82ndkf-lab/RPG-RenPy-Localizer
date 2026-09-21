package com.rpgrtl.shell.ui.workbench

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
import androidx.compose.material.icons.outlined.FileDownload
import androidx.compose.material.icons.outlined.FileUpload
import androidx.compose.material.icons.outlined.HourglassEmpty
import androidx.compose.material.icons.outlined.Save
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rpgrtl.shell.data.TranslationManager
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.EmptyPlaceholder
import com.rpgrtl.shell.ui.components.EngineBadge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun TranslationScreen(
    activeGame: GameItem?,
    onPickGame: () -> Unit,
    onImportFile: () -> Unit = {},
    onExportFile: () -> Unit = {},
    refreshTrigger: Int = 0
) {
    val context = LocalContext.current
    var totalCount by remember { mutableIntStateOf(0) }
    var translatedCount by remember { mutableIntStateOf(0) }
    var isLoading by remember { mutableStateOf(false) }
    var fileName by remember { mutableStateOf("") }

    // 必须在 Dispatchers.IO 异步加载，严禁阻塞 UI 主线程
    LaunchedEffect(activeGame, refreshTrigger) {
        if (activeGame != null) {
            isLoading = true
            withContext(Dispatchers.IO) {
                val gameDir = File(activeGame.folderPath)
                val transFile = TranslationManager.findTranslationFile(gameDir)
                if (transFile != null && transFile.exists()) {
                    fileName = transFile.name
                    val items = TranslationManager.loadTranslations(transFile)
                    totalCount = items.size
                    translatedCount = items.count { it.target.isNotBlank() }
                } else {
                    fileName = "未找到翻译文件"
                    totalCount = 0
                    translatedCount = 0
                }
            }
            isLoading = false
        } else {
            totalCount = 0
            translatedCount = 0
            fileName = ""
        }
    }

    val untranslatedCount = (totalCount - translatedCount).coerceAtLeast(0)
    val progress = if (totalCount > 0) translatedCount.toFloat() / totalCount.toFloat() else 0f

    Scaffold(
        topBar = {
            AppTopBar(
                title = if (activeGame != null) "${activeGame.title} · 翻译" else "翻译"
            )
        }
    ) { innerPadding ->
        if (activeGame == null) {
            EmptyPlaceholder(
                icon = Icons.Outlined.Translate,
                title = "未选择游戏",
                subtitle = "请先在游戏库中选择一个游戏以查看翻译统计或导入翻译文件",
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
                // 游戏信息概览
                ElevatedCard(
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = activeGame.title,
                                style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                                modifier = Modifier.weight(1f)
                            )
                            EngineBadge(engine = activeGame.engine)
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "文件: $fileName",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        // 翻译进度条
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "翻译完成度",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = "${(progress * 100).toInt()}%",
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                                color = MaterialTheme.colorScheme.primary
                            )
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { progress },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp),
                            color = MaterialTheme.colorScheme.primary,
                            trackColor = MaterialTheme.colorScheme.surfaceVariant
                        )
                    }
                }

                // 核心统计卡片：已翻译 N 与 未翻译 N
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    // 已翻译卡片
                    ElevatedCard(
                        shape = RoundedCornerShape(16.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(18.dp),
                            horizontalAlignment = Alignment.Start
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Icon(
                                    Icons.Outlined.CheckCircle,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(20.dp)
                                )
                                Text(
                                    text = "已翻译",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Spacer(modifier = Modifier.height(12.dp))
                            if (isLoading) {
                                CircularProgressIndicator(modifier = Modifier.size(28.dp))
                            } else {
                                Text(
                                    text = "$translatedCount",
                                    style = MaterialTheme.typography.headlineLarge.copy(
                                        fontWeight = FontWeight.ExtraBold,
                                        fontSize = 32.sp
                                    ),
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }

                    // 未翻译卡片
                    ElevatedCard(
                        shape = RoundedCornerShape(16.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(18.dp),
                            horizontalAlignment = Alignment.Start
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Icon(
                                    Icons.Outlined.HourglassEmpty,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.outline,
                                    modifier = Modifier.size(20.dp)
                                )
                                Text(
                                    text = "未翻译",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Spacer(modifier = Modifier.height(12.dp))
                            if (isLoading) {
                                CircularProgressIndicator(modifier = Modifier.size(28.dp))
                            } else {
                                Text(
                                    text = "$untranslatedCount",
                                    style = MaterialTheme.typography.headlineLarge.copy(
                                        fontWeight = FontWeight.ExtraBold,
                                        fontSize = 32.sp
                                    ),
                                    color = MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // 操作按钮组
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Button(
                        onClick = onImportFile,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Icon(Icons.Outlined.FileUpload, contentDescription = null)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text("导入翻译文件")
                    }

                    OutlinedButton(
                        onClick = onExportFile,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Icon(Icons.Outlined.FileDownload, contentDescription = null)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text("导出翻译文件")
                    }
                }

                // 保存到游戏目录按钮
                OutlinedButton(
                    onClick = {
                        val gameDir = File(activeGame.folderPath)
                        val transFile = TranslationManager.findTranslationFile(gameDir)
                        if (transFile != null && transFile.exists()) {
                            Toast.makeText(context, "翻译文件已在游戏目录中生效: ${transFile.name}", Toast.LENGTH_SHORT).show()
                        } else {
                            val targetFile = TranslationManager.getDefaultTranslationFile(gameDir)
                            targetFile.writeText("{}", Charsets.UTF_8)
                            Toast.makeText(context, "已在游戏目录创建并保存空模板: ${targetFile.name}", Toast.LENGTH_SHORT).show()
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Outlined.Save, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                    Text("保存到游戏目录")
                }
            }
        }
    }
}

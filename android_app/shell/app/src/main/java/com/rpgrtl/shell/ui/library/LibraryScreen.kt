package com.rpgrtl.shell.ui.library

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.accompanist.swiperefresh.SwipeRefresh
import com.google.accompanist.swiperefresh.rememberSwipeRefreshState
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.EmptyPlaceholder
import com.rpgrtl.shell.ui.components.EngineBadge

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryScreen(
    games: List<GameItem>,
    isRefreshing: Boolean,
    onRefresh: () -> Unit,
    onAddGame: () -> Unit,
    onLaunchGame: (GameItem) -> Unit,
    onOpenTranslation: (GameItem) -> Unit,
    onOpenTrainer: (GameItem) -> Unit = {},
    onDeleteGame: (GameItem) -> Unit,
    onUpdatePreset: (GameItem, String, String) -> Unit,
    onUpdateExecutable: (GameItem, String) -> Unit = { _, _ -> }
) {
    var selectedGameForDetail by remember { mutableStateOf<GameItem?>(null) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    Scaffold(
        topBar = {
            AppTopBar(
                title = "游戏库",
                actions = {
                    IconButton(onClick = onAddGame) {
                        Icon(Icons.Outlined.Add, contentDescription = "导入游戏")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = onAddGame,
                containerColor = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer
            ) {
                Icon(Icons.Outlined.Add, contentDescription = "导入游戏")
            }
        }
    ) { innerPadding ->
        SwipeRefresh(
            state = rememberSwipeRefreshState(isRefreshing),
            onRefresh = onRefresh,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            if (games.isEmpty()) {
                EmptyPlaceholder(
                    icon = Icons.Outlined.FolderOpen,
                    title = "暂无游戏",
                    subtitle = "点击右下角按钮导入包含游戏文件的本地目录",
                    action = {
                        FilledTonalButton(onClick = onAddGame) {
                            Icon(Icons.Outlined.Add, contentDescription = null)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("导入本地游戏")
                        }
                    }
                )
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                    modifier = Modifier.fillMaxSize()
                ) {
                    items(games, key = { it.id }) { game ->
                        GameCard(
                            game = game,
                            onLaunch = { onLaunchGame(game) },
                            onOpenTranslation = { onOpenTranslation(game) },
                            onMoreOptions = { selectedGameForDetail = game }
                        )
                    }
                }
            }
        }

        selectedGameForDetail?.let { game ->
            GameDetailSheet(
                game = game,
                sheetState = sheetState,
                onDismiss = { selectedGameForDetail = null },
                onLaunch = {
                    selectedGameForDetail = null
                    onLaunchGame(game)
                },
                onOpenTranslation = {
                    selectedGameForDetail = null
                    onOpenTranslation(game)
                },
                onOpenTrainer = {
                    selectedGameForDetail = null
                    onOpenTrainer(game)
                },
                onDelete = {
                    selectedGameForDetail = null
                    onDeleteGame(game)
                },
                onUpdatePreset = { box64, driver ->
                    onUpdatePreset(game, box64, driver)
                },
                onUpdateExecutable = { newExePath ->
                    onUpdateExecutable(game, newExePath)
                }
            )
        }
    }
}

@Composable
fun GameCard(
    game: GameItem,
    onLaunch: () -> Unit,
    onOpenTranslation: () -> Unit,
    onMoreOptions: () -> Unit
) {
    ElevatedCard(
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onMoreOptions() }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = game.title,
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                        maxLines = 1
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    EngineBadge(engine = game.engine)
                }

                IconButton(onClick = onMoreOptions) {
                    Icon(
                        imageVector = Icons.Outlined.MoreVert,
                        contentDescription = "更多设置",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 翻译进度指示器
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                val statusText = if (game.translationFileExists) {
                    "翻译进度: ${game.translatedCount} / ${game.totalCount}"
                } else {
                    "未生成翻译文件"
                }
                Text(
                    text = statusText,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp
                )
                if (game.totalCount > 0) {
                    Text(
                        text = "${(game.translationRatio * 100).toInt()}%",
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Bold),
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 12.sp
                    )
                }
            }

            if (game.totalCount > 0) {
                Spacer(modifier = Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = { game.translationRatio },
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // 快捷操作按钮
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilledTonalButton(
                    onClick = onLaunch,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Outlined.PlayArrow, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                    Text("启动游戏")
                }

                FilledTonalButton(
                    onClick = onOpenTranslation,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Outlined.Translate, contentDescription = null)
                    Spacer(modifier = Modifier.padding(horizontal = 2.dp))
                    Text("翻译文件")
                }
            }
        }
    }
}

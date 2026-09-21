package com.rpgrtl.shell.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.Dns
import androidx.compose.material.icons.outlined.Games
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.SyncAlt
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Library : Screen("library", "游戏库", Icons.Outlined.Games)
    object Workbench : Screen("workbench", "翻译", Icons.Outlined.Language)
    object HotReload : Screen("hotreload", "热重载", Icons.Outlined.Bolt)
    object Trainer : Screen("trainer", "修改器", Icons.Outlined.Tune)
    object PcLink : Screen("pclink", "PC 联动", Icons.Outlined.SyncAlt)
    object Winlator : Screen("winlator", "容器", Icons.Outlined.Dns)
    object Settings : Screen("settings", "设置", Icons.Outlined.Settings)
}

// 游戏未启动时的导航 Tab：游戏库 / 翻译 / 设置
val workspaceNavScreens = listOf(
    Screen.Library,
    Screen.Workbench,
    Screen.Settings
)

// 游戏运行中的导航 Tab：热重载 / 修改器 / 设置
val inGameNavScreens = listOf(
    Screen.HotReload,
    Screen.Trainer,
    Screen.Settings
)

// 兼容别名
val bottomNavScreens = workspaceNavScreens


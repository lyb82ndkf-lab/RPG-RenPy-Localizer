package com.rpgrtl.shell.ui.settings

import android.content.Context
import android.os.Build
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.outlined.ColorLens
import androidx.compose.material.icons.outlined.Extension
import androidx.compose.material.icons.outlined.Html
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Speed
import androidx.compose.material.icons.outlined.SportsEsports
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.outlined.VideogameAsset
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
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
import com.rpgrtl.shell.MainActivity
import com.rpgrtl.shell.ui.components.AppTopBar
import com.rpgrtl.shell.ui.components.SectionHeader
import org.json.JSONObject

@Composable
fun SettingsScreen(
    dynamicColor: Boolean,
    onDynamicColorChange: (Boolean) -> Unit
) {
    val context = LocalContext.current
    val prefs = remember {
        context.getSharedPreferences(MainActivity::class.java.simpleName, Context.MODE_PRIVATE)
    }
    val enginePrefs = remember {
        context.getSharedPreferences("engine_global_configs", Context.MODE_PRIVATE)
    }

    // ── AI 服务配置（仅 OpenAI 兼容 和 Anthropic 兼容） ────────────────
    val initialAiObj = remember {
        val raw = prefs.getString("android_ai_settings_json", "") ?: ""
        runCatching { JSONObject(raw) }.getOrNull() ?: JSONObject()
    }

    var aiProvider by remember {
        val p = initialAiObj.optString("provider", "openai_compatible")
        mutableStateOf(
            if (p == "anthropic" || p == "anthropic_compatible" || p == "claude") {
                "Anthropic 兼容"
            } else {
                "OpenAI 兼容"
            }
        )
    }
    var aiBaseUrl by remember {
        mutableStateOf(
            initialAiObj.optString(
                "baseUrl",
                if (aiProvider == "Anthropic 兼容") "https://api.anthropic.com/v1" else "https://api.openai.com/v1"
            )
        )
    }
    var aiApiKey by remember {
        mutableStateOf(initialAiObj.optString("apiKey", ""))
    }
    var aiModel by remember {
        mutableStateOf(
            initialAiObj.optString(
                "model",
                if (aiProvider == "Anthropic 兼容") "claude-3-5-haiku-20241022" else "gpt-4o-mini"
            )
        )
    }

    val providers = listOf("OpenAI 兼容", "Anthropic 兼容")

    // ── Winlator & Box64 全局预设 ─────────────────────────────────────
    var box64Preset by remember {
        mutableStateOf(prefs.getString("global_box64_preset", "Performance") ?: "Performance")
    }
    var graphicsDriver by remember {
        mutableStateOf(prefs.getString("global_graphics_driver", "Turnip + DXVK") ?: "Turnip + DXVK")
    }

    // ── 折叠卡片展开状态 ─────────────────────────────────────────────
    var box64Expanded by remember { mutableStateOf(false) }
    var gpuExpanded by remember { mutableStateOf(false) }
    var renpyExpanded by remember { mutableStateOf(false) }
    var htmlExpanded by remember { mutableStateOf(false) }
    var rpgmakerExpanded by remember { mutableStateOf(false) }

    // ── 真实应用版本号（动态获取） ──────────────────────────────────
    val appVersionString = remember {
        runCatching {
            val pm = context.packageManager
            val pInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getPackageInfo(context.packageName, android.content.pm.PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(context.packageName, 0)
            }
            val code = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                pInfo.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode.toLong()
            }
            "v${pInfo.versionName} (Build $code)"
        }.getOrNull() ?: "v3.3.0"
    }

    Scaffold(
        topBar = {
            AppTopBar(title = "全局设置")
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
            // ── 1. 外观与设计 ─────────────────────────────────────────
            SectionHeader(title = "外观与设计")
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
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.ColorLens, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Column {
                                Text("Material You 动态色彩", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                Text("从系统壁纸提取主色调 (Android 12+)", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }

                        Switch(
                            checked = dynamicColor,
                            onCheckedChange = onDynamicColorChange
                        )
                    }
                }
            }

            // ── 2. AI 自动翻译配置（严格仅支持 OpenAI兼容 与 Anthropic兼容）
            SectionHeader(title = "AI 批量翻译接口")
            ElevatedCard(
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
                        Icon(Icons.Outlined.Psychology, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text(
                            text = "服务提供商",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)
                        )
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        providers.forEach { p ->
                            FilterChip(
                                selected = aiProvider == p,
                                onClick = {
                                    aiProvider = p
                                    if (p == "Anthropic 兼容") {
                                        if (aiBaseUrl.isBlank() || aiBaseUrl.contains("openai.com")) {
                                            aiBaseUrl = "https://api.anthropic.com/v1"
                                        }
                                        if (aiModel.isBlank() || aiModel.contains("gpt")) {
                                            aiModel = "claude-3-5-haiku-20241022"
                                        }
                                    } else {
                                        if (aiBaseUrl.isBlank() || aiBaseUrl.contains("anthropic.com")) {
                                            aiBaseUrl = "https://api.openai.com/v1"
                                        }
                                        if (aiModel.isBlank() || aiModel.contains("claude")) {
                                            aiModel = "gpt-4o-mini"
                                        }
                                    }
                                },
                                label = { Text(p) }
                            )
                        }
                    }

                    OutlinedTextField(
                        value = aiBaseUrl,
                        onValueChange = { aiBaseUrl = it },
                        label = { Text("API 接口地址") },
                        placeholder = {
                            Text(if (aiProvider == "Anthropic 兼容") "https://api.anthropic.com/v1" else "https://api.openai.com/v1")
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    )

                    OutlinedTextField(
                        value = aiApiKey,
                        onValueChange = { aiApiKey = it },
                        label = { Text("API Key (本地保存)") },
                        placeholder = { Text(if (aiProvider == "Anthropic 兼容") "sk-ant-api..." else "sk-...") },
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    )

                    OutlinedTextField(
                        value = aiModel,
                        onValueChange = { aiModel = it },
                        label = { Text("模型名称") },
                        placeholder = {
                            Text(if (aiProvider == "Anthropic 兼容") "claude-3-5-haiku-20241022" else "gpt-4o-mini")
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    )

                    Button(
                        onClick = {
                            val providerKey = if (aiProvider == "Anthropic 兼容") "anthropic_compatible" else "openai_compatible"
                            val json = JSONObject().apply {
                                put("provider", providerKey)
                                put("baseUrl", aiBaseUrl.trim())
                                put("apiKey", aiApiKey.trim())
                                put("model", aiModel.trim())
                                put("concurrency", 2)
                                put("requestIntervalMs", 80)
                            }
                            prefs.edit().putString("android_ai_settings_json", json.toString()).apply()
                            Toast.makeText(context, "AI 翻译配置已保存", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("保存 AI 配置")
                    }
                }
            }

            // ── 3. Box64 运行模式介绍与切换 ─────────────────────────────
            SectionHeader(title = "Box64 模拟器模式")
            ElevatedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { box64Expanded = !box64Expanded },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.Speed, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Column {
                                Text("Box64 运行模式切换", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                Text("当前: $box64Preset (点击展开原理与说明)", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Icon(
                            imageVector = if (box64Expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = null
                        )
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("Performance", "Compatibility", "Safe").forEach { preset ->
                            FilterChip(
                                selected = box64Preset == preset,
                                onClick = {
                                    box64Preset = preset
                                    prefs.edit().putString("global_box64_preset", preset).apply()
                                    Toast.makeText(context, "Box64 预设已切换为 $preset", Toast.LENGTH_SHORT).show()
                                },
                                label = { Text(preset) }
                            )
                        }
                    }

                    AnimatedVisibility(visible = box64Expanded) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 6.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text("• Performance (性能优先)：\n开启所有高频指令的 JIT 动态重编译缓存，关闭严格内存断言，最高帧率，推荐 90% 游戏使用。", style = MaterialTheme.typography.bodySmall)
                            Text("• Compatibility (兼容模式)：\n启用完整的 x86_64 异常处理与复杂多线程协同，减少 Unity IL2CPP 或外部 DLL 崩溃，当游戏闪退时首选。", style = MaterialTheme.typography.bodySmall)
                            Text("• Safe (安全稳定)：\n关闭激进重排与投机指令翻译，完全按照标准 x86 规约逐条执行，速度较慢但极难因 JIT 异常报错退出。", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            // ── 4. GPU 图形渲染驱动模式与说明 ──────────────────────────
            SectionHeader(title = "GPU 渲染驱动模式")
            ElevatedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { gpuExpanded = !gpuExpanded },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.VideogameAsset, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Column {
                                Text("GPU 驱动模式选择", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                                Text("当前: $graphicsDriver (点击展开芯片适用指南)", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Icon(
                            imageVector = if (gpuExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = null
                        )
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("Turnip + DXVK", "Turnip + Zink", "VirGL").forEach { drv ->
                            FilterChip(
                                selected = graphicsDriver == drv,
                                onClick = {
                                    graphicsDriver = drv
                                    prefs.edit().putString("global_graphics_driver", drv).apply()
                                    Toast.makeText(context, "图形驱动已切换为 $drv", Toast.LENGTH_SHORT).show()
                                },
                                label = { Text(drv) }
                            )
                        }
                    }

                    AnimatedVisibility(visible = gpuExpanded) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 6.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text("• Turnip + DXVK (推荐骁龙芯片)：\n高通 Adreno 原生开源 Vulkan 驱动，配合 Direct3D 9/10/11 翻译，渲染速度最快，发热低，支持现代 3D 游戏。", style = MaterialTheme.typography.bodySmall)
                            Text("• Turnip + Zink (OpenGL 专属)：\n在 Vulkan 之上运行通用 OpenGL 驱动，专为老款 PC 游戏、Ren'Py 及依赖 OpenGL 2.1/3.3 的引擎打造，画面稳定无撕裂。", style = MaterialTheme.typography.bodySmall)
                            Text("• VirGL (天玑 / 麒麟 / Exynos 首选)：\n通过安卓原生宿主 OpenGL ES 通信进行虚拟化加速，通用性最佳，非高通处理器启动 PC 游戏建议首选。", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            // ── 5. 图 1：Ren'Py 设置 ───────────────────────────────────
            SectionHeader(title = "Ren'Py 引擎设置")
            ElevatedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { renpyExpanded = !renpyExpanded },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.Tune, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("Ren'Py 专属优化选项", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                        }
                        Icon(
                            imageVector = if (renpyExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = null
                        )
                    }

                    AnimatedVisibility(visible = renpyExpanded) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            SettingToggleItem(enginePrefs, "renpy_auto_save", "自动保存", "在选择后保存游戏", defaultValue = false)
                            SettingToggleItem(enginePrefs, "renpy_hardware_video", "视频采用硬件解码", "为视频启用硬件加速", defaultValue = true)
                            SettingToggleItem(enginePrefs, "renpy_mobile_scale", "使用手机/小型缩放", "设置屏幕变量为电话/移动电话", defaultValue = false)
                            SettingToggleItem(enginePrefs, "renpy_vsync", "垂直同步", "使用垂直同步以避免画面撕裂", defaultValue = false)
                            SettingToggleItem(enginePrefs, "renpy_less_memory", "使用更少的内存", "减少内存使用，以换取速度的降低", defaultValue = false)
                            SettingToggleItem(enginePrefs, "renpy_less_updates", "更新较少", "减少发生的屏幕更新次数", defaultValue = false)
                            SettingToggleItem(enginePrefs, "renpy_model_renderer", "基于模型的渲染", "解决了某些设备上缓慢的菜单动画问题", defaultValue = true)
                            SettingToggleItem(enginePrefs, "renpy_recompile_scripts", "重新编译脚本", "始终重新编译脚本以提高兼容性以换取加载时间的增加", defaultValue = false)
                        }
                    }
                }
            }

            // ── 6. 图 2：HTML 设置 ─────────────────────────────────────
            SectionHeader(title = "HTML 网页引擎设置")
            ElevatedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { htmlExpanded = !htmlExpanded },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.Html, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("HTML 运行容器选项", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                        }
                        Icon(
                            imageVector = if (htmlExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = null
                        )
                    }

                    AnimatedVisibility(visible = htmlExpanded) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            SettingToggleItem(enginePrefs, "html_use_http_server", "使用HTTP服务器", "使用HTTP服务器来为文件进行服务", defaultValue = false)
                            SettingToggleItem(enginePrefs, "html_nwjs_api", "NWJSAPI", "为常用的Node.js 和 NW.js API提供封包脚本", defaultValue = true)
                            SettingToggleItem(enginePrefs, "html_webgl", "WebGL", "为 HTML游戏启用WebGL", defaultValue = true)
                            SettingToggleItem(enginePrefs, "html_desktop_mode", "桌面模式", "启用桌面模式。", defaultValue = false)
                            SettingToggleItem(enginePrefs, "html_allow_external_modules", "允许外部模块", "允许加载CommonJS模块和JSON文件。可能会对一些游戏造成问题。", defaultValue = false)
                        }
                    }
                }
            }

            // ── 7. 图 3：RPG Maker 设置 ─────────────────────────────────
            SectionHeader(title = "RPG Maker 引擎设置")
            ElevatedCard(
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { rpgmakerExpanded = !rpgmakerExpanded },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Outlined.SportsEsports, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                            Text("RPG Maker (MV/MZ/XP/VX) 选项", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                        }
                        Icon(
                            imageVector = if (rpgmakerExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = null
                        )
                    }

                    AnimatedVisibility(visible = rpgmakerExpanded) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            SettingToggleItem(enginePrefs, "rpgm_debug_log", "调试日志", "写入调试消息到logs.txt", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_ruby_18", "使用Ruby 1.8", "在 RPGM XP和VX游戏中使用Ruby 1.8", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_use_miniz", "使用 Miniz", "使用 Miniz 代替原生 Ruby Zlib 模块", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_smooth_scaling", "平滑缩放", "使用线性插值来让游戏画面更加平滑", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_vsync", "垂直同步", "使用垂直同步以避免画面撕裂", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_skip_frames", "跳帧", "当发生延迟时跳过且不绘制延迟的帧", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_solid_font", "实心字体", "渲染文本时不使用Alpha混合", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_directory_cache", "目录缓存", "以小写路径索引所有文件", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_prebuild_cache", "预建路径缓存", "添加游戏后生成路径缓存并使用它", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_fast_path_enum", "更快的路径枚举", "通过首先检查常见文件类型来提高文件访问速度。可能导致资产覆盖", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_post_load_script", "启用后加载脚本", "在标题屏幕之前执行加载后脚本以修复常见问题", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_copy_text_clipboard", "复制文本到剪贴板", "绘图时将文本复制到剪贴板", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_update_corescript", "更新 CoreScript", "在 RPG Maker MV 游戏中选用最新版本的 CoreScript", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_webgl2", "使用 WebGL2", "在 RPG Maker MV 游戏中选用 WebGL2 上下文", defaultValue = false)
                            SettingToggleItem(enginePrefs, "rpgm_adjust_large_textures", "调整大纹理大小", "调整 RPG Maker MV 游戏的大纹理大小以防止出现渲染问题", defaultValue = true)
                            SettingToggleItem(enginePrefs, "rpgm_pixijs_v5", "使用PixiJS v5", "在RPG Maker MV游戏中选用PixiJS v5", defaultValue = false)
                        }
                    }
                }
            }

            // ── 8. 关于与版本信息（真实动态版本） ───────────────────────
            SectionHeader(title = "关于")
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
                        Icon(Icons.Outlined.Info, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                        Text("RPGRenPyLocalizer Android", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold))
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text("应用版本: $appVersionString", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("运行架构: ARM64-v8a (Winlator 64-bit Wine Kernel)", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("UI 规范: Google Material 3 Expressive + Accompanist", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun SettingToggleItem(
    prefs: android.content.SharedPreferences,
    key: String,
    title: String,
    subtitle: String,
    defaultValue: Boolean
) {
    var state by remember { mutableStateOf(prefs.getBoolean(key, defaultValue)) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Medium))
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(
            checked = state,
            onCheckedChange = {
                state = it
                prefs.edit().putBoolean(key, it).apply()
            }
        )
    }
}

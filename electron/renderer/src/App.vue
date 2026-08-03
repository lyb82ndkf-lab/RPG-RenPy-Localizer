<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-logo" :src="logoUrl" alt="RPGRenPyLocalizer logo" />
        <div class="brand-copy">
          <div class="brand-title">RPGRenPyLocalizer</div>
          <div class="brand-subtitle">工具工作台</div>
        </div>
      </div>

      <div class="game-card" v-if="selectedEntry" data-tour="current-game">
        <div class="game-card-label">当前游戏</div>
        <div class="game-card-name">{{ selectedEntry.name || '未命名' }}</div>
        <div class="game-card-engine">{{ selectedEntry.engine || '未知引擎' }}</div>
        <el-tag v-if="gameRunning" class="running-tag" size="small" type="success" effect="dark">游戏运行中</el-tag>
        <div class="game-card-path">{{ selectedEntry.path }}</div>
        <div class="game-card-actions">
          <el-button size="small" type="primary" :icon="VideoPlay" @click="launchSelected" :loading="busy.launch" :disabled="gameRunning">{{ gameRunning ? '运行中' : '启动' }}</el-button>
          <el-button size="small" :icon="FolderOpened" @click="openSelectedFolder">目录</el-button>
        </div>
      </div>

      <div class="game-card empty" v-else data-tour="current-game">
        <div class="game-card-label">当前游戏</div>
        <div class="game-card-name">未选择</div>
        <div class="game-card-path">先添加或选择一个游戏。</div>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in visibleNavItems"
          :key="item.key"
          class="nav-item"
          :data-tour="`nav-${item.key}`"
          :class="{ active: currentView === item.key }"
          @click="currentView = item.key"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <button class="tutorial-link" data-tour="tutorial-link" type="button" @click="startTutorial">如何使用</button>
      <button class="update-indicator" data-tour="update-status" :class="{ available: updateInfo.hasUpdate }" @click="currentView = 'settings'">
        <span>{{ updateInfo.hasUpdate ? `发现新版本 ${updateInfo.latestVersion}` : `版本 ${appVersion || '读取中'}` }}</span>
      </button>
    </aside>

    <main class="content">
      <header class="topbar">
        <div>
          <div class="eyebrow">{{ viewMeta.eyebrow }}</div>
          <h1>{{ viewMeta.title }}</h1>
          <div class="subtitle">{{ viewMeta.subtitle }}</div>
        </div>

        <div class="top-actions">
          <el-tag v-if="gameRunning" type="success" effect="dark">游戏运行中</el-tag>
          <el-tag v-else-if="selectedEntry" effect="plain">{{ selectedEntry.engine || 'Game' }}</el-tag>
          <el-button v-if="selectedEntry" :icon="Refresh" @click="reloadCurrentView" :loading="busy.reload">刷新当前页</el-button>
          <el-button v-if="!selectedEntry && currentView !== 'library'" type="warning" plain @click="currentView = 'library'">先去游戏库</el-button>
        </div>
      </header>

      <div v-if="currentView !== 'library'" class="game-strip">
        <div class="game-strip-left">
          <span class="game-strip-label">当前游戏</span>
          <strong>{{ selectedEntry ? (selectedEntry.name || '未命名') : '未选择游戏' }}</strong>
          <span class="game-strip-meta">{{ selectedEntry ? (selectedEntry.engine || '未知引擎') : '先去游戏库选择一个游戏再回来。' }}</span>
        </div>
        <div class="game-strip-actions">
          <el-button size="small" @click="currentView = 'library'" :disabled="gameRunning">{{ gameRunning ? '游戏运行中' : '切换游戏' }}</el-button>
          <el-dropdown v-if="currentView === 'translations' && isRpgMakerSelected" trigger="click" :disabled="!selectedEntry || busy.translation" @command="launchTranslationVersion">
            <el-button size="small" type="primary" :loading="busy.translation">选择译文启动<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="current">完成翻译并启动当前译文</el-dropdown-item>
                <el-dropdown-item command="original">原文（不替换）</el-dropdown-item>
                <el-dropdown-item v-for="version in translationVersions" :key="version.id" :command="version.id" :disabled="!version.available">
                  {{ version.label }}{{ version.reason ? ` · ${version.reason}` : '' }}（{{ version.count || 0 }} 条）
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button v-else-if="currentView === 'translations'" size="small" type="primary" :loading="busy.translation" :disabled="!selectedEntry" @click="startTranslation">开始翻译</el-button>
          <el-button v-else-if="currentView === 'data'" size="small" :disabled="!selectedEntry" @click="loadData(true)">载入数据</el-button>
          <el-button v-else-if="currentView === 'saves'" size="small" :disabled="!selectedEntry" @click="loadSaveSlots">载入存档</el-button>
          <el-button v-else-if="currentView === 'maps'" size="small" :disabled="!selectedEntry" @click="loadMaps">载入地图</el-button>
        </div>
      </div>

      <div class="view-loading-wrap" v-loading="pageLoading" element-loading-text="正在载入..." element-loading-background="rgba(7, 15, 28, .62)">
      <section v-if="currentView === 'library'" class="view-shell" data-tour="library-table">
        <el-card shadow="never" class="section-card library-card">
          <template #header>
            <div class="card-head">
              <strong>全部游戏</strong>
              <div class="card-head-right">
                <el-input v-model="librarySearch" class="search-inline" size="small" placeholder="搜索游戏名、路径、引擎" clearable :prefix-icon="Search" />
                <el-button size="small" :icon="Refresh" @click="loadLibrary" :loading="busy.refresh">刷新库</el-button>
                <el-button size="small" type="primary" data-tour="add-game" :icon="Plus" @click="addGame" :loading="busy.add" :disabled="gameRunning">添加游戏</el-button>
                <el-button size="small" @click="addGameFolder" :loading="busy.add" :disabled="gameRunning">导入文件夹</el-button>
              </div>
            </div>
          </template>

          <el-table
            :data="filteredLibrary"
            height="100%"
            highlight-current-row
            :row-class-name="libraryRowClassName"
            empty-text="还没有游戏，点击左侧添加游戏。"
            @row-click="onLibraryRowClick"
            @row-dblclick="onLibraryRowDoubleClick"
          >
            <el-table-column prop="name" label="游戏" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="game-name">{{ row.name || '未命名' }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="engine" label="引擎" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag size="small" :type="engineTagType(row.engine)" effect="plain">{{ row.engine || '未知' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_opened_at" label="最近打开" width="160" show-overflow-tooltip />
            <el-table-column prop="path" label="路径" min-width="280" show-overflow-tooltip />
          </el-table>
        </el-card>

        <el-card shadow="never" class="section-card detail-card">
          <template #header>
            <div class="card-head">
              <strong>详情</strong>
              <span>{{ selectedEntry ? '已选中' : '未选择' }}</span>
            </div>
          </template>

          <el-empty v-if="!selectedEntry" description="选择左侧游戏查看详情" />

          <div v-else class="detail-view">
            <div class="detail-title-row">
              <div>
                <div class="detail-name">{{ selectedEntry.name || '未命名' }}</div>
                <div class="detail-engine">{{ selectedEntry.engine || '未知引擎' }}</div>
              </div>
              <el-tag effect="dark" round>{{ selectedEntry.engine || 'Game' }}</el-tag>
            </div>

            <div class="detail-grid">
              <div class="info-box large"><span>游戏目录</span><div class="selectable">{{ selectedEntry.path }}</div></div>
              <div class="info-box large"><span>启动文件</span><div class="selectable">{{ selectedEntry.launcher_path || '—' }}</div></div>
              <div class="info-box"><span>加入时间</span><div>{{ selectedEntry.added_at || '—' }}</div></div>
              <div class="info-box"><span>最近打开</span><div>{{ selectedEntry.last_opened_at || '—' }}</div></div>
            </div>

            <div class="detail-actions">
              <el-button type="primary" :icon="VideoPlay" @click="launchSelected" :loading="busy.launch">启动游戏</el-button>
              <el-button :icon="FolderOpened" @click="openSelectedFolder">打开目录</el-button>
              <el-button type="danger" plain :icon="Delete" @click="removeSelected" :loading="busy.remove" :disabled="gameRunning">移除</el-button>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'translations'" class="view-shell feature-shell" data-tour="translation-workbench">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>翻译工作台</strong>
              <div class="card-head-right translation-toolbar">
                <el-input v-model="translationSearch" class="search-inline" size="small" placeholder="搜索原文 / 译文 / 文件" clearable :prefix-icon="Search" />
                <el-select v-model="translationCategory" size="small" class="mini-select" clearable placeholder="安全分类">
                  <el-option label="全部分类" value="" />
                  <el-option v-for="item in translationCategories" :key="item" :label="translationCategoryLabel(item)" :value="item" />
                </el-select>
                <el-switch v-model="translationMissingOnly" size="small" active-text="仅未译" />
                <el-button size="small" :icon="Refresh" @click="loadTranslations(true)" :loading="busy.translation">刷新</el-button>
                <el-button v-if="busy.translation" size="small" type="danger" plain @click="stopTranslationBatch">停止并保存</el-button>
                <el-button v-else size="small" type="primary" :disabled="!translations.length" @click="translateBatch({ scope: 'filtered' })">AI 批译</el-button>
                <el-button size="small" type="warning" plain :loading="busy.translation" :disabled="!translations.length || busy.translation" @click="repairMissingTranslations">修复未译</el-button>
                <el-dropdown trigger="click" @command="handleTranslationCommand">
                  <el-button size="small">翻译包</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="import">导入翻译包</el-dropdown-item>
                      <el-dropdown-item command="export">导出翻译包</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>

          <div class="translation-list-layout">
            <div v-if="translationProgress.active || translationProgress.total" class="translation-progress-card">
              <div class="translation-progress-head">
                <strong>{{ translationProgress.title }}</strong>
                <span>{{ translationProgress.current }} / {{ translationProgress.total }} &#183; 成功 {{ translationProgress.success }} &#183; 失败 {{ translationProgress.failed }}</span>
              </div>
              <el-progress :percentage="translationProgressPercent" :status="translationProgress.failed ? 'exception' : (translationProgressPercent >= 100 ? 'success' : undefined)" :stroke-width="8" striped striped-flow />
              <div class="translation-progress-message">{{ translationProgress.message }}</div>
            </div>
            <div class="translation-table-wrap">
              <el-table
                :data="pagedTranslations"
                height="100%"
                empty-text="没有文本条目"
                @row-click="openTranslationDetail"
              >
                <el-table-column label="#" width="72">
                  <template #default="{ $index }">{{ (translationPage - 1) * translationPageSize + $index + 1 }}</template>
                </el-table-column>
                <el-table-column label="状态" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.target ? 'success' : 'warning'" effect="plain">{{ row.target ? '已翻译' : '待翻译' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="category" label="分类" min-width="190">
                  <template #default="{ row }">{{ row.category || '未分类' }}</template>
                </el-table-column>
                <el-table-column prop="file" label="来源文件" min-width="260" />
                <el-table-column label="操作" width="110" align="right">
                  <template #default="{ row }"><el-button link type="primary" @click.stop="openTranslationDetail(row)">查看详情</el-button></template>
                </el-table-column>
              </el-table>
            </div>
            <div class="table-pager">
              <span class="pager-summary">{{ translationRangeLabel }}</span>
              <el-pagination
                v-model:current-page="translationPage"
                v-model:page-size="translationPageSize"
                :page-sizes="translationPageSizes"
                :total="filteredTranslations.length"
                :pager-count="5"
                size="small"
                layout="sizes, prev, pager, next, jumper"
                background
              />
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'data'" class="view-shell feature-shell" data-tour="data-editor">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>数据修改</strong>
              <div class="card-head-right wrap">
                <el-input v-model="dataSearch" class="search-inline" size="small" placeholder="搜索角色 / 物品 / 技能 / 敌人" clearable :prefix-icon="Search" />
                <el-select v-model="dataCategory" size="small" class="mini-select" clearable placeholder="分类">
                  <el-option label="全部分类" value="" />
                  <el-option v-for="item in dataCategories" :key="item" :label="item" :value="item" />
                </el-select>
                <el-button size="small" :icon="Refresh" @click="loadData(true)" :loading="busy.data">刷新</el-button>
              </div>
            </div>
          </template>
          <div class="data-workspace">
            <el-tabs v-model="dataSection" class="data-tabs">
              <el-tab-pane label="数据库" name="database" />
              <el-tab-pane label="物品" name="items" />
              <el-tab-pane label="装备" name="armors" />
              <el-tab-pane label="武器" name="weapons" />
              <el-tab-pane label="角色" name="actors" />
              <el-tab-pane label="开关" name="switches" />
              <el-tab-pane label="变量" name="variables" />
            </el-tabs>
            <div v-if="dataSection === 'database'" class="split-layout data-body">
              <div class="left-pane">
              <el-table
                :data="filteredData"
                height="100%"
                highlight-current-row
                :row-class-name="dataRowClassName"
                empty-text="没有数据记录"
                @row-click="selectDataRecord"
              >
                <el-table-column prop="object_label" label="对象" min-width="170" show-overflow-tooltip />
                <el-table-column prop="label" label="字段" min-width="180" show-overflow-tooltip />
                <el-table-column prop="value" label="值" min-width="220" show-overflow-tooltip />
                <el-table-column prop="file" label="文件" width="160" show-overflow-tooltip />
              </el-table>
              </div>
              <div class="right-pane">
                <div v-if="selectedData" class="editor-stack">
                  <div class="editor-title">修改数据库字段</div>
                  <div class="mini-info">{{ dataMeta }}</div>
                  <el-input v-model="dataDraft.label" readonly />
                  <el-input v-model="dataDraft.value" type="textarea" :rows="10" placeholder="修改值后点击写入" />
                  <div class="detail-actions"><el-button type="primary" @click="saveDataValue">写入游戏数据</el-button></div>
                </div>
                <el-empty v-else description="点击左侧记录编辑" />
              </div>
            </div>
            <div v-else class="split-layout data-body runtime-data-body">
              <div class="left-pane">
                <div v-if="!runtimeConnected" class="runtime-required"><strong>需要连接运行中的游戏</strong><span>先启动 RPGMaker 游戏，桥接组件会自动连接；连接后这里会显示当前游戏数据。</span><el-button type="primary" @click="currentView = 'runtime'">前往实时修改</el-button></div>
                <el-table v-else :data="runtimeDataRows" height="100%" highlight-current-row @row-click="selectRuntimeDataRow">
                  <el-table-column prop="id" label="ID" width="72" />
                  <el-table-column prop="name" label="名称" min-width="180" />
                  <el-table-column v-if="['items','armors','weapons'].includes(dataSection)" prop="count" label="持有数量" width="110" />
                  <el-table-column v-if="dataSection === 'actors'" prop="level" label="等级" width="90" />
                  <el-table-column v-if="dataSection === 'actors'" prop="hp" label="HP" width="90" />
                  <el-table-column v-if="dataSection === 'switches'" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.value ? 'success' : 'info'">{{ row.value ? 'ON' : 'OFF' }}</el-tag></template></el-table-column>
                  <el-table-column v-if="dataSection === 'variables'" prop="value" label="当前值" min-width="150" />
                </el-table>
              </div>
              <div class="right-pane">
                <div v-if="selectedRuntimeData" class="editor-stack">
                  <div class="editor-title">{{ selectedRuntimeData.name || `#${selectedRuntimeData.id}` }}</div>
                  <div class="mini-info">{{ runtimeDataSectionLabel }} #{{ selectedRuntimeData.id }} · 实时修改立即生效</div>
                  <template v-if="['items','armors','weapons'].includes(dataSection)"><el-input v-model="runtimeDataForm.count" type="number"><template #prepend>数量</template></el-input><el-button type="primary" @click="saveRuntimeDataRow">设置持有数量</el-button></template>
                  <template v-else-if="dataSection === 'actors'"><el-input v-model="runtimeDataForm.level" type="number"><template #prepend>等级</template></el-input><div class="actor-gauges"><el-input v-model="runtimeDataForm.hp" type="number"><template #prepend>HP</template></el-input><el-input v-model="runtimeDataForm.mp" type="number"><template #prepend>MP</template></el-input><el-input v-model="runtimeDataForm.tp" type="number"><template #prepend>TP</template></el-input></div><el-button type="primary" @click="saveRuntimeDataRow">应用角色数值</el-button></template>
                  <template v-else-if="dataSection === 'switches'"><el-switch v-model="runtimeDataForm.switchValue" active-text="ON" inactive-text="OFF" /><el-button type="primary" @click="saveRuntimeDataRow">应用开关状态</el-button></template>
                  <template v-else-if="dataSection === 'variables'"><el-input v-model="runtimeDataForm.variableValue" placeholder="变量值" /><el-button type="primary" @click="saveRuntimeDataRow">应用变量值</el-button></template>
                </div>
                <el-empty v-else description="选择左侧条目进行修改" />
              </div>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'saves'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>存档修改</strong>
              <div class="card-head-right wrap">
                <el-button size="small" :icon="Refresh" @click="loadSaveSlots" :loading="busy.saves">刷新</el-button>
                <el-button size="small" type="primary" @click="writeSave">写回存档</el-button>
              </div>
            </div>
          </template>

          <div class="save-layout">
            <div class="save-slot-pane">
              <el-scrollbar class="list-scroll">
                <div class="slot-list">
                  <button
                    v-for="slot in saveSlots"
                    :key="slot.path"
                    class="library-item save-item"
                    :class="{ selected: slot.path === selectedSavePath }"
                    @click="loadSave(slot.path)"
                  >
                    <strong>{{ slot.label }}</strong>
                    <span>{{ slot.modified_at || '—' }}</span>
                    <em>{{ saveFileName(slot.path) }}</em>
                  </button>
                </div>
              </el-scrollbar>
            </div>

            <div class="save-editor-pane">
              <div v-if="saveSummary" class="save-editor-content">
                <div class="save-editor-heading">
                  <div><div class="editor-title">当前存档</div><div class="mini-info selectable">{{ selectedSavePath }}</div></div>
                  <el-button size="small" @click="saveDataDialogVisible = true">查看完整数据</el-button>
                </div>
                <div class="save-summary-grid">
                  <div class="info-box"><span>金钱</span><div>{{ saveSummary.gold ?? 0 }}</div></div>
                  <div class="info-box"><span>步数</span><div>{{ saveSummary.steps ?? 0 }}</div></div>
                  <div class="info-box"><span>角色数</span><div>{{ saveSummary.actor_count ?? 0 }}</div></div>
                </div>

                <div class="save-tools-grid">
                  <section class="save-tool-group">
                    <strong>资源</strong>
                    <div class="compact-action"><el-input v-model="saveForm.gold" type="number" placeholder="金钱" /><el-button @click="setSaveGold">设置金钱</el-button></div>
                    <div class="compact-action three"><el-input v-model="saveForm.itemId" type="number" placeholder="物品ID" /><el-input v-model="saveForm.itemCount" type="number" placeholder="数量" /><el-button @click="setSaveItem">设置物品</el-button></div>
                  </section>
                  <section class="save-tool-group">
                    <strong>角色</strong>
                    <div class="compact-action three"><el-input v-model="saveForm.actorId" type="number" placeholder="角色ID" /><el-input v-model="saveForm.actorLevel" type="number" placeholder="等级" /><el-button @click="setActorLevel">设置等级</el-button></div>
                  </section>
                </div>
              </div>
              <el-empty v-else description="先选择一个存档槽" />
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'maps'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>地图查看</strong>
              <div class="card-head-right wrap"><el-button size="small" :icon="Refresh" @click="loadMaps" :loading="busy.maps">刷新</el-button></div>
            </div>
          </template>

          <div class="map-layout">
            <div class="map-list-pane">
              <el-scrollbar class="list-scroll">
                <div class="slot-list">
                  <button
                    v-for="map in maps"
                    :key="map.map_id"
                    class="library-item save-item"
                    :class="{ selected: map.map_id === selectedMapId }"
                    @click="loadMapDetail(map.map_id)"
                  >
                    <strong>{{ map.name }} #{{ map.map_id }}</strong>
                    <span>{{ map.width }}×{{ map.height }} · 事件 {{ map.event_count }}</span>
                    <em>{{ map.file }}</em>
                  </button>
                </div>
              </el-scrollbar>
            </div>

            <div class="map-workspace">
              <div v-if="mapDetail" class="map-main">
                <div class="map-toolbar">
                  <div><strong>{{ mapDetail.record.name }}</strong><span>{{ mapDetail.record.width }}×{{ mapDetail.record.height }} · {{ mapDetail.events?.length || 0 }} 个事件</span></div>
                  <div class="map-legend"><span class="passable">可通行</span><span class="blocked">阻挡</span><span class="event">事件</span><span class="player">玩家</span></div>
                </div>
                <div
                  ref="mapViewport"
                  class="map-viewport"
                  :class="{ dragging: mapDragging }"
                  @mousedown="startMapDrag"
                  @mousemove="moveMapPointer"
                  @mouseup="endMapDrag"
                  @mouseleave="leaveMapPointer"
                >
                  <canvas
                    ref="mapCanvas"
                    class="map-canvas"
                    :width="mapCanvasWidth"
                    :height="mapCanvasHeight"
                    @click="selectMapTile"
                  ></canvas>
                </div>
                <div class="map-coordinate">{{ hoveredTile ? `格子 (${hoveredTile.x}, ${hoveredTile.y})` : '拖动画布移动，滚轮可上下浏览' }}</div>
              </div>
              <el-empty v-else description="选择左侧地图查看" />

              <aside class="event-inspector">
                <template v-if="selectedTile">
                  <div class="event-inspector-head"><div><strong>格子 {{ selectedTile.x }}, {{ selectedTile.y }}</strong><span>{{ selectedTileEvents.length }} 个事件</span></div><el-button size="small" type="primary" @click="teleportToTile(selectedTile.x, selectedTile.y)">传送到这里</el-button></div>
                  <el-scrollbar class="event-scroll">
                    <div v-if="!selectedTileEvents.length" class="empty-tile">这个格子没有事件。</div>
                    <section v-for="event in selectedTileEvents" :key="event.event_id" class="event-block">
                      <div class="event-title"><strong>EV{{ event.event_id }} · {{ event.name }}</strong><span>{{ event.page_count }} 页 / {{ event.command_count }} 步</span></div>
                      <div class="event-section-label">触发条件</div>
                      <div v-for="condition in event.conditions" :key="condition" class="condition-row">
                        <span>{{ condition }}</span>
                        <el-button v-if="conditionSwitchId(condition) !== null" size="small" :type="runtimeSwitchValue(conditionSwitchId(condition)) ? 'success' : 'default'" @click="toggleRuntimeSwitch(conditionSwitchId(condition))">
                          {{ runtimeSwitchValue(conditionSwitchId(condition)) ? 'ON' : 'OFF' }}
                        </el-button>
                      </div>
                      <div class="event-section-label">执行步骤</div>
                      <button v-for="(command, index) in event.commands" :key="index" class="command-row" @click="handleEventCommand(command)"><span>{{ index + 1 }}</span>{{ command }}</button>
                    </section>
                  </el-scrollbar>
                </template>
                <div v-else class="empty-tile">点击地图格子查看事件与触发条件。</div>
              </aside>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'runtime'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>游戏实时修改</strong>
              <div class="card-head-right wrap">
                <el-tag :type="runtimeConnected ? 'success' : 'info'" effect="plain">{{ runtimeConnected ? '已连接游戏' : '未连接' }}</el-tag>
                <el-button size="small" type="primary" :icon="Refresh" @click="loadRuntimeState(false)">刷新状态</el-button>
              </div>
            </div>
          </template>
          <div class="runtime-page">
            <div class="runtime-summary">
              <div class="info-box"><span>金币</span><div>{{ runtimeState?.gold ?? '—' }}</div></div>
              <div class="info-box"><span>当前地图</span><div>{{ runtimeState?.map?.name || runtimeState?.map?.id || '—' }}</div></div>
              <div class="info-box"><span>玩家位置</span><div>{{ runtimeState?.map ? `${runtimeState.map.x}, ${runtimeState.map.y}` : '—' }}</div></div>
              <div class="info-box"><span>队伍人数</span><div>{{ runtimeState?.actors?.length ?? '—' }}</div></div>
            </div>
            <div class="runtime-groups">
              <section class="runtime-group">
                <h3>玩家与资源</h3>
                <div class="form-row"><span>金币</span><el-input v-model="runtimeForm.gold" type="number" /><el-button type="primary" @click="setRuntimeGold">应用</el-button></div>
                <div class="form-row"><span>穿墙</span><el-switch v-model="runtimeForm.through" @change="setRuntimeThrough" /></div>
                <div class="form-row"><span>点击传送</span><el-switch v-model="runtimeForm.clickTeleport" @change="setRuntimeOptions" /></div>
                <div class="form-row"><span>自动存档（分钟）</span><el-input v-model="runtimeForm.autoSaveMinutes" type="number" /><el-button @click="setRuntimeOptions">应用</el-button></div>
                <div class="form-row teleport-row"><span>传送坐标</span><el-input v-model="runtimeForm.x" type="number" placeholder="X" /><el-input v-model="runtimeForm.y" type="number" placeholder="Y" /><el-button @click="teleportToTile(runtimeForm.x, runtimeForm.y)">传送</el-button></div>
              </section>
              <section class="runtime-group">
                <h3>角色状态</h3>
                <el-select v-model="runtimeForm.actorId" placeholder="选择角色" @change="syncRuntimeActorForm"><el-option v-for="actor in runtimeState?.actors || []" :key="actor.id" :label="`${actor.name} #${actor.id}`" :value="actor.id" /></el-select>
                <div class="actor-gauges"><el-input v-model="runtimeForm.hp" type="number"><template #prepend>HP</template></el-input><el-input v-model="runtimeForm.mp" type="number"><template #prepend>MP</template></el-input><el-input v-model="runtimeForm.tp" type="number"><template #prepend>TP</template></el-input></div>
                <el-button type="primary" @click="setRuntimeActor">应用角色数值</el-button>
                <div class="lock-row"><el-checkbox v-model="runtimeForm.lockHp">锁定 HP</el-checkbox><el-checkbox v-model="runtimeForm.lockMp">锁定 MP</el-checkbox><el-checkbox v-model="runtimeForm.lockTp">锁定 TP</el-checkbox><el-button @click="setRuntimeLocks">应用锁定</el-button></div>
              </section>
              <section class="runtime-group">
                <h3>战斗与速度</h3>
                <div class="battle-actions"><el-button type="default" @click="setBattleResult('win')">直接胜利</el-button><el-button type="default" @click="setBattleResult('escape')">立即逃跑</el-button><el-button type="default" @click="setBattleResult('lose')">直接失败</el-button></div>
                <div class="form-row"><span>游戏速度</span><el-input v-model="runtimeForm.gameSpeed" type="number" /><el-button @click="setRuntimeAdvancedOptions">应用</el-button></div>
                <div class="form-row"><span>战斗速度</span><el-input v-model="runtimeForm.battleSpeed" type="number" /><el-button @click="setRuntimeAdvancedOptions">应用</el-button></div>
                <div class="form-row"><span>移动速度增加</span><el-input v-model="runtimeForm.moveSpeedIncrease" type="number" /><el-button @click="setRuntimeAdvancedOptions">应用</el-button></div>
                <div class="form-row"><span>自动战斗</span><el-switch v-model="runtimeForm.autoBattle" @change="setRuntimeAdvancedOptions" /></div>
                <div class="form-row"><span>上帝模式</span><el-switch v-model="runtimeForm.godMode" @change="setRuntimeAdvancedOptions" /></div>
              </section>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'live'" class="view-shell feature-shell" data-tour="live-translate">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>实时 Hook 翻译</strong>
              <div class="card-head-right wrap">
                <el-button size="small" type="primary" @click="startLive">启动</el-button>
                <el-button size="small" @click="stopLive">停止</el-button>
                <el-button size="small" @click="refreshLive">刷新状态</el-button>
                <el-button size="small" :icon="Notebook" @click="openLiveDebug">调试窗口</el-button>
              </div>
            </div>
          </template>

          <div class="live-page">
            <el-alert
              v-if="isRenPySelected && !gameRunning"
              title="RenPy 启动顺序"
              description="请先启动 RenPy 游戏，进入游戏后再点击“启动”开启实时翻译。RPGMaker 会在项目载入时自动准备桥接组件。"
              type="info"
              :closable="false"
              show-icon
            />
            <div class="live-summary">
              <div class="info-box"><span>本地服务</span><div>{{ liveStatus.running ? '运行中' : '未启动' }}</div></div>
              <div class="info-box"><span>游戏 Hook</span><div>{{ liveStatus.connected ? '已连接' : '等待游戏' }}</div></div>
              <div class="info-box"><span>AI 状态</span><div>{{ liveWorkerStateLabel }}</div></div>
              <div class="info-box"><span>实时进度</span><div>已译 {{ liveStatus.worker?.translated || 0 }} · 队列 {{ liveStatus.queue_count || 0 }}</div></div>
            </div>
            <div class="split-layout live-layout">
              <div class="left-pane live-events-pane">
                <div class="live-pane-head"><div><strong>最近捕获</strong><span>Hook 捕获的对话、选项与实时替换结果</span></div><el-tag :type="liveStatus.worker?.failures ? 'danger' : 'success'">失败 {{ liveStatus.worker?.failures || 0 }}</el-tag></div>
                <el-alert v-if="liveStatus.worker?.lastError" :title="liveStatus.worker.lastError" type="warning" :closable="false" show-icon />
                <el-table :data="liveRecentEvents" height="100%" empty-text="启动游戏后将在这里显示捕获文本">
                  <el-table-column label="状态" width="82"><template #default="{ row }"><el-tag size="small" :type="row.matched ? 'success' : 'info'">{{ row.matched ? '已替换' : '已捕获' }}</el-tag></template></el-table-column>
                  <el-table-column prop="kind" label="来源" width="120" />
                  <el-table-column prop="source" label="文本" min-width="260" />
                </el-table>
              </div>
            <div class="right-pane">
              <div class="editor-stack">
                <div class="editor-title">手动写入实时译文</div>
                <el-input v-model="liveSource" type="textarea" :rows="4" placeholder="原文" />
                <el-input v-model="liveTarget" type="textarea" :rows="4" placeholder="译文" />
                <div class="detail-actions"><el-button type="primary" @click="mergeLive">写入实时翻译表</el-button></div>
                <div class="mini-info">实时组件会在工具安装时随项目准备。RenPy 请先启动游戏，再回到这里启动实时翻译；RPGMaker 会在启动实时翻译时自动启用桥接，并优先使用已提前翻译的对白。</div>
              </div>
            </div>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'ai'" class="view-shell feature-shell" data-tour="ai-settings">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>AI 翻译</strong>
              <div class="card-head-right wrap">
                <el-tag type="success" effect="plain">自动保存</el-tag>
              </div>
            </div>
          </template>

          <div class="split-layout ai-layout">
            <div class="left-pane">
              <div class="editor-stack">
                <div class="editor-title">渠道配置</div>
                <div class="ai-profile-manager">
                  <div class="profile-picker">
                    <el-select v-model="selectedAiConfigName" size="small" clearable filterable placeholder="选择已保存配置" @change="loadNamedAiConfig">
                      <el-option v-for="profile in namedAiConfigList" :key="profile.name" :label="profile.name" :value="profile.name">
                        <span>{{ profile.name }}</span>
                        <small>{{ profile.providerLabel }} · {{ profile.model || '未选模型' }}</small>
                      </el-option>
                    </el-select>
                    <el-input v-model="aiConfigName" size="small" placeholder="配置名称，例如 NVIDIA 免费 / Ollama 本地" />
                  </div>
                  <div class="profile-actions">
                    <el-button size="small" type="primary" plain @click="saveNamedAiConfig">保存为配置</el-button>
                    <el-button size="small" type="danger" plain @click="deleteNamedAiConfig" :disabled="!selectedAiConfigName">删除</el-button>
                  </div>
                </div>
                <div class="ai-field-grid ai-connection-grid">
                  <label class="ai-field">
                    <span>&#x63A5;&#x53E3;&#x7C7B;&#x578B;</span>
                    <el-select v-model="aiForm.provider" placeholder="&#x9009;&#x62E9;&#x63A5;&#x53E3;&#x7C7B;&#x578B;" @change="onAiProviderChange">
                      <el-option label="OpenAI &#x517C;&#x5BB9;&#x63A5;&#x53E3;" value="openai" />
                      <el-option label="Anthropic &#x517C;&#x5BB9;&#x63A5;&#x53E3;" value="anthropic" />
                      <el-option label="Ollama &#x672C;&#x5730;&#x6A21;&#x578B;" value="ollama" />
                      <el-option label="本机已登录 Agent（无需 API Key）" value="accountbridge" />
                    </el-select>
                  </label>
                  <label v-if="aiForm.provider !== 'accountbridge'" class="ai-field ai-field-wide">
                    <span>&#x63A5;&#x53E3;&#x5730;&#x5740; Base URL</span>
                    <el-input v-model="aiForm.baseUrl" :placeholder="aiForm.provider === 'ollama' ? 'http://127.0.0.1:11434' : 'https://api.openai.com/v1'" />
                  </label>
                  <label v-if="aiForm.provider !== 'ollama' && aiForm.provider !== 'accountbridge'" class="ai-field ai-field-wide">
                    <span>API Key</span>
                    <el-input v-model="aiForm.apiKey" type="password" show-password placeholder="&#x7C98;&#x8D34;&#x4F60;&#x7684; API Key" />
                  </label>
                  <div v-else-if="aiForm.provider === 'ollama'" class="ollama-note ai-field-wide"><el-tag type="success" effect="plain">&#x65E0;&#x9700; API Key</el-tag><span>&#x5207;&#x6362;&#x5230; Ollama &#x65F6;&#x4F1A;&#x81EA;&#x52A8;&#x68C0;&#x6D4B;&#x672C;&#x673A;&#x5DF2;&#x7ECF;&#x5B89;&#x88C5;&#x7684;&#x6A21;&#x578B;&#x3002;</span></div>
                  <template v-else>
                    <label class="ai-field"><span>本机 Agent</span><el-select v-model="aiForm.accountProvider" @change="onAccountProviderChange"><el-option label="自动检测（推荐：agy/Claude/Codex/OpenCode）" value="local-agent-auto" /><el-option label="Antigravity（agy CLI 登录态）" value="antigravity-cli" /><el-option label="Claude Code（本机 CLI）" value="anthropic" /><el-option label="Codex CLI（本机登录态）" value="openai-codex" /><el-option label="OpenCode（本机 CLI）" value="opencode" /><el-option label="Gemini / Google 账号（浏览器 OAuth，备用）" value="gemini-cli" /><el-option label="GitHub Copilot（旧桥接）" value="github-copilot" /><el-option label="Kimi Coding（旧桥接）" value="kimi-coding" /><el-option label="xAI / Grok（旧桥接）" value="xai" /></el-select></label>
                    <div class="ollama-note ai-field-wide"><el-button v-if="aiForm.accountProvider === 'gemini-cli'" type="primary" plain @click="startAccountLogin">登录 Gemini 账号</el-button><el-tag v-else type="success" effect="plain">读取本机 CLI 登录态</el-tag><span>{{ accountLoginStatus || (aiForm.accountProvider === 'gemini-cli' ? 'Gemini OAuth 仅作为备用；推荐使用本机 Agent 自动或 Antigravity。' : '请先在终端登录对应 CLI，例如运行 agy、claude、codex 或 opencode；本软件只调用 CLI，不读取账号密码。') }}</span></div>
                  </template>
                  <div class="ai-field ai-field-wide">
                    <span>&#x6A21;&#x578B; Model</span>
                  <div class="model-picker"><el-select v-model="aiForm.model" filterable allow-create placeholder="&#x4F8B;&#x5982; gpt-4o-mini / claude / qwen"><el-option v-for="model in aiModels" :key="model" :label="model" :value="model" /></el-select><el-button :loading="busy.models" @click="fetchAiModels(false)"><span v-if="aiForm.provider === 'ollama'">&#x68C0;&#x6D4B;&#x672C;&#x5730;&#x6A21;&#x578B;</span><span v-else-if="aiForm.provider === 'accountbridge'">读取可选模型</span><span v-else>&#x83B7;&#x53D6;&#x6A21;&#x578B;</span></el-button></div>
                  </div>
                </div>
                <div class="ai-section-caption">&#x6279;&#x8BD1;&#x53C2;&#x6570;</div>
                <div class="ai-field-grid ai-run-grid">
                  <label class="ai-field"><span>&#x5355;&#x6279;&#x6570;&#x91CF;</span><el-input v-model.number="aiForm.batchSize" type="number" min="1" max="200" placeholder="&#x5EFA;&#x8BAE; 30-80&#xFF0C;&#x6700;&#x5927; 200" /></label>
                  <label class="ai-field"><span>&#x5E76;&#x53D1;&#x7EBF;&#x7A0B;</span><el-input v-model.number="aiForm.concurrency" type="number" min="1" max="8" placeholder="&#x514D;&#x8D39; API &#x5EFA;&#x8BAE; 1" /></label>
                  <label class="ai-field"><span>&#x8BF7;&#x6C42;&#x95F4;&#x9694; ms</span><el-input v-model.number="aiForm.requestIntervalMs" type="number" min="0" max="60000" placeholder="&#x5982; 3000" /></label>
                  <label class="ai-field"><span>429 &#x91CD;&#x8BD5;&#x6B21;&#x6570;</span><el-input v-model.number="aiForm.rateLimitRetries" type="number" min="0" max="10" placeholder="&#x5982; 3" /></label>
                  <label class="ai-field"><span>&#x8BF7;&#x6C42;&#x8D85;&#x65F6;&#x79D2;</span><el-input v-model.number="aiForm.requestTimeoutSec" type="number" min="30" max="900" placeholder="&#x5982; 240 / 600" /></label>
                  <label class="ai-field"><span>&#x76EE;&#x6807;&#x8BED;&#x8A00;</span><el-input v-model="aiForm.targetLang" placeholder="&#x7B80;&#x4F53;&#x4E2D;&#x6587;" /></label>
                </div>
                <div class="mini-info">&#x63A8;&#x8350;&#xFF1A;&#x514D;&#x8D39; API &#x7528;&#x5355;&#x6279; 30-80&#x3001;&#x5E76;&#x53D1; 1&#x3001;&#x95F4;&#x9694; 3000-8000ms&#xFF1B;&#x5982;&#x679C;&#x5355;&#x6279; 200 &#x8D85;&#x65F6;&#xFF0C;&#x4F1A;&#x81EA;&#x52A8;&#x62C6;&#x6210;&#x5C0F;&#x6279;&#x91CD;&#x8BD5;&#xFF0C;&#x4E5F;&#x53EF;&#x4EE5;&#x628A;&#x8BF7;&#x6C42;&#x8D85;&#x65F6;&#x79D2;&#x8C03;&#x5230; 300-600&#x3002;</div>
              </div>
            </div>
            <div class="right-pane">
              <el-tabs v-model="aiToolTab" class="ai-tool-tabs">
                <el-tab-pane label="测试翻译" name="test"><div class="editor-stack ai-tool-pane"><el-input v-model="aiTestSource" type="textarea" :rows="5" placeholder="输入一段要测试的原文" /><div class="detail-actions"><el-button type="primary" :loading="busy.aiTest" @click="testAi">开始测试</el-button></div><el-input v-model="aiTestResult" type="textarea" :rows="6" readonly placeholder="测试译文会显示在这里" /></div></el-tab-pane>
                <el-tab-pane label="批量翻译" name="batch"><div class="editor-stack ai-tool-pane"><el-input v-model="aiPreview" type="textarea" :rows="10" readonly placeholder="批量翻译结果" /><div class="detail-actions"><el-button type="primary" @click="translateBatch">翻译当前未完成文本</el-button><el-button :loading="busy.aiTest" @click="testAiBatch">批量测试</el-button></div></div></el-tab-pane>
              </el-tabs>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'settings'" class="view-shell feature-shell" data-tour="settings-page">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>设置与关于</strong>
            </div>
          </template>
          <div class="settings-page">
            <section class="settings-section">
              <h3>版本</h3>
              <div class="settings-line"><div><strong>RPGRenPyLocalizer {{ appVersion || '—' }}</strong><span>{{ updateInfo.hasUpdate ? `最新版本 ${updateInfo.latestVersion} 可用` : updateInfo.checked ? '当前已是最新版本' : '尚未检查更新' }}</span></div><el-button type="primary" :loading="busy.update" @click="checkForUpdates(true)">检查更新</el-button></div>
            </section>
            <section class="settings-section">
              <h3>开源项目</h3>
              <div class="settings-line"><div><strong>lyb82ndkf-lab/RPG-RenPy-Localizer</strong><span>查看源码、版本标签和发布说明</span></div><el-button @click="openExternal(githubUrl)">打开 GitHub</el-button></div>
            </section>
            <section class="settings-section feedback-section">
              <h3>提交建议给作者</h3>
              <el-input v-model="feedback.subject" placeholder="建议主题" />
              <el-input v-model="feedback.body" type="textarea" :rows="7" placeholder="请描述问题、建议或希望增加的功能" />
              <div class="settings-line"><span class="mini-info">将通过系统默认邮件程序发送到 lyb82ndkf@gmail.com</span><el-button type="primary" @click="sendFeedback">打开邮件</el-button></div>
            </section>
          </div>
        </el-card>
      </section>

      </div>

      <el-dialog v-model="translationDialogVisible" title="翻译详情" width="min(860px, 88vw)" destroy-on-close>
        <div v-if="selectedTranslation" class="translation-dialog-content">
          <div class="translation-detail-meta"><el-tag :type="selectedTranslation.target ? 'success' : 'warning'">{{ selectedTranslation.target ? '已翻译' : '待翻译' }}</el-tag><span>{{ translationMeta }}</span></div>
          <label>原文</label>
          <el-input v-model="translationDraft.source" type="textarea" :autosize="{ minRows: 5, maxRows: 10 }" readonly />
          <label>译文</label>
          <el-input v-model="translationDraft.target" type="textarea" :autosize="{ minRows: 6, maxRows: 12 }" placeholder="输入译文" />
        </div>
        <template #footer><el-button @click="translateSelectedWithAI">AI 翻译</el-button><el-button type="primary" @click="saveTranslationTarget">保存译文</el-button></template>
      </el-dialog>

      <el-dialog v-model="saveDataDialogVisible" title="完整存档数据" width="min(960px, 90vw)">
        <el-input v-model="savePreview" class="save-json-preview" type="textarea" :rows="24" readonly />
      </el-dialog>

      <el-dialog
        v-model="liveDebugVisible"
        title="Ren'Py 实时翻译状态"
        width="min(1160px, 94vw)"
        class="live-debug-dialog"
        destroy-on-close
        @closed="stopLiveDebugPolling"
      >
        <div class="live-debug-shell simplified">
          <section class="live-debug-main">
            <div class="live-debug-current">
              <div>
                <span>当前游戏文本</span>
                <strong>{{ liveDebug.status?.current_source || '等待游戏显示一条对话…' }}</strong>
                <small v-if="liveDebug.status?.current_target">当前译文：{{ liveDebug.status.current_target }}</small>
              </div>
              <el-tag :type="liveDebug.status?.connected ? 'success' : 'info'">{{ liveDebug.status?.connected ? '已连接游戏' : '等待连接' }}</el-tag>
            </div>
            <div class="live-debug-metrics compact">
              <div><span>待翻译</span><strong>{{ liveDebug.status?.queue_count || 0 }}</strong></div>
              <div><span>本次已译</span><strong>{{ liveDebug.worker?.translated || 0 }}</strong></div>
              <div><span>自动重试</span><strong>{{ liveDebug.worker?.failures || 0 }}</strong></div>
              <div><span>批量状态</span><strong>{{ liveBatchPlanLabel }}</strong></div>
            </div>
            <div v-if="liveDebug.worker?.lastError" class="live-debug-notice">{{ liveDebug.worker.lastError }}</div>
            <el-tabs v-model="liveDebugTab" class="live-debug-tabs">
              <el-tab-pane label="翻译队列" name="queue">
                <el-table :data="liveDebugQueue" height="400" empty-text="队列为空；游戏新文本会自动出现在这里">
                  <el-table-column label="#" type="index" width="58" />
                  <el-table-column label="待翻译文本" prop="source" min-width="600" show-overflow-tooltip />
                  <el-table-column label="状态" width="130">
                    <template #default="{ row }"><el-tag size="small" :type="row.current ? 'warning' : 'info'">{{ row.current ? '正在处理' : '排队等待' }}</el-tag></template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="详细日志" name="logs">
                <el-table :data="liveDebugEvents" height="400" empty-text="尚无翻译活动">
                  <el-table-column label="步骤" width="150">
                    <template #default="{ row }"><el-tag size="small" :type="liveDebugStageType(row.stage)">{{ liveDebugStageLabel(row.stage) }}</el-tag></template>
                  </el-table-column>
                  <el-table-column label="详细信息" min-width="650">
                    <template #default="{ row }">{{ liveDebugSummary(row) }}</template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
            <div class="live-debug-actions horizontal">
              <el-button type="success" :icon="Connection" @click="startLiveFromDebug">启动 AI 翻译</el-button>
              <el-button type="primary" :icon="MagicStick" @click="forceLiveHello">替换当前文本为 hello</el-button>
              <el-button :icon="Refresh" @click="loadLiveDebug">刷新</el-button>
              <el-button plain @click="clearLiveDebug">清空日志</el-button>
            </div>
          </section>
        </div>
      </el-dialog>

      <el-tour
        v-model="tutorialOpen"
        v-model:current="tutorialCurrent"
        type="primary"
        :scroll-into-view-options="{ block: 'center', inline: 'center' }"
        :mask="{ color: 'rgba(6, 12, 22, .66)' }"
        :z-index="3000"
        @change="handleTutorialChange"
      >
        <el-tour-step
          v-for="step in tutorialSteps"
          :key="step.key"
          :target="step.target"
          :title="step.title"
          :description="step.description"
          :placement="step.placement"
        />
        <template #indicators="{ current, total }">
          <span>{{ current + 1 }} / {{ total }}</span>
        </template>
      </el-tour>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowDown, Delete, FolderOpened, MagicStick, MapLocation, Notebook, Plus, Refresh, Search, Setting, VideoPlay, Connection, Reading, Coin, EditPen } from '@element-plus/icons-vue';
import logoUrl from './assets/app-logo.png';

const navItems = [
  { key: 'library', label: '游戏库', icon: Reading },
  { key: 'translations', label: '翻译', icon: Notebook },
  { key: 'data', label: '数据修改', icon: EditPen },
  { key: 'saves', label: '存档', icon: Coin },
  { key: 'maps', label: '地图', icon: MapLocation },
  { key: 'runtime', label: '实时修改', icon: Connection },
  { key: 'live', label: '实时翻译', icon: Connection },
  { key: 'ai', label: 'AI 设置', icon: MagicStick },
  { key: 'settings', label: '设置', icon: Setting },
];

const viewMetaMap = {
  library: { eyebrow: 'Library', title: '游戏库', subtitle: '在这一页完成添加、筛选、启动和移除游戏。' },
  translations: { eyebrow: 'Translation', title: '翻译工作台', subtitle: 'AI 批译、查看详情，以及导入导出翻译包。' },
  data: { eyebrow: 'Data', title: '数据修改', subtitle: '角色、物品、技能、敌人等数据库字段直接编辑。' },
  saves: { eyebrow: 'Save', title: '存档修改', subtitle: '直接读取存档槽并修改金钱、物品和角色等级。开关与变量请在数据修改页实时操作。' },
  maps: { eyebrow: 'Map', title: '地图查看', subtitle: '查看地图、事件和基础布局。' },
  runtime: { eyebrow: 'Runtime', title: '游戏实时修改', subtitle: '读取当前玩家状态，并实时修改数值、移动与游戏选项。' },
  live: { eyebrow: 'Live', title: '实时翻译', subtitle: '桥接组件会自动准备，启动服务后即可写入实时译文。' },
  ai: { eyebrow: 'AI', title: 'AI 翻译', subtitle: '配置模型和渠道，批量翻译当前文本。' },
  settings: { eyebrow: 'Settings', title: '设置', subtitle: '版本更新、项目地址与意见反馈。' },
};

const apiBase = ref('');
const currentView = ref('library');
const backendReady = ref(false);
const backendError = ref(false);
const backendLabel = ref('连接中...');
const entries = ref([]);
const librarySearch = ref('');
const selectedPath = ref('');
const loadedProjectPath = ref('');
const busy = reactive({ add: false, refresh: false, reload: false, launch: false, remove: false, translation: false, data: false, saves: false, maps: false, models: false, aiTest: false, update: false });
const viewLoading = ref(false);
const gameStatus = ref({ running: false, activePath: '', games: [] });
let gameStatusTimer = null;
const loadedViewKeys = new Set();

const translations = ref([]);
const translationVersions = ref([]);
const translationSearch = ref('');
const translationCategory = ref('');
const translationMissingOnly = ref(false);
const selectedTranslationId = ref('');
const translationPage = ref(1);
const translationPageSize = ref(50);
const translationPageSizes = [25, 50, 100, 200];
const translationDraft = reactive({ source: '', target: '' });
const translationMeta = ref('');
const translationDialogVisible = ref(false);
const translationProgress = reactive({ active: false, title: 'AI 批译进度', message: '等待开始', current: 0, total: 0, success: 0, failed: 0 });
const translationStopRequested = ref(false);

const dataRecords = ref([]);
const dataSearch = ref('');
const dataCategory = ref('');
const selectedDataId = ref('');
const dataDraft = reactive({ label: '', value: '' });
const dataMeta = ref('');
const dataSection = ref('database');
const selectedRuntimeDataId = ref(null);
const runtimeDataForm = reactive({ count: 0, level: 1, hp: 0, mp: 0, tp: 0, switchValue: false, variableValue: '' });

const saveSlots = ref([]);
const selectedSavePath = ref('');
const saveSummary = ref(null);
const savePreview = ref('');
const saveDataDialogVisible = ref(false);
const saveForm = reactive({ gold: 0, itemId: 1, itemCount: 1, actorId: 1, actorLevel: 1, switchId: 1, switchValue: true, variableId: 1, variableValue: '' });

const maps = ref([]);
const selectedMapId = ref(0);
const mapDetail = ref(null);
const mapCanvas = ref(null);
const mapViewport = ref(null);
const mapTileSize = 28;
const hoveredTile = ref(null);
const selectedTile = ref(null);
const mapDragging = ref(false);
const mapDragState = reactive({ x: 0, y: 0, left: 0, top: 0, moved: false });

const runtimeState = ref(null);
const runtimeConnected = ref(false);
const runtimeForm = reactive({ gold: 0, actorId: null, hp: 0, mp: 0, tp: 0, lockHp: false, lockMp: false, lockTp: false, through: false, clickTeleport: false, autoSaveMinutes: 0, x: 0, y: 0, gameSpeed: 1, battleSpeed: 1, moveSpeedIncrease: 0, autoBattle: false, godMode: false });
let runtimePollTimer = null;

const liveStatus = ref({ running: false, connected: false, queue_count: 0, worker: { running: false, state: 'stopped', translated: 0, failures: 0, lastError: '' }, recentEvents: [] });
const liveSource = ref('');
const liveTarget = ref('');
const liveDebugVisible = ref(false);
const liveDebugTab = ref('queue');
const liveDebug = ref({ status: {}, worker: {}, tree: [], debugEvents: [], hookEvents: [] });
const liveDebugSelected = ref(null);
let liveDebugTimer = null;

const aiForm = reactive({ provider: 'openai', apiKey: '', baseUrl: 'https://api.openai.com/v1', model: '', localAgentPath: '', accountProvider: 'local-agent-auto', batchSize: 50, concurrency: 1, requestIntervalMs: 1200, rateLimitRetries: 3, requestTimeoutSec: 240, targetLang: '\u7b80\u4f53\u4e2d\u6587' });
const aiModels = ref([]);
const accountLoginStatus = ref('');
const aiProfiles = reactive({});
const aiNamedConfigs = reactive({});
const selectedAiConfigName = ref('');
const aiConfigName = ref('');
let previousAiProvider = 'openai';
let aiAutosaveTimer = null;
let aiSettingsReady = false;
let suppressAiAutosave = false;
const aiToolTab = ref('test');
const aiTestSource = ref('Hello, welcome to the game.');
const aiTestResult = ref('');
const aiPreview = ref('');
const appVersion = ref('');
const updateInfo = reactive({ checked: false, hasUpdate: false, latestVersion: '' });
const feedback = reactive({ subject: '', body: '' });
const githubUrl = 'https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer';
const releasesUrl = githubUrl + '/releases';
const tutorialOpen = ref(false);
const tutorialCurrent = ref(0);
const tutorialSteps = computed(() => [
  {
    "key": "intro",
    "view": "library",
    "target": "[data-tour=\"tutorial-link\"]",
    "title": "先从这里开始",
    "description": "本教程会按新流程走一遍：导入游戏 → 载入项目 → 识别引擎 → 按 RPGMaker 或 RenPy 的正确方式翻译。",
    "placement": "right"
  },
  {
    "key": "add",
    "view": "library",
    "target": "[data-tour=\"add-game\"]",
    "title": "第一步：导入游戏",
    "description": "在游戏库顶部点击“添加游戏”导入单个 exe，或点击“导入文件夹”递归扫描整个目录。工具只会加入 RenPy 和 RPG Maker MV/MZ，并会自动去重。",
    "placement": "right"
  },
  {
    "key": "library",
    "view": "library",
    "target": "[data-tour=\"library-table\"]",
    "title": "第二步：选中并载入项目",
    "description": "在游戏库点选刚导入的游戏。选中后，左侧当前游戏卡片会显示识别出的引擎类型、路径和运行状态。",
    "placement": "right"
  },
  {
    "key": "current-game",
    "view": "library",
    "target": "[data-tour=\"current-game\"]",
    "title": "确认游戏类型",
    "description": "这里会显示 RPG Maker MV/MZ 或 RenPy。后续流程会根据类型自动隐藏不适用功能，避免用户误操作。",
    "placement": "right"
  },
  {
    "key": "translation-open",
    "view": "translations",
    "target": "[data-tour=\"nav-translations\"]",
    "title": "第三步：进入翻译工作台",
    "description": "先进入“翻译”，点击“一键翻译并启动”或“AI 批译”。RPGMaker 只会展示 database/dialogue；RenPy 只会展示 dialogue/choice。",
    "placement": "right"
  },
  {
    "key": "translation-table",
    "view": "translations",
    "target": "[data-tour=\"translation-workbench\"]",
    "title": "只翻译安全条目",
    "description": "RPGMaker 的 event/system/plugin 不再展示也不会写回，避免破坏事件脚本。批量翻译会按 entry_id 发送 JSON，并按 entry_id 写回。",
    "placement": "top"
  },
  {
    "key": "ai",
    "view": "ai",
    "target": "[data-tour=\"ai-settings\"]",
    "title": "配置 AI 与并发",
    "description": "在 AI 设置里选择 OpenAI、Anthropic 或 Ollama，设置单批数量和 1-8 个并发线程。多线程批译会分批并发执行并只保存有效译文。",
    "placement": "left"
  },
  {
    "key": "rpg-flow",
    "view": "translations",
    "target": "[data-tour=\"translation-workbench\"]",
    "title": "RPGMaker 推荐流程",
    "description": "RPGMaker 暂不引导用户使用实时 Hook：先完成翻译，再由“开始翻译”自动生成运行时副本并启动游戏。左侧会隐藏“实时翻译”。",
    "placement": "top"
  },
  {
    "key": "renpy-flow",
    "view": "library",
    "target": "[data-tour=\"tutorial-link\"]",
    "title": "RenPy 推荐流程",
    "description": "RenPy 可使用实时翻译：先启动游戏进入画面，再回到“实时翻译”启动 Hook。RenPy 翻译范围只包含对白和选项。",
    "placement": "right"
  },
  {
    "key": "data",
    "view": "data",
    "target": "[data-tour=\"nav-data\"]",
    "title": "数据修改是可选功能",
    "description": "RPGMaker 可继续使用数据、存档、地图和实时修改；RenPy 会自动隐藏不适用的数据页，避免误导。",
    "placement": "right"
  },
  {
    "key": "settings",
    "view": "settings",
    "target": "[data-tour=\"settings-page\"]",
    "title": "设置与反馈",
    "description": "最后可在设置页检查更新、打开项目主页或反馈问题。以后点击左侧“如何使用”可以重新查看教程。",
    "placement": "left"
  }
]);

const selectedEntry = computed(() => entries.value.find((entry) => entry.path === selectedPath.value) || null);
const gameRunning = computed(() => Boolean(gameStatus.value.running));
const isRenPySelected = computed(() => selectedEntry.value?.engine === "Ren'Py");
const isRpgMakerSelected = computed(() => selectedEntry.value?.engine === 'RPG Maker MV/MZ');
const pageLoading = computed(() => {
  if (viewLoading.value || busy.reload) return true;
  return ({
    library: busy.refresh,
    translations: false,
    data: false,
    saves: false,
    maps: false,
    runtime: false,
    live: busy.reload,
    ai: busy.models || busy.aiTest,
    settings: busy.update,
  })[currentView.value] || false;
});
const visibleNavItems = computed(() => navItems.filter((item) => {
  if (isRenPySelected.value && ['saves', 'maps', 'runtime'].includes(item.key)) return false;
  if (isRpgMakerSelected.value && item.key === 'live') return false;
  return true;
}));
const rpgMakerMissingTranslations = computed(() => translations.value.filter((item) => needsTranslationRepair(item)).length);
const namedAiConfigList = computed(() => Object.entries(aiNamedConfigs).map(([name, config]) => ({
  name,
  provider: config.provider || 'openai',
  providerLabel: ({ openai: 'OpenAI 兼容', anthropic: 'Anthropic', ollama: 'Ollama', accountbridge: '订阅账号' })[normalizeAiProvider(config.provider)] || 'OpenAI 兼容',
  model: config.model || '',
})).sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN')));
const viewMeta = computed(() => viewMetaMap[currentView.value] || viewMetaMap.library);
const filteredLibrary = computed(() => {
  const q = librarySearch.value.trim().toLowerCase();
  if (!q) return entries.value;
  return entries.value.filter((entry) => [entry.name, entry.path, entry.engine, entry.launcher_path, entry.note].some((value) => String(value || '').toLowerCase().includes(q)));
});
const translationCategories = computed(() => Array.from(new Set(translations.value.map((item) => item.category || item.file).filter(Boolean))));
function hasUsableTranslation(item) {
  const target = String(item?.target || '').trim();
  const source = String(item?.source || '').trim();
  return !!target && (target !== source || isAutoConfirmableSource(source));
}
function isAutoConfirmableSource(value) {
  const visible = String(value || '')
    .replace(/\\(?:[A-Za-z]+\[[^\]]*\]|[A-Za-z]+|.)/g, '')
    .replace(/\[[^\]]+\]|\{[^}]+\}/g, '')
    .trim();
  return !visible || !/\p{L}/u.test(visible);
}
function needsTranslationRepair(item) {
  return !!String(item?.source || '').trim() && !hasUsableTranslation(item);
}
const filteredTranslations = computed(() => {
  const q = translationSearch.value.trim().toLowerCase();
  return translations.value.filter((item) => {
    if (translationCategory.value && (item.category || item.file) !== translationCategory.value) return false;
    if (translationMissingOnly.value && !needsTranslationRepair(item)) return false;
    if (!q) return true;
    return [item.source, item.target, item.file, item.context].some((value) => String(value || '').toLowerCase().includes(q));
  });
});
const translationPageCount = computed(() => Math.max(1, Math.ceil(filteredTranslations.value.length / translationPageSize.value)));
const pagedTranslations = computed(() => {
  const start = (translationPage.value - 1) * translationPageSize.value;
  return filteredTranslations.value.slice(start, start + translationPageSize.value);
});
const translationRangeLabel = computed(() => {
  const total = filteredTranslations.value.length;
  if (!total) return '0 / 0';
  const start = (translationPage.value - 1) * translationPageSize.value + 1;
  const end = Math.min(start + translationPageSize.value - 1, total);
  return `${start}-${end} / ${total}`;
});
const translationProgressPercent = computed(() => translationProgress.total ? Math.min(100, Math.round((translationProgress.current / translationProgress.total) * 100)) : 0);
const selectedTranslation = computed(() => translations.value.find((item) => item.entry_id === selectedTranslationId.value) || null);
const dataCategories = computed(() => Array.from(new Set(dataRecords.value.map((item) => item.category || item.file).filter(Boolean))));
const filteredData = computed(() => {
  const q = dataSearch.value.trim().toLowerCase();
  return dataRecords.value.filter((item) => {
    if (dataCategory.value && (item.category || item.file) !== dataCategory.value) return false;
    if (!q) return true;
    return [item.object_label, item.object_id, item.label, item.value, item.file].some((value) => String(value || '').toLowerCase().includes(q));
  });
});
const selectedData = computed(() => dataRecords.value.find((item) => item.record_id === selectedDataId.value) || null);
const runtimeDataRows = computed(() => runtimeState.value?.[dataSection.value] || []);
const selectedRuntimeData = computed(() => runtimeDataRows.value.find((item) => Number(item.id) === Number(selectedRuntimeDataId.value)) || null);
const runtimeDataSectionLabel = computed(() => ({ items: '物品', armors: '装备', weapons: '武器', actors: '角色', switches: '开关', variables: '变量' })[dataSection.value] || '数据');
const mapCanvasWidth = computed(() => Math.max(1, Number(mapDetail.value?.record?.width || 1)) * mapTileSize);
const mapCanvasHeight = computed(() => Math.max(1, Number(mapDetail.value?.record?.height || 1)) * mapTileSize);
const selectedTileEvents = computed(() => {
  if (!selectedTile.value) return [];
  return (mapDetail.value?.events || []).filter((event) => event.x === selectedTile.value.x && event.y === selectedTile.value.y);
});
const liveRecentEvents = computed(() => [...(liveStatus.value?.recentEvents || [])].reverse());
const liveWorkerStateLabel = computed(() => ({ stopped: '已停止', waiting: '等待文本', translating: '翻译中', retrying: '失败重试', configuration_required: '需要配置 AI' })[liveStatus.value?.worker?.state] || '等待启动');
const liveBatchPlanLabel = computed(() => {
  const worker = liveDebug.value?.worker || liveStatus.value?.worker || {};
  if (worker.state !== 'translating') return liveWorkerStateLabel.value;
  const batches = Number(worker.activeBatches || 1);
  const configured = Number(worker.concurrency || 1);
  const size = Number(worker.batchSize || 0);
  return size ? `${batches}/${configured} 批运行 × ${size}` : '翻译中';
});
const liveDebugEvents = computed(() => [...(liveDebug.value?.debugEvents || [])].reverse());
const liveDebugHookEvents = computed(() => [...(liveDebug.value?.hookEvents || [])].reverse());
const liveDebugQueue = computed(() => {
  const pending = Array.isArray(liveDebug.value?.status?.pending_sources) ? liveDebug.value.status.pending_sources : [];
  const current = String(liveDebug.value?.worker?.lastSource || '');
  const sources = [...new Set([current, ...pending].filter(Boolean))];
  return sources.map((source) => ({ source, current: source === current && liveDebug.value?.worker?.state === 'translating' }));
});
const liveDebugCurrentText = computed(() => {
  const event = liveDebugHookEvents.value.find((item) => item?.source || item?.displayed || item?.target) || liveDebug.value?.status?.last_event || {};
  return event.target || event.displayed || event.source || '';
});
const liveDebugSelectedJson = computed(() => JSON.stringify(liveDebugSelected.value || liveDebug.value || {}, null, 2));

async function startTutorial() {
  translationDialogVisible.value = false;
  saveDataDialogVisible.value = false;
  tutorialCurrent.value = 0;
  currentView.value = 'library';
  await nextTick();
  tutorialOpen.value = true;
}
async function handleTutorialChange(index) {
  const step = tutorialSteps.value[index];
  if (!step?.view || currentView.value === step.view) return;
  currentView.value = step.view;
  await nextTick();
}
function toast(message, type = 'success') { ElMessage({ message, type, showClose: true, grouping: true }); }
async function api(path, options = {}) {
  const method = options.method || (options.body ? 'POST' : 'GET');
  const response = await fetch(apiBase.value + path, { method, headers: { 'Content-Type': 'application/json' }, body: options.body ? JSON.stringify(options.body) : undefined });
  const json = await response.json().catch(() => ({}));
  if (!response.ok || json.ok === false) throw new Error(json.error || ('HTTP ' + response.status));
  return json.data;
}
function requireGameSelected() { if (selectedEntry.value) return true; toast('请先在游戏库选择一个游戏', 'warning'); currentView.value = 'library'; return false; }
async function ensureProjectLoaded(force = false) {
  if (!requireGameSelected()) return false;
  const path = selectedEntry.value.path;
  if (!force && loadedProjectPath.value === path) return true;
  try {
    await api('/project/load', { body: { path } });
    loadedProjectPath.value = path;
    return true;
  } catch (error) {
    toast('载入游戏失败：' + error.message, 'error');
    return false;
  }
}
async function loadLibrary() {
  busy.refresh = true;
  try {
    const data = await api('/library');
    entries.value = data.entries || [];
    if (selectedPath.value && !entries.value.some((entry) => entry.path === selectedPath.value)) selectedPath.value = '';
    if (data.removed) toast(`已从游戏库移除 ${data.removed} 个不存在或无法启动的游戏路径。`, 'warning');
  } finally {
    busy.refresh = false;
  }
}
async function loadGameStatus() { try { gameStatus.value = await api('/game/status'); if (gameStatus.value.running && gameStatus.value.activePath) selectedPath.value = gameStatus.value.activePath; } catch (_) {} }
function clearProjectScopedState() {
  translations.value = [];
  selectedTranslationId.value = '';
  translationPage.value = 1;
  dataRecords.value = [];
  selectedDataId.value = '';
  saveSlots.value = [];
  selectedSavePath.value = '';
  saveSummary.value = null;
  savePreview.value = '';
  maps.value = [];
  selectedMapId.value = 0;
  mapDetail.value = null;
  selectedTile.value = null;
  hoveredTile.value = null;
  runtimeState.value = null;
  runtimeConnected.value = false;
  liveStatus.value = { running: false, connected: false, queue_count: 0, worker: { running: false, state: 'stopped', translated: 0, failures: 0, lastError: '' }, recentEvents: [] };
}
function onLibraryRowClick(row) { if (gameRunning.value && row.path !== gameStatus.value.activePath) return toast('游戏运行中，暂时不能切换其他游戏', 'warning'); selectedPath.value = row.path; }
function onLibraryRowDoubleClick(row) { onLibraryRowClick(row); if (row.path === selectedPath.value) launchSelected(); }
function libraryRowClassName({ row }) { return [row.path === selectedPath.value ? 'selected-row' : '', gameRunning.value && row.path !== gameStatus.value.activePath ? 'locked-row' : ''].filter(Boolean).join(' '); }
function engineTagType(engine) { if (String(engine || '').includes('RPG Maker')) return 'success'; if (String(engine || '').includes('Ren')) return 'warning'; return 'info'; }
function isMissingGameError(error) {
  const message = String(error?.message || error || '');
  return /找不到游戏启动文件|游戏库中找不到该游戏|未找到游戏启动文件|launcher|executable|not found/i.test(message);
}
async function addGame() {
  if (gameRunning.value) return toast('游戏运行中，不能添加或切换游戏', 'warning');
  const file = await window.rpgrtl.selectProject();
  if (!file) return;
  busy.add = true;
  try {
    await api('/library/add', { body: { path: file } });
    await loadLibrary();
    const added = entries.value.find((entry) => entry.launcher_path === file) || entries.value[0];
    if (added) selectedPath.value = added.path;
    toast('游戏已加入库');
  } catch (error) { toast(error.message, 'error'); } finally { busy.add = false; }
}
async function addGameFolder() {
  if (gameRunning.value) return toast('游戏运行中，不能添加或切换游戏', 'warning');
  const folder = await window.rpgrtl.selectGameFolder();
  if (!folder) return;
  busy.add = true;
  try {
    const data = await api('/library/add-folder', { body: { path: folder } });
    entries.value = data.entries || [];
    const imported = entries.value.find((entry) => String(entry.path || '').toLowerCase().startsWith(String(folder).toLowerCase()));
    if (imported) selectedPath.value = imported.path;
    toast(`文件夹导入完成：新增 ${data.added || 0} 个，更新 ${data.updated || 0} 个`);
  } catch (error) { toast(error.message, 'error'); } finally { busy.add = false; }
}
async function loadTranslationVersions() {
  if (!isRpgMakerSelected.value || !selectedEntry.value) { translationVersions.value = []; return; }
  const data = await api('/translations/versions');
  translationVersions.value = (data.versions || []).filter((item) => item.id !== 'original');
}
async function buildRpgMakerRuntimeAndLaunch(versionId = 'current', hotSwitch = false) {
  const body = { versionId, hotSwitch };
  if (versionId === 'current') body.entries = translations.value;
  const data = await api('/translations/runtime', { body });
  if (data.hotSwitched) {
    toast(versionId === 'original' ? '已热切换为原文，当前对话会自动刷新。' : '已热切换所选译文，当前对话会自动刷新。');
    return true;
  }
  if (!data.launcher) {
    toast('已准备翻译副本，但没有找到可启动文件，请手动打开副本目录。', 'warning');
    if (data.path) await window.rpgrtl.openPath(data.path);
    return false;
  }
  const launch = await api('/project/launch', { body: { launcherPath: data.launcher } });
  toast(`RPGMaker 译文副本已启动 PID ${launch.pid}`);
  await loadGameStatus();
  return true;
}
async function buildRenpyRuntimeAndLaunch() {
  const data = await api('/translations/runtime', { body: { entries: translations.value } });
  if (!data.launcher) {
    toast('已生成 RenPy 翻译副本，但没有找到可启动文件。', 'warning');
    if (data.runtimeRoot) await window.rpgrtl.openPath(data.runtimeRoot);
    return false;
  }
  const launch = await api('/project/launch', { body: { launcherPath: data.launcher } });
  toast(`RenPy 译文副本已启动 PID ${launch.pid}`);
  await loadGameStatus();
  return true;
}
async function launchTranslationVersion(versionId) {
  if (!requireGameSelected()) return;
  if (versionId === 'current') return startTranslation();
  busy.translation = true;
  try {
    await buildRpgMakerRuntimeAndLaunch(versionId, gameRunning.value);
    if (!gameRunning.value) await loadLibrary();
  } catch (error) { toast(error.message, 'error'); } finally { busy.translation = false; }
}
async function ensureRpgMakerReadyBeforeLaunch() {
  if (!isRpgMakerSelected.value) return true;
  if (!translations.value.length) await loadTranslations(true);
  if (rpgMakerMissingTranslations.value > 0) {
    currentView.value = 'translations';
    toast(`RPGMaker 请先完成翻译：还有 ${rpgMakerMissingTranslations.value} 条未译。完成后点击“开始翻译”，工具会生成运行时副本并启动。`, 'warning');
    return false;
  }
  return true;
}
async function launchSelected() {
  if (!selectedEntry.value) return toast('请先选择游戏', 'warning');
  const currentPath = selectedEntry.value.path;
  busy.launch = true;
  try {
    if (!(await ensureProjectLoaded())) return;
    if (isRpgMakerSelected.value) {
      if (!(await ensureRpgMakerReadyBeforeLaunch())) return;
      await buildRpgMakerRuntimeAndLaunch();
      await loadLibrary();
      selectedPath.value = currentPath;
      return;
    }
    const data = await api('/library/launch', { body: { path: currentPath } });
    toast('游戏已启动 PID ' + data.pid);
    await loadGameStatus();
    await loadLibrary();
    selectedPath.value = currentPath;
  } catch (error) {
    if (isMissingGameError(error)) await offerRemoveMissingGame(currentPath);
    else toast(error.message, 'error');
  } finally { busy.launch = false; }
}
async function openSelectedFolder() { if (!selectedEntry.value) return toast('请先选择游戏', 'warning'); await window.rpgrtl.openPath(selectedEntry.value.path); }
async function removeSelected() {
  if (!selectedEntry.value) return toast('请先选择游戏', 'warning');
  const target = selectedEntry.value;
  const confirmed = await ElMessageBox.confirm('确定移除【' + (target.name || '未命名') + '】吗？', '移除游戏', { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' }).catch(() => false);
  if (!confirmed) return;
  busy.remove = true;
  try {
    await api('/library/remove', { body: { path: target.path } });
    await loadLibrary();
    toast('已移除');
  } catch (error) { toast(error.message, 'error'); } finally { busy.remove = false; }
}
async function reloadCurrentView() { busy.reload = true; try { await loadViewData(currentView.value, true); } finally { busy.reload = false; } }
async function loadTranslations(refresh = false) {
  if (!(await ensureProjectLoaded(refresh))) return;
  busy.translation = true;
  try {
    const data = await api('/translations?all=1&refresh=' + (refresh ? 1 : 0));
    translations.value = data.entries || [];
    translationPage.value = 1;
    if (!translations.value.some((item) => item.entry_id === selectedTranslationId.value)) selectedTranslationId.value = translations.value[0]?.entry_id || '';
    syncTranslationDraft();
    await loadTranslationVersions();
  } finally { busy.translation = false; }
}
function translationCategoryLabel(category) {
  return ({ database: 'database · 数据库/物品', dialogue: 'dialogue · 对话', choice: 'choice · 选项' })[category] || category;
}
async function handleTranslationCommand(command) {
  if (command === 'import') return openImportPack();
  if (command === 'export') return openExportPack();
  if (command === 'runtime') return runtimePatch();
  if (command === 'replace-translated') return replaceTranslationMode('translated');
  if (command === 'replace-original') return replaceTranslationMode('original');
  if (command === 'apply') return applyTranslations();
}
function openTranslationDetail(row) { selectedTranslationId.value = row.entry_id; syncTranslationDraft(); translationDialogVisible.value = true; }
function syncTranslationDraft() { const item = selectedTranslation.value; translationDraft.source = item?.source || ''; translationDraft.target = item?.target || ''; translationMeta.value = item ? (item.file || '') + ' · ' + (item.context || item.category || '') + ' · ' + item.entry_id : ''; }
async function saveTranslationTarget() { if (!selectedTranslation.value) return; const payload = { ...selectedTranslation.value, target: translationDraft.target }; await api('/translations/save-targets', { body: { updates: [payload] } }); selectedTranslation.value.target = translationDraft.target; translationDialogVisible.value = false; toast('译文已保存'); }
function clampAiBatchSize() { return Math.max(1, Math.min(Number(aiForm.batchSize || 50), 200)); }
function clampAiConcurrency() { return Math.max(1, Math.min(Number(aiForm.concurrency || 1), 8)); }
function clampAiRequestInterval() { return Math.max(0, Math.min(Number(aiForm.requestIntervalMs || 0), 60000)); }
function clampAiRateLimitRetries() { return Math.max(0, Math.min(Number(aiForm.rateLimitRetries ?? 3), 10)); }
function clampAiRequestTimeoutSec() { return Math.max(30, Math.min(Number(aiForm.requestTimeoutSec || aiForm.timeout || 240), 900)); }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0)))); }
function isRateLimitError(error) { return /\b429\b|Too Many Requests|rate limit|rate_limit/i.test(String(error?.message || error || '')); }
function isTimeoutError(error) { return /timeout|timed out|read operation timed out|AI request timed out|504/i.test(String(error?.message || error || '')); }
function isTransientAiError(error) {
  const message = String(error?.message || error || '');
  return isRateLimitError(error) || isTimeoutError(error) || /\b(?:408|409|425|500|502|503|529)\b|temporar|overloaded|connection reset|network error|fetch failed|empty response/i.test(message);
}
function createRequestGate(intervalMs) {
  let nextAt = 0;
  return async () => {
    const interval = Math.max(0, Number(intervalMs || 0));
    if (!interval) return;
    const now = Date.now();
    const wait = Math.max(0, nextAt - now);
    nextAt = Math.max(now, nextAt) + interval;
    if (wait) await sleep(wait);
  };
}
function validateAiReady() {
  if (!aiForm.model) { toast('请先在 AI 设置里选择模型', 'warning'); currentView.value = 'ai'; return false; }
  if (aiForm.provider === 'accountbridge') return true;
  if (aiForm.provider !== 'ollama' && !aiForm.apiKey) { toast('请先在 AI 设置里填写 API Key', 'warning'); currentView.value = 'ai'; return false; }
  if (!aiForm.baseUrl) { toast('请先在 AI 设置里填写接口 URL', 'warning'); currentView.value = 'ai'; return false; }
  return true;
}
function resetTranslationProgress(total = 0, title = 'AI 批译进度') {
  Object.assign(translationProgress, { active: Boolean(total), title, message: total ? '准备发送翻译请求...' : '等待开始', current: 0, total, success: 0, failed: 0 });
}
function finishTranslationProgress(message) {
  translationProgress.active = false;
  translationProgress.message = message || translationProgress.message;
}
function aiEntryPayload(entry) {
  return { entry_id: entry.entry_id, source: entry.source, file: entry.file || '', context: entry.context || '', category: entry.category || '' };
}
function normalizeAiTranslationMap(translationsResult) {
  const map = new Map();
  if (Array.isArray(translationsResult)) {
    translationsResult.forEach((item, index) => {
      if (item && typeof item === 'object') map.set(String(item.entry_id || item.id || ''), String(item.target || item.translation || item.text || ''));
      else map.set(String(index), String(item || ''));
    });
  } else if (translationsResult && typeof translationsResult === 'object') {
    Object.entries(translationsResult).forEach(([key, value]) => map.set(String(key), String(value || '')));
  }
  return map;
}
function isUsefulAiTarget(entry, target) {
  const value = String(target || '').trim();
  return Boolean(value) && (value !== String(entry?.source || '').trim() || isAutoConfirmableSource(entry?.source));
}
function getAiTarget(map, entry, index) {
  const entryKey = String(entry?.entry_id || '');
  if (entryKey && map.has(entryKey)) return String(map.get(entryKey) || '');
  const indexKey = String(index);
  if (map.has(indexKey)) return String(map.get(indexKey) || '');
  return '';
}
async function callTranslateApi(payload, gate) {
  if (gate) await gate();
  return api('/ai/translate', { body: payload });
}
async function translateChunkOnce(chunk, options = {}) {
  if (options.shouldStop?.()) return new Map();
  const gate = options.gate;
  const data = await callTranslateApi({ ...aiForm, maxTokens: 8192, timeout: clampAiRequestTimeoutSec(), requestTimeoutSec: clampAiRequestTimeoutSec(), entries: chunk.map(aiEntryPayload), targetLang: aiForm.targetLang, from: 'auto', to: 'zh' }, gate);
  let map = normalizeAiTranslationMap(data.translations || []);
  let returned = chunk.filter((entry, index) => isUsefulAiTarget(entry, getAiTarget(map, entry, index))).length;
  if (!returned && chunk.length <= 50) {
    const fallback = await callTranslateApi({ ...aiForm, maxTokens: 8192, timeout: clampAiRequestTimeoutSec(), requestTimeoutSec: clampAiRequestTimeoutSec(), texts: chunk.map((entry) => entry.source), targetLang: aiForm.targetLang, from: 'auto', to: 'zh' }, gate);
    map = normalizeAiTranslationMap(fallback.translations || []);
  }
  return map;
}
async function translateChunkWithAI(chunk, options = {}) {
  const chunkIndex = Number(options.chunkIndex || 0);
  const maxRetries = clampAiRateLimitRetries();
  const minSplitSize = Math.max(1, Number(options.minSplitSize || 10));
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      const map = await translateChunkOnce(chunk, options);
      if (options.shouldStop?.()) return map;
      const missing = chunk.filter((entry, index) => !isUsefulAiTarget(entry, getAiTarget(map, entry, index)));
      // A long JSON response can be truncated by a gateway/model. Salvage the
      // valid part and re-request only the missing entries in smaller chunks.
      if (missing.length && chunk.length > minSplitSize) {
        const split = Math.max(minSplitSize, Math.ceil(missing.length / 2));
        const repaired = new Map();
        for (let i = 0; i < missing.length; i += split) {
          const part = await translateChunkWithAI(missing.slice(i, i + split), { ...options, chunkIndex, minSplitSize: Math.max(1, Math.floor(minSplitSize / 2)) });
          part.forEach((value, key) => repaired.set(key, value));
        }
        repaired.forEach((value, key) => map.set(key, value));
      }
      return map;
    } catch (error) {
      if (isTimeoutError(error) && chunk.length > minSplitSize) {
        const mid = Math.ceil(chunk.length / 2);
        translationProgress.message = `Batch ${chunkIndex + 1} timed out at ${chunk.length} entries; splitting into ${mid}+${chunk.length - mid} entries and retrying...`;
        const left = await translateChunkWithAI(chunk.slice(0, mid), { ...options, chunkIndex, minSplitSize });
        const right = await translateChunkWithAI(chunk.slice(mid), { ...options, chunkIndex, minSplitSize });
        return new Map([...left, ...right]);
      }
      if (!isTransientAiError(error) || attempt >= maxRetries) throw error;
      const waitMs = Math.min(120000, Math.max(clampAiRequestInterval() * 2, 1500) * Math.pow(2, attempt));
      translationProgress.message = `Batch ${chunkIndex + 1} temporary AI error; waiting ${Math.ceil(waitMs / 1000)}s before retry ${attempt + 1}/${maxRetries}...`;
      await sleep(waitMs);
    }
  }
  return new Map();
}
async function translateSelectedWithAI() {
  if (!selectedTranslation.value || !validateAiReady()) return;
  const entry = selectedTranslation.value;
  try {
    const map = await translateChunkWithAI([entry], { gate: createRequestGate(clampAiRequestInterval()), chunkIndex: 0 });
    translationDraft.target = getAiTarget(map, entry, 0);
    if (!translationDraft.target) toast('AI 没有返回有效译文', 'warning');
  } catch (error) { toast('AI 翻译失败：' + error.message, 'error'); }
}
async function applyTranslations() { if (!requireGameSelected()) return; const result = await api('/translations/apply', { body: { entries: translations.value } }); toast('永久写入完成：' + (result.changed || 0) + ' 处'); }
async function runtimePatch() { if (!requireGameSelected()) return; const data = await api('/translations/runtime', { body: { entries: translations.value } }); toast('补丁已生成：' + (data.changed || 0) + ' 处'); if (data.path) await window.rpgrtl.openPath(data.path); }
async function replaceTranslationMode(mode) { if (!requireGameSelected()) return; const data = await api('/translations/runtime', { body: { entries: translations.value, mode } }); if (data.path) await window.rpgrtl.openPath(data.path); toast(mode === 'original' ? '已生成原文替换补丁' : '已生成译文替换补丁'); }
function currentGameDialogLocation() {
  return {
    gamePath: selectedEntry.value?.path || '',
    launcherPath: selectedEntry.value?.launcher_path || '',
  };
}
function rpgMakerControlTokens(value) {
  return String(value || '').match(/\\(?:[A-Za-z]+\[[^\]]*\]|[A-Za-z]+|.)/g) || [];
}
function restoreLeadingRpgMakerControlTokens(entry, value) {
  const target = String(value || '').trim();
  if (!isRpgMakerSelected.value || !target) return target;
  const source = String(entry?.source || '');
  const expected = rpgMakerControlTokens(source);
  const actual = rpgMakerControlTokens(target);
  // Colour/font escape sequences are commonly at the very beginning of a
  // dialogue line. Models occasionally omit them even when asked to preserve
  // them; restoring a source-only prefix is safe and keeps the line renderable.
  const prefix = expected.join('');
  if (expected.length && !actual.length && prefix && source.startsWith(prefix)) return prefix + target;
  return target;
}
function hasPreservedRpgMakerControlTokens(entry, target) {
  if (!isRpgMakerSelected.value) return true;
  const expected = rpgMakerControlTokens(entry?.source);
  return expected.join('\u0000') === rpgMakerControlTokens(target).join('\u0000');
}
async function openImportPack() { if (!requireGameSelected()) return; const path = await window.rpgrtl.openPack(currentGameDialogLocation()); if (!path) return; const data = await api('/translations/import', { body: { path } }); toast('导入完成：匹配 ' + data.matched + '/' + data.imported); await loadTranslations(true); }
async function openExportPack() { if (!requireGameSelected()) return; const path = await window.rpgrtl.savePack(currentGameDialogLocation()); if (!path) return; const data = await api('/translations/export', { body: { path } }); await loadTranslationVersions(); toast(data.version ? `翻译包已导出，并已保存版本 ${data.version.label}` : '翻译包已导出'); }
async function runLimited(items, limit, worker, shouldStop = () => false) {
  const results = [];
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      if (shouldStop()) break;
      const index = cursor;
      cursor += 1;
      results[index] = await worker(items[index], index);
    }
  });
  await Promise.all(runners);
  return results;
}
async function translateBatch(options = {}) {
  const manageBusy = options.manageBusy !== false;
  if (!requireGameSelected()) return 0;
  if (!validateAiReady()) return 0;
  if (manageBusy && busy.translation) return 0;
  const batchSize = clampAiBatchSize();
  const concurrency = clampAiConcurrency();
  const requestIntervalMs = clampAiRequestInterval();
  const maxRetries = clampAiRateLimitRetries();
  const scope = options.scope || 'filtered';
  const sourceList = scope === 'all' ? translations.value : filteredTranslations.value;
  const allTargets = sourceList.filter((item) => needsTranslationRepair(item));
  const maxCount = Math.max(0, Number(options.maxCount || 0));
  const selectedTargets = maxCount ? allTargets.slice(0, maxCount) : allTargets;
  const knownBySource = new Map();
  translations.value.forEach((entry) => {
    if (hasUsableTranslation(entry)) knownBySource.set(String(entry.source || ''), String(entry.target || '').trim());
  });
  const cacheFillUpdates = [];
  const autoConfirmedUpdates = [];
  const aiTargets = [];
  selectedTargets.forEach((entry) => {
    if (isAutoConfirmableSource(entry.source)) {
      entry.target = String(entry.source || '');
      autoConfirmedUpdates.push({ ...entry, target: entry.target });
      return;
    }
    const cachedTarget = knownBySource.get(String(entry.source || ''));
    if (cachedTarget) {
      entry.target = cachedTarget;
      cacheFillUpdates.push({ ...entry, target: cachedTarget });
    } else {
      aiTargets.push(entry);
    }
  });
  const immediateUpdates = [...cacheFillUpdates, ...autoConfirmedUpdates];
  if (immediateUpdates.length) {
    await api('/translations/save-targets', { body: { updates: immediateUpdates } });
  }
  // RPG Maker databases repeat the same label/text in many records.  Keep
  // one representative per source for the API and fan its result back out to
  // all matching records, avoiding duplicate prompts even across concurrency.
  const sourceGroups = new Map();
  aiTargets.forEach((entry) => {
    const key = String(entry.source || '');
    const group = sourceGroups.get(key) || [];
    group.push(entry);
    sourceGroups.set(key, group);
  });
  const targets = Array.from(sourceGroups.values()).map((group) => group[0]);
  if (!targets.length) {
    aiPreview.value = immediateUpdates.length ? `已保存 ${cacheFillUpdates.length} 条缓存命中与 ${autoConfirmedUpdates.length} 条无需翻译文本，无需请求 AI。` : '没有找到未翻译文本。';
    resetTranslationProgress(0);
    toast(immediateUpdates.length ? `已保存 ${immediateUpdates.length} 条无需 AI 的条目` : '没有找到未翻译文本', immediateUpdates.length ? 'success' : 'warning');
    return immediateUpdates.length;
  }
  if (manageBusy) busy.translation = true;
  translationStopRequested.value = false;
  resetTranslationProgress(aiTargets.length, `AI 批译：${aiTargets.length} 条文本 / ${targets.length} 条唯一原文，按来源文件分批，单批 ${batchSize}，并发 ${concurrency}`);
  aiPreview.value = `当前范围：${scope === 'all' ? '全部项目' : '当前筛选'}；真正待修复 ${selectedTargets.length} 条，缓存补齐 ${cacheFillUpdates.length} 条，无需翻译 ${autoConfirmedUpdates.length} 条，提交 AI ${aiTargets.length} 条。请求会按来源文件与原始顺序分批；单批 ${batchSize}，并发 ${concurrency}，请求间隔 ${requestIntervalMs}ms，429重试 ${maxRetries} 次...`;
  const chunks = [];
  const targetsByFile = new Map();
  targets.forEach((entry) => {
    const file = String(entry.file || '(unknown source file)');
    const group = targetsByFile.get(file) || [];
    group.push(entry);
    targetsByFile.set(file, group);
  });
  targetsByFile.forEach((fileTargets, file) => {
    for (let i = 0; i < fileTargets.length; i += batchSize) chunks.push({ file, entries: fileTargets.slice(i, i + batchSize) });
  });
  const failureMessages = [];
  const requestGate = createRequestGate(requestIntervalMs);
  let completedChunks = 0;
  let savedCount = immediateUpdates.length;
  let saveQueue = Promise.resolve();
  const saveChunkUpdates = (chunkUpdates) => {
    if (!chunkUpdates.length) return Promise.resolve();
    const task = saveQueue.then(async () => {
      translationProgress.message = `正在保存已完成的 ${chunkUpdates.length} 条译文...`;
      const result = await api('/translations/save-targets', { body: { updates: chunkUpdates, allowPartial: true } });
      savedCount += Number(result.changed || chunkUpdates.length);
      const rejected = Array.isArray(result.rejected) ? result.rejected : [];
      if (rejected.length) {
        translationProgress.failed += rejected.length;
        failureMessages.push(...rejected.map((item) => `保存跳过：${item.reason || item.entry_id}`));
      }
    });
    saveQueue = task.catch(() => {});
    return task;
  };
  try {
    await runLimited(chunks, concurrency, async (chunkPlan, chunkIndex) => {
      const chunk = chunkPlan.entries;
      translationProgress.message = `正在处理 ${chunkPlan.file} 的第 ${chunkIndex + 1}/${chunks.length} 批（${chunk.length} 条）...`;
      try {
        const map = await translateChunkWithAI(chunk, { gate: requestGate, chunkIndex, shouldStop: () => translationStopRequested.value });
        let chunkSuccess = 0;
        let chunkAffected = 0;
        const chunkUpdates = [];
        chunk.forEach((entry, index) => {
          const target = restoreLeadingRpgMakerControlTokens(entry, getAiTarget(map, entry, index));
          if (isUsefulAiTarget(entry, target) && hasPreservedRpgMakerControlTokens(entry, target)) {
            const group = sourceGroups.get(String(entry.source || '')) || [entry];
            group.forEach((related) => {
              related.target = target;
              chunkUpdates.push({ ...related, target });
            });
            chunkSuccess += group.length;
          }
          chunkAffected += (sourceGroups.get(String(entry.source || '')) || [entry]).length;
        });
        translationProgress.success += chunkSuccess;
        translationProgress.failed += Math.max(0, chunkAffected - chunkSuccess);
        // Persist each completed chunk.  A bad AI answer in one chunk must not
        // discard thousands of already valid translations when export follows.
        await saveChunkUpdates(chunkUpdates);
      } catch (error) {
        translationProgress.failed += chunk.reduce((sum, entry) => sum + (sourceGroups.get(String(entry.source || '')) || [entry]).length, 0);
        translationProgress.message = `Batch ${chunkIndex + 1} failed: ${error.message}. If it still times out, set batch size to 30-80 or timeout to 300-600s.`;
        failureMessages.push(`Batch ${chunkIndex + 1}: ${String(error?.message || error || 'unknown error')}`);
        // Keep other workers running; one failed request must not abort the batch.
      } finally {
        completedChunks += 1;
        translationProgress.current += chunk.reduce((sum, entry) => sum + (sourceGroups.get(String(entry.source || '')) || [entry]).length, 0);
        if (translationProgress.active) {
          translationProgress.message = `已完成 ${completedChunks}/${chunks.length} 个批次，成功 ${translationProgress.success} 条，失败 ${translationProgress.failed} 条。`;
        }
      }
    }, () => translationStopRequested.value);
    await saveQueue;
    if (savedCount > immediateUpdates.length) await loadTranslations(false);
    aiPreview.value = targets.map((entry, index) => (index + 1) + '. ' + entry.source + '\\n=> ' + (entry.target || '未返回有效译文')).join('\\n\\n');
    const totalWritten = savedCount;
    const message = translationStopRequested.value
      ? `已停止，已安全保存 ${totalWritten} 条译文；下次可继续翻译剩余内容。`
      : (totalWritten ? `已修复 ${totalWritten}/${selectedTargets.length} 条（AI 请求 ${targets.length} 条唯一原文）` : 'AI 返回了结果，但没有可写入的有效译文；请检查提示词/模型输出。');
    finishTranslationProgress(message);
    toast(message, totalWritten ? 'success' : 'warning');
    return totalWritten;
  } catch (error) {
    finishTranslationProgress('批译失败：' + error.message);
    toast('批译失败：' + error.message, 'error');
    return 0;
  } finally {
    if (manageBusy) busy.translation = false;
  }
}
function stopTranslationBatch() {
  if (!busy.translation) return;
  translationStopRequested.value = true;
  translationProgress.message = '已请求停止：不会启动新批次，正在保存已完成批次的译文...';
  toast('正在停止；已完成的译文会保留并保存。', 'warning');
}
async function repairMissingTranslations() {
  translationMissingOnly.value = true;
  translationPage.value = 1;
  await nextTick();
  return translateBatch({ scope: 'filtered' });
}
async function loadData(refresh = false) {
  if (!(await ensureProjectLoaded(refresh))) return;
  busy.data = true;
  try {
    const data = await api('/data?limit=5000&refresh=' + (refresh ? 1 : 0));
    dataRecords.value = data.records || [];
    if (!dataRecords.value.some((item) => item.record_id === selectedDataId.value)) selectedDataId.value = dataRecords.value[0]?.record_id || '';
    syncDataDraft();
    await loadRuntimeState(true);
  } finally { busy.data = false; }
}
async function startTranslation() {
  if (!requireGameSelected()) return;
  if (!translations.value.length) await loadTranslations(true);
  if (!translations.value.length) return;
  busy.translation = true;
  try {
    let previousRemaining = Number.POSITIVE_INFINITY;
    for (let pass = 0; pass < 200; pass += 1) {
      const remaining = translations.value.filter((item) => needsTranslationRepair(item)).length;
      if (!remaining || remaining >= previousRemaining) break;
      previousRemaining = remaining;
      const translated = await translateBatch({ manageBusy: false, scope: 'all' });
      if (!translated) break;
    }
    const remaining = translations.value.filter((item) => needsTranslationRepair(item)).length;
    if (isRpgMakerSelected.value) {
      if (remaining) {
        toast(`RPGMaker 仍有 ${remaining} 条未译，未启动游戏。请检查 AI 设置或手动补译后再点开始翻译。`, 'warning');
        return;
      }
      await buildRpgMakerRuntimeAndLaunch();
      toast('RPGMaker 翻译完成，已生成运行时副本并启动游戏。');
      return;
    }
    await buildRenpyRuntimeAndLaunch();
    toast('RenPy 翻译完成，已生成独立运行副本并启动；原游戏保持原文。');
  } catch (error) {
    toast(error.message, 'error');
  } finally { busy.translation = false; }
}
function dataRowClassName({ row }) { return row.record_id === selectedDataId.value ? 'selected-row' : ''; }
function selectDataRecord(row) { selectedDataId.value = row.record_id; syncDataDraft(); }
function syncDataDraft() { const item = selectedData.value; dataDraft.label = item?.label || ''; dataDraft.value = item?.value || ''; dataMeta.value = item ? ((item.object_label || item.object_id || '') + ' · ' + (item.file || '') + ' · ' + item.record_id) : ''; }
async function saveDataValue() { if (!selectedData.value) return; const data = await api('/data/update', { body: { record_id: selectedData.value.record_id, value: dataDraft.value } }); selectedData.value.value = data.record?.value || dataDraft.value; toast('数据已写入'); }
function selectRuntimeDataRow(row) {
  selectedRuntimeDataId.value = row.id;
  runtimeDataForm.count = row.count ?? 0; runtimeDataForm.level = row.level ?? 1; runtimeDataForm.hp = row.hp ?? 0; runtimeDataForm.mp = row.mp ?? 0; runtimeDataForm.tp = row.tp ?? 0; runtimeDataForm.switchValue = Boolean(row.value); runtimeDataForm.variableValue = typeof row.value === 'string' ? row.value : JSON.stringify(row.value ?? '');
}
function parseRuntimeValue(value) { const text = String(value ?? '').trim(); if (/^-?\d+(\.\d+)?$/.test(text)) return Number(text); if (text === 'true') return true; if (text === 'false') return false; try { return JSON.parse(text); } catch (_) { return text; } }
async function saveRuntimeDataRow() {
  const row = selectedRuntimeData.value; if (!row) return;
  let payload = {};
  if (['items', 'armors', 'weapons'].includes(dataSection.value)) payload = { [dataSection.value]: { [row.id]: Number(runtimeDataForm.count || 0) } };
  else if (dataSection.value === 'actors') payload = { actors: { [row.id]: { level: Number(runtimeDataForm.level || 1), hp: Number(runtimeDataForm.hp || 0), mp: Number(runtimeDataForm.mp || 0), tp: Number(runtimeDataForm.tp || 0) } } };
  else if (dataSection.value === 'switches') payload = { switches: { [row.id]: runtimeDataForm.switchValue } };
  else if (dataSection.value === 'variables') payload = { variables: { [row.id]: parseRuntimeValue(runtimeDataForm.variableValue) } };
  if (await setRuntimePayload(payload)) { selectRuntimeDataRow((runtimeState.value?.[dataSection.value] || []).find((item) => Number(item.id) === Number(row.id)) || row); toast(`${runtimeDataSectionLabel.value}已更新`); }
}
async function loadSaveSlots() {
  if (!(await ensureProjectLoaded())) return;
  busy.saves = true;
  try {
    const data = await api('/saves/slots');
    saveSlots.value = data.slots || [];
    if (!saveSlots.value.some((item) => item.path === selectedSavePath.value)) selectedSavePath.value = saveSlots.value[0]?.path || '';
    if (selectedSavePath.value) await loadSave(selectedSavePath.value);
  } finally { busy.saves = false; }
}
async function loadSave(path) { selectedSavePath.value = path; const data = await api('/saves/load', { body: { path: path } }); saveSummary.value = data.summary || null; savePreview.value = JSON.stringify(data.payload || {}, null, 2); if (data.summary?.gold !== undefined) saveForm.gold = data.summary.gold; }
function saveFileName(path) { return String(path || '').split(/[\\/]/).pop() || '存档'; }
async function writeSave() { if (!requireGameSelected() || !selectedSavePath.value) return; await api('/saves/write', { body: { path: selectedSavePath.value } }); toast('存档已写回'); }
async function setSaveGold() { const data = await api('/saves/mutate', { body: { op: 'gold', value: saveForm.gold } }); saveSummary.value = data.summary || saveSummary.value; savePreview.value = JSON.stringify(data.payload || {}, null, 2); }
async function setSaveItem() { const data = await api('/saves/mutate', { body: { op: 'item', kind: 'items', itemId: saveForm.itemId, value: saveForm.itemCount } }); saveSummary.value = data.summary || saveSummary.value; savePreview.value = JSON.stringify(data.payload || {}, null, 2); }
async function setActorLevel() { const data = await api('/saves/mutate', { body: { op: 'actorLevel', actorId: saveForm.actorId, value: saveForm.actorLevel } }); saveSummary.value = data.summary || saveSummary.value; savePreview.value = JSON.stringify(data.payload || {}, null, 2); }
async function setSwitch() { const data = await api('/saves/mutate', { body: { op: 'switch', switchId: saveForm.switchId, value: saveForm.switchValue } }); saveSummary.value = data.summary || saveSummary.value; savePreview.value = JSON.stringify(data.payload || {}, null, 2); }
async function setVariable() { const data = await api('/saves/mutate', { body: { op: 'variable', variableId: saveForm.variableId, value: saveForm.variableValue } }); saveSummary.value = data.summary || saveSummary.value; savePreview.value = JSON.stringify(data.payload || {}, null, 2); }
async function loadMaps() {
  if (!(await ensureProjectLoaded())) return;
  busy.maps = true;
  try {
    const data = await api('/maps');
    maps.value = data.maps || [];
    await loadRuntimeState(true);
    const liveMapId = Number(runtimeState.value?.map?.id || 0);
    if (liveMapId && maps.value.some((item) => item.map_id === liveMapId)) selectedMapId.value = liveMapId;
    if (!maps.value.some((item) => item.map_id === selectedMapId.value)) selectedMapId.value = maps.value[0]?.map_id || 0;
    if (selectedMapId.value) await loadMapDetail(selectedMapId.value);
  } finally { busy.maps = false; }
}
async function loadMapDetail(id) { selectedMapId.value = Number(id); selectedTile.value = null; hoveredTile.value = null; mapDetail.value = await api('/maps/detail?id=' + id); await nextTick(); drawMap(); }
function drawMap() {
  const canvas = mapCanvas.value;
  if (!canvas || !mapDetail.value) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#091321';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const tile of mapDetail.value.tiles || []) {
    ctx.fillStyle = tile.passable ? '#163039' : '#352332';
    ctx.fillRect(tile.x * mapTileSize + 1, tile.y * mapTileSize + 1, mapTileSize - 2, mapTileSize - 2);
  }
  ctx.strokeStyle = 'rgba(148,163,184,.12)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += mapTileSize) { ctx.beginPath(); ctx.moveTo(x + .5, 0); ctx.lineTo(x + .5, canvas.height); ctx.stroke(); }
  for (let y = 0; y <= canvas.height; y += mapTileSize) { ctx.beginPath(); ctx.moveTo(0, y + .5); ctx.lineTo(canvas.width, y + .5); ctx.stroke(); }
  for (const event of mapDetail.value.events || []) {
    ctx.fillStyle = '#a78bfa';
    ctx.fillRect(event.x * mapTileSize + 7, event.y * mapTileSize + 7, mapTileSize - 14, mapTileSize - 14);
  }
  if (selectedTile.value) { ctx.strokeStyle = '#f4c55c'; ctx.lineWidth = 3; ctx.strokeRect(selectedTile.value.x * mapTileSize + 2, selectedTile.value.y * mapTileSize + 2, mapTileSize - 4, mapTileSize - 4); }
  if (hoveredTile.value) { ctx.fillStyle = 'rgba(255,255,255,.24)'; ctx.fillRect(hoveredTile.value.x * mapTileSize + 1, hoveredTile.value.y * mapTileSize + 1, mapTileSize - 2, mapTileSize - 2); }
  const player = runtimeState.value?.map;
  if (player && Number(player.id) === selectedMapId.value) {
    const cx = (Number(player.x) + .5) * mapTileSize; const cy = (Number(player.y) + .5) * mapTileSize;
    ctx.fillStyle = '#4dd6c8'; ctx.beginPath(); ctx.moveTo(cx, cy - 10); ctx.lineTo(cx + 9, cy); ctx.lineTo(cx, cy + 10); ctx.lineTo(cx - 9, cy); ctx.closePath(); ctx.fill();
  }
}
function mapTileFromEvent(event) {
  const rect = mapCanvas.value?.getBoundingClientRect();
  if (!rect) return null;
  const x = Math.floor((event.clientX - rect.left) * mapCanvas.value.width / rect.width / mapTileSize);
  const y = Math.floor((event.clientY - rect.top) * mapCanvas.value.height / rect.height / mapTileSize);
  if (x < 0 || y < 0 || x >= Number(mapDetail.value?.record?.width || 0) || y >= Number(mapDetail.value?.record?.height || 0)) return null;
  return { x, y };
}
function startMapDrag(event) { mapDragging.value = true; mapDragState.x = event.clientX; mapDragState.y = event.clientY; mapDragState.left = mapViewport.value.scrollLeft; mapDragState.top = mapViewport.value.scrollTop; mapDragState.moved = false; }
function moveMapPointer(event) {
  if (mapDragging.value) {
    const dx = event.clientX - mapDragState.x; const dy = event.clientY - mapDragState.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) mapDragState.moved = true;
    mapViewport.value.scrollLeft = mapDragState.left - dx; mapViewport.value.scrollTop = mapDragState.top - dy;
  } else { hoveredTile.value = mapTileFromEvent(event); drawMap(); }
}
function endMapDrag() { mapDragging.value = false; setTimeout(() => { mapDragState.moved = false; }, 0); }
function leaveMapPointer() { mapDragging.value = false; hoveredTile.value = null; drawMap(); }
function selectMapTile(event) { if (mapDragState.moved) return; selectedTile.value = mapTileFromEvent(event); drawMap(); }
function conditionSwitchId(condition) { const match = String(condition || '').match(/开关\s+(\d+)/); return match ? Number(match[1]) : null; }
function runtimeSwitchValue(id) { return Boolean((runtimeState.value?.switches || []).find((item) => Number(item.id) === Number(id))?.value); }
async function toggleRuntimeSwitch(id) { await setRuntimePayload({ switches: { [id]: !runtimeSwitchValue(id) } }); }
async function handleEventCommand(command) { const match = String(command || '').match(/传送[：:]\s*地图\s*(\d+)\s*\((\d+)\s*,\s*(\d+)\)/); if (!match) return; await loadMapDetail(Number(match[1])); selectedTile.value = { x: Number(match[2]), y: Number(match[3]) }; await nextTick(); centerMapTile(selectedTile.value.x, selectedTile.value.y); drawMap(); }
function centerMapTile(x, y) { if (!mapViewport.value) return; mapViewport.value.scrollTo({ left: x * mapTileSize - mapViewport.value.clientWidth / 2, top: y * mapTileSize - mapViewport.value.clientHeight / 2, behavior: 'smooth' }); }

async function loadRuntimeState(silent = false) {
  if (!(await ensureProjectLoaded())) return;
  try {
    const state = await api('/runtime/state');
    if (state.connected === false) { runtimeConnected.value = false; if (!silent) toast(state.error || '游戏尚未连接', 'warning'); return; }
    runtimeState.value = state; runtimeConnected.value = true;
    if (!silent) syncRuntimeForm();
    if (currentView.value === 'maps') drawMap();
  } catch (error) {
    runtimeConnected.value = false;
    if (!silent) toast(error.message, 'warning');
  }
}
function syncRuntimeForm() {
  const state = runtimeState.value; if (!state) return;
  runtimeForm.gold = state.gold ?? 0; runtimeForm.through = Boolean(state.map?.through); runtimeForm.clickTeleport = Boolean(state.options?.clickTeleport); runtimeForm.autoSaveMinutes = Number(state.options?.autoSaveInterval || 0) / 60; runtimeForm.x = state.map?.x ?? 0; runtimeForm.y = state.map?.y ?? 0; runtimeForm.gameSpeed = state.options?.gameSpeed ?? 1; runtimeForm.battleSpeed = state.options?.battleSpeed ?? 1; runtimeForm.moveSpeedIncrease = state.options?.moveSpeedIncrease ?? 0; runtimeForm.autoBattle = Boolean(state.options?.autoBattle); runtimeForm.godMode = Boolean(state.options?.godMode);
  if (!runtimeForm.actorId && state.actors?.length) runtimeForm.actorId = state.actors[0].id;
  syncRuntimeActorForm();
}
function syncRuntimeActorForm() { const actor = (runtimeState.value?.actors || []).find((item) => Number(item.id) === Number(runtimeForm.actorId)); if (!actor) return; runtimeForm.hp = actor.hp ?? 0; runtimeForm.mp = actor.mp ?? 0; runtimeForm.tp = actor.tp ?? 0; const locks = runtimeState.value?.locks?.[String(actor.id)] || {}; runtimeForm.lockHp = locks.hp !== undefined; runtimeForm.lockMp = locks.mp !== undefined; runtimeForm.lockTp = locks.tp !== undefined; }
async function setRuntimePayload(payload) { try { runtimeState.value = await api('/runtime/set', { body: payload }); runtimeConnected.value = true; if (currentView.value === 'maps') drawMap(); return true; } catch (error) { runtimeConnected.value = false; toast(error.message, 'warning'); return false; } }
async function setRuntimeGold() { await setRuntimePayload({ gold: Number(runtimeForm.gold || 0) }); }
async function setRuntimeThrough() { await setRuntimePayload({ player: { through: runtimeForm.through } }); }
async function setRuntimeOptions() { await setRuntimePayload({ options: { clickTeleport: runtimeForm.clickTeleport, autoSaveInterval: Math.max(0, Number(runtimeForm.autoSaveMinutes || 0)) * 60 } }); }
async function teleportToTile(x, y) { const ok = await setRuntimePayload({ player: { teleport: { x: Number(x), y: Number(y) } } }); if (ok) toast(`已传送到 (${Number(x)}, ${Number(y)})`); }
async function setRuntimeActor() { if (!runtimeForm.actorId) return; await setRuntimePayload({ actors: { [runtimeForm.actorId]: { hp: Number(runtimeForm.hp || 0), mp: Number(runtimeForm.mp || 0), tp: Number(runtimeForm.tp || 0) } } }); }
async function setRuntimeLocks() { if (!runtimeForm.actorId) return; const locks = {}; if (runtimeForm.lockHp) locks.hp = Number(runtimeForm.hp || 0); if (runtimeForm.lockMp) locks.mp = Number(runtimeForm.mp || 0); if (runtimeForm.lockTp) locks.tp = Number(runtimeForm.tp || 0); await setRuntimePayload({ locks: { [runtimeForm.actorId]: locks } }); }
async function setBattleResult(result) { if (await setRuntimePayload({ battle: result })) toast(({ win: '已触发战斗胜利', lose: '已触发战斗失败', escape: '已触发战斗逃跑' })[result]); }
async function setRuntimeAdvancedOptions() { await setRuntimePayload({ options: { gameSpeed: Number(runtimeForm.gameSpeed || 1), battleSpeed: Number(runtimeForm.battleSpeed || 1), moveSpeedIncrease: Number(runtimeForm.moveSpeedIncrease || 0), autoBattle: runtimeForm.autoBattle, godMode: runtimeForm.godMode } }); }
async function loadLiveStatus(silent = false) { if (!(await ensureProjectLoaded())) return; try { liveStatus.value = await api('/live/status'); } catch (error) { if (!silent) toast(error.message, 'warning'); } }
async function startLive() {
  if (!(await ensureProjectLoaded())) return false;
  if (isRpgMakerSelected.value) {
    toast('RPGMaker 当前使用“先翻译、再启动译文副本”的流程，不再开放实时翻译入口。', 'warning');
    return false;
  }
  if (isRenPySelected.value && !gameRunning.value) {
    toast('请先启动 RenPy 游戏，再启动实时翻译', 'warning');
    return false;
  }
  liveStatus.value = await api('/live/start', { body: { autoTranslate: true } });
  toast('RenPy 实时翻译已启动');
  return true;
}
async function stopLive() { if (!(await ensureProjectLoaded())) return; liveStatus.value = await api('/live/stop', { body: {} }); toast('实时翻译已停止'); }
async function refreshLive() { if (!(await ensureProjectLoaded())) return; await api('/live/refresh', { body: {} }); await loadLiveStatus(true); }
async function mergeLive() { if (!(await ensureProjectLoaded())) return; await api('/live/merge', { body: { source: liveSource.value, target: liveTarget.value } }); await loadLiveStatus(true); toast('已写入实时翻译表并通知游戏刷新'); }
async function openLiveDebug() {
  if (!(await ensureProjectLoaded())) return;
  liveDebugVisible.value = true;
  await loadLiveDebug(false, true);
  stopLiveDebugPolling();
  liveDebugTimer = setInterval(() => loadLiveDebug(true, true), 1000);
}
function stopLiveDebugPolling() {
  if (liveDebugTimer) clearInterval(liveDebugTimer);
  liveDebugTimer = null;
}
async function loadLiveDebug(silent = false, autostart = false) {
  if (!(await ensureProjectLoaded())) return;
  try {
    liveDebug.value = await api('/live/debug?limit=240' + (autostart ? '&autostart=1' : ''));
    liveStatus.value = liveDebug.value.status || liveStatus.value;
    if (!liveDebugSelected.value && liveDebug.value.debugEvents?.length) liveDebugSelected.value = liveDebug.value.debugEvents[liveDebug.value.debugEvents.length - 1];
  } catch (error) {
    if (!silent) toast(error.message, 'warning');
  }
}
async function startLiveFromDebug() {
  const ok = await startLive();
  if (ok) await loadLiveDebug(true, true);
}
async function clearLiveDebug() {
  if (!(await ensureProjectLoaded())) return;
  liveDebugSelected.value = null;
  liveDebug.value = await api('/live/debug?limit=240&clear=1');
}
async function forceLiveHello() {
  if (!(await ensureProjectLoaded())) return;
  await api('/live/force-text', { body: { text: 'hello' } });
  await loadLiveDebug(true);
  toast("已向当前 Ren'Py 文本框注入 hello");
}
function liveDebugStageType(stage) {
  return ({ capture: 'info', api: 'warning', inject: 'success', filter: 'warning', error: 'danger' })[String(stage || '')] || 'info';
}
function liveDebugStageLabel(stage) {
  return ({ capture: '捕获文本', api: '调用 AI', inject: '写入游戏', filter: '校验译文', error: '自动重试', worker: '翻译服务' })[String(stage || '')] || '系统';
}
function liveDebugSummary(row) {
  const payload = row?.payload || {};
  const preview = (values) => (Array.isArray(values) ? values.filter(Boolean).slice(0, 2).map((item) => String(item).replace(/\s+/g, ' ').slice(0, 90)).join('；') : '');
  if (row?.title === 'candidate_batch') return `从游戏捕获 ${payload.raw_count || 0} 条文本，脚本顺序补入 ${payload.seeded_count || 0} 条，本轮准备翻译 ${payload.candidate_count || 0} 条；延迟重试 ${payload.deferred_count || 0} 条。`;
  if (row?.title === 'parallel_batch_wave') return `${payload.phase === 'repair' ? '批量补救' : '主批处理'}：${payload.candidate_count || 0} 条文本，拆为 ${payload.batch_count || 0} 批，每批最多 ${payload.batch_size || 0} 条，同时最多 ${payload.concurrency || 1} 批；预读窗口上限 ${payload.window_size || 300} 条。`;
  if (row?.title === 'parallel_repair_wave') return `主批有 ${payload.candidate_count || 0} 条未返回，改为 ${payload.batch_count || 0} 个小批（每批 ${payload.batch_size || 0} 条），仍按 ${payload.concurrency || 1} 批并发重试。`;
  if (row?.title === 'urgent_current_retry') return '当前屏幕文本未在批量响应中返回，正在立即单独补救；后续文本仍在后台批量翻译。';
  if (row?.title === 'urgent_current_retry_failed') return '当前屏幕文本的即时补救请求失败，已在极短延迟后重新排队。';
  if (row?.title === 'submit_request') return `正在向 AI 提交 ${payload.count || 0} 条文本。首条：${preview(payload.texts) || '无'}。模型返回前会一直保持当前游戏画面，不会跳到下一句。`;
  if (row?.title === 'timeout_split_retry') return `AI 请求超时，已将 ${payload.count || 0} 条文本自动拆为 ${payload.left || 0} 条和 ${payload.right || 0} 条继续重试。`;
  if (row?.title === 'response_content' || row?.title === 'parsed_translations') return `AI 已返回并解析 ${Array.isArray(payload.translations) ? payload.translations.length : 0} 条译文。示例：${preview(payload.translations) || '无'}。`;
  if (row?.title === 'merge_live_translations') return `已把 ${payload.count || 0} 条译文写入游戏，当前显示的文本会自动刷新。示例：${Object.values(payload.translations || {}).slice(0, 2).map((item) => String(item).slice(0, 90)).join('；') || '无'}。`;
  if (row?.title === 'translation_rejected') return `${payload.count || 0} 条译文格式不完整或未翻译，已自动改为小批重试。`;
  if (row?.title === 'force_text') return `已请求替换当前文本为“${payload.text || 'hello'}”，只会作用于点击时正在显示的这句。`;
  if (payload.error) return `发生错误：${payload.error}`;
  if (payload.sources) return `正在处理 ${payload.sources.length} 条文本。`;
  if (payload.text) return String(payload.text);
  return '翻译服务状态已更新。';
}
function normalizeAiProvider(provider) { const value = String(provider || '').toLowerCase(); if (value.includes('accountbridge') || value.includes('account-bridge') || value.includes('localagent') || value.includes('local-agent') || value.includes('订阅账号') || value.includes('本地agent') || value.includes('本地 agent')) return 'accountbridge'; if (value.includes('ollama') || value.includes('本地模型')) return 'ollama'; if (value.includes('anthropic') || value.includes('claude')) return 'anthropic'; return 'openai'; }
function defaultAiBaseUrl(provider) { return provider === 'anthropic' ? 'https://api.anthropic.com' : provider === 'ollama' ? 'http://127.0.0.1:11434' : provider === 'accountbridge' ? '' : 'https://api.openai.com/v1'; }
function snapshotAiProfile(provider = aiForm.provider) { aiProfiles[provider] = { apiKey: aiForm.apiKey, baseUrl: aiForm.baseUrl, model: aiForm.model, localAgentPath: aiForm.localAgentPath, accountProvider: aiForm.accountProvider, models: [...aiModels.value], batchSize: aiForm.batchSize, concurrency: aiForm.concurrency, requestIntervalMs: aiForm.requestIntervalMs, rateLimitRetries: aiForm.rateLimitRetries, requestTimeoutSec: aiForm.requestTimeoutSec, targetLang: aiForm.targetLang }; }
function currentAiConfigSnapshot() {
  return { ...aiForm, availableModels: [...aiModels.value], models: [...aiModels.value] };
}
function applyAiConfig(config = {}) {
  const provider = normalizeAiProvider(config.provider || aiForm.provider);
  aiForm.provider = provider;
  aiForm.apiKey = ['ollama', 'accountbridge'].includes(provider) ? '' : (config.apiKey || '');
  aiForm.baseUrl = config.baseUrl || defaultAiBaseUrl(provider);
  aiForm.model = config.model || '';
  aiForm.localAgentPath = config.localAgentPath || aiForm.localAgentPath || '';
  aiForm.accountProvider = config.accountProvider || aiForm.accountProvider || 'local-agent-auto';
  aiForm.batchSize = Math.max(1, Math.min(Number(config.batchSize || aiForm.batchSize || 50), 200));
  aiForm.concurrency = Math.max(1, Math.min(Number(config.concurrency || config.threads || aiForm.concurrency || 1), 8));
  aiForm.requestIntervalMs = Math.max(0, Math.min(Number(config.requestIntervalMs ?? config.rateLimitMs ?? aiForm.requestIntervalMs ?? 1200), 60000));
  aiForm.rateLimitRetries = Math.max(0, Math.min(Number(config.rateLimitRetries ?? config.retry429 ?? aiForm.rateLimitRetries ?? 3), 10));
  aiForm.requestTimeoutSec = Math.max(30, Math.min(Number(config.requestTimeoutSec ?? config.timeout ?? aiForm.requestTimeoutSec ?? 240), 900));
  aiForm.targetLang = config.targetLang || aiForm.targetLang || '简体中文';
  aiModels.value = Array.isArray(config.availableModels) ? config.availableModels : (Array.isArray(config.models) ? config.models : []);
  previousAiProvider = provider;
  snapshotAiProfile(provider);
}
async function persistAiSettings(showToast = false) {
  snapshotAiProfile();
  await api('/settings', { body: { ai: { ...aiForm, availableModels: [...aiModels.value] }, ai_profiles: { ...aiProfiles }, ai_named_configs: { ...aiNamedConfigs } } });
  if (showToast) toast('AI 设置与命名配置已保存');
}
function scheduleAiAutosave() {
  if (!aiSettingsReady || suppressAiAutosave) return;
  if (aiAutosaveTimer) clearTimeout(aiAutosaveTimer);
  aiAutosaveTimer = setTimeout(async () => {
    aiAutosaveTimer = null;
    try {
      await persistAiSettings(false);
    } catch (error) {
      toast('AI 设置自动保存失败：' + error.message, 'warning');
    }
  }, 500);
}
async function saveNamedAiConfig() {
  const name = aiConfigName.value.trim() || selectedAiConfigName.value || `${({ openai: 'OpenAI', anthropic: 'Anthropic', ollama: 'Ollama', accountbridge: '订阅账号' })[aiForm.provider] || 'AI'} 配置 ${namedAiConfigList.value.length + 1}`;
  aiNamedConfigs[name] = currentAiConfigSnapshot();
  selectedAiConfigName.value = name;
  aiConfigName.value = name;
  await persistAiSettings(false);
  toast(`已保存 AI 配置：${name}`);
}
function loadNamedAiConfig(name) {
  if (!name || !aiNamedConfigs[name]) return;
  suppressAiAutosave = true;
  selectedAiConfigName.value = name;
  aiConfigName.value = name;
  applyAiConfig(aiNamedConfigs[name]);
  suppressAiAutosave = false;
  scheduleAiAutosave();
  toast(`已打开 AI 配置：${name}`);
}
async function deleteNamedAiConfig() {
  const name = selectedAiConfigName.value;
  if (!name || !aiNamedConfigs[name]) return;
  delete aiNamedConfigs[name];
  selectedAiConfigName.value = '';
  if (aiConfigName.value === name) aiConfigName.value = '';
  await persistAiSettings(false);
  toast(`已删除 AI 配置：${name}`);
}
async function onAiProviderChange(provider) {
  snapshotAiProfile(previousAiProvider);
  const profile = aiProfiles[provider] || {};
  aiForm.apiKey = ['ollama', 'accountbridge'].includes(provider) ? '' : (profile.apiKey || '');
  aiForm.baseUrl = profile.baseUrl || defaultAiBaseUrl(provider);
  aiForm.model = profile.model || '';
  aiForm.localAgentPath = profile.localAgentPath || aiForm.localAgentPath || '';
  aiForm.accountProvider = profile.accountProvider || aiForm.accountProvider || 'local-agent-auto';
  aiModels.value = Array.isArray(profile.models) ? profile.models : [];
  previousAiProvider = provider;
  if (provider === 'ollama') await fetchAiModels(true);
  scheduleAiAutosave();
}
async function onAccountProviderChange() {
  // Account selection always means the local subscription bridge. This
  // prevents a saved OpenAI-compatible profile from issuing a remote
  // /models request with an empty or stale bearer token.
  aiForm.provider = 'accountbridge';
  aiModels.value = [];
  aiForm.model = '';
  await fetchAiModels(true);
  scheduleAiAutosave();
}
async function startAccountLogin() {
  if (!window.rpgrtl?.startAccountLogin) return toast('当前应用版本不支持账号登录，请重新打包桌面端。', 'error');
  try {
    // Logging into a subscription account is an explicit mode switch. Do not
    // let a previously loaded OpenAI profile send /models with its stale URL
    // and empty bearer token before the bridge request is made.
    aiForm.provider = 'accountbridge';
    aiForm.apiKey = '';
    aiForm.baseUrl = '';
    previousAiProvider = 'accountbridge';
    await persistAiSettings(false);
    const result = await window.rpgrtl.startAccountLogin({ provider: aiForm.accountProvider });
    if (result.mode === 'google-browser-oauth' || result.mode === 'gemini-cli-oauth') {
      accountLoginStatus.value = '已打开浏览器：请完成 Google 授权。成功后浏览器会显示 localhost 授权成功页，本页会自动检测。';
      toast('已打开 Gemini 浏览器授权。');
      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        try {
          const status = await window.rpgrtl.getAccountStatus?.({ provider: 'gemini-cli' });
          if (status?.authenticated) {
            accountLoginStatus.value = '已检测到 Gemini 登录态，可以读取模型并开始翻译。';
            toast('Gemini 账号登录成功。');
            await fetchAiModels(true);
            return;
          }
        } catch (_) { /* Keep waiting for the CLI-owned OAuth flow. */ }
        if (attempts < 100) setTimeout(poll, 3000);
        else accountLoginStatus.value = '仍未检测到 Gemini 登录态。请确认浏览器授权页面已经显示成功。';
      };
      setTimeout(poll, 1500);
    }
  } catch (error) { toast(`打开账号登录失败：${error.message}`, 'error'); }
}
async function loadAiSettings(showToast = true) {
  try {
    const data = await api('/settings');
    suppressAiAutosave = true;
    Object.assign(aiProfiles, data.ai_profiles || {});
    Object.keys(aiNamedConfigs).forEach((key) => delete aiNamedConfigs[key]);
    Object.assign(aiNamedConfigs, data.ai_named_configs || data.aiConfigs || {});
    const ai = data.ai || data;
    applyAiConfig({ ...ai, availableModels: Array.isArray(ai.availableModels) ? ai.availableModels : (Array.isArray(aiProfiles[normalizeAiProvider(ai.provider)]?.models) ? aiProfiles[normalizeAiProvider(ai.provider)].models : []) });
    if (aiForm.provider === 'ollama') await fetchAiModels(true);
    aiSettingsReady = true;
    suppressAiAutosave = false;
    if (showToast) toast('已读取本机 AI 设置');
  } catch (error) { suppressAiAutosave = false; toast('读取设置失败：' + error.message, 'error'); }
}
async function saveAiSettings(showToast = true) {
  snapshotAiProfile();
  await api('/settings', { body: { ai: { ...aiForm, availableModels: [...aiModels.value] }, ai_profiles: { ...aiProfiles }, ai_named_configs: { ...aiNamedConfigs } } });
  if (showToast) toast('AI 设置已保存到本机缓存');
}
async function fetchAiModels(silent = false) {
  const accountBridge = aiForm.provider === 'accountbridge';
  if (!accountBridge && (!aiForm.baseUrl || (aiForm.provider !== 'ollama' && !aiForm.apiKey))) { if (!silent) toast('当前是 API 接口模式，请先填写接口 URL 和 API Key；若要使用账号订阅，请切换“订阅账号登录（OAuth 桥接）”。', 'warning'); return; }
  busy.models = true;
  try {
    const data = await api('/ai/models', { body: { provider: accountBridge ? 'accountbridge' : aiForm.provider, baseUrl: aiForm.baseUrl, apiKey: accountBridge ? '' : aiForm.apiKey, model: aiForm.model, localAgentPath: aiForm.localAgentPath, accountProvider: aiForm.accountProvider } });
    aiModels.value = data.models || [];
    if (!aiModels.value.includes(aiForm.model)) aiForm.model = aiModels.value[0] || '';
    snapshotAiProfile();
    await saveAiSettings(false);
    if (!silent) toast(`已获取 ${aiModels.value.length} 个模型`);
  } catch (error) { if (!silent) toast((accountBridge ? '读取账号模型失败：' : aiForm.provider === 'ollama' ? '未检测到 Ollama：' : '获取模型失败：') + error.message, 'error'); } finally { busy.models = false; }
}
async function testAi() {
  const source = aiTestSource.value.trim();
  if (!source) return toast('请输入测试原文', 'warning');
  if (!aiForm.model) return toast('请先选择模型', 'warning');
  if (!['ollama', 'accountbridge'].includes(aiForm.provider) && !aiForm.apiKey) return toast('请先填写 API Key', 'warning');
  busy.aiTest = true; aiTestResult.value = '';
  try { const data = await api('/ai/translate', { body: { ...aiForm, timeout: clampAiRequestTimeoutSec(), requestTimeoutSec: clampAiRequestTimeoutSec(), texts: [source], targetLang: aiForm.targetLang, from: 'auto', to: 'zh' } }); aiTestResult.value = data.translations?.[0] || ''; if (!aiTestResult.value) toast('接口没有返回译文', 'warning'); else toast('测试翻译成功'); }
  catch (error) { aiTestResult.value = '测试失败：' + error.message; toast(error.message, 'error'); }
  finally { busy.aiTest = false; }
}
async function testAiBatch() {
  if (!aiForm.model) return toast('请先选择模型', 'warning');
  if (!['ollama', 'accountbridge'].includes(aiForm.provider) && !aiForm.apiKey) return toast('请先填写 API Key', 'warning');
  busy.aiTest = true;
  try {
    const samples = ['[mc], nice to see you here.', 'I did not expect you to come back so soon.', 'The hallway is quieter than usual tonight.', 'Can we talk somewhere nobody will hear us?', 'Of course. Follow me to the library.', 'The door is locked from the inside.', 'I found this letter under the old desk.', 'It mentions a promise we made years ago.', 'That cannot be true... can it?', 'Please do not look at me like that.', 'We still have time to fix this.', 'Then tell me everything you know.', 'The rain began before either of us spoke again.', 'I will wait here until you are ready.', 'Do you want to save your game?', 'Yes, save the current progress.', 'No, continue without saving.', 'A new message appears on the screen.', 'Objective updated: find the hidden key.', 'The key should be somewhere near the garden.', 'I hear footsteps behind the door.', 'Do not turn around.', 'Why not?', 'Because someone is standing right behind you.'];
    const sampleEntries = samples.map((source, index) => ({ entry_id: `renpy_dialogue_${index + 1}`, source, category: 'renpy_dialogue', context: `say_${index + 1}` }));
    const batchSize = clampAiBatchSize();
    const concurrency = clampAiConcurrency();
    const chunks = [];
    for (let index = 0; index < sampleEntries.length; index += batchSize) chunks.push(sampleEntries.slice(index, index + batchSize));
    const gate = createRequestGate(clampAiRequestInterval());
    const map = new Map();
    await runLimited(chunks, concurrency, async (chunk, chunkIndex) => {
      const result = await translateChunkWithAI(chunk, { gate, chunkIndex, minSplitSize: 1 });
      result.forEach((target, key) => map.set(key, target));
    });
    aiPreview.value = `Ren'Py 连续对话批量模拟：${sampleEntries.length} 条；单批 ${batchSize} 条；并发 ${concurrency} 批。\\n\\n` + samples.map((source, index) => `${index + 1}. ${source}\\n=> ${getAiTarget(map, sampleEntries[index], index) || '未返回译文'}`).join('\\n\\n');
    toast('批量测试完成');
  } catch (error) { aiPreview.value = '批量测试失败：' + error.message; toast(error.message, 'error'); }
  finally { busy.aiTest = false; }
}
async function openExternal(url) { await window.rpgrtl.openExternal(url); }
async function checkForUpdates(showResult = true) {
  busy.update = true;
  try {
    const data = await window.rpgrtl.checkUpdate();
    Object.assign(updateInfo, { ...data, checked: true });
    if (!showResult) return;
    if (!data.hasUpdate) return toast('当前已是最新版本');
    const open = await ElMessageBox.confirm(`发现新版本 ${data.latestVersion}，是否前往下载？`, '发现更新', { confirmButtonText: '前往下载', cancelButtonText: '稍后', type: 'success' }).catch(() => false);
    if (open) await openExternal(releasesUrl);
  } catch (error) { if (showResult) toast('检查更新失败：' + error.message, 'error'); } finally { busy.update = false; }
}
async function sendFeedback() {
  const subject = encodeURIComponent(feedback.subject || 'RPGRenPyLocalizer 使用建议');
  const body = encodeURIComponent(feedback.body || '');
  await openExternal(`mailto:lyb82ndkf@gmail.com?subject=${subject}&body=${body}`);
}
async function loadViewData(view, refresh = false) {
  if (view === 'settings') return;
  if (view === 'library') { if (refresh) await loadLibrary(); return; }
  if (view === 'ai') { if (refresh) await loadAiSettings(); return; }
  if (!requireGameSelected()) return;
  const key = `${selectedPath.value}:${view}`;
  if (!refresh && loadedViewKeys.has(key)) return;
  if (view === 'translations') await loadTranslations(refresh);
  else if (view === 'data') await loadData(refresh);
  else if (view === 'saves') await loadSaveSlots();
  else if (view === 'maps') await loadMaps();
  else if (view === 'runtime') await loadRuntimeState(false);
  else if (view === 'live' && !isRpgMakerSelected.value) await loadLiveStatus();
  loadedViewKeys.add(key);
}
watch(currentView, async (view) => {
  if (runtimePollTimer) { clearInterval(runtimePollTimer); runtimePollTimer = null; }
  viewLoading.value = true;
  try {
    await loadViewData(view);
    if ((['maps', 'runtime'].includes(view) || (view === 'data' && dataSection.value !== 'database')) && !isRenPySelected.value) runtimePollTimer = setInterval(() => loadRuntimeState(true), 2000);
    else if (view === 'live' && !isRpgMakerSelected.value) runtimePollTimer = setInterval(() => loadLiveStatus(true), 1000);
  } finally {
    viewLoading.value = false;
  }
});
watch(selectedPath, async () => {
  viewLoading.value = true;
  loadedProjectPath.value = '';
  loadedViewKeys.clear();
  clearProjectScopedState();
  try {
    if (isRenPySelected.value && ['saves', 'maps', 'runtime'].includes(currentView.value)) currentView.value = 'translations';
    if (isRpgMakerSelected.value && currentView.value === 'live') currentView.value = 'translations';
    if (currentView.value !== 'library' && selectedEntry.value) await loadViewData(currentView.value);
  } finally {
    viewLoading.value = false;
  }
});
watch(visibleNavItems, (items) => {
  if (!items.some((item) => item.key === currentView.value)) currentView.value = 'translations';
});
watch([translationSearch, translationCategory, translationMissingOnly], () => { translationPage.value = 1; });
watch(translationPageSize, () => { translationPage.value = 1; });
watch(translationPageCount, (count) => { if (translationPage.value > count) translationPage.value = count; });
watch(selectedTranslationId, syncTranslationDraft);
watch(selectedDataId, syncDataDraft);
watch(
  () => [
    aiForm.provider,
    aiForm.apiKey,
    aiForm.baseUrl,
    aiForm.model,
    aiForm.localAgentPath,
    aiForm.accountProvider,
    aiForm.batchSize,
    aiForm.concurrency,
    aiForm.requestIntervalMs,
    aiForm.rateLimitRetries,
    aiForm.requestTimeoutSec,
    aiForm.targetLang,
    aiModels.value.join('\u0001'),
    selectedAiConfigName.value,
  ],
  scheduleAiAutosave,
);
watch(dataSection, async (section) => {
  selectedRuntimeDataId.value = null;
  if (runtimePollTimer) { clearInterval(runtimePollTimer); runtimePollTimer = null; }
  if (section !== 'database' && currentView.value === 'data' && !isRenPySelected.value) {
    await loadRuntimeState(true);
    const row = runtimeState.value?.[section]?.[0];
    if (row) selectRuntimeDataRow(row);
    runtimePollTimer = setInterval(() => loadRuntimeState(true), 2000);
  }
});
watch(mapDetail, () => nextTick(drawMap));
async function init() {
  const params = new URLSearchParams(window.location.search);
  const port = params.get('port') || await window.rpgrtl.backendPort();
  apiBase.value = 'http://127.0.0.1:' + port;
  try {
    const health = await api('/health');
    backendReady.value = true;
    backendLabel.value = 'Python ' + health.python;
    await loadLibrary();
    await loadAiSettings(false);
    await loadGameStatus();
    appVersion.value = await window.rpgrtl.appVersion();
    checkForUpdates(false);
    gameStatusTimer = setInterval(loadGameStatus, 1200);
  } catch (error) {
    backendError.value = true;
    backendLabel.value = '后端异常';
    toast(error.message, 'error');
  }
}
onMounted(init);
onBeforeUnmount(() => { if (runtimePollTimer) clearInterval(runtimePollTimer); if (gameStatusTimer) clearInterval(gameStatusTimer); if (aiAutosaveTimer) clearTimeout(aiAutosaveTimer); stopLiveDebugPolling(); });
</script>

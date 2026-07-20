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

      <div class="game-card" v-if="selectedEntry">
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

      <div class="game-card empty" v-else>
        <div class="game-card-label">当前游戏</div>
        <div class="game-card-name">未选择</div>
        <div class="game-card-path">先添加或选择一个游戏。</div>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in visibleNavItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: currentView === item.key }"
          @click="currentView = item.key"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <el-button type="primary" class="add-button" :icon="Plus" @click="addGame" :loading="busy.add" :disabled="gameRunning">添加游戏</el-button>
      <button class="update-indicator" :class="{ available: updateInfo.hasUpdate }" @click="currentView = 'settings'">
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
          <el-button v-if="currentView === 'translations'" size="small" type="primary" :disabled="!selectedEntry" @click="loadTranslations(true)">载入文本资源</el-button>
          <el-button v-else-if="currentView === 'data'" size="small" :disabled="!selectedEntry" @click="loadData(true)">载入数据</el-button>
          <el-button v-else-if="currentView === 'saves'" size="small" :disabled="!selectedEntry" @click="loadSaveSlots">载入存档</el-button>
          <el-button v-else-if="currentView === 'maps'" size="small" :disabled="!selectedEntry" @click="loadMaps">载入地图</el-button>
        </div>
      </div>

      <section v-if="currentView === 'library'" class="view-shell">
        <el-card shadow="never" class="section-card library-card">
          <template #header>
            <div class="card-head">
              <strong>全部游戏</strong>
              <div class="card-head-right">
                <el-input v-model="librarySearch" class="search-inline" size="small" placeholder="搜索游戏名、路径、引擎" clearable :prefix-icon="Search" />
                <el-button size="small" :icon="Refresh" @click="loadLibrary" :loading="busy.refresh">刷新库</el-button>
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

      <section v-else-if="currentView === 'translations'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>翻译工作台</strong>
              <div class="card-head-right wrap">
                <el-input v-model="translationSearch" class="search-inline" size="small" placeholder="搜索原文 / 译文 / 文件" clearable :prefix-icon="Search" />
                <el-select v-model="translationCategory" size="small" class="mini-select" clearable placeholder="分类">
                  <el-option label="全部分类" value="" />
                  <el-option v-for="item in translationCategories" :key="item" :label="item" :value="item" />
                </el-select>
                <el-switch v-model="translationMissingOnly" size="small" active-text="仅未译" />
                <el-button size="small" :icon="Refresh" @click="loadTranslations(true)" :loading="busy.translation">刷新</el-button>
                <el-button size="small" @click="openImportPack">导入</el-button>
                <el-button size="small" @click="openExportPack">导出</el-button>
                <el-button size="small" type="danger" plain @click="applyTranslations">永久写入</el-button>
                <el-button size="small" type="primary" @click="runtimePatch">运行时补丁</el-button>
              </div>
            </div>
          </template>

          <div class="translation-list-layout">
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

      <section v-else-if="currentView === 'data'" class="view-shell feature-shell">
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
                <div v-if="!runtimeConnected" class="runtime-required"><strong>需要连接运行中的游戏</strong><span>先在实时修改页安装组件并启动游戏，连接后这里会显示当前游戏数据。</span><el-button type="primary" @click="currentView = 'runtime'">前往实时修改</el-button></div>
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
                  <div class="info-box"><span>开关数</span><div>{{ saveSummary.switch_count ?? 0 }}</div></div>
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
                  <section class="save-tool-group">
                    <strong>开关与变量</strong>
                    <div class="compact-action three"><el-input v-model="saveForm.switchId" type="number" placeholder="开关ID" /><el-select v-model="saveForm.switchValue"><el-option label="ON" :value="true" /><el-option label="OFF" :value="false" /></el-select><el-button @click="setSwitch">设置</el-button></div>
                    <div class="compact-action three"><el-input v-model="saveForm.variableId" type="number" placeholder="变量ID" /><el-input v-model="saveForm.variableValue" placeholder="变量值" /><el-button @click="setVariable">设置</el-button></div>
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
                <el-button size="small" @click="installBridge">安装实时组件</el-button>
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
                <div class="battle-actions"><el-button type="success" @click="setBattleResult('win')">直接胜利</el-button><el-button type="warning" @click="setBattleResult('escape')">立即逃跑</el-button><el-button type="danger" @click="setBattleResult('lose')">直接失败</el-button></div>
                <div class="form-row"><span>游戏速度</span><el-input v-model="runtimeForm.gameSpeed" type="number" /><el-button @click="setRuntimeAdvancedOptions">应用</el-button></div>
                <div class="form-row"><span>战斗速度</span><el-input v-model="runtimeForm.battleSpeed" type="number" /><el-button @click="setRuntimeAdvancedOptions">应用</el-button></div>
                <div class="form-row"><span>自动战斗</span><el-switch v-model="runtimeForm.autoBattle" @change="setRuntimeAdvancedOptions" /></div>
                <div class="form-row"><span>上帝模式</span><el-switch v-model="runtimeForm.godMode" @change="setRuntimeAdvancedOptions" /></div>
              </section>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'live'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>实时 Hook 翻译</strong>
              <div class="card-head-right wrap">
                <el-button size="small" @click="installBridge">安装 {{ isRenPySelected ? 'Ren’Py Hook' : '实时组件' }}</el-button>
                <el-button size="small" type="primary" @click="startLive">启动</el-button>
                <el-button size="small" @click="stopLive">停止</el-button>
                <el-button size="small" @click="refreshLive">刷新状态</el-button>
              </div>
            </div>
          </template>

          <div class="live-page">
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
                <div class="mini-info">启动后会自动安装对应桥接，并使用 AI 设置中的接口实时翻译。游戏已运行时需重启一次才能加载新 Hook。</div>
              </div>
            </div>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'ai'" class="view-shell feature-shell">
        <el-card shadow="never" class="section-card full-card">
          <template #header>
            <div class="card-head">
              <strong>AI 翻译</strong>
              <div class="card-head-right wrap">
                <el-button size="small" @click="loadAiSettings">读取设置</el-button>
                <el-button size="small" type="primary" @click="saveAiSettings">保存设置</el-button>
                <el-button size="small" @click="testAi">测试翻译</el-button>
              </div>
            </div>
          </template>

          <div class="split-layout ai-layout">
            <div class="left-pane">
              <div class="editor-stack">
                <div class="editor-title">渠道配置</div>
                <el-select v-model="aiForm.provider" placeholder="接口类型" @change="onAiProviderChange">
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Anthropic" value="anthropic" />
                  <el-option label="Ollama 本地模型" value="ollama" />
                </el-select>
                <el-input v-model="aiForm.baseUrl" :placeholder="aiForm.provider === 'ollama' ? 'http://127.0.0.1:11434' : '接口 URL'" />
                <el-input v-if="aiForm.provider !== 'ollama'" v-model="aiForm.apiKey" type="password" show-password placeholder="API Key" />
                <div v-else class="ollama-note"><el-tag type="success" effect="plain">无需 API Key</el-tag><span>切换到 Ollama 时会自动检测本机已经安装的模型。</span></div>
                <div class="model-picker"><el-select v-model="aiForm.model" filterable allow-create placeholder="选择模型"><el-option v-for="model in aiModels" :key="model" :label="model" :value="model" /></el-select><el-button :loading="busy.models" @click="fetchAiModels(false)">{{ aiForm.provider === 'ollama' ? '检测本地模型' : '获取模型' }}</el-button></div>
                <div class="mini-form-grid">
                  <el-input v-model="aiForm.batchSize" type="number" placeholder="批量数量" />
                  <el-input v-model="aiForm.targetLang" placeholder="目标语言" />
                </div>
                <div class="mini-info">URL、API Key 和所选模型会保存在当前 Windows 用户配置目录，与原 Python 版本共用缓存。</div>
              </div>
            </div>
            <div class="right-pane">
              <el-tabs v-model="aiToolTab" class="ai-tool-tabs">
                <el-tab-pane label="测试翻译" name="test"><div class="editor-stack ai-tool-pane"><el-input v-model="aiTestSource" type="textarea" :rows="5" placeholder="输入一段要测试的原文" /><div class="detail-actions"><el-button type="primary" :loading="busy.aiTest" @click="testAi">开始测试</el-button></div><el-input v-model="aiTestResult" type="textarea" :rows="6" readonly placeholder="测试译文会显示在这里" /></div></el-tab-pane>
                <el-tab-pane label="批量翻译" name="batch"><div class="editor-stack ai-tool-pane"><el-input v-model="aiPreview" type="textarea" :rows="10" readonly placeholder="批量翻译结果" /><div class="detail-actions"><el-button type="primary" @click="translateBatch">翻译当前未完成文本</el-button></div></div></el-tab-pane>
              </el-tabs>
            </div>
          </div>
        </el-card>
      </section>

      <section v-else-if="currentView === 'settings'" class="view-shell feature-shell">
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
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Delete, FolderOpened, MagicStick, MapLocation, Notebook, Plus, Refresh, Search, Setting, VideoPlay, Connection, Reading, Coin, EditPen } from '@element-plus/icons-vue';
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
  translations: { eyebrow: 'Translation', title: '翻译工作台', subtitle: '提取、编辑、导入导出、永久写入和运行时补丁。' },
  data: { eyebrow: 'Data', title: '数据修改', subtitle: '角色、物品、技能、敌人等数据库字段直接编辑。' },
  saves: { eyebrow: 'Save', title: '存档修改', subtitle: '直接读取存档槽并修改金钱、物品、等级、开关和变量。' },
  maps: { eyebrow: 'Map', title: '地图查看', subtitle: '查看地图、事件和基础布局。' },
  runtime: { eyebrow: 'Runtime', title: '游戏实时修改', subtitle: '读取当前玩家状态，并实时修改数值、移动与游戏选项。' },
  live: { eyebrow: 'Live', title: '实时翻译', subtitle: '安装桥接、启动服务、写入实时译文。' },
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
const gameStatus = ref({ running: false, activePath: '', games: [] });
let gameStatusTimer = null;
const loadedViewKeys = new Set();

const translations = ref([]);
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
const runtimeForm = reactive({ gold: 0, actorId: null, hp: 0, mp: 0, tp: 0, lockHp: false, lockMp: false, lockTp: false, through: false, clickTeleport: false, autoSaveMinutes: 0, x: 0, y: 0, gameSpeed: 1, battleSpeed: 1, autoBattle: false, godMode: false });
let runtimePollTimer = null;

const liveStatus = ref({ running: false, connected: false, queue_count: 0, worker: { running: false, state: 'stopped', translated: 0, failures: 0, lastError: '' }, recentEvents: [] });
const liveSource = ref('');
const liveTarget = ref('');

const aiForm = reactive({ provider: 'openai', apiKey: '', baseUrl: 'https://api.openai.com/v1', model: '', batchSize: 20, targetLang: '简体中文' });
const aiModels = ref([]);
const aiProfiles = reactive({});
let previousAiProvider = 'openai';
const aiToolTab = ref('test');
const aiTestSource = ref('Hello, welcome to the game.');
const aiTestResult = ref('');
const aiPreview = ref('');
const appVersion = ref('');
const updateInfo = reactive({ checked: false, hasUpdate: false, latestVersion: '' });
const feedback = reactive({ subject: '', body: '' });
const githubUrl = 'https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer';
const releasesUrl = githubUrl + '/releases';

const selectedEntry = computed(() => entries.value.find((entry) => entry.path === selectedPath.value) || null);
const gameRunning = computed(() => Boolean(gameStatus.value.running));
const isRenPySelected = computed(() => selectedEntry.value?.engine === "Ren'Py");
const visibleNavItems = computed(() => navItems.filter((item) => !isRenPySelected.value || !['saves', 'maps', 'runtime'].includes(item.key)));
const viewMeta = computed(() => viewMetaMap[currentView.value] || viewMetaMap.library);
const filteredLibrary = computed(() => {
  const q = librarySearch.value.trim().toLowerCase();
  if (!q) return entries.value;
  return entries.value.filter((entry) => [entry.name, entry.path, entry.engine, entry.launcher_path, entry.note].some((value) => String(value || '').toLowerCase().includes(q)));
});
const translationCategories = computed(() => Array.from(new Set(translations.value.map((item) => item.category || item.file).filter(Boolean))));
const filteredTranslations = computed(() => {
  const q = translationSearch.value.trim().toLowerCase();
  return translations.value.filter((item) => {
    if (translationCategory.value && (item.category || item.file) !== translationCategory.value) return false;
    if (translationMissingOnly.value && item.target) return false;
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
  const data = await api('/library');
  entries.value = data.entries || [];
  if (!entries.value.some((entry) => entry.path === selectedPath.value)) selectedPath.value = entries.value[0]?.path || '';
}
async function loadGameStatus() { try { gameStatus.value = await api('/game/status'); if (gameStatus.value.running && gameStatus.value.activePath) selectedPath.value = gameStatus.value.activePath; } catch (_) {} }
function onLibraryRowClick(row) { if (gameRunning.value && row.path !== gameStatus.value.activePath) return toast('游戏运行中，暂时不能切换其他游戏', 'warning'); selectedPath.value = row.path; }
function onLibraryRowDoubleClick(row) { onLibraryRowClick(row); if (row.path === selectedPath.value) launchSelected(); }
function libraryRowClassName({ row }) { return [row.path === selectedPath.value ? 'selected-row' : '', gameRunning.value && row.path !== gameStatus.value.activePath ? 'locked-row' : ''].filter(Boolean).join(' '); }
function engineTagType(engine) { if (String(engine || '').includes('RPG Maker')) return 'success'; if (String(engine || '').includes('Ren')) return 'warning'; return 'info'; }
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
async function launchSelected() {
  if (!selectedEntry.value) return toast('请先选择游戏', 'warning');
  const currentPath = selectedEntry.value.path;
  busy.launch = true;
  try {
    const data = await api('/library/launch', { body: { path: currentPath } });
    toast('游戏已启动 PID ' + data.pid);
    await loadGameStatus();
    await loadLibrary();
    selectedPath.value = currentPath;
  } catch (error) {
    if (error.message.includes('找不到游戏启动文件') || error.message.includes('游戏库中找不到该游戏')) await offerRemoveMissingGame(currentPath);
    else toast(error.message, 'error');
  } finally { busy.launch = false; }
}
async function offerRemoveMissingGame(path) {
  const entry = entries.value.find((item) => item.path === path);
  const remove = await ElMessageBox.confirm(`找不到“${entry?.name || path}”的游戏文件，可能已被移动或删除。是否从游戏库移除这条记录？`, '找不到游戏', { type: 'warning', confirmButtonText: '从游戏库删除', cancelButtonText: '保留记录' }).catch(() => false);
  if (!remove) return;
  try { await api('/library/remove', { body: { path } }); await loadLibrary(); toast('已从游戏库删除失效记录'); }
  catch (error) { toast(error.message, 'error'); }
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
    const data = await api('/translations?limit=5000&refresh=' + (refresh ? 1 : 0));
    translations.value = data.entries || [];
    translationPage.value = 1;
    if (!translations.value.some((item) => item.entry_id === selectedTranslationId.value)) selectedTranslationId.value = translations.value[0]?.entry_id || '';
    syncTranslationDraft();
  } finally { busy.translation = false; }
}
function openTranslationDetail(row) { selectedTranslationId.value = row.entry_id; syncTranslationDraft(); translationDialogVisible.value = true; }
function syncTranslationDraft() { const item = selectedTranslation.value; translationDraft.source = item?.source || ''; translationDraft.target = item?.target || ''; translationMeta.value = item ? (item.file || '') + ' · ' + (item.context || item.category || '') + ' · ' + item.entry_id : ''; }
async function saveTranslationTarget() { if (!selectedTranslation.value) return; const payload = { ...selectedTranslation.value, target: translationDraft.target }; await api('/translations/save-targets', { body: { updates: [payload] } }); selectedTranslation.value.target = translationDraft.target; translationDialogVisible.value = false; toast('译文已保存'); }
async function translateSelectedWithAI() { if (!selectedTranslation.value) return; const data = await api('/ai/translate', { body: { ...aiForm, texts: [selectedTranslation.value.source], targetLang: aiForm.targetLang, from: 'auto', to: 'zh' } }); translationDraft.target = data.translations?.[0] || ''; }
async function applyTranslations() { if (!requireGameSelected()) return; const result = await api('/translations/apply', { body: { entries: translations.value } }); toast('永久写入完成：' + (result.changed || 0) + ' 处'); }
async function runtimePatch() { if (!requireGameSelected()) return; const data = await api('/translations/runtime', { body: { entries: translations.value } }); toast('补丁已生成：' + (data.changed || 0) + ' 处'); if (data.path) await window.rpgrtl.openPath(data.path); }
async function openImportPack() { const path = await window.rpgrtl.openPack(); if (!path || !requireGameSelected()) return; const data = await api('/translations/import', { body: { path: path } }); toast('导入完成：匹配 ' + data.matched + '/' + data.imported); await loadTranslations(true); }
async function openExportPack() { const path = await window.rpgrtl.savePack(); if (!path || !requireGameSelected()) return; await api('/translations/export', { body: { path: path, entries: translations.value } }); toast('翻译包已导出'); }
async function translateBatch() {
  if (!requireGameSelected()) return;
  const batchSize = Math.max(1, Math.min(Number(aiForm.batchSize || 20), 200));
  const targets = translations.value.filter((item) => !item.target && item.source).slice(0, batchSize);
  if (!targets.length) { aiPreview.value = '没有找到未翻译文本。'; return; }
  const data = await api('/ai/translate', { body: { ...aiForm, texts: targets.map((item) => item.source), targetLang: aiForm.targetLang, from: 'auto', to: 'zh' } });
  const result = data.translations || [];
  targets.forEach((entry, index) => { entry.target = result[index] || entry.target || ''; });
  await api('/translations/save-targets', { body: { updates: targets } });
  aiPreview.value = targets.map((entry, index) => (index + 1) + '. ' + entry.source + '\n=> ' + entry.target).join('\n\n');
  toast('已批译 ' + targets.length + ' 条');
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
  runtimeForm.gold = state.gold ?? 0; runtimeForm.through = Boolean(state.map?.through); runtimeForm.clickTeleport = Boolean(state.options?.clickTeleport); runtimeForm.autoSaveMinutes = Number(state.options?.autoSaveInterval || 0) / 60; runtimeForm.x = state.map?.x ?? 0; runtimeForm.y = state.map?.y ?? 0; runtimeForm.gameSpeed = state.options?.gameSpeed ?? 1; runtimeForm.battleSpeed = state.options?.battleSpeed ?? 1; runtimeForm.autoBattle = Boolean(state.options?.autoBattle); runtimeForm.godMode = Boolean(state.options?.godMode);
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
async function setRuntimeAdvancedOptions() { await setRuntimePayload({ options: { gameSpeed: Number(runtimeForm.gameSpeed || 1), battleSpeed: Number(runtimeForm.battleSpeed || 1), autoBattle: runtimeForm.autoBattle, godMode: runtimeForm.godMode } }); }
async function loadLiveStatus(silent = false) { if (!(await ensureProjectLoaded())) return; try { liveStatus.value = await api('/live/status'); } catch (error) { if (!silent) toast(error.message, 'warning'); } }
async function installBridge() {
  if (!(await ensureProjectLoaded())) return;
  const endpoint = isRenPySelected.value ? '/renpy/install-live-bridge' : '/rpgmaker/install-bridge';
  await api(endpoint, { body: {} });
  await loadLiveStatus(true);
  toast(`${isRenPySelected.value ? 'Ren’Py Hook' : '实时组件'}已安装，请重新启动游戏`);
}
async function startLive() { if (!(await ensureProjectLoaded())) return; liveStatus.value = await api('/live/start', { body: { autoTranslate: true } }); toast('实时 Hook 翻译已启动'); }
async function stopLive() { if (!(await ensureProjectLoaded())) return; liveStatus.value = await api('/live/stop', { body: {} }); toast('实时翻译已停止'); }
async function refreshLive() { if (!(await ensureProjectLoaded())) return; await api('/live/refresh', { body: {} }); await loadLiveStatus(true); }
async function mergeLive() { if (!(await ensureProjectLoaded())) return; await api('/live/merge', { body: { source: liveSource.value, target: liveTarget.value } }); await loadLiveStatus(true); toast('已写入实时翻译表并通知游戏刷新'); }
function normalizeAiProvider(provider) { const value = String(provider || '').toLowerCase(); if (value.includes('ollama') || value.includes('本地模型')) return 'ollama'; if (value.includes('anthropic') || value.includes('claude')) return 'anthropic'; return 'openai'; }
function defaultAiBaseUrl(provider) { return provider === 'anthropic' ? 'https://api.anthropic.com' : provider === 'ollama' ? 'http://127.0.0.1:11434' : 'https://api.openai.com/v1'; }
function snapshotAiProfile(provider = aiForm.provider) { aiProfiles[provider] = { apiKey: aiForm.apiKey, baseUrl: aiForm.baseUrl, model: aiForm.model, models: [...aiModels.value] }; }
async function onAiProviderChange(provider) {
  snapshotAiProfile(previousAiProvider);
  const profile = aiProfiles[provider] || {};
  aiForm.apiKey = provider === 'ollama' ? '' : (profile.apiKey || '');
  aiForm.baseUrl = profile.baseUrl || defaultAiBaseUrl(provider);
  aiForm.model = profile.model || '';
  aiModels.value = Array.isArray(profile.models) ? profile.models : [];
  previousAiProvider = provider;
  if (provider === 'ollama') await fetchAiModels(true);
}
async function loadAiSettings(showToast = true) {
  try {
    const data = await api('/settings');
    Object.assign(aiProfiles, data.ai_profiles || {});
    const ai = data.ai || data;
    aiForm.provider = normalizeAiProvider(ai.provider);
    aiForm.apiKey = aiForm.provider === 'ollama' ? '' : (ai.apiKey || '');
    aiForm.baseUrl = ai.baseUrl || defaultAiBaseUrl(aiForm.provider);
    aiForm.model = ai.model || '';
    aiForm.targetLang = ai.targetLang || aiForm.targetLang;
    aiForm.batchSize = ai.batchSize || aiForm.batchSize;
    aiModels.value = Array.isArray(ai.availableModels) ? ai.availableModels : (Array.isArray(aiProfiles[aiForm.provider]?.models) ? aiProfiles[aiForm.provider].models : []);
    previousAiProvider = aiForm.provider;
    snapshotAiProfile();
    if (aiForm.provider === 'ollama') await fetchAiModels(true);
    if (showToast) toast('已读取本机 AI 设置');
  } catch (error) { toast('读取设置失败：' + error.message, 'error'); }
}
async function saveAiSettings(showToast = true) {
  snapshotAiProfile();
  await api('/settings', { body: { ai: { ...aiForm, availableModels: [...aiModels.value] }, ai_profiles: { ...aiProfiles } } });
  if (showToast) toast('AI 设置已保存到本机缓存');
}
async function fetchAiModels(silent = false) {
  if (!aiForm.baseUrl || (aiForm.provider !== 'ollama' && !aiForm.apiKey)) { if (!silent) toast('请先填写接口 URL 和 API Key', 'warning'); return; }
  busy.models = true;
  try {
    const data = await api('/ai/models', { body: { provider: aiForm.provider, baseUrl: aiForm.baseUrl, apiKey: aiForm.apiKey } });
    aiModels.value = data.models || [];
    if (!aiModels.value.includes(aiForm.model)) aiForm.model = aiModels.value[0] || '';
    snapshotAiProfile();
    await saveAiSettings(false);
    if (!silent) toast(`已获取 ${aiModels.value.length} 个模型`);
  } catch (error) { if (!silent) toast((aiForm.provider === 'ollama' ? '未检测到 Ollama：' : '获取模型失败：') + error.message, 'error'); } finally { busy.models = false; }
}
async function testAi() {
  const source = aiTestSource.value.trim();
  if (!source) return toast('请输入测试原文', 'warning');
  if (!aiForm.model) return toast('请先选择模型', 'warning');
  if (aiForm.provider !== 'ollama' && !aiForm.apiKey) return toast('请先填写 API Key', 'warning');
  busy.aiTest = true; aiTestResult.value = '';
  try { const data = await api('/ai/translate', { body: { ...aiForm, texts: [source], targetLang: aiForm.targetLang, from: 'auto', to: 'zh' } }); aiTestResult.value = data.translations?.[0] || ''; if (!aiTestResult.value) toast('接口没有返回译文', 'warning'); else toast('测试翻译成功'); }
  catch (error) { aiTestResult.value = '测试失败：' + error.message; toast(error.message, 'error'); }
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
  else if (view === 'live') await loadLiveStatus();
  loadedViewKeys.add(key);
}
watch(currentView, async (view) => {
  if (runtimePollTimer) { clearInterval(runtimePollTimer); runtimePollTimer = null; }
  await loadViewData(view);
  if ((['maps', 'runtime'].includes(view) || (view === 'data' && dataSection.value !== 'database')) && !isRenPySelected.value) runtimePollTimer = setInterval(() => loadRuntimeState(true), 2000);
  else if (view === 'live') runtimePollTimer = setInterval(() => loadLiveStatus(true), 1000);
});
watch(selectedPath, async () => {
  loadedProjectPath.value = '';
  loadedViewKeys.clear();
  runtimeState.value = null;
  runtimeConnected.value = false;
  if (isRenPySelected.value && ['saves', 'maps', 'runtime'].includes(currentView.value)) currentView.value = 'translations';
  if (currentView.value !== 'library') await loadViewData(currentView.value);
});
watch(visibleNavItems, (items) => {
  if (!items.some((item) => item.key === currentView.value)) currentView.value = 'translations';
});
watch([translationSearch, translationCategory, translationMissingOnly], () => { translationPage.value = 1; });
watch(translationPageSize, () => { translationPage.value = 1; });
watch(translationPageCount, (count) => { if (translationPage.value > count) translationPage.value = count; });
watch(selectedTranslationId, syncTranslationDraft);
watch(selectedDataId, syncDataDraft);
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
onBeforeUnmount(() => { if (runtimePollTimer) clearInterval(runtimePollTimer); if (gameStatusTimer) clearInterval(gameStatusTimer); });
</script>

<template>
  <div class="app-page cheats-view">
    <!-- Data page: database editor -->
    <template v-if="!isRuntimePage">
      <section class="app-hero">
        <div>
          <span class="eyebrow">DATABASE</span>
          <h2>数据修改</h2>
          <p>编辑 RPG Maker 数据库 JSON：角色、物品、武器、防具、技能、敌人。</p>
        </div>
        <button class="app-button primary" @click="loadRecords">载入数据</button>
      </section>

      <section class="data-filter-bar">
        <button v-for="cat in categories" :key="cat.key" class="chip-btn" :class="{ active: category === cat.key }" @click="selectCategory(cat.key)">{{ cat.label }}</button>
      </section>

      <section v-if="records.length" class="db-counts-bar">
        <span v-for="item in dbCounts" :key="item.key"><b>{{ item.count }}</b> {{ item.label }}</span>
      </section>

      <section v-if="records.length" class="data-editor-grid">
        <div class="compact-records">
          <input v-model="keyword" placeholder="搜索名称、字段、文件和值" class="search-input" />
          <article v-for="record in filteredRecords.slice(0,120)" :key="record.record_id||record.name" class="item-card" :class="{ active: selectedKey(record) === selectedRecordKey }" @click="selectRecord(record)">
            <div class="item-head"><span>{{ record.object_label || record.label || record.name || record.record_id }}</span><span>{{ record.category||record.file }}</span></div>
            <div class="source-box">{{ record.file }} · {{ record.location || record.record_id }}</div>
            <p class="record-value">{{ record.value }}</p>
          </article>
        </div>
        <aside class="editor-panel">
          <template v-if="selectedRecord">
            <div class="item-head"><span>{{ selectedRecord.object_label || selectedRecord.label || selectedRecord.name }}</span><span>立即写回 JSON</span></div>
            <div class="source-box">{{ selectedRecord.file }} · {{ selectedRecord.location || selectedRecord.record_id }}</div>
            <textarea v-model="selectedRecord.value" rows="8"></textarea>
            <button class="app-button primary" @click="applyRecord(selectedRecord)">应用当前字段</button>
          </template>
          <p v-else class="empty-hint">选择左侧条目进行修改。</p>
        </aside>
      </section>
    </template>

    <!-- Real-time cheats page: only the action controls -->
    <template v-else>
      <section class="app-hero">
        <div>
          <span class="eyebrow">LIVE CHEATS</span>
          <h2>实时修改</h2>
          <p>游戏运行时立即生效：金币、传送、状态、速度、战斗。</p>
        </div>
        <button class="app-button" @click="loadRuntime">刷新</button>
      </section>

      <section class="cheats-actions">
        <div class="cheat-group">
          <h3>玩家与资源</h3>
          <div class="cheat-row"><span>金币</span><input v-model="quick.gold" inputmode="numeric"/><button class="app-button small" @click="runtimeAction('gold', quick.gold)">应用</button></div>
          <div class="cheat-row"><span>传送 X</span><input v-model="quick.x" inputmode="numeric"/><span>Y</span><input v-model="quick.y" inputmode="numeric"/><button class="app-button small" @click="teleport">传送</button></div>
          <div class="cheat-btn-row">
            <button class="app-button small" @click="toggleAction('through')">穿墙</button>
            <button class="app-button small" @click="toggleAction('clickWarp')">点击传送</button>
            <button class="app-button small" @click="runtimeAction('autoSave', quick.autoSave)">自动存档</button>
          </div>
        </div>

        <div class="cheat-group">
          <h3>角色状态</h3>
          <div class="cheat-gauges">
            <input v-model="quick.hp" inputmode="numeric" placeholder="HP"/>
            <input v-model="quick.mp" inputmode="numeric" placeholder="MP"/>
            <input v-model="quick.tp" inputmode="numeric" placeholder="TP"/>
          </div>
          <div class="cheat-btn-row">
            <button class="app-button small" @click="runtimeAction('hp', quick.hp)">HP</button>
            <button class="app-button small" @click="runtimeAction('mp', quick.mp)">MP</button>
            <button class="app-button small" @click="runtimeAction('tp', quick.tp)">TP</button>
          </div>
          <div class="cheat-btn-row">
            <button class="app-button small" @click="runtimeAction('hpLock', quick.hp)">锁 HP</button>
            <button class="app-button small" @click="runtimeAction('mpLock', quick.mp)">锁 MP</button>
            <button class="app-button small" @click="runtimeAction('tpLock', quick.tp)">锁 TP</button>
          </div>
          <button class="app-button primary" @click="runtimeAction('recoverAll', '1')">全员恢复</button>
        </div>

        <div class="cheat-group">
          <h3>战斗与速度</h3>
          <div class="cheat-row"><span>游戏速度</span><input v-model="quick.speed" inputmode="numeric"/><button class="app-button small" @click="runtimeAction('speed', quick.speed)">应用</button></div>
          <div class="cheat-btn-row">
            <button class="app-button small" @click="toggleAction('autoBattle')">自动战斗</button>
            <button class="app-button small" @click="toggleAction('godMode')">上帝模式</button>
            <button class="app-button small" @click="runtimeAction('fpsOptimize', '1')">FPS 优化</button>
          </div>
          <div class="cheat-btn-row">
            <button class="app-button small" @click="runtimeAction('battleWin', '1')">直接胜利</button>
            <button class="app-button small" @click="runtimeAction('battleEscape', '1')">立即逃跑</button>
            <button class="app-button small" @click="runtimeAction('enemyHp1', '1')">敌人 1HP</button>
          </div>
        </div>
      </section>
    </template>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
const route=useRoute();const records=ref([]),status=ref(''),keyword=ref(''),category=ref(''),selectedRecordKey=ref('')
const runtime=reactive({})
const quick=reactive({gold:'999999',hp:'9999',mp:'9999',tp:'100',speed:'1',autoSave:'3',x:'0',y:'0'})
let timer=null
const categories=[{key:'',label:'全部'},{key:'Actors.json',label:'角色'},{key:'Items.json',label:'物品'},{key:'Weapons.json',label:'武器'},{key:'Armors.json',label:'防具'},{key:'Skills.json',label:'技能'},{key:'Enemies.json',label:'敌人'}]
const isRuntimePage=computed(()=>route.path==='/cheats')
const filteredRecords=computed(()=>{const q=keyword.value.trim().toLowerCase();return records.value.filter(r=>{const inCategory=!category.value||String(r.file||r.category||'')===category.value;const text=[r.file,r.category,r.object_label,r.label,r.location,r.value,r.name].some(v=>String(v||'').toLowerCase().includes(q));return inCategory&&(!q||text)})})
const selectedRecord=computed(()=>filteredRecords.value.find(r=>selectedKey(r)===selectedRecordKey.value)||null)
const dbCounts=computed(()=>{const groups={Actors:0,Items:0,Weapons:0,Armors:0,Skills:0,Enemies:0};records.value.forEach(r=>{const f=String(r.file||r.category||'');Object.keys(groups).forEach(k=>{if(f.includes(k))groups[k]++})});return [{key:'actors',label:'角色',count:groups.Actors},{key:'items',label:'物品',count:groups.Items},{key:'weapons',label:'武器',count:groups.Weapons},{key:'armors',label:'防具',count:groups.Armors},{key:'skills',label:'技能',count:groups.Skills},{key:'enemies',label:'敌人',count:groups.Enemies}]})
function selectedKey(r){return String(r.record_id||r.name||r.file||'')+'::'+String(r.location||r.label||'')}
function parse(raw){try{return raw?typeof raw==='string'?JSON.parse(raw):raw:{}}catch(e){return{ok:false,error:e.message}}}
function selectCategory(key){category.value=key;selectedRecordKey.value=''}
function selectRecord(record){selectedRecordKey.value=selectedKey(record)}
function loadRecords(){try{const res=parse(window.RPGRenPyShell?.androidDataRecords?window.RPGRenPyShell.androidDataRecords(JSON.stringify({limit:900,category:category.value})):'');if(res.ok===false)throw new Error(res.error||'load failed');records.value=Array.isArray(res.records)?res.records:Array.isArray(res)?res:[];status.value='已载入 '+records.value.length+' 项';if(!selectedRecord.value&&filteredRecords.value[0])selectRecord(filteredRecords.value[0])}catch(e){status.value='载入数据失败：'+(e.message||e)}}
function loadRuntime(){try{const res=parse(window.RPGRenPyShell?.runtimeStatus?window.RPGRenPyShell.runtimeStatus():'');if(res.ok!==false){Object.assign(runtime,res);quick.x=String(res.x??quick.x);quick.y=String(res.y??quick.y)}}catch{}}
function runtimeAction(action,value){try{const res=parse(window.RPGRenPyShell?.runtimeCheat?window.RPGRenPyShell.runtimeCheat(action,String(value??'')):JSON.stringify({ok:true}));if(res.ok===false)throw new Error(res.error||'runtime failed');status.value='已执行：'+action;loadRuntime()}catch(e){status.value='执行失败：'+(e.message||e)}}
function toggleAction(action){const current=Boolean(runtime[action]);runtimeAction(action,current?'0':'1')}
function teleport(){runtimeAction('teleport', `${quick.x},${quick.y}`)}
function applyRecord(r){try{const res=parse(window.RPGRenPyShell?.androidUpdateRecord?window.RPGRenPyShell.androidUpdateRecord(JSON.stringify(r),String(r.value??'')):JSON.stringify({ok:true}));if(res.ok===false)throw new Error(res.error||'update failed');status.value='已应用：'+(r.label||r.name||r.record_id)}catch(e){status.value='应用失败：'+(e.message||e)}}
watch(()=>route.path,()=>{status.value='';if(route.path==='/cheats')loadRuntime()})
onMounted(()=>{if(isRuntimePage.value)loadRuntime();timer=setInterval(()=>{if(isRuntimePage.value)loadRuntime()},3000)})
onBeforeUnmount(()=>{if(timer)clearInterval(timer)})
</script>

<template>
  <div class="stack parity-view saves-view">
    <section class="card glass-panel header-card">
      <div class="header-info"><h2 class="card-title">存档修改</h2><p class="card-desc">读取 RPG Maker 存档槽，修改金钱、物品、角色等级、开关和变量。</p></div>
      <button class="btn-primary" :disabled="busy" @click="loadSlots"><span v-if="busy" class="mini-spinner"></span>刷新</button>
    </section>

    <section class="mobile-grid">
      <div class="card metric"><span>存档槽</span><strong>{{ slots.length }}</strong></div>
      <div class="card metric"><span>金钱</span><strong>{{ summary?.gold ?? '-' }}</strong></div>
      <div class="card metric"><span>步数</span><strong>{{ summary?.steps ?? '-' }}</strong></div>
      <div class="card metric"><span>角色</span><strong>{{ summary?.actor_count ?? '-' }}</strong></div>
    </section>

    <section class="card glass-panel card-pad action-grid two">
      <select v-model="selectedPath" @change="loadSave(selectedPath)"><option value="">选择存档</option><option v-for="slot in slots" :key="slot.path" :value="slot.path">{{ slot.label || slot.name }} · {{ slot.modified_at || slot.source }}</option></select>
      <button class="btn-secondary" :disabled="!selectedPath" @click="writeSave">写回存档</button>
      <button class="btn-secondary" @click="backupSaves">备份存档</button>
      <button class="btn-secondary" @click="loadBackups">查看备份</button>
    </section>

    <section v-if="status" class="notice">{{ status }}</section>

    <section class="card glass-panel card-pad stack">
      <div class="item-head"><span>资源</span><span>和 PC 端一致</span></div>
      <div class="action-grid two"><input v-model="form.gold" inputmode="numeric" placeholder="金钱"/><button class="btn-secondary" @click="mutate({op:'gold',value:Number(form.gold||0)})">设置金钱</button></div>
      <div class="action-grid three"><input v-model="form.itemId" inputmode="numeric" placeholder="物品ID"/><input v-model="form.itemCount" inputmode="numeric" placeholder="数量"/><button class="btn-secondary" @click="mutate({op:'item',kind:'items',itemId:Number(form.itemId||0),value:Number(form.itemCount||0)})">设置物品</button></div>
    </section>

    <section class="card glass-panel card-pad stack">
      <div class="item-head"><span>角色 / 开关 / 变量</span><span>离线存档</span></div>
      <div class="action-grid three"><input v-model="form.actorId" inputmode="numeric" placeholder="角色ID"/><input v-model="form.actorLevel" inputmode="numeric" placeholder="等级"/><button class="btn-secondary" @click="mutate({op:'actorLevel',actorId:Number(form.actorId||0),value:Number(form.actorLevel||1)})">角色等级</button></div>
      <div class="action-grid three"><input v-model="form.switchId" inputmode="numeric" placeholder="开关ID"/><select v-model="form.switchValue"><option :value="true">ON</option><option :value="false">OFF</option></select><button class="btn-secondary" @click="mutate({op:'switch',switchId:Number(form.switchId||0),value:form.switchValue===true||form.switchValue==='true'})">设置开关</button></div>
      <div class="action-grid three"><input v-model="form.variableId" inputmode="numeric" placeholder="变量ID"/><input v-model="form.variableValue" placeholder="变量值"/><button class="btn-secondary" @click="mutate({op:'variable',variableId:Number(form.variableId||0),value:form.variableValue})">设置变量</button></div>
    </section>

    <section v-if="preview" class="card glass-panel card-pad"><div class="item-head"><span>预览</span><span>{{ selectedFile }}</span></div><pre class="preview-json">{{ preview }}</pre></section>
    <section v-if="backups.length" class="list compact-records"><article v-for="item in backups.slice(0,30)" :key="item.path" class="card item-card"><div class="item-head"><span>{{ item.name }}</span><span>{{ item.modified_at }}</span></div><div class="source-box">{{ item.path }} · {{ item.size }} bytes</div></article></section>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
const slots=ref([]),backups=ref([]),selectedPath=ref(''),summary=ref(null),payload=ref(null),status=ref(''),busy=ref(false)
const form=reactive({gold:0,itemId:1,itemCount:1,actorId:1,actorLevel:1,switchId:1,switchValue:true,variableId:1,variableValue:''})
const selectedFile=computed(()=>String(selectedPath.value||'').split(/[\\/]/).pop()||'未选择')
const preview=computed(()=>payload.value?JSON.stringify(payload.value,null,2):'')
function parse(raw){try{return raw?typeof raw==='string'?JSON.parse(raw):raw:{}}catch(e){return{ok:false,error:e.message}}}
function setResult(res){summary.value=res.summary||summary.value;payload.value=res.payload||payload.value;if(res.summary?.gold!==undefined)form.gold=res.summary.gold}
function call(name,...args){return parse(window.RPGRenPyShell?.[name]?.(...args)||JSON.stringify({ok:false,error:'真机桥接不可用'}))}
function loadSlots(){busy.value=true;try{const res=call('androidSaveSlots');if(res.ok===false)throw new Error(res.error||'load failed');slots.value=res.slots||[];if(!slots.value.some(s=>s.path===selectedPath.value))selectedPath.value=slots.value[0]?.path||'';if(selectedPath.value)loadSave(selectedPath.value);else status.value='未找到存档，请先在游戏内保存一次。'}catch(e){status.value='读取存档失败：'+(e.message||e)}finally{busy.value=false}}
function loadSave(path){if(!path)return;try{const res=call('androidLoadSave',path);if(res.ok===false)throw new Error(res.error||'load failed');setResult(res);status.value='已载入 '+selectedFile.value}catch(e){status.value='载入失败：'+(e.message||e)}}
function mutate(req){if(!selectedPath.value)return status.value='请先选择存档';try{const res=call('androidMutateSave',JSON.stringify(req));if(res.ok===false)throw new Error(res.error||'mutate failed');setResult(res);status.value='已修改，确认后点写回存档'}catch(e){status.value='修改失败：'+(e.message||e)}}
function writeSave(){if(!selectedPath.value)return;try{const res=call('androidWriteSave',selectedPath.value);if(res.ok===false)throw new Error(res.error||'write failed');status.value='已写回存档'}catch(e){status.value='写回失败：'+(e.message||e)}}
function backupSaves(){try{const res=call('androidCreateSaveBackup');if(res.ok===false)throw new Error(res.error||'backup failed');status.value=res.message||('已备份 '+(res.count||0)+' 个存档')}catch(e){status.value='备份失败：'+(e.message||e)}}
function loadBackups(){try{const res=call('androidBackups');if(res.ok===false)throw new Error(res.error||'backups failed');backups.value=res.backups||[];status.value='已找到 '+backups.value.length+' 个备份'}catch(e){status.value='读取备份失败：'+(e.message||e)}}
onMounted(loadSlots)
</script>

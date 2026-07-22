<template>
  <div class="stack game-data-view">
    <section class="card glass-panel header-card">
      <div class="header-info"><h2 class="card-title">{{ t.title }}</h2><p class="card-desc">{{ t.desc }}</p></div>
      <button class="btn-primary" @click="refreshAll">{{ t.refresh }}</button>
    </section>

    <section class="mobile-grid">
      <div class="card metric"><span>{{ t.gold }}</span><strong>{{ runtime.gold ?? '-' }}</strong></div>
      <div class="card metric"><span>{{ t.map }}</span><strong>{{ runtime.mapId ?? runtime.map_id ?? '-' }}</strong></div>
      <div class="card metric"><span>X / Y</span><strong>{{ runtime.x ?? '-' }} / {{ runtime.y ?? '-' }}</strong></div>
      <div class="card metric"><span>{{ t.party }}</span><strong>{{ partyCount }}</strong></div>
      <div class="card metric"><span>{{ t.records }}</span><strong>{{ records.length }}</strong></div>
      <div class="card metric"><span>{{ t.changed }}</span><strong>{{ changed }}</strong></div>
    </section>

    <section class="card glass-panel card-pad action-grid three">
      <button class="btn-secondary" @click="runtimeAction('gold', quick.gold)">{{ t.setGold }}</button>
      <input v-model="quick.gold" inputmode="numeric" />
      <button class="btn-secondary" @click="runtimeAction('through', 'toggle')">{{ t.through }}</button>
    </section>

    <section class="card glass-panel card-pad">
      <div class="item-head"><span>{{ t.database }}</span><span>{{ t.liveTip }}</span></div>
      <div class="mobile-grid db-counts">
        <div v-for="item in dbCounts" :key="item.key" class="card metric"><span>{{ item.label }}</span><strong>{{ item.count }}</strong></div>
      </div>
    </section>

    <section v-if="status" class="notice">{{ status }}</section>

    <section class="list compact-records">
      <article v-for="record in records.slice(0,80)" :key="record.record_id||record.name" class="card item-card">
        <div class="item-head"><span>{{ record.label||record.name }}</span><span>{{ record.category||record.type }}</span></div>
        <div class="source-box">{{ record.file||record.object_label||record.record_id }}</div>
        <div class="action-grid two"><input v-model="record.value"/><button class="btn-secondary" @click="applyRecord(record)">{{ t.apply }}</button></div>
      </article>
    </section>
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
const t={title:'\u6e38\u620f\u5185\u6570\u636e',desc:'\u6a2a\u5c4f\u6e38\u620f\u65f6\u53ea\u4fdd\u7559\u5b9e\u65f6\u4fee\u6539\u3001\u6570\u636e\u5e93\u6570\u91cf\u548c\u5730\u56fe\u4f4d\u7f6e\u3002',refresh:'\u5237\u65b0',gold:'\u91d1\u94b1',map:'\u5730\u56fe',party:'\u961f\u4f0d',records:'\u6570\u636e',changed:'\u5df2\u6539',setGold:'\u8bbe\u7f6e\u91d1\u94b1',through:'\u7a7f\u5899/\u901a\u884c',database:'\u6570\u636e\u5e93\u6570\u91cf',liveTip:'\u89d2\u8272/\u7269\u54c1/\u88c5\u5907/\u6b66\u5668',apply:'\u5e94\u7528'}
const records=ref([]),status=ref(''),changed=ref(0);const runtime=reactive({});const quick=reactive({gold:'999999'});let timer=null
const partyCount=computed(()=>Array.isArray(runtime.actors)?runtime.actors.length:(runtime.partySize??runtime.party_size??'-'))
const dbCounts=computed(()=>{
  const groups={Actors:0,Items:0,Weapons:0,Armors:0,Skills:0,Enemies:0}
  records.value.forEach(r=>{const f=String(r.file||r.category||'');Object.keys(groups).forEach(k=>{if(f.includes(k))groups[k]++})})
  return [
    {key:'actors',label:'\u89d2\u8272',count:groups.Actors},
    {key:'items',label:'\u7269\u54c1',count:groups.Items},
    {key:'weapons',label:'\u6b66\u5668',count:groups.Weapons},
    {key:'armors',label:'\u88c5\u5907/\u9632\u5177',count:groups.Armors},
    {key:'skills',label:'\u6280\u80fd',count:groups.Skills},
    {key:'enemies',label:'\u654c\u4eba',count:groups.Enemies},
  ]
})
function parse(raw){try{return raw?typeof raw==='string'?JSON.parse(raw):raw:{}}catch(e){return{ok:false,error:e.message}}}
function loadRecords(){try{const res=parse(window.RPGRenPyShell?.androidDataRecords?window.RPGRenPyShell.androidDataRecords(JSON.stringify({limit:500})):'');if(res.ok===false)throw new Error(res.error||'load failed');records.value=Array.isArray(res.records)?res.records:Array.isArray(res)?res:[];status.value='\u5df2\u8f7d\u5165 '+records.value.length+' \u9879'}catch(e){status.value='\u8f7d\u5165\u6570\u636e\u5931\u8d25\uff1a'+(e.message||e)}}
function loadRuntime(){try{const res=parse(window.RPGRenPyShell?.runtimeStatus?window.RPGRenPyShell.runtimeStatus():'');if(res.ok!==false)Object.assign(runtime,res)}catch{}}
function refreshAll(){loadRuntime();loadRecords()}
function runtimeAction(action,value){try{const res=parse(window.RPGRenPyShell?.runtimeCheat?window.RPGRenPyShell.runtimeCheat(action,String(value??'')):JSON.stringify({ok:true}));if(res.ok===false)throw new Error(res.error||'runtime failed');status.value='\u5df2\u6267\u884c\uff1a'+action;loadRuntime()}catch(e){status.value='\u6267\u884c\u5931\u8d25\uff1a'+(e.message||e)}}
function applyRecord(r){try{const res=parse(window.RPGRenPyShell?.androidUpdateRecord?window.RPGRenPyShell.androidUpdateRecord(JSON.stringify(r),String(r.value??'')):JSON.stringify({ok:true}));if(res.ok===false)throw new Error(res.error||'update failed');changed.value++;status.value='\u5df2\u5e94\u7528\uff1a'+(r.label||r.name)}catch(e){status.value='\u5e94\u7528\u5931\u8d25\uff1a'+(e.message||e)}}
onMounted(()=>{refreshAll();timer=setInterval(loadRuntime,3000)})
onBeforeUnmount(()=>{if(timer)clearInterval(timer)})
</script>

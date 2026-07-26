<template>
  <div class="app-page maps-view">
    <section class="app-hero">
      <div>
        <span class="eyebrow">MAPS</span>
        <h2>地图</h2>
        <p>查看 RPG Maker 地图布局、通行区域和事件位置。</p>
      </div>
      <button class="app-button primary" :disabled="busy" @click="loadMaps">
        <span v-if="busy" class="mini-spinner"></span>{{ busy ? '加载中' : '刷新' }}
      </button>
    </section>

    <section class="map-toolbar">
      <select v-model.number="selectedMapId" @change="loadMapDetail(selectedMapId)">
        <option :value="0">选择地图</option>
        <option v-for="map in maps" :key="map.map_id" :value="map.map_id">#{{ map.map_id }} {{ map.name || map.display_name }}</option>
      </select>
      <button class="app-button small" :disabled="!selectedMapId" @click="loadMapDetail(selectedMapId)">载入</button>
    </section>

    <section v-if="status" class="app-status">{{ status }}</section>

    <section v-if="detail" class="map-view-panel">
      <div class="map-info-bar">
        <span>{{ record.name || ('Map ' + record.map_id) }}</span>
        <small>{{ record.width || '-' }}×{{ record.height || '-' }} · {{ events.length }} 事件 · {{ transferCount }} 传送</small>
      </div>
      <div class="map-legend">
        <span class="legend-item"><i class="legend-tile passable"></i>可通行</span>
        <span class="legend-item"><i class="legend-tile blocked"></i>阻挡</span>
        <span class="legend-item"><i class="legend-tile event"></i>事件</span>
        <span class="legend-item"><i class="legend-tile transfer"></i>传送</span>
      </div>
      <div class="map-canvas-wrap">
        <div class="map-grid" :style="gridStyle">
          <div v-for="tile in visibleTiles" :key="tile.x+'-'+tile.y" class="map-tile" :class="{blocked:!tile.passable,event:tile.event_count,transfer:tile.transfer_count}" @click="selectTile(tile)" :title="tile.x+','+tile.y"></div>
        </div>
      </div>
      <div v-if="selectedTile" class="map-coord-info">坐标 {{ selectedTile.x }},{{ selectedTile.y }} · 事件 {{ selectedTile.event_count }} · 传送 {{ selectedTile.transfer_count }}</div>
    </section>

    <section v-if="events.length" class="event-list">
      <article v-for="event in events.slice(0,80)" :key="event.event_id" class="event-card" @click="focusEvent(event)">
        <div class="event-head"><span>#{{ event.event_id }} {{ event.name }}</span><small>{{ event.x }},{{ event.y }}</small></div>
        <div class="event-meta">页 {{ event.page_count }} · 指令 {{ event.command_count }}</div>
        <div v-if="event.conditions?.length" class="tag-row"><span v-for="c in toArray(event.conditions).slice(0,4)" :key="c" class="mini-tag">{{ c }}</span></div>
        <div v-if="event.commands?.length" class="event-cmds">{{ toArray(event.commands).slice(0,5).join(' / ') }}</div>
      </article>
    </section>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
const maps=ref([]),detail=ref(null),selectedMapId=ref(0),selectedTile=ref(null),status=ref(''),busy=ref(false)
const record=computed(()=>detail.value?.detail?.record||detail.value?.record||{})
const tiles=computed(()=>detail.value?.detail?.tiles||detail.value?.tiles||[])
const events=computed(()=>detail.value?.detail?.events||detail.value?.events||[])
const transferCount=computed(()=>events.value.reduce((sum,e)=>sum+toArray(e.transfers).length,0))
const visibleTiles=computed(()=>tiles.value.slice(0,2500))
const gridStyle=computed(()=>({gridTemplateColumns:`repeat(${Math.max(1,Math.min(Number(record.value.width||1),100))}, minmax(8px, 1fr))`}))
function parse(raw){try{return raw?typeof raw==='string'?JSON.parse(raw):raw:{}}catch(e){return{ok:false,error:e.message}}}
function toArray(v){return Array.isArray(v)?v:Array.from({length:v?.length||0},(_,i)=>v[i]).filter(x=>x!==undefined&&x!==null)}
function call(name,...args){return parse(window.RPGRenPyShell?.[name]?.(...args)||JSON.stringify({ok:false,error:'真机桥接不可用'}))}
function loadMaps(){busy.value=true;try{const res=call('androidMaps');if(res.ok===false)throw new Error(res.error||'maps failed');maps.value=res.maps||[];if(!maps.value.some(m=>m.map_id===selectedMapId.value))selectedMapId.value=maps.value[0]?.map_id||0;if(selectedMapId.value)loadMapDetail(selectedMapId.value);else status.value='未找到地图数据'}catch(e){status.value='读取地图失败：'+(e.message||e)}finally{busy.value=false}}
function loadMapDetail(id){if(!id)return;try{selectedTile.value=null;const res=call('androidMapDetail',Number(id));if(res.ok===false)throw new Error(res.error||'detail failed');detail.value=res;status.value='已载入地图 #'+id}catch(e){status.value='读取地图详情失败：'+(e.message||e)}}
function selectTile(tile){selectedTile.value=tile}
function focusEvent(event){if(event.x!=null&&event.y!=null)selectedTile.value={x:event.x,y:event.y,event_count:1,transfer_count:toArray(event.transfers).length}}
onMounted(loadMaps)
</script>

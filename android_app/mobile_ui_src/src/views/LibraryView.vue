<template>
  <div class="library-view stack">
    <section class="card glass-panel header-card">
      <div class="header-info"><h2 class="card-title">{{ t.title }}</h2><p class="card-desc">{{ t.desc }}</p></div>
      <button class="btn-primary" :disabled="busy.pick" @click="pickGameFolder"><svg class="icon-inline"><use :href="icon('rpgrtl-folder-plus')"></use></svg>{{ t.add }}</button>
    </section>

    <section class="mobile-grid">
      <div class="card metric"><span>{{ t.engine }}</span><strong>{{ context.engine || t.unknown }}</strong></div>
      <div class="card metric"><span>{{ t.files }}</span><strong>{{ context.fileCount || stats.files }}</strong></div>
      <div class="card metric"><span>{{ t.texts }}</span><strong>{{ stats.texts }}</strong></div>
      <div class="card metric"><span>{{ t.runMode }}</span><strong>{{ backendLabel }}</strong></div>
    </section>

    <section class="card glass-panel card-pad">
      <h3 class="card-title">{{ gameName }}</h3>
      <p class="card-desc path-text">{{ context.game_path || context.path || context.uri || t.noPath }}</p>
      <div class="pill-row">
        <span class="pill" v-if="context.engine">{{ context.engine }}</span>
        <span class="pill">{{ t.portraitWork }}</span>
        <span class="pill">{{ t.landscapeGame }}</span>
      </div>
    </section>

    <section class="card glass-panel card-pad stack">
      <div class="action-grid two">
        <button class="btn-secondary" :disabled="busy.scan" @click="scanGame"><span v-if="busy.scan" class="mini-spinner"></span>{{ t.scan }}</button>
        <button class="btn-secondary" :disabled="busy.pick" @click="pickExe">{{ t.pickExe }}</button>
      </div>
      <div class="action-grid two">
        <button class="btn-primary" :disabled="busy.launch" @click="launchGame('rpgmaker-webview')"><svg class="icon-inline"><use :href="icon('rpgrtl-play')"></use></svg>{{ t.rpgWeb }}</button>
        <button class="btn-primary" :disabled="busy.launch" @click="launchGame('renpy')"><svg class="icon-inline"><use :href="icon('rpgrtl-play')"></use></svg>{{ t.renpy }}</button>
      </div>
      <button class="btn-secondary wide" :disabled="busy.launch" @click="launchGame('windows-exe')">{{ t.exeRunner }}</button>
    </section>

    <section class="notice">{{ status || t.tip }}</section>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
const t={title:'\u6e38\u620f\u5e93',desc:'\u7ad6\u5c4f\u5bfc\u5165\u3001\u626b\u63cf\u3001\u8bbe\u7f6e\uff1b\u542f\u52a8\u6e38\u620f\u540e\u81ea\u52a8\u5207\u5230\u6a2a\u5c4f\u3002',add:'\u6dfb\u52a0',engine:'\u5f15\u64ce',files:'\u6587\u4ef6',texts:'\u6587\u672c',runMode:'\u8fd0\u884c',working:'\u5904\u7406\u4e2d',ready:'\u5c31\u7eea',unknown:'\u672a\u77e5',noPath:'\u8def\u5f84\u7b49\u5f85 Android \u8fd4\u56de',portraitWork:'\u7ad6\u5c4f\u5de5\u4f5c\u53f0',landscapeGame:'\u6a2a\u5c4f\u6e38\u620f',scan:'\u626b\u63cf\u8d44\u6e90',pickExe:'\u9009\u62e9 EXE',rpgWeb:'RPGMaker WebView',renpy:'RenPy / EXE',exeRunner:'Windows EXE \u517c\u5bb9\u8fd0\u884c\u5668',tip:'RPGMaker MV/MZ \u4f18\u5148\u4f7f\u7528\u5185\u7f6e WebView \u76f4\u63a5\u8fd0\u884c\uff0c\u4e0d\u9700\u8981 Winlator\u3002RenPy Web \u4f18\u5148 WebView\uff1b\u5982\u679c\u53ea\u6709 Windows exe\uff0c\u518d\u4ea4\u7ed9\u517c\u5bb9\u8fd0\u884c\u5668\u3002'}
const context=reactive({}); const busy=reactive({pick:false,scan:false,launch:false}); const stats=reactive({files:0,texts:0}); const status=ref('')
const gameName=computed(()=>context.game_title||context.title||context.name||'\u672a\u9009\u62e9\u6e38\u620f')
const backendLabel=computed(()=>context.backend==='wine'?'EXE':context.backend||'WebView')
function icon(id){return 'icons.svg#'+id} function parse(raw){try{return typeof raw==='string'?JSON.parse(raw):raw||{}}catch{return{ok:false,error:String(raw||'parse error')}}}
function setContext(ctx={}){Object.keys(context).forEach(k=>delete context[k]);Object.assign(context,ctx||window.appContext||{});stats.files=Number(context.fileCount||context.files||0);window.dispatchEvent(new CustomEvent('rpgrtl-context',{detail:context}))}
function pickGameFolder(){busy.pick=true;status.value='\u6b63\u5728\u6253\u5f00\u76ee\u5f55\u9009\u62e9...';try{window.RPGRenPyShell?.pickGameFolder?.()}finally{setTimeout(()=>busy.pick=false,900)}}
function pickExe(){busy.pick=true;status.value='\u6b63\u5728\u9009\u62e9 Windows EXE...';try{window.RPGRenPyShell?.pickGameExe?.()}finally{setTimeout(()=>busy.pick=false,900)}}
function scanGame(){busy.scan=true;status.value='\u6b63\u5728\u626b\u63cf\u8d44\u6e90...';try{window.RPGRenPyShell?.scanSelectedGame?.(); const raw=window.RPGRenPyShell?.androidTranslationEntries?.(1); const res=parse(raw); stats.texts=Number(res.count||res.total||res.entries?.length||stats.texts)}catch(e){status.value='\u626b\u63cf\u5931\u8d25\uff1a'+(e.message||e)}finally{setTimeout(()=>busy.scan=false,1200)}}
function launchGame(backend){busy.launch=true;status.value=backend.includes('rpgmaker')?'\u6b63\u5728\u7528 WebView \u542f\u52a8 RPGMaker...':'\u6b63\u5728\u542f\u52a8\u6e38\u620f...';try{const raw=window.RPGRenPyShell?.androidLaunchGame?window.RPGRenPyShell.androidLaunchGame(backend):JSON.stringify({ok:true,message:'preview'});const res=parse(raw);if(res.ok===false)throw new Error(res.error||'launch failed');status.value=res.message||'\u5df2\u53d1\u9001\u542f\u52a8\u8bf7\u6c42'}catch(e){status.value='\u542f\u52a8\u5931\u8d25\uff1a'+(e.message||e)}finally{setTimeout(()=>busy.launch=false,1600)}}
onMounted(()=>{setContext(window.appContext||{});window.addEventListener('rpgrtl-context',e=>setContext(e.detail||{}));})
</script>

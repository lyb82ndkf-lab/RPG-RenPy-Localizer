<script setup>
import { onLaunch } from '@dcloudio/uni-app'
import { useProjectStore } from '@/store/project'
import { isAndroidShell } from '@/utils/shell-bridge'
import { switchTopPage } from '@/utils/navigation'

onLaunch(() => {
  const project = useProjectStore()
  project.restoreLibrary()
  project.restoreCurrentSelection()
  if (isAndroidShell() && typeof window !== 'undefined') {
    window.onAndroidExternalLaunchContext = (payload) => {
      project.applyExternalLaunchContext(payload)
      if (payload?.target_page) switchTopPage(payload.target_page)
    }
    window.onAndroidOpenToolPage = (page) => {
      if (page) switchTopPage(page)
    }
  }
})
</script>

<style lang="scss">
@import './uni.scss';

page {
  min-height: 100vh;
  height: 100vh;
  overflow: hidden;
  background: $color-bg;
  color: $color-ink;
  font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif;
}

view, text, button, input, textarea, scroll-view {
  box-sizing: border-box;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>

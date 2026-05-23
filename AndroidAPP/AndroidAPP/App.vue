<script setup>
import { onLaunch } from '@dcloudio/uni-app'
import { useProjectStore } from '@/store/project'

onLaunch(() => {
  const project = useProjectStore()
  project.restoreLibrary()
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

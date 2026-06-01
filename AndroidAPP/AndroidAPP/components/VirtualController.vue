<template>
  <view class="control-stage">
    <ControlButton
      v-for="button in buttons"
      :key="button.id"
      :config="button"
      :selected="button.id === selectedId"
      :stage-width="stage.width"
      :stage-height="stage.height"
      @drag="onDrag"
      @select="$emit('select', button.id)"
    />
  </view>
</template>

<script setup>
import { nextTick, onMounted, reactive } from 'vue'
import ControlButton from './ControlButton.vue'

defineProps({
  buttons: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' },
})
const emit = defineEmits(['update', 'select'])
const stage = reactive({ width: 0, height: 0 })

function updateStageRect(done) {
  uni.createSelectorQuery()
    .select('.control-stage')
    .boundingClientRect((rect) => {
      if (rect) {
        stage.width = rect.width || stage.width
        stage.height = rect.height || stage.height
      }
      done?.(rect)
    })
    .exec()
}

onMounted(() => {
  nextTick(() => updateStageRect())
})

function onDrag(button, event) {
  const touch = event.touches?.[0]
  if (!touch) return
  updateStageRect((rect) => {
    if (!rect) return
    emit('select', button.id)
    emit('update', button.id, {
      x: Math.max(0.02, Math.min(0.98, (touch.clientX - rect.left) / rect.width)),
      y: Math.max(0.04, Math.min(0.96, (touch.clientY - rect.top) / rect.height)),
    })
  })
}
</script>

<style scoped lang="scss">
.control-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  min-height: 220rpx;
  background:
    linear-gradient(rgba(78, 161, 255, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(78, 161, 255, 0.12) 1px, transparent 1px),
    #111820;
  background-size: 24rpx 24rpx;
  border: 1px solid #263746;
  border-radius: 4rpx;
  overflow: hidden;
}
</style>

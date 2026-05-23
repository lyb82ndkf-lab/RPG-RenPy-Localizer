<template>
  <view
    class="control-button"
    :class="{ joystick: config.kind === 'joystick', selected }"
    :style="style"
    @tap.stop="$emit('select', config.id)"
    @touchstart.stop="onTouch"
    @touchmove.stop="onTouch"
  >
    <text v-if="config.kind !== 'joystick'">{{ config.label }}</text>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  stageWidth: { type: Number, default: 0 },
  stageHeight: { type: Number, default: 0 },
})
const emit = defineEmits(['drag', 'select'])

const buttonSize = computed(() => Math.max(34, Math.min(150, Number(props.config.size || 52))))
const style = computed(() => {
  const size = buttonSize.value
  if (props.stageWidth && props.stageHeight) {
    return {
      left: `${props.stageWidth * props.config.x - size / 2}px`,
      top: `${props.stageHeight * props.config.y - size / 2}px`,
      width: `${size}px`,
      height: `${size}px`,
      opacity: props.config.opacity,
    }
  }
  return {
    left: `${props.config.x * 100}%`,
    top: `${props.config.y * 100}%`,
    width: `${size}px`,
    height: `${size}px`,
    opacity: props.config.opacity,
  }
})

function onTouch(event) {
  emit('select', props.config.id)
  emit('drag', props.config, event)
}
</script>

<style scoped lang="scss">
.control-button {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 44rpx;
  min-height: 44rpx;
  border: 1px solid rgba(0, 201, 201, 0.8);
  border-radius: 6rpx;
  background: rgba(0, 102, 255, 0.72);
  color: #fff;
  font-weight: 600;
  font-size: 16rpx;
}
.joystick {
  border-radius: 999rpx;
  background: rgba(12, 18, 26, 0.45);
}
.selected {
  border-color: #ffd166;
  box-shadow: 0 0 0 2rpx rgba(255, 209, 102, 0.32);
}
</style>

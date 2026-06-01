<template>
  <view class="legend">
    <view class="item"><text class="dot passable" />可走</view>
    <view class="item"><text class="dot wall" />墙</view>
    <view class="item"><text class="dot event" />事件</view>
    <view class="item"><text class="dot transfer" />传送</view>
  </view>
</template>

<style scoped lang="scss">
.legend {
  display: flex;
  gap: 8rpx;
  flex-wrap: wrap;
}
.item {
  display: flex;
  align-items: center;
  gap: 6rpx;
  color: #95a7ba;
  font-size: 14rpx;
}
.dot {
  width: 10rpx;
  height: 10rpx;
}
.passable { background: #e8dec1; }
.wall { background: #5a655f; }
.event { background: #e0a13b; }
.transfer { background: #53a6ce; }
</style>


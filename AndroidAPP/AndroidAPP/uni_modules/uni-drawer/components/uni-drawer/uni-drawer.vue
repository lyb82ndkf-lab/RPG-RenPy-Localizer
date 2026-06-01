<template>
	<view v-if="visibleSync" :class="{ 'uni-drawer--visible': showDrawer }" class="uni-drawer" @touchmove.stop.prevent="clear">
		<view class="uni-drawer__mask" :class="{ 'uni-drawer__mask--visible': showDrawer && mask }" @tap="close('mask')" />
		<view class="uni-drawer__content" :class="{'uni-drawer--right': rightMode,'uni-drawer--left': !rightMode, 'uni-drawer__content--visible': showDrawer}" :style="{width:drawerWidth+'px'}">
			<slot />
		</view>
		<!-- #ifdef H5 -->
		<keypress @esc="close('mask')" />
		<!-- #endif -->
	</view>
</template>

<script>
	// #ifdef H5
	import keypress from './keypress.js'
	// #endif
	/**
	 * Drawer 鎶藉眽
	 * @description 鎶藉眽渚ф粦鑿滃崟
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=26
	 * @property {Boolean} mask = [true | false] 鏄惁鏄剧ず閬僵
	 * @property {Boolean} maskClick = [true | false] 鐐瑰嚮閬僵鏄惁鍏抽棴
	 * @property {Boolean} mode = [left | right] Drawer 婊戝嚭浣嶇疆
	 * 	@value left 浠庡乏渚ф粦鍑?
	 * 	@value right 浠庡彸渚т晶婊戝嚭
	 * @property {Number} width 鎶藉眽鐨勫搴?锛屼粎 vue 椤甸潰鐢熸晥
	 * @event {Function} close 缁勪欢鍏抽棴鏃惰Е鍙戜簨浠?
	 */
	export default {
		name: 'UniDrawer',
		components: {
			// #ifdef H5
			keypress
			// #endif
		},
		emits:['change'],
		props: {
			/**
			 * 鏄剧ず妯″紡锛堝乏銆佸彸锛夛紝鍙湪鍒濆鍖栫敓鏁?
			 */
			mode: {
				type: String,
				default: ''
			},
			/**
			 * 钂欏眰鏄剧ず鐘舵€?
			 */
			mask: {
				type: Boolean,
				default: true
			},
			/**
			 * 閬僵鏄惁鍙偣鍑诲叧闂?			 */
			maskClick:{
				type: Boolean,
				default: true
			},
			/**
			 * 鎶藉眽瀹藉害
			 */
			width: {
				type: Number,
				default: 220
			}
		},
		data() {
			return {
				visibleSync: false,
				showDrawer: false,
				rightMode: false,
				watchTimer: null,
				drawerWidth: 220
			}
		},
		created() {
			// #ifndef APP-NVUE
			this.drawerWidth = this.width
			// #endif
			this.rightMode = this.mode === 'right'
		},
		methods: {
			clear(){},
			close(type) {
				// fixed by mehaotian 鎶藉眽灏氭湭瀹屽叏鍏抽棴鎴栭伄缃╃姝㈢偣鍑绘椂涓嶈Е鍙戜互涓嬮€昏緫
				if((type === 'mask' && !this.maskClick) || !this.visibleSync) return
				this._change('showDrawer', 'visibleSync', false)
			},
			open() {
				// fixed by mehaotian 澶勭悊閲嶅鐐瑰嚮鎵撳紑鐨勪簨浠?				if(this.visibleSync) return
				this._change('visibleSync', 'showDrawer', true)
			},
			_change(param1, param2, status) {
				this[param1] = status
				if (this.watchTimer) {
					clearTimeout(this.watchTimer)
				}
				this.watchTimer = setTimeout(() => {
					this[param2] = status
					this.$emit('change',status)
				}, status ? 50 : 300)
			}
		}
	}
</script>

<style lang="scss" scoped>
	$uni-mask: rgba($color: #000000, $alpha: 0.4) ;
	// 鎶藉眽瀹藉害
	$drawer-width: 220px;

	.uni-drawer {
		/* #ifndef APP-NVUE */
		display: block;
		/* #endif */
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		overflow: hidden;
		z-index: 999;
	}

	.uni-drawer__content {
		/* #ifndef APP-NVUE */
		display: block;
		/* #endif */
		position: absolute;
		top: 0;
		width: $drawer-width;
		bottom: 0;
		background-color: $uni-bg-color;
		transition: transform 0.3s ease;
	}

	.uni-drawer--left {
		left: 0;
		/* #ifdef APP-NVUE */
		transform: translateX(-$drawer-width);
		/* #endif */
		/* #ifndef APP-NVUE */
		transform: translateX(-100%);
		/* #endif */
	}

	.uni-drawer--right {
		right: 0;
		/* #ifdef APP-NVUE */
		transform: translateX($drawer-width);
		/* #endif */
		/* #ifndef APP-NVUE */
		transform: translateX(100%);
		/* #endif */
	}

	.uni-drawer__content--visible {
		transform: translateX(0px);
	}


	.uni-drawer__mask {
		/* #ifndef APP-NVUE */
		display: block;
		/* #endif */
		opacity: 0;
		position: absolute;
		top: 0;
		left: 0;
		bottom: 0;
		right: 0;
		background-color: $uni-mask;
		transition: opacity 0.3s;
	}

	.uni-drawer__mask--visible {
		/* #ifndef APP-NVUE */
		display: block;
		/* #endif */
		opacity: 1;
	}
</style>


<template>
	<!-- 鍦ㄥ井淇″皬绋嬪簭 app vue绔?h5 浣跨敤wxs 瀹炵幇-->
	<!-- #ifdef APP-VUE || APP-HARMONY || MP-WEIXIN || H5 -->
	<view class="uni-swipe">
		<!--  #ifdef MP-WEIXIN || H5 -->
		<view class="uni-swipe_box" :change:prop="wxsswipe.showWatch" :prop="is_show" :data-threshold="threshold"
			:data-disabled="disabled" @touchstart="wxsswipe.touchstart" @touchmove="wxsswipe.touchmove"
			@touchend="wxsswipe.touchend">
			<!-- #endif -->
			<!--  #ifndef MP-WEIXIN || H5 -->
			<view class="uni-swipe_box" :change:prop="renderswipe.showWatch" :prop="is_show" :data-threshold="threshold"
				:data-disabled="disabled+''" @touchstart="renderswipe.touchstart" @touchmove="renderswipe.touchmove"
				@touchend="renderswipe.touchend">
			<!-- #endif -->
				<!-- 鍦ㄥ井淇″皬绋嬪簭 app vue绔?h5 浣跨敤wxs 瀹炵幇-->
				<view class="uni-swipe_button-group button-group--left">
					<slot name="left">
						<view v-for="(item,index) in leftOptions" :key="index" :style="{
					  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD'
					}" class="uni-swipe_button button-hock" @touchstart.stop="appTouchStart"
							@touchend.stop="appTouchEnd($event,index,item,'left')" @click.stop="onClickForPC(index,item,'left')">
							<text class="uni-swipe_button-text"
								:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF',fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'}">{{ item.text }}</text>
						</view>
					</slot>
				</view>
				<view class="uni-swipe_text--center">
					<slot></slot>
				</view>
				<view class="uni-swipe_button-group button-group--right">
					<slot name="right">
						<view v-for="(item,index) in rightOptions" :key="index" :style="{
					  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD'
					}" class="uni-swipe_button button-hock" @touchstart.stop="appTouchStart"
							@touchend.stop="appTouchEnd($event,index,item,'right')" @click.stop="onClickForPC(index,item,'right')"><text
								class="uni-swipe_button-text"
								:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF',fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'}">{{ item.text }}</text>
						</view>
					</slot>
				</view>
			</view>
		</view>
		<!-- #endif -->
		<!-- app nvue绔?浣跨敤 bindingx -->
		<!-- #ifdef APP-NVUE -->
		<view ref="selector-box--hock" class="uni-swipe" @horizontalpan="touchstart" @touchend="touchend">
			<view ref='selector-left-button--hock' class="uni-swipe_button-group button-group--left">
				<slot name="left">
					<view v-for="(item,index) in leftOptions" :key="index" :style="{
				  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD'
				}" class="uni-swipe_button button-hock" @click.stop="onClick(index,item,'left')">
						<text class="uni-swipe_button-text"
							:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF', fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'}">
							{{ item.text }}
						</text>
					</view>
				</slot>
			</view>
			<view ref='selector-right-button--hock' class="uni-swipe_button-group button-group--right">
				<slot name="right">
					<view v-for="(item,index) in rightOptions" :key="index" :style="{
				  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD'
				}" class="uni-swipe_button button-hock" @click.stop="onClick(index,item,'right')"><text
							class="uni-swipe_button-text"
							:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF',fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'}">{{ item.text }}</text>
					</view>
				</slot>
			</view>
			<view ref='selector-content--hock' class="uni-swipe_box">
				<slot></slot>
			</view>
		</view>
		<!-- #endif -->
		<!-- 鍏朵粬骞冲彴浣跨敤 js 锛岄暱鍒楄〃鎬ц兘鍙兘浼氭湁褰卞搷-->
		<!-- #ifdef MP-ALIPAY || MP-BAIDU || MP-TOUTIAO || MP-QQ -->
		<view class="uni-swipe">
			<view class="uni-swipe_box" @touchstart="touchstart" @touchmove="touchmove" @touchend="touchend"
				:style="{transform:moveLeft}" :class="{ani:ani}">
				<view class="uni-swipe_button-group button-group--left" :class="[elClass]">
					<slot name="left">
						<view v-for="(item,index) in leftOptions" :key="index" :style="{
					  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD',
					  fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'
					}" class="uni-swipe_button button-hock" @touchstart.stop="appTouchStart"
							@touchend.stop="appTouchEnd($event,index,item,'left')"><text class="uni-swipe_button-text"
								:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF',}">{{ item.text }}</text>
						</view>
					</slot>
				</view>
				<slot></slot>
				<view class="uni-swipe_button-group button-group--right" :class="[elClass]">
					<slot name="right">
						<view v-for="(item,index) in rightOptions" :key="index" :style="{
					  backgroundColor: item.style && item.style.backgroundColor ? item.style.backgroundColor : '#C7C6CD',
					  fontSize: item.style && item.style.fontSize ? item.style.fontSize : '16px'
					}" @touchstart.stop="appTouchStart" @touchend.stop="appTouchEnd($event,index,item,'right')"
							class="uni-swipe_button button-hock"><text class="uni-swipe_button-text"
								:style="{color: item.style && item.style.color ? item.style.color : '#FFFFFF',}">{{ item.text }}</text>
						</view>
					</slot>
				</view>
			</view>
		</view>
		<!-- #endif -->

</template>
<script src="./wx.wxs" module="wxsswipe" lang="wxs"></script>

<script module="renderswipe" lang="renderjs">
	import render from './render.js'
	export default {
		mounted(e, ins, owner) {
			this.state = {}
		},
		methods: {
			showWatch(newVal, oldVal, ownerInstance, instance) {
				render.showWatch(newVal, oldVal, ownerInstance, instance, this)
			},
			touchstart(e, ownerInstance) {
				render.touchstart(e, ownerInstance, this)
			},
			touchmove(e, ownerInstance) {
				render.touchmove(e, ownerInstance, this)
			},
			touchend(e, ownerInstance) {
				render.touchend(e, ownerInstance, this)
			}
		}
	}
</script>
<script>
	import mpwxs from './mpwxs'
	import bindingx from './bindingx.js'
	import mpother from './mpother'

	/**
	 * SwipeActionItem 婊戝姩鎿嶄綔瀛愮粍浠?
	 * @description 閫氳繃婊戝姩瑙﹀彂閫夐」鐨勫鍣?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=181
	 * @property {Boolean} show = [left|right锝渘one] 	寮€鍚叧闂粍浠讹紝auto-close = false 鏃剁敓鏁?
	 * @property {Boolean} disabled = [true|false] 		鏄惁绂佹婊戝姩
	 * @property {Boolean} autoClose = [true|false] 	婊戝姩鎵撳紑褰撳墠缁勪欢锛屾槸鍚﹀叧闂叾浠栫粍浠?
	 * @property {Number}  threshold 					婊戝姩缂虹渷鍊?
	 * @property {Array} leftOptions 					宸︿晶閫夐」鍐呭鍙婃牱寮?
	 * @property {Array} rightOptions 					鍙充晶閫夐」鍐呭鍙婃牱寮?
	 * @event {Function} click 							鐐瑰嚮閫夐」鎸夐挳鏃惰Е鍙戜簨浠讹紝e = {content,index} 锛宑ontent锛堢偣鍑诲唴瀹癸級銆乮ndex锛堜笅鏍?
	 * @event {Function} change 						缁勪欢鎵撳紑鎴栧叧闂椂瑙﹀彂锛宭eft\right\none
	 */

	export default {
		mixins: [mpwxs, bindingx, mpother],
		emits: ['click', 'change'],
		props: {
			// 鎺у埗寮€鍏?
			show: {
				type: String,
				default: 'none'
			},

			// 绂佺敤
			disabled: {
				type: Boolean,
				default: false
			},

			// 鏄惁鑷姩鍏抽棴
			autoClose: {
				type: Boolean,
				default: true
			},

			// 婊戝姩缂虹渷璺濈
			threshold: {
				type: Number,
				default: 20
			},

			// 宸︿晶鎸夐挳鍐呭
			leftOptions: {
				type: Array,
				default () {
					return []
				}
			},

			// 鍙充晶鎸夐挳鍐呭
			rightOptions: {
				type: Array,
				default () {
					return []
				}
			}

		},
		// #ifndef VUE3
		// TODO vue2
		destroyed() {
			if (this.__isUnmounted) return
			this.uninstall()
		},
		// #endif
		// #ifdef VUE3
		// TODO vue3
		unmounted() {
			this.__isUnmounted = true
			this.uninstall()
		},
		// #endif

		methods: {
			uninstall() {
				if (this.swipeaction) {
					this.swipeaction.children.forEach((item, index) => {
						if (item === this) {
							this.swipeaction.children.splice(index, 1)
						}
					})
				}
			},
			/**
			 * 鑾峰彇鐖跺厓绱犲疄渚?
			 */
			getSwipeAction(name = 'uniSwipeAction') {
				let parent = this.$parent;
				let parentName = parent.$options.name;
				while (parentName !== name) {
					parent = parent.$parent;
					if (!parent) return false;
					parentName = parent.$options.name;
				}
				return parent;
			}
		}
	}
</script>
<style lang="scss">
	.uni-swipe {
		position: relative;
		/* #ifndef APP-NVUE */
		overflow: hidden;
		/* #endif */
	}

	.uni-swipe_box {
		/* #ifndef APP-NVUE */
		display: flex;
		flex-shrink: 0;
		// touch-action: none;
		/* #endif */
		position: relative;
	}

	.uni-swipe_content {
		// border: 1px red solid;
	}

	.uni-swipe_text--center {
		width: 100%;
		/* #ifndef APP-NVUE */
		cursor: grab;
		/* #endif */
	}

	.uni-swipe_button-group {
		/* #ifndef APP-NVUE */
		box-sizing: border-box;
		display: flex;
		/* #endif */
		flex-direction: row;
		position: absolute;
		top: 0;
		bottom: 0;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.button-group--left {
		left: 0;
		transform: translateX(-100%)
	}

	.button-group--right {
		right: 0;
		transform: translateX(100%)
	}

	.uni-swipe_button {
		/* #ifdef APP-NVUE */
		flex: 1;
		/* #endif */
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		justify-content: center;
		align-items: center;
		padding: 0 20px;
	}

	.uni-swipe_button-text {
		/* #ifndef APP-NVUE */
		flex-shrink: 0;
		/* #endif */
		font-size: 14px;
	}

	.ani {
		transition-property: transform;
		transition-duration: 0.3s;
		transition-timing-function: cubic-bezier(0.165, 0.84, 0.44, 1);
	}

	/* #ifdef MP-ALIPAY */
	.movable-area {
		/* width: 100%; */
		height: 45px;
	}

	.movable-view {
		display: flex;
		/* justify-content: center; */
		position: relative;
		flex: 1;
		height: 45px;
		z-index: 2;
	}

	.movable-view-button {
		display: flex;
		flex-shrink: 0;
		flex-direction: row;
		height: 100%;
		background: #C0C0C0;
	}

	/* .transition {
		transition: all 0.3s;
	} */

	.movable-view-box {
		flex-shrink: 0;
		height: 100%;
		background-color: #fff;
	}

	/* #endif */
</style>


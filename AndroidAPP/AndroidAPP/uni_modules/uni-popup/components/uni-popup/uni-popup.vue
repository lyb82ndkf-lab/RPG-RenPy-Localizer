<template>
	<view v-if="showPopup" class="uni-popup" :class="[popupstyle, isDesktop ? 'fixforpc-z-index' : '']">
		<view @touchstart="touchstart">
			<uni-transition key="1" v-if="maskShow" name="mask" mode-class="fade" :styles="maskClass"
				:duration="duration" :show="showTrans" @click="onTap" />
			<uni-transition key="2" :mode-class="ani" name="content" :styles="transClass" :duration="duration"
				:show="showTrans" @click="onTap">
				<view class="uni-popup__wrapper" :style="getStyles" :class="[popupstyle]" @click="clear">
					<slot />
				</view>
			</uni-transition>
		</view>
		<!-- #ifdef H5 -->
		<keypress v-if="maskShow" @esc="onTap" />
		<!-- #endif -->
	</view>
</template>

<script>
	// #ifdef H5
	import keypress from './keypress.js'
	// #endif

	/**
	 * PopUp 寮瑰嚭灞?
	 * @description 寮瑰嚭灞傜粍浠讹紝涓轰簡瑙ｅ喅閬僵寮瑰眰鐨勯棶棰?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=329
	 * @property {String} type = [top|center|bottom|left|right|message|dialog|share] 寮瑰嚭鏂瑰紡
	 * 	@value top 椤堕儴寮瑰嚭
	 * 	@value center 涓棿寮瑰嚭
	 * 	@value bottom 搴曢儴寮瑰嚭
	 * 	@value left		宸︿晶寮瑰嚭
	 * 	@value right  鍙充晶寮瑰嚭
	 * 	@value message 娑堟伅鎻愮ず
	 * 	@value dialog 瀵硅瘽妗?
	 * 	@value share 搴曢儴鍒嗕韩绀轰緥
	 * @property {Boolean} animation = [true|false] 鏄惁寮€鍚姩鐢?
	 * @property {Boolean} maskClick = [true|false] 钂欑増鐐瑰嚮鏄惁鍏抽棴寮圭獥(搴熷純)
	 * @property {Boolean} isMaskClick = [true|false] 钂欑増鐐瑰嚮鏄惁鍏抽棴寮圭獥
	 * @property {String}  backgroundColor 涓荤獥鍙ｈ儗鏅壊
	 * @property {String}  maskBackgroundColor 钂欑増棰滆壊
	 * @property {String}  borderRadius 璁剧疆鍦嗚(宸︿笂銆佸彸涓娿€佸彸涓嬪拰宸︿笅) 绀轰緥:"10px 10px 10px 10px"
	 * @property {Boolean} safeArea		   鏄惁閫傞厤搴曢儴瀹夊叏鍖?
	 * @event {Function} change 鎵撳紑鍏抽棴寮圭獥瑙﹀彂锛宔={show: false}
	 * @event {Function} maskClick 鐐瑰嚮閬僵瑙﹀彂
	 */

	export default {
		name: 'uniPopup',
		components: {
			// #ifdef H5
			keypress
			// #endif
		},
		emits: ['change', 'maskClick'],
		props: {
			// 寮€鍚姩鐢?
			animation: {
				type: Boolean,
				default: true
			},
			// 寮瑰嚭灞傜被鍨嬶紝鍙€夊€硷紝top: 椤堕儴寮瑰嚭灞傦紱bottom锛氬簳閮ㄥ脊鍑哄眰锛沜enter锛氬叏灞忓脊鍑哄眰
			// message: 娑堟伅鎻愮ず ; dialog : 瀵硅瘽妗?
			type: {
				type: String,
				default: 'center'
			},
			// maskClick
			isMaskClick: {
				type: Boolean,
				default: null
			},
			// TODO 2 涓増鏈悗搴熷純灞炴€?锛屼娇鐢?isMaskClick
			maskClick: {
				type: Boolean,
				default: null
			},
			backgroundColor: {
				type: String,
				default: 'none'
			},
			safeArea: {
				type: Boolean,
				default: true
			},
			maskBackgroundColor: {
				type: String,
				default: 'rgba(0, 0, 0, 0.4)'
			},
			borderRadius:{
				type: String,
			}
		},

		watch: {
			/**
			 * 鐩戝惉type绫诲瀷
			 */
			type: {
				handler: function(type) {
					if (!this.config[type]) return
					this[this.config[type]](true)
				},
				immediate: true
			},
			isDesktop: {
				handler: function(newVal) {
					if (!this.config[newVal]) return
					this[this.config[this.type]](true)
				},
				immediate: true
			},
			/**
			 * 鐩戝惉閬僵鏄惁鍙偣鍑?
			 * @param {Object} val
			 */
			maskClick: {
				handler: function(val) {
					this.mkclick = val
				},
				immediate: true
			},
			isMaskClick: {
				handler: function(val) {
					this.mkclick = val
				},
				immediate: true
			},
			// H5 涓嬬姝㈠簳閮ㄦ粴鍔?
			showPopup(show) {
				// #ifdef H5
				// fix by mehaotian 澶勭悊 h5 婊氬姩绌块€忕殑闂
				document.getElementsByTagName('body')[0].style.overflow = show ? 'hidden' : 'visible'
				// #endif
			}
		},
		data() {
			return {
				duration: 300,
				ani: [],
				showPopup: false,
				showTrans: false,
				popupWidth: 0,
				popupHeight: 0,
				config: {
					top: 'top',
					bottom: 'bottom',
					center: 'center',
					left: 'left',
					right: 'right',
					message: 'top',
					dialog: 'center',
					share: 'bottom'
				},
				maskClass: {
					position: 'fixed',
					bottom: 0,
					top: 0,
					left: 0,
					right: 0,
					backgroundColor: 'rgba(0, 0, 0, 0.4)'
				},
				transClass: {
					backgroundColor: 'transparent',
					borderRadius: this.borderRadius || "0",
					position: 'fixed',
					left: 0,
					right: 0
				},
				maskShow: true,
				mkclick: true,
				popupstyle: 'top'
			}
		},
		computed: {
			getStyles() {
				let res = { backgroundColor: this.bg };
				if (this.borderRadius || "0") {
					res = Object.assign(res, { borderRadius: this.borderRadius })
				}
				return res;
			},
			isDesktop() {
				return this.popupWidth >= 500 && this.popupHeight >= 500
			},
			bg() {
				if (this.backgroundColor === '' || this.backgroundColor === 'none') {
					return 'transparent'
				}
				return this.backgroundColor
			}
		},
		mounted() {
			const fixSize = () => {
				// #ifdef MP-WEIXIN
				const {
					windowWidth,
					windowHeight,
					windowTop,
					safeArea,
					screenHeight,
					safeAreaInsets
				} = uni.getWindowInfo()
				// #endif
				// #ifndef MP-WEIXIN
				const {
					windowWidth,
					windowHeight,
					windowTop,
					safeArea,
					screenHeight,
					safeAreaInsets
				} = uni.getSystemInfoSync()
				// #endif
				this.popupWidth = windowWidth
				this.popupHeight = windowHeight + (windowTop || 0)
				// TODO fix by mehaotian 鏄惁閫傞厤搴曢儴瀹夊叏鍖?,鐩墠寰俊ios 銆佸拰 app ios 璁＄畻鏈夊樊寮傦紝闇€瑕佹鏋朵慨澶?
				if (safeArea && this.safeArea) {
					// #ifdef MP-WEIXIN
					this.safeAreaInsets = screenHeight - safeArea.bottom
					// #endif
					// #ifndef MP-WEIXIN
					this.safeAreaInsets = safeAreaInsets.bottom
					// #endif
				} else {
					this.safeAreaInsets = 0
				}
			}
			fixSize()
			// #ifdef H5
			// window.addEventListener('resize', fixSize)
			// this.$once('hook:beforeDestroy', () => {
			// 	window.removeEventListener('resize', fixSize)
			// })
			// #endif
		},
		// #ifndef VUE3
		// TODO vue2
		destroyed() {
			this.setH5Visible()
		},
		// #endif
		// #ifdef VUE3
		// TODO vue3
		unmounted() {
			this.setH5Visible()
		},
		// #endif
		activated() {
   	  this.setH5Visible(!this.showPopup);
    },
    deactivated() {
      this.setH5Visible(true);
    },
		created() {
			// this.mkclick =  this.isMaskClick || this.maskClick
			if (this.isMaskClick === null && this.maskClick === null) {
				this.mkclick = true
			} else {
				this.mkclick = this.isMaskClick !== null ? this.isMaskClick : this.maskClick
			}
			if (this.animation) {
				this.duration = 300
			} else {
				this.duration = 0
			}
			// TODO 澶勭悊 message 缁勪欢鐢熷懡鍛ㄦ湡寮傚父鐨勯棶棰?
			this.messageChild = null
			// TODO 瑙ｅ喅澶存潯鍐掓场鐨勯棶棰?
			this.clearPropagation = false
			this.maskClass.backgroundColor = this.maskBackgroundColor
		},
		methods: {
			setH5Visible(visible = true) {
				// #ifdef H5
				// fix by mehaotian 澶勭悊 h5 婊氬姩绌块€忕殑闂
				document.getElementsByTagName('body')[0].style.overflow =  visible ? "visible" : "hidden";
				// #endif
			},
			/**
			 * 鍏敤鏂规硶锛屼笉鏄剧ず閬僵灞?
			 */
			closeMask() {
				this.maskShow = false
			},
			/**
			 * 鍏敤鏂规硶锛岄伄缃╁眰绂佹鐐瑰嚮
			 */
			disableMask() {
				this.mkclick = false
			},
			// TODO nvue 鍙栨秷鍐掓场
			clear(e) {
				// #ifndef APP-NVUE
				e.stopPropagation()
				// #endif
				this.clearPropagation = true
			},

			open(direction) {
				// fix by mehaotian 澶勭悊蹇€熸墦寮€鍏抽棴鐨勬儏鍐?
				if (this.showPopup) {
					return
				}
				let innerType = ['top', 'center', 'bottom', 'left', 'right', 'message', 'dialog', 'share']
				if (!(direction && innerType.indexOf(direction) !== -1)) {
					direction = this.type
				}
				if (!this.config[direction]) {
					console.error('缂哄皯绫诲瀷锛?, direction)
					return
				}
				this[this.config[direction]]()
				this.$emit('change', {
					show: true,
					type: direction
				})
			},
			close(type) {
				this.showTrans = false
				this.$emit('change', {
					show: false,
					type: this.type
				})
				clearTimeout(this.timer)
				// // 鑷畾涔夊叧闂簨浠?
				// this.customOpen && this.customClose()
				this.timer = setTimeout(() => {
					this.showPopup = false
				}, 300)
			},
			// TODO 澶勭悊鍐掓场浜嬩欢锛屽ご鏉＄殑鍐掓场浜嬩欢鏈夐棶棰?锛屽厛杩欐牱鍏煎
			touchstart() {
				this.clearPropagation = false
			},

			onTap() {
				if (this.clearPropagation) {
					// fix by mehaotian 鍏煎 nvue
					this.clearPropagation = false
					return
				}
				this.$emit('maskClick')
				if (!this.mkclick) return
				this.close()
			},
			/**
			 * 椤堕儴寮瑰嚭鏍峰紡澶勭悊
			 */
			top(type) {
				this.popupstyle = this.isDesktop ? 'fixforpc-top' : 'top'
				this.ani = ['slide-top']
				this.transClass = {
					position: 'fixed',
					left: 0,
					right: 0,
					backgroundColor: this.bg,
					borderRadius:this.borderRadius || "0"
				}
				// TODO 鍏煎 type 灞炴€?锛屽悗缁細搴熷純
				if (type) return
				this.showPopup = true
				this.showTrans = true
				this.$nextTick(() => {
					this.showPoptrans()
					if (this.messageChild && this.type === 'message') {
						this.messageChild.timerClose()
					}
				})
			},
			/**
			 * 搴曢儴寮瑰嚭鏍峰紡澶勭悊
			 */
			bottom(type) {
				this.popupstyle = 'bottom'
				this.ani = ['slide-bottom']
				this.transClass = {
					position: 'fixed',
					left: 0,
					right: 0,
					bottom: 0,
					paddingBottom: this.safeAreaInsets + 'px',
					backgroundColor: this.bg,
					borderRadius:this.borderRadius || "0",
				}
				// TODO 鍏煎 type 灞炴€?锛屽悗缁細搴熷純
				if (type) return
				this.showPoptrans()
			},
			/**
			 * 涓棿寮瑰嚭鏍峰紡澶勭悊
			 */
			center(type) {
				this.popupstyle = 'center'
				//寰俊灏忕▼搴忎笅锛岀粍鍚堝姩鐢讳細鍑虹幇鏂囧瓧鍚戜笂闂姩闂锛屽啀姝ゅ仛鐗规畩澶勭悊
				// #ifdef MP-WEIXIN
					this.ani = ['fade']
				// #endif
				// #ifndef MP-WEIXIN
					this.ani = ['zoom-out', 'fade']
				// #endif
				this.transClass = {
					position: 'fixed',
					/* #ifndef APP-NVUE */
					display: 'flex',
					flexDirection: 'column',
					/* #endif */
					bottom: 0,
					left: 0,
					right: 0,
					top: 0,
					justifyContent: 'center',
					alignItems: 'center',
					borderRadius:this.borderRadius || "0"
				}
				// TODO 鍏煎 type 灞炴€?锛屽悗缁細搴熷純
				if (type) return
				this.showPoptrans()
			},
			left(type) {
				this.popupstyle = 'left'
				this.ani = ['slide-left']
				this.transClass = {
					position: 'fixed',
					left: 0,
					bottom: 0,
					top: 0,
					backgroundColor: this.bg,
					borderRadius:this.borderRadius || "0",
					/* #ifndef APP-NVUE */
					display: 'flex',
					flexDirection: 'column'
					/* #endif */
				}
				// TODO 鍏煎 type 灞炴€?锛屽悗缁細搴熷純
				if (type) return
				this.showPoptrans()
			},
			right(type) {
				this.popupstyle = 'right'
				this.ani = ['slide-right']
				this.transClass = {
					position: 'fixed',
					bottom: 0,
					right: 0,
					top: 0,
					backgroundColor: this.bg,
					borderRadius:this.borderRadius || "0",
					/* #ifndef APP-NVUE */
					display: 'flex',
					flexDirection: 'column'
					/* #endif */
				}
				// TODO 鍏煎 type 灞炴€?锛屽悗缁細搴熷純
				if (type) return
				this.showPoptrans()
			},
			showPoptrans(){
				this.$nextTick(()=>{
					this.showPopup = true
					this.showTrans = true
				})
			}
		}
	}
</script>
<style lang="scss">
	.uni-popup {
		position: fixed;
		/* #ifndef APP-NVUE */
		z-index: 99;

		/* #endif */
		&.top,
		&.left,
		&.right {
			/* #ifdef H5 */
			top: var(--window-top);
			/* #endif */
			/* #ifndef H5 */
			top: 0;
			/* #endif */
		}

		.uni-popup__wrapper {
			/* #ifndef APP-NVUE */
			display: block;
			/* #endif */
			position: relative;

			/* iphonex 绛夊畨鍏ㄥ尯璁剧疆锛屽簳閮ㄥ畨鍏ㄥ尯閫傞厤 */
			/* #ifndef APP-NVUE */
			// padding-bottom: constant(safe-area-inset-bottom);
			// padding-bottom: env(safe-area-inset-bottom);
			/* #endif */
			&.left,
			&.right {
				/* #ifdef H5 */
				padding-top: var(--window-top);
				/* #endif */
				/* #ifndef H5 */
				padding-top: 0;
				/* #endif */
				flex: 1;
			}
		}
	}

	.fixforpc-z-index {
		/* #ifndef APP-NVUE */
		z-index: 999;
		/* #endif */
	}

	.fixforpc-top {
		top: 0;
	}
</style>


<template>
	<view>
		<view ref="uni-rate" class="uni-rate">
			<view class="uni-rate__icon" :class="{'uni-cursor-not-allowed': disabled}"
				:style="{ 'margin-right': marginNumber + 'px' }" v-for="(star, index) in stars" :key="index"
				@touchstart.stop="touchstart" @touchmove.stop="touchmove" @mousedown.stop="mousedown"
				@mousemove.stop="mousemove" @mouseleave="mouseleave">
				<uni-icons :color="color" :size="size" :type="isFill ? 'star-filled' : 'star'" />
				<!-- #ifdef APP-NVUE -->
				<view :style="{ width: star.activeWitch.replace('%','')*size/100+'px'}" class="uni-rate__icon-on">
					<uni-icons style="text-align: left;" :color="disabled?'#ccc':activeColor" :size="size"
						type="star-filled" />
				</view>
				<!-- #endif -->
				<!-- #ifndef APP-NVUE -->
				<view :style="{ width: star.activeWitch}" class="uni-rate__icon-on">
					<uni-icons :color="disabled?disabledColor:activeColor" :size="size" type="star-filled" />
				</view>
				<!-- #endif -->
			</view>
		</view>
	</view>
</template>

<script>
	// #ifdef APP-NVUE
	const dom = uni.requireNativePlugin('dom');
	// #endif
	/**
	 * Rate 璇勫垎
	 * @description 璇勫垎缁勪欢
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=33
	 * @property {Boolean} 	isFill = [true|false] 		鏄熸槦鐨勭被鍨嬶紝鏄惁涓哄疄蹇冪被鍨? 榛樿涓哄疄蹇?
	 * @property {String} 	color 						鏈€変腑鐘舵€佺殑鏄熸槦棰滆壊锛岄粯璁や负 "#ececec"
	 * @property {String} 	activeColor 				閫変腑鐘舵€佺殑鏄熸槦棰滆壊锛岄粯璁や负 "#ffca3e"
	 * @property {String} 	disabledColor 				绂佺敤鐘舵€佺殑鏄熸槦棰滆壊锛岄粯璁や负 "#c0c0c0"
	 * @property {Number} 	size 						鏄熸槦鐨勫ぇ灏?
	 * @property {Number} 	value/v-model 				褰撳墠璇勫垎
	 * @property {Number} 	max 						鏈€澶ц瘎鍒嗚瘎鍒嗘暟閲忥紝鐩墠涓€鍒嗕竴棰楁槦
	 * @property {Number} 	margin 						鏄熸槦鐨勯棿璺濓紝鍗曚綅 px
	 * @property {Boolean} 	disabled = [true|false] 	鏄惁涓虹鐢ㄧ姸鎬侊紝榛樿涓?false
	 * @property {Boolean} 	readonly = [true|false] 	鏄惁涓哄彧璇荤姸鎬侊紝榛樿涓?false
	 * @property {Boolean} 	allowHalf = [true|false] 	鏄惁瀹炵幇鍗婃槦锛岄粯璁や负 false
	 * @property {Boolean} 	touchable = [true|false] 	鏄惁鏀寔婊戝姩鎵嬪娍锛岄粯璁や负 true
	 * @event {Function} change 						uniRate 鐨?value 鏀瑰彉鏃惰Е鍙戜簨浠讹紝e={value:Number}
	 */

	export default {
		name: "UniRate",
		props: {
			isFill: {
				// 鏄熸槦鐨勭被鍨嬶紝鏄惁闀傜┖
				type: [Boolean, String],
				default: true
			},
			color: {
				// 鏄熸槦鏈€変腑鐨勯鑹?
				type: String,
				default: "#ececec"
			},
			activeColor: {
				// 鏄熸槦閫変腑鐘舵€侀鑹?
				type: String,
				default: "#ffca3e"
			},
			disabledColor: {
				// 鏄熸槦绂佺敤鐘舵€侀鑹?
				type: String,
				default: "#c0c0c0"
			},
			size: {
				// 鏄熸槦鐨勫ぇ灏?
				type: [Number, String],
				default: 24
			},
			value: {
				// 褰撳墠璇勫垎
				type: [Number, String],
				default: 0
			},
			modelValue: {
				// 褰撳墠璇勫垎
				type: [Number, String],
				default: 0
			},
			max: {
				// 鏈€澶ц瘎鍒?
				type: [Number, String],
				default: 5
			},
			margin: {
				// 鏄熸槦鐨勯棿璺?
				type: [Number, String],
				default: 0
			},
			disabled: {
				// 鏄惁鍙偣鍑?
				type: [Boolean, String],
				default: false
			},
			readonly: {
				// 鏄惁鍙
				type: [Boolean, String],
				default: false
			},
			allowHalf: {
				// 鏄惁鏄剧ず鍗婃槦
				type: [Boolean, String],
				default: false
			},
			touchable: {
				// 鏄惁鏀寔婊戝姩鎵嬪娍
				type: [Boolean, String],
				default: true
			}
		},
		data() {
			return {
				valueSync: "",
				userMouseFristMove: true,
				userRated: false,
				userLastRate: 1
			};
		},
		watch: {
			value(newVal) {
				this.valueSync = Number(newVal);
			},
			modelValue(newVal) {
				this.valueSync = Number(newVal);
			},
		},
		computed: {
			stars() {
				const value = this.valueSync ? this.valueSync : 0;
				const starList = [];
				const floorValue = Math.floor(value);
				const ceilValue = Math.ceil(value);
				for (let i = 0; i < this.max; i++) {
					if (floorValue > i) {
						starList.push({
							activeWitch: "100%"
						});
					} else if (ceilValue - 1 === i) {
						starList.push({
							activeWitch: (value - floorValue) * 100 + "%"
						});
					} else {
						starList.push({
							activeWitch: "0"
						});
					}
				}
				return starList;
			},

			marginNumber() {
				return Number(this.margin)
			}
		},
		created() {
			this.valueSync = Number(this.value || this.modelValue);
			this._rateBoxLeft = 0
			this._oldValue = null
		},
		mounted() {
			setTimeout(() => {
				this._getSize()
			}, 100)
			// #ifdef H5
			this.PC = this.IsPC()
			// #endif
		},
		methods: {
			touchstart(e) {
				// #ifdef H5
				if (this.IsPC()) return
				// #endif
				if (this.readonly || this.disabled) return
				const {
					clientX,
					screenX
				} = e.changedTouches[0]
				// TODO 鍋氫竴涓嬪吋瀹癸紝鍙湁 Nvue 涓嬫墠鏈?screenX锛屽叾浠栧钩鍙板紡 clientX
				this._getRateCount(clientX || screenX)
			},
			touchmove(e) {
				// #ifdef H5
				if (this.IsPC()) return
				// #endif
				if (this.readonly || this.disabled || !this.touchable) return
				const {
					clientX,
					screenX
				} = e.changedTouches[0]
				this._getRateCount(clientX || screenX)
			},

			/**
			 * 鍏煎 PC @tian
			 */

			mousedown(e) {
				// #ifdef H5
				if (!this.IsPC()) return
				if (this.readonly || this.disabled) return
				const {
					clientX,
				} = e
				this.userLastRate = this.valueSync
				this._getRateCount(clientX)
				this.userRated = true
				// #endif
			},
			mousemove(e) {
				// #ifdef H5
				if (!this.IsPC()) return
				if (this.userRated) return
				if (this.userMouseFristMove) {
					console.log('---mousemove----', this.valueSync);
					this.userLastRate = this.valueSync
					this.userMouseFristMove = false
				}
				if (this.readonly || this.disabled || !this.touchable) return
				const {
					clientX,
				} = e
				this._getRateCount(clientX)
				// #endif
			},
			mouseleave(e) {
				// #ifdef H5
				if (!this.IsPC()) return
				if (this.readonly || this.disabled || !this.touchable) return
				if (this.userRated) {
					this.userRated = false
					return
				}
				this.valueSync = this.userLastRate
				// #endif
			},
			// #ifdef H5
			IsPC() {
				var userAgentInfo = navigator.userAgent;
				var Agents = ["Android", "iPhone", "SymbianOS", "Windows Phone", "iPad", "iPod"];
				var flag = true;
				for (let v = 0; v < Agents.length - 1; v++) {
					if (userAgentInfo.indexOf(Agents[v]) > 0) {
						flag = false;
						break;
					}
				}
				return flag;
			},
			// #endif

			/**
			 * 鑾峰彇鏄熸槦涓暟
			 */
			_getRateCount(clientX) {
				this._getSize()
				const size = Number(this.size)
				if (isNaN(size)) {
					return new Error('size 灞炴€у彧鑳借缃负鏁板瓧')
				}
				const rateMoveRange = clientX - this._rateBoxLeft
				let index = parseInt(rateMoveRange / (size + this.marginNumber))
				index = index < 0 ? 0 : index;
				index = index > this.max ? this.max : index;
				const range = parseInt(rateMoveRange - (size + this.marginNumber) * index);
				let value = 0;
				if (this._oldValue === index && !this.PC) return;
				this._oldValue = index;
				if (this.allowHalf) {
					if (range > (size / 2)) {
						value = index + 1
					} else {
						value = index + 0.5
					}
				} else {
					value = index + 1
				}

				value = Math.max(0.5, Math.min(value, this.max))
				this.valueSync = value
				this._onChange()
			},

			/**
			 * 瑙﹀彂鍔ㄦ€佷慨鏀?
			 */
			_onChange() {

				this.$emit("input", this.valueSync);
				this.$emit("update:modelValue", this.valueSync);
				this.$emit("change", {
					value: this.valueSync
				});
			},
			/**
			 * 鑾峰彇鏄熸槦璺濈灞忓箷宸︿晶璺濈
			 */
			_getSize() {
				// #ifndef APP-NVUE
				uni.createSelectorQuery()
					.in(this)
					.select('.uni-rate')
					.boundingClientRect()
					.exec(ret => {
						if (ret) {
							this._rateBoxLeft = ret[0].left
						}
					})
				// #endif
				// #ifdef APP-NVUE
				dom.getComponentRect(this.$refs['uni-rate'], (ret) => {
					const size = ret.size
					if (size) {
						this._rateBoxLeft = size.left
					}
				})
				// #endif
			}
		}
	};
</script>

<style lang="scss">
	.uni-rate {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		line-height: 1;
		font-size: 0;
		flex-direction: row;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.uni-rate__icon {
		position: relative;
		line-height: 1;
		font-size: 0;
	}

	.uni-rate__icon-on {
		overflow: hidden;
		position: absolute;
		top: 0;
		left: 0;
		line-height: 1;
		text-align: left;
	}

	.uni-cursor-not-allowed {
		/* #ifdef H5 */
		cursor: not-allowed !important;
		/* #endif */
	}
</style>


<template>
	<view class="uni-badge--x">
		<slot />
		<text v-if="text" :class="classNames" :style="[positionStyle, customStyle, dotStyle]"
			class="uni-badge" @click="onClick()">{{displayValue}}</text>
	</view>
</template>

<script>
	/**
	 * Badge 鏁板瓧瑙掓爣
	 * @description 鏁板瓧瑙掓爣涓€鑸拰鍏跺畠鎺т欢锛堝垪琛ㄣ€?瀹牸绛夛級閰嶅悎浣跨敤锛岀敤浜庤繘琛屾暟閲忔彁绀猴紝榛樿涓哄疄蹇冪伆鑹茶儗鏅?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=21
	 * @property {String} text 瑙掓爣鍐呭
	 * @property {String} size = [normal|small] 瑙掓爣鍐呭
	 * @property {String} type = [info|primary|success|warning|error] 棰滆壊绫诲瀷
	 * 	@value info 鐏拌壊
	 * 	@value primary 钃濊壊
	 * 	@value success 缁胯壊
	 * 	@value warning 榛勮壊
	 * 	@value error 绾㈣壊
	 * @property {String} inverted = [true|false] 鏄惁鏃犻渶鑳屾櫙棰滆壊
	 * @property {Number} maxNum 灞曠ず灏侀《鐨勬暟瀛楀€硷紝瓒呰繃 99 鏄剧ず 99+
	 * @property {String} absolute = [rightTop|rightBottom|leftBottom|leftTop] 寮€鍚粷瀵瑰畾浣? 瑙掓爣灏嗗畾浣嶅埌鍏跺寘瑁圭殑鏍囩鐨勫洓瑙掍笂
	 * 	@value rightTop 鍙充笂
	 * 	@value rightBottom 鍙充笅
	 * 	@value leftTop 宸︿笂
	 * 	@value leftBottom 宸︿笅
	 * @property {Array[number]} offset	璺濆畾浣嶈涓績鐐圭殑鍋忕Щ閲忥紝鍙湁瀛樺湪 absolute 灞炴€ф椂鏈夋晥锛屼緥濡傦細[-10, -10] 琛ㄧず鍚戝鍋忕Щ 10px锛孾10, 10] 琛ㄧず鍚?absolute 鎸囧畾鐨勫唴鍋忕Щ 10px
	 * @property {String} isDot = [true|false] 鏄惁鏄剧ず涓轰竴涓皬鐐?
	 * @event {Function} click 鐐瑰嚮 Badge 瑙﹀彂浜嬩欢
	 * @example <uni-badge text="1"></uni-badge>
	 */

	export default {
		name: 'UniBadge',
		emits: ['click'],
		props: {
			type: {
				type: String,
				default: 'error'
			},
			inverted: {
				type: Boolean,
				default: false
			},
			isDot: {
				type: Boolean,
				default: false
			},
			maxNum: {
				type: Number,
				default: 99
			},
			absolute: {
				type: String,
				default: ''
			},
			offset: {
				type: Array,
				default () {
					return [0, 0]
				}
			},
			text: {
				type: [String, Number],
				default: ''
			},
			size: {
				type: String,
				default: 'small'
			},
			customStyle: {
				type: Object,
				default () {
					return {}
				}
			}
		},
		data() {
			return {};
		},
		computed: {
			width() {
				return String(this.text).length * 8 + 12
			},
			classNames() {
				const {
					inverted,
					type,
					size,
					absolute
				} = this
				return [
					inverted ? 'uni-badge--' + type + '-inverted' : '',
					'uni-badge--' + type,
					'uni-badge--' + size,
					absolute ? 'uni-badge--absolute' : ''
				].join(' ')
			},
			positionStyle() {
				if (!this.absolute) return {}
				let w = this.width / 2,
					h = 10
				if (this.isDot) {
					w = 5
					h = 5
				}
				const x = `${- w  + this.offset[0]}px`
				const y = `${- h + this.offset[1]}px`

				const whiteList = {
					rightTop: {
						right: x,
						top: y
					},
					rightBottom: {
						right: x,
						bottom: y
					},
					leftBottom: {
						left: x,
						bottom: y
					},
					leftTop: {
						left: x,
						top: y
					}
				}
				const match = whiteList[this.absolute]
				return match ? match : whiteList['rightTop']
			},
			dotStyle() {
				if (!this.isDot) return {}
				return {
					width: '10px',
					minWidth: '0',
					height: '10px',
					padding: '0',
					borderRadius: '10px'
				}
			},
			displayValue() {
				const {
					isDot,
					text,
					maxNum
				} = this
				return isDot ? '' : (Number(text) > maxNum ? `${maxNum}+` : text)
			}
		},
		methods: {
			onClick() {
				this.$emit('click');
			}
		}
	};
</script>

<style lang="scss" >
	$uni-primary: #2979ff !default;
	$uni-success: #4cd964 !default;
	$uni-warning: #f0ad4e !default;
	$uni-error: #dd524d !default;
	$uni-info: #909399 !default;


	$bage-size: 12px;
	$bage-small: scale(0.8);

	.uni-badge--x {
		/* #ifdef APP-NVUE */
		// align-self: flex-start;
		/* #endif */
		/* #ifndef APP-NVUE */
		display: inline-block;
		/* #endif */
		position: relative;
	}

	.uni-badge--absolute {
		position: absolute;
	}

	.uni-badge--small {
		transform: $bage-small;
		transform-origin: center center;
	}

	.uni-badge {
		/* #ifndef APP-NVUE */
		display: flex;
		overflow: hidden;
		box-sizing: border-box;
		font-feature-settings: "tnum";
		min-width: 20px;
		/* #endif */
		justify-content: center;
		flex-direction: row;
		height: 20px;
		padding: 0 4px;
		line-height: 18px;
		color: #fff;
		border-radius: 100px;
		background-color: $uni-info;
		background-color: transparent;
		border: 1px solid #fff;
		text-align: center;
		font-family: 'Helvetica Neue', Helvetica, sans-serif;
		font-size: $bage-size;
		/* #ifdef H5 */
		z-index: 999;
		cursor: pointer;
		/* #endif */

		&--info {
			color: #fff;
			background-color: $uni-info;
		}

		&--primary {
			background-color: $uni-primary;
		}

		&--success {
			background-color: $uni-success;
		}

		&--warning {
			background-color: $uni-warning;
		}

		&--error {
			background-color: $uni-error;
		}

		&--inverted {
			padding: 0 5px 0 0;
			color: $uni-info;
		}

		&--info-inverted {
			color: $uni-info;
			background-color: transparent;
		}

		&--primary-inverted {
			color: $uni-primary;
			background-color: transparent;
		}

		&--success-inverted {
			color: $uni-success;
			background-color: transparent;
		}

		&--warning-inverted {
			color: $uni-warning;
			background-color: transparent;
		}

		&--error-inverted {
			color: $uni-error;
			background-color: transparent;
		}

	}
</style>


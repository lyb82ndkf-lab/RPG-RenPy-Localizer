<template>
	<text class="uni-tag" v-if="text" :class="classes" :style="customStyle" @click="onClick">{{text}}</text>
</template>

<script>
	/**
	 * Tag 鏍囩
	 * @description 鐢ㄤ簬灞曠ず1涓垨澶氫釜鏂囧瓧鏍囩锛屽彲鐐瑰嚮鍒囨崲閫変腑銆佷笉閫変腑鐨勭姸鎬?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=35
	 * @property {String} text 鏍囩鍐呭
	 * @property {String} size = [default|small|mini] 澶у皬灏哄
	 * 	@value default 姝ｅ父
	 * 	@value small 灏忓昂瀵?
	 * 	@value mini 杩蜂綘灏哄
	 * @property {String} type = [default|primary|success锝渨arning锝渆rror]  棰滆壊绫诲瀷
	 * 	@value default 鐏拌壊
	 * 	@value primary 钃濊壊
	 * 	@value success 缁胯壊
	 * 	@value warning 榛勮壊
	 * 	@value error 绾㈣壊
	 * @property {Boolean} disabled = [true|false] 鏄惁涓虹鐢ㄧ姸鎬?
	 * @property {Boolean} inverted = [true|false] 鏄惁鏃犻渶鑳屾櫙棰滆壊锛堢┖蹇冩爣绛撅級
	 * @property {Boolean} circle = [true|false] 鏄惁涓哄渾瑙?
	 * @event {Function} click 鐐瑰嚮 Tag 瑙﹀彂浜嬩欢
	 */

	export default {
		name: "UniTag",
		emits: ['click'],
		props: {
			type: {
				// 鏍囩绫诲瀷default銆乸rimary銆乻uccess銆亀arning銆乪rror銆乺oyal
				type: String,
				default: "default"
			},
			size: {
				// 鏍囩澶у皬 normal, small
				type: String,
				default: "normal"
			},
			// 鏍囩鍐呭
			text: {
				type: String,
				default: ""
			},
			disabled: {
				// 鏄惁涓虹鐢ㄧ姸鎬?
				type: [Boolean, String],
				default: false
			},
			inverted: {
				// 鏄惁涓虹┖蹇?
				type: [Boolean, String],
				default: false
			},
			circle: {
				// 鏄惁涓哄渾瑙掓牱寮?
				type: [Boolean, String],
				default: false
			},
			mark: {
				// 鏄惁涓烘爣璁版牱寮?
				type: [Boolean, String],
				default: false
			},
			customStyle: {
				type: String,
				default: ''
			}
		},
		computed: {
			classes() {
				const {
					type,
					disabled,
					inverted,
					circle,
					mark,
					size,
					isTrue
				} = this
				const classArr = [
					'uni-tag--' + type,
					'uni-tag--' + size,
					isTrue(disabled) ? 'uni-tag--disabled' : '',
					isTrue(inverted) ? 'uni-tag--' + type + '--inverted' : '',
					isTrue(circle) ? 'uni-tag--circle' : '',
					isTrue(mark) ? 'uni-tag--mark' : '',
					// type === 'default' ? 'uni-tag--default' : 'uni-tag-text',
					isTrue(inverted) ? 'uni-tag--inverted uni-tag-text--' + type : '',
					size === 'small' ? 'uni-tag-text--small' : ''
				]
				// 杩斿洖绫荤殑瀛楃涓诧紝鍏煎瀛楄妭灏忕▼搴?
				return classArr.join(' ')
			}
		},
		methods: {
			isTrue(value) {
				return value === true || value === 'true'
			},
			onClick() {
				if (this.isTrue(this.disabled)) return
				this.$emit("click");
			}
		}
	};
</script>

<style lang="scss" scoped>
	$uni-primary: #2979ff !default;
	$uni-success: #18bc37 !default;
	$uni-warning: #f3a73f !default;
	$uni-error: #e43d33 !default;
	$uni-info: #8f939c !default;


	$tag-default-pd: 4px 7px;
	$tag-small-pd: 2px 5px;
	$tag-mini-pd: 1px 3px;

	.uni-tag {
		line-height: 14px;
		font-size: 12px;
		font-weight: 200;
		padding: $tag-default-pd;
		color: #fff;
		border-radius: 3px;
		background-color: $uni-info;
		border-width: 1px;
		border-style: solid;
		border-color: $uni-info;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */

		// size attr
		&--default {
			font-size: 12px;
		}

		&--default--inverted {
			color: $uni-info;
			border-color: $uni-info;
		}

		&--small {
			padding: $tag-small-pd;
			font-size: 12px;
			border-radius: 2px;
		}

		&--mini {
			padding: $tag-mini-pd;
			font-size: 12px;
			border-radius: 2px;
		}

		// type attr
		&--primary {
			background-color: $uni-primary;
			border-color: $uni-primary;
			color: #fff;
		}

		&--success {
			color: #fff;
			background-color: $uni-success;
			border-color: $uni-success;
		}

		&--warning {
			color: #fff;
			background-color: $uni-warning;
			border-color: $uni-warning;
		}

		&--error {
			color: #fff;
			background-color: $uni-error;
			border-color: $uni-error;
		}

		&--primary--inverted {
			color: $uni-primary;
			border-color: $uni-primary;
		}

		&--success--inverted {
			color: $uni-success;
			border-color: $uni-success;
		}

		&--warning--inverted {
			color: $uni-warning;
			border-color: $uni-warning;
		}

		&--error--inverted {
			color: $uni-error;
			border-color: $uni-error;
		}

		&--inverted {
			background-color: #fff;
		}

		// other attr
		&--circle {
			border-radius: 15px;
		}

		&--mark {
			border-top-left-radius: 0;
			border-bottom-left-radius: 0;
			border-top-right-radius: 15px;
			border-bottom-right-radius: 15px;
		}

		&--disabled {
			opacity: 0.5;
			/* #ifdef H5 */
			cursor: not-allowed;
			/* #endif */
		}
	}


	.uni-tag-text {
		color: #fff;
		font-size: 14px;

		&--primary {
			color: $uni-primary;
		}

		&--success {
			color: $uni-success;
		}

		&--warning {
			color: $uni-warning;
		}

		&--error {
			color: $uni-error;
		}

		&--small {
			font-size: 12px;
		}
	}
</style>


<template>
	<view class="uni-numbox">
		<view @click="_calcValue('minus')" class="uni-numbox__minus uni-numbox-btns" :style="{background}">
			<text class="uni-numbox--text" :class="{ 'uni-numbox--disabled': inputValue <= min || disabled }"
				:style="{color}">-</text>
		</view>
		<input :disabled="disabled" @focus="_onFocus" @blur="_onBlur" class="uni-numbox__value"
			:type="step<1?'digit':'number'" v-model="inputValue" :style="{background, color, width:widthWithPx}" />
		<view @click="_calcValue('plus')" class="uni-numbox__plus uni-numbox-btns" :style="{background}">
			<text class="uni-numbox--text" :class="{ 'uni-numbox--disabled': inputValue >= max || disabled }"
				:style="{color}">+</text>
		</view>
	</view>
</template>
<script>
	/**
	 * NumberBox 鏁板瓧杈撳叆妗?
	 * @description 甯﹀姞鍑忔寜閽殑鏁板瓧杈撳叆妗?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=31
	 * @property {Number} value 杈撳叆妗嗗綋鍓嶅€?
	 * @property {Number} min 鏈€灏忓€?
	 * @property {Number} max 鏈€澶у€?
	 * @property {Number} step 姣忔鐐瑰嚮鏀瑰彉鐨勯棿闅斿ぇ灏?
	 * @property {String} background 鑳屾櫙鑹?
	 * @property {String} color 瀛椾綋棰滆壊锛堝墠鏅壊锛?
	 * @property {Number} width 杈撳叆妗嗗搴?鍗曚綅:px)
	 * @property {Boolean} disabled = [true|false] 鏄惁涓虹鐢ㄧ姸鎬?
	 * @event {Function} change 杈撳叆妗嗗€兼敼鍙樻椂瑙﹀彂鐨勪簨浠讹紝鍙傛暟涓鸿緭鍏ユ褰撳墠鐨?value
	 * @event {Function} focus 杈撳叆妗嗚仛鐒︽椂瑙﹀彂鐨勪簨浠讹紝鍙傛暟涓?event 瀵硅薄
	 * @event {Function} blur 杈撳叆妗嗗け鐒︽椂瑙﹀彂鐨勪簨浠讹紝鍙傛暟涓?event 瀵硅薄
	 */

	export default {
		name: "UniNumberBox",
		emits: ['change', 'input', 'update:modelValue', 'blur', 'focus'],
		props: {
			value: {
				type: [Number, String],
				default: 1
			},
			modelValue: {
				type: [Number, String],
				default: 1
			},
			min: {
				type: Number,
				default: 0
			},
			max: {
				type: Number,
				default: 100
			},
			step: {
				type: Number,
				default: 1
			},
			background: {
				type: String,
				default: '#f5f5f5'
			},
			color: {
				type: String,
				default: '#333'
			},
			disabled: {
				type: Boolean,
				default: false
			},
			width: {
				type: Number,
				default: 40,
			}
		},
		data() {
			return {
				inputValue: 0
			};
		},
		watch: {
			value(val) {
				this.inputValue = +val;
			},
			modelValue(val) {
				this.inputValue = +val;
			}
		},
		computed: {
			widthWithPx() {
				return this.width + 'px';
			}
		},
		created() {
			if (this.value === 1) {
				this.inputValue = +this.modelValue;
			}
			if (this.modelValue === 1) {
				this.inputValue = +this.value;
			}
		},
		methods: {
			_calcValue(type) {
				if (this.disabled) {
					return;
				}
				const scale = this._getDecimalScale();
				let value = this.inputValue * scale;
				let step = this.step * scale;
				if (type === "minus") {
					value -= step;
					if (value < (this.min * scale)) {
						return;
					}
					if (value > (this.max * scale)) {
						value = this.max * scale
					}
				}

				if (type === "plus") {
					value += step;
					if (value > (this.max * scale)) {
						return;
					}
					if (value < (this.min * scale)) {
						value = this.min * scale
					}
				}

				this.inputValue = (value / scale).toFixed(String(scale).length - 1);
				// TODO vue2 鍏煎
				this.$emit("input", +this.inputValue);
				// TODO vue3 鍏煎
				this.$emit("update:modelValue", +this.inputValue);
				this.$emit("change", +this.inputValue);
			},
			_getDecimalScale() {

				let scale = 1;
				// 娴偣鍨?
				if (~~this.step !== this.step) {
					scale = Math.pow(10, String(this.step).split(".")[1].length);
				}
				return scale;
			},
			_onBlur(event) {
				this.$emit('blur', event)
				let value = event.detail.value;
				if (isNaN(value)) {
					this.inputValue = this.value;
					return;
				}
				value = +value;
				if (value > this.max) {
					value = this.max;
				} else if (value < this.min) {
					value = this.min;
				}
				const scale = this._getDecimalScale();
				this.inputValue = value.toFixed(String(scale).length - 1);
				this.$emit("input", +this.inputValue);
				this.$emit("update:modelValue", +this.inputValue);
				this.$emit("change", +this.inputValue);
			},
			_onFocus(event) {
				this.$emit('focus', event)
			}
		}
	};
</script>
<style lang="scss">
	$box-height: 26px;
	$bg: #f5f5f5;
	$br: 2px;
	$color: #333;

	.uni-numbox {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
	}

	.uni-numbox-btns {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		align-items: center;
		justify-content: center;
		padding: 0 8px;
		background-color: $bg;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.uni-numbox__value {
		margin: 0 2px;
		background-color: $bg;
		width: 40px;
		height: $box-height;
		text-align: center;
		font-size: 14px;
		border-width: 0;
		color: $color;
	}

	.uni-numbox__minus {
		border-top-left-radius: $br;
		border-bottom-left-radius: $br;
	}

	.uni-numbox__plus {
		border-top-right-radius: $br;
		border-bottom-right-radius: $br;
	}

	.uni-numbox--text {
		// fix nvue
		line-height: 20px;
		margin-bottom: 2px;
		font-size: 20px;
		font-weight: 300;
		color: $color;
	}

	.uni-numbox .uni-numbox--disabled {
		color: #c0c0c0 !important;
		/* #ifdef H5 */
		cursor: not-allowed;
		/* #endif */
	}
</style>


<template>
	<view class="uni-popup-dialog">
		<view class="uni-dialog-title">
			<text class="uni-dialog-title-text" :class="['uni-popup__'+dialogType]">{{titleText}}</text>
		</view>
		<view v-if="mode === 'base'" class="uni-dialog-content">
			<slot>
				<text class="uni-dialog-content-text">{{content}}</text>
			</slot>
		</view>
		<view v-else class="uni-dialog-content">
			<slot>
				<input class="uni-dialog-input" :maxlength="maxlength" v-model="val" :type="inputType"
					:placeholder="placeholderText" :focus="focus">
			</slot>
		</view>
		<view class="uni-dialog-button-group">
			<view class="uni-dialog-button" v-if="showClose" @click="closeDialog">
				<text class="uni-dialog-button-text">{{closeText}}</text>
			</view>
			<view class="uni-dialog-button" :class="showClose?'uni-border-left':''" @click="onOk">
				<text class="uni-dialog-button-text uni-button-color">{{okText}}</text>
			</view>
		</view>

	</view>
</template>

<script>
	import popup from '../uni-popup/popup.js'
	import {
		initVueI18n
	} from '@dcloudio/uni-i18n'
	import messages from '../uni-popup/i18n/index.js'
	const {
		t
	} = initVueI18n(messages)
	/**
	 * PopUp 寮瑰嚭灞?瀵硅瘽妗嗘牱寮?
	 * @description 寮瑰嚭灞?瀵硅瘽妗嗘牱寮?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=329
	 * @property {String} value input 妯″紡涓嬬殑榛樿鍊?
	 * @property {String} placeholder input 妯″紡涓嬭緭鍏ユ彁绀?
	 * @property {Boolean} focus input妯″紡涓嬫槸鍚﹁嚜鍔ㄨ仛鐒︼紝榛樿涓簍rue
	 * @property {String} type = [success|warning|info|error] 涓婚鏍峰紡
	 *  @value success 鎴愬姛
	 * 	@value warning 鎻愮ず
	 * 	@value info 娑堟伅
	 * 	@value error 閿欒
	 * @property {String} mode = [base|input] 妯″紡銆?
	 * 	@value base 鍩虹瀵硅瘽妗?
	 * 	@value input 鍙緭鍏ュ璇濇
	 * @showClose {Boolean} 鏄惁鏄剧ず鍏抽棴鎸夐挳
	 * @property {String} content 瀵硅瘽妗嗗唴瀹?
	 * @property {Boolean} beforeClose 鏄惁鎷︽埅鍙栨秷浜嬩欢
	 * @property {Number} maxlength 杈撳叆
	 * @event {Function} confirm 鐐瑰嚮纭鎸夐挳瑙﹀彂
	 * @event {Function} close 鐐瑰嚮鍙栨秷鎸夐挳瑙﹀彂
	 */

	export default {
		name: "uniPopupDialog",
		mixins: [popup],
		emits: ['confirm', 'close', 'update:modelValue', 'input'],
		props: {
			inputType: {
				type: String,
				default: 'text'
			},
			showClose: {
				type: Boolean,
				default: true
			},
			// #ifdef VUE2
			value: {
				type: [String, Number],
				default: ''
			},
			// #endif
			// #ifdef VUE3
			modelValue: {
				type: [Number, String],
				default: ''
			},
			// #endif


			placeholder: {
				type: [String, Number],
				default: ''
			},
			type: {
				type: String,
				default: 'error'
			},
			mode: {
				type: String,
				default: 'base'
			},
			title: {
				type: String,
				default: ''
			},
			content: {
				type: String,
				default: ''
			},
			beforeClose: {
				type: Boolean,
				default: false
			},
			cancelText: {
				type: String,
				default: ''
			},
			confirmText: {
				type: String,
				default: ''
			},
			maxlength: {
				type: Number,
				default: -1,
			},
			focus: {
				type: Boolean,
				default: true,
			}
		},
		data() {
			return {
				dialogType: 'error',
				val: ""
			}
		},
		computed: {
			okText() {
				return this.confirmText || t("uni-popup.ok")
			},
			closeText() {
				return this.cancelText || t("uni-popup.cancel")
			},
			placeholderText() {
				return this.placeholder || t("uni-popup.placeholder")
			},
			titleText() {
				return this.title || t("uni-popup.title")
			}
		},
		watch: {
			type(val) {
				this.dialogType = val
			},
			mode(val) {
				if (val === 'input') {
					this.dialogType = 'info'
				}
			},
			value(val) {
				if (this.maxlength != -1 && this.mode === 'input') {
					this.val = val.slice(0, this.maxlength);
				} else {
					this.val = val
				}
			},
			val(val) {
				// #ifdef VUE2
				// TODO 鍏煎 vue2
				this.$emit('input', val);
				// #endif
				// #ifdef VUE3
				// TODO銆€鍏煎銆€vue3
				this.$emit('update:modelValue', val);
				// #endif
			}
		},
		created() {
			// 瀵硅瘽妗嗛伄缃╀笉鍙偣鍑?
			this.popup.disableMask()
			// this.popup.closeMask()
			if (this.mode === 'input') {
				this.dialogType = 'info'
				this.val = this.value;
				// #ifdef VUE3
				this.val = this.modelValue;
				// #endif
			} else {
				this.dialogType = this.type
			}
		},
		methods: {
			/**
			 * 鐐瑰嚮纭鎸夐挳
			 */
			onOk() {
				if (this.mode === 'input') {
					this.$emit('confirm', this.val)
				} else {
					this.$emit('confirm')
				}
				if (this.beforeClose) return
				this.popup.close()
			},
			/**
			 * 鐐瑰嚮鍙栨秷鎸夐挳
			 */
			closeDialog() {
				this.$emit('close')
				if (this.beforeClose) return
				this.popup.close()
			},
			close() {
				this.popup.close()
			}
		}
	}
</script>

<style lang="scss">
	.uni-popup-dialog {
		width: 300px;
		border-radius: 11px;
		background-color: #fff;
	}

	.uni-dialog-title {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		justify-content: center;
		padding-top: 25px;
	}

	.uni-dialog-title-text {
		font-size: 16px;
		font-weight: 500;
	}

	.uni-dialog-content {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		justify-content: center;
		align-items: center;
		padding: 20px;
	}

	.uni-dialog-content-text {
		font-size: 14px;
		color: #6C6C6C;
	}

	.uni-dialog-button-group {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		border-top-color: #f5f5f5;
		border-top-style: solid;
		border-top-width: 1px;
	}

	.uni-dialog-button {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */

		flex: 1;
		flex-direction: row;
		justify-content: center;
		align-items: center;
		height: 45px;
	}

	.uni-border-left {
		border-left-color: #f0f0f0;
		border-left-style: solid;
		border-left-width: 1px;
	}

	.uni-dialog-button-text {
		font-size: 16px;
		color: #333;
	}

	.uni-button-color {
		color: #007aff;
	}

	.uni-dialog-input {
		flex: 1;
		font-size: 14px;
		border: 1px #eee solid;
		height: 40px;
		padding: 0 10px;
		border-radius: 5px;
		color: #555;
	}

	.uni-popup__success {
		color: #4cd964;
	}

	.uni-popup__warn {
		color: #f0ad4e;
	}

	.uni-popup__error {
		color: #dd524d;
	}

	.uni-popup__info {
		color: #909399;
	}
</style>


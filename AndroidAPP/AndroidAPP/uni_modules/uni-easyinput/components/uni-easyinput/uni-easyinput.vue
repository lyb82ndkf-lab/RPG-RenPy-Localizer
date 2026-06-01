<template>
	<view class="uni-easyinput" :class="{ 'uni-easyinput-error': msg }" :style="boxStyle">
		<view class="uni-easyinput__content" :class="inputContentClass" :style="inputContentStyle">
			<uni-icons v-if="prefixIcon" class="content-clear-icon" :type="prefixIcon" color="#c0c4cc" @click="onClickIcon('prefix')" size="22"></uni-icons>
			<slot name="left">
			</slot>
			<!-- #ifdef MP-ALIPAY -->
			<textarea :enableNative="enableNative" v-if="type === 'textarea'" class="uni-easyinput__content-textarea" :class="{ 'input-padding': inputBorder }" :name="name" :value="val" :placeholder="placeholder" :placeholderStyle="placeholderStyle" :disabled="disabled" placeholder-class="uni-easyinput__placeholder-class" :maxlength="inputMaxlength" :focus="focused" :autoHeight="autoHeight" :cursor-spacing="cursorSpacing" :adjust-position="adjustPosition" @input="onInput" @blur="_Blur" @focus="_Focus" @confirm="onConfirm" @keyboardheightchange="onkeyboardheightchange"></textarea>
			<input :enableNative="enableNative" v-else :type="type === 'password' ? 'text' : type" class="uni-easyinput__content-input" :style="inputStyle" :name="name" :value="val" :password="!showPassword && type === 'password'" :placeholder="placeholder" :placeholderStyle="placeholderStyle" placeholder-class="uni-easyinput__placeholder-class" :disabled="disabled" :maxlength="inputMaxlength" :focus="focused" :confirmType="confirmType" :cursor-spacing="cursorSpacing" :adjust-position="adjustPosition" @focus="_Focus" @blur="_Blur" @input="onInput" @confirm="onConfirm" @keyboardheightchange="onkeyboardheightchange" />
			<!-- #endif -->
			<!-- #ifndef MP-ALIPAY -->
			<textarea v-if="type === 'textarea'" class="uni-easyinput__content-textarea" :class="{ 'input-padding': inputBorder }" :name="name" :value="val" :placeholder="placeholder" :placeholderStyle="placeholderStyle" :disabled="disabled" placeholder-class="uni-easyinput__placeholder-class" :maxlength="inputMaxlength" :focus="focused" :autoHeight="autoHeight" :cursor-spacing="cursorSpacing" :adjust-position="adjustPosition" @input="onInput" @blur="_Blur" @focus="_Focus" @confirm="onConfirm" @keyboardheightchange="onkeyboardheightchange"></textarea>
			<input v-else :type="type === 'password' ? 'text' : type" class="uni-easyinput__content-input" :style="inputStyle" :name="name" :value="val" :password="!showPassword && type === 'password'" :placeholder="placeholder" :placeholderStyle="placeholderStyle" placeholder-class="uni-easyinput__placeholder-class" :disabled="disabled" :maxlength="inputMaxlength" :focus="focused" :confirmType="confirmType" :cursor-spacing="cursorSpacing" :adjust-position="adjustPosition" @focus="_Focus" @blur="_Blur" @input="onInput" @confirm="onConfirm" @keyboardheightchange="onkeyboardheightchange" />
			<!-- #endif -->

			<template v-if="type === 'password' && passwordIcon">
				<!-- 寮€鍚瘑鐮佹椂鏄剧ず灏忕溂鐫?-->
				<uni-icons v-if="isVal" class="content-clear-icon" :class="{ 'is-textarea-icon': type === 'textarea' }" :type="showPassword ? 'eye-slash-filled' : 'eye-filled'" :size="22" :color="focusShow ? primaryColor : '#c0c4cc'" @click="onEyes"></uni-icons>
			</template>
			<template v-if="suffixIcon">
				<uni-icons v-if="suffixIcon" class="content-clear-icon" :type="suffixIcon" color="#c0c4cc" @click="onClickIcon('suffix')" size="22"></uni-icons>
			</template>
			<template v-else>
				<uni-icons v-if="clearable && isVal && !disabled && type !== 'textarea'" class="content-clear-icon" :class="{ 'is-textarea-icon': type === 'textarea' }" type="clear" :size="clearSize" :color="msg ? '#dd524d' : focusShow ? primaryColor : '#c0c4cc'" @click="onClear"></uni-icons>
			</template>
			<slot name="right"></slot>
		</view>
	</view>
</template>

<script>
	/**
	 * Easyinput 杈撳叆妗?
	 * @description 姝ょ粍浠跺彲浠ュ疄鐜拌〃鍗曠殑杈撳叆涓庢牎楠岋紝鍖呮嫭 "text" 鍜?"textarea" 绫诲瀷銆?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=3455
	 * @property {String}	value	杈撳叆鍐呭
	 * @property {String }	type	杈撳叆妗嗙殑绫诲瀷锛堥粯璁ext锛?password/text/textarea/..
	 * 	@value text			鏂囨湰杈撳叆閿洏
	 * 	@value textarea	澶氳鏂囨湰杈撳叆閿洏
	 * 	@value password	瀵嗙爜杈撳叆閿洏
	 * 	@value number		鏁板瓧杈撳叆閿洏锛屾敞鎰廼OS涓奱pp-vue寮瑰嚭鐨勬暟瀛楅敭鐩樺苟闈?瀹牸鏂瑰紡
	 * 	@value idcard		韬唤璇佽緭鍏ラ敭鐩橈紝淇°€佹敮浠樺疂銆佺櫨搴︺€丵Q灏忕▼搴?
	 * 	@value digit		甯﹀皬鏁扮偣鐨勬暟瀛楅敭鐩?锛孉pp鐨刵vue椤甸潰銆佸井淇°€佹敮浠樺疂銆佺櫨搴︺€佸ご鏉°€丵Q灏忕▼搴忔敮鎸?
	 * @property {Boolean}	clearable	鏄惁鏄剧ず鍙充晶娓呯┖鍐呭鐨勫浘鏍囨帶浠讹紝鐐瑰嚮鍙竻绌鸿緭鍏ユ鍐呭锛堥粯璁rue锛?
	 * @property {Boolean}	autoHeight	鏄惁鑷姩澧為珮杈撳叆鍖哄煙锛宼ype涓簍extarea鏃舵湁鏁堬紙榛樿true锛?
	 * @property {String }	placeholder	杈撳叆妗嗙殑鎻愮ず鏂囧瓧
	 * @property {String }	placeholderStyle	placeholder鐨勬牱寮?鍐呰仈鏍峰紡锛屽瓧绗︿覆)锛屽"color: #ddd"
	 * @property {Boolean}	focus	鏄惁鑷姩鑾峰緱鐒︾偣锛堥粯璁alse锛?
	 * @property {Boolean}	disabled	鏄惁绂佺敤锛堥粯璁alse锛?
	 * @property {Number }	maxlength	鏈€澶ц緭鍏ラ暱搴︼紝璁剧疆涓?-1 鐨勬椂鍊欎笉闄愬埗鏈€澶ч暱搴︼紙榛樿140锛?
	 * @property {String }	confirmType	璁剧疆閿洏鍙充笅瑙掓寜閽殑鏂囧瓧锛屼粎鍦╰ype="text"鏃剁敓鏁堬紙榛樿done锛?
	 * @property {Number }	clearSize	娓呴櫎鍥炬爣鐨勫ぇ灏忥紝鍗曚綅px锛堥粯璁?5锛?
	 * @property {String}	prefixIcon	杈撳叆妗嗗ご閮ㄥ浘鏍?
	 * @property {String}	suffixIcon	杈撳叆妗嗗熬閮ㄥ浘鏍?
	 * @property {String}	primaryColor	璁剧疆涓婚鑹诧紙榛樿#2979ff锛?
	 * @property {Boolean}	trim	鏄惁鑷姩鍘婚櫎涓ょ鐨勭┖鏍?
	 * @property {Boolean}	cursorSpacing	鎸囧畾鍏夋爣涓庨敭鐩樼殑璺濈锛屽崟浣?px
	 * @property {Boolean}  ajust-position 褰撻敭鐩樺脊璧锋椂锛屾槸鍚︿笂鎺ㄥ唴瀹癸紝榛樿鍊硷細true
	 * @value both	鍘婚櫎涓ょ绌烘牸
	 * @value left	鍘婚櫎宸︿晶绌烘牸
	 * @value right	鍘婚櫎鍙充晶绌烘牸
	 * @value start	鍘婚櫎宸︿晶绌烘牸
	 * @value end		鍘婚櫎鍙充晶绌烘牸
	 * @value all		鍘婚櫎鍏ㄩ儴绌烘牸
	 * @value none	涓嶅幓闄ょ┖鏍?
	 * @property {Boolean}	inputBorder	鏄惁鏄剧ずinput杈撳叆妗嗙殑杈规锛堥粯璁rue锛?
	 * @property {Boolean}	passwordIcon	type=password鏃舵槸鍚︽樉绀哄皬鐪肩潧鍥炬爣
	 * @property {Object}	styles	鑷畾涔夐鑹?
	 * @event {Function}	input	杈撳叆妗嗗唴瀹瑰彂鐢熷彉鍖栨椂瑙﹀彂
	 * @event {Function}	focus	杈撳叆妗嗚幏寰楃劍鐐规椂瑙﹀彂
	 * @event {Function}	blur	杈撳叆妗嗗け鍘荤劍鐐规椂瑙﹀彂
	 * @event {Function}	confirm	鐐瑰嚮瀹屾垚鎸夐挳鏃惰Е鍙?
	 * @event {Function}	iconClick	鐐瑰嚮鍥炬爣鏃惰Е鍙?
	 * @example <uni-easyinput v-model="mobile"></uni-easyinput>
	 */
	function obj2strClass(obj) {
		let classess = '';
		for (let key in obj) {
			const val = obj[key];
			if (val) {
				classess += `${key} `;
			}
		}
		return classess;
	}

	function obj2strStyle(obj) {
		let style = '';
		for (let key in obj) {
			const val = obj[key];
			style += `${key}:${val};`;
		}
		return style;
	}
	export default {
		name: 'uni-easyinput',
		emits: [
			'click',
			'iconClick',
			'update:modelValue',
			'input',
			'focus',
			'blur',
			'confirm',
			'clear',
			'eyes',
			'change',
			'keyboardheightchange'
		],
		model: {
			prop: 'modelValue',
			event: 'update:modelValue'
		},
		options: {
			// #ifdef MP-TOUTIAO
			virtualHost: false,
			// #endif
			// #ifndef MP-TOUTIAO
			virtualHost: true
			// #endif
		},
		inject: {
			form: {
				from: 'uniForm',
				default: null
			},
			formItem: {
				from: 'uniFormItem',
				default: null
			}
		},
		props: {
			name: String,
			value: [Number, String],
			modelValue: [Number, String],
			type: {
				type: String,
				default: 'text'
			},
			clearable: {
				type: Boolean,
				default: true
			},
			autoHeight: {
				type: Boolean,
				default: false
			},
			placeholder: {
				type: String,
				default: ' '
			},
			placeholderStyle: String,
			focus: {
				type: Boolean,
				default: false
			},
			disabled: {
				type: Boolean,
				default: false
			},
			maxlength: {
				type: [Number, String],
				default: 140
			},
			confirmType: {
				type: String,
				default: 'done'
			},
			clearSize: {
				type: [Number, String],
				default: 24
			},
			inputBorder: {
				type: Boolean,
				default: true
			},
			prefixIcon: {
				type: String,
				default: ''
			},
			suffixIcon: {
				type: String,
				default: ''
			},
			trim: {
				type: [Boolean, String],
				default: false
			},
			cursorSpacing: {
				type: Number,
				default: 0
			},
			passwordIcon: {
				type: Boolean,
				default: true
			},
			adjustPosition: {
				type: Boolean,
				default: true
			},
			primaryColor: {
				type: String,
				default: '#2979ff'
			},
			styles: {
				type: Object,
				default () {
					return {
						color: '#333',
						backgroundColor: '#fff',
						disableColor: '#F7F6F6',
						borderColor: '#e5e5e5'
					};
				}
			},
			errorMessage: {
				type: [String, Boolean],
				default: ''
			},
			// #ifdef MP-ALIPAY
			enableNative: {
				type: Boolean,
				default: false
			}
			// #endif
		},
		data() {
			return {
				focused: false,
				val: '',
				showMsg: '',
				border: false,
				isFirstBorder: false,
				showClearIcon: false,
				showPassword: false,
				focusShow: false,
				localMsg: '',
				isEnter: false // 鐢ㄤ簬鍒ゆ柇褰撳墠鏄惁鏄娇鐢ㄥ洖杞︽搷浣?
			};
		},
		computed: {
			// 杈撳叆妗嗗唴鏄惁鏈夊€?
			isVal() {
				const val = this.val;
				// fixed by mehaotian 澶勭悊鍊间负0鐨勬儏鍐碉紝瀛楃涓?涓嶅湪澶勭悊鑼冨洿
				if (val || val === 0) {
					return true;
				}
				return false;
			},

			msg() {
				// console.log('computed', this.form, this.formItem);
				// if (this.form) {
				// 	return this.errorMessage || this.formItem.errMsg;
				// }
				// TODO 澶勭悊澶存潯 formItem 涓?errMsg 涓嶆洿鏂扮殑闂
				return this.localMsg || this.errorMessage;
			},
			// 鍥犱负uniapp鐨刬nput缁勪欢鐨刴axlength缁勪欢蹇呴』瑕佹暟鍊硷紝杩欓噷杞负鏁板€硷紝鐢ㄦ埛鍙互浼犲叆瀛楃涓叉暟鍊?
			inputMaxlength() {
				return Number(this.maxlength);
			},

			// 澶勭悊澶栧眰鏍峰紡鐨剆tyle
			boxStyle() {
				return `color:${
					this.inputBorder && this.msg ? '#e43d33' : this.styles.color
				};`;
			},
			// input 鍐呭鐨勭被鍜屾牱寮忓鐞?
			inputContentClass() {
				return obj2strClass({
					'is-input-border': this.inputBorder,
					'is-input-error-border': this.inputBorder && this.msg,
					'is-textarea': this.type === 'textarea',
					'is-disabled': this.disabled,
					'is-focused': this.focusShow
				});
			},
			inputContentStyle() {
				const focusColor = this.focusShow ?
					this.primaryColor :
					this.styles.borderColor;
				const borderColor =
					this.inputBorder && this.msg ? '#dd524d' : focusColor;
				return obj2strStyle({
					'border-color': borderColor || '#e5e5e5',
					'background-color': this.disabled ?
						this.styles.disableColor : this.styles.backgroundColor
				});
			},
			// input鍙充晶鏍峰紡
			inputStyle() {
				const paddingRight =
					this.type === 'password' || this.clearable || this.prefixIcon ?
					'' :
					'10px';
				return obj2strStyle({
					'padding-right': paddingRight,
					'padding-left': this.prefixIcon ? '' : '10px'
				});
			}
		},
		watch: {
			value(newVal) {
				// fix by mehaotian 瑙ｅ喅 鍊间负null鐨勬儏鍐典笅锛宨nput鎶ラ敊鐨刡ug
				if (newVal === null) {
					this.val = '';
					return
				}
				this.val = newVal;
			},
			modelValue(newVal) {
				if (newVal === null) {
					this.val = '';
					return
				}
				this.val = newVal;
			},
			focus(newVal) {
				this.$nextTick(() => {
					this.focused = this.focus;
					this.focusShow = this.focus;
				});
			}
		},
		created() {
			this.init();
			// TODO 澶勭悊澶存潯vue3 computed 涓嶇洃鍚?inject 鏇存敼鐨勯棶棰橈紙formItem.errMsg锛?
			if (this.form && this.formItem) {
				this.$watch('formItem.errMsg', newVal => {
					this.localMsg = newVal;
				});
			}
		},
		mounted() {
			this.$nextTick(() => {
				this.focused = this.focus;
				this.focusShow = this.focus;
			});
		},
		methods: {
			/**
			 * 鍒濆鍖栧彉閲忓€?
			 */
			init() {
				if (this.value || this.value === 0) {
					this.val = this.value;
				} else if (
					this.modelValue ||
					this.modelValue === 0 ||
					this.modelValue === ''
				) {
					this.val = this.modelValue; 
				} else {
					// fix by ht 濡傛灉鍒濆鍊间负null锛屽垯input鎶ラ敊锛屽緟妗嗘灦淇
					this.val = '';
				}
			},

			/**
			 * 鐐瑰嚮鍥炬爣鏃惰Е鍙?
			 * @param {Object} type
			 */
			onClickIcon(type) {
				this.$emit('iconClick', type);
			},

			/**
			 * 鏄剧ず闅愯棌鍐呭锛屽瘑鐮佹鏃剁敓鏁?
			 */
			onEyes() {
				this.showPassword = !this.showPassword;
				this.$emit('eyes', this.showPassword);
			},

			/**
			 * 杈撳叆鏃惰Е鍙?
			 * @param {Object} event
			 */
			onInput(event) {
				let value = event.detail.value;
				// 鍒ゆ柇鏄惁鍘婚櫎绌烘牸
				if (this.trim) {
					if (typeof this.trim === 'boolean' && this.trim) {
						value = this.trimStr(value);
					}
					if (typeof this.trim === 'string') {
						value = this.trimStr(value, this.trim);
					}
				}
				if (this.errMsg) this.errMsg = '';
				this.val = value;
				// TODO 鍏煎 vue2
				this.$emit('input', value);
				// TODO銆€鍏煎銆€vue3
				this.$emit('update:modelValue', value);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 鑾峰彇鐒︾偣鏃惰Е鍙?
			 * @param {Object} event
			 */
			onFocus() {
				this.$nextTick(() => {
					this.focused = true;
				});
				this.$emit('focus', null);
			},

			_Focus(event) {
				this.focusShow = true;
				this.$emit('focus', event);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 澶卞幓鐒︾偣鏃惰Е鍙?
			 * @param {Object} event
			 */
			onBlur() {
				this.focused = false;
				this.$emit('blur', null);
			},
			_Blur(event) {
				let value = event.detail.value;
				this.focusShow = false;
				this.$emit('blur', event);
				// 鏍规嵁绫诲瀷杩斿洖鍊硷紝鍦╡vent涓幏鍙栫殑鍊肩悊璁轰笂璁查兘鏄痵tring
				if (this.isEnter === false) {
					this.$emit('change', this.val);
				}
				// 澶卞幓鐒︾偣鏃跺弬涓庤〃鍗曟牎楠?
				if (this.form && this.formItem) {
					const { validateTrigger } = this.form;
					if (validateTrigger === 'blur') {
						this.formItem.onFieldChange();
					}
				}
			},

			/**
			 * 鎸変笅閿洏鐨勫彂閫侀敭
			 * @param {Object} e
			 */
			onConfirm(e) {
				this.$emit('confirm', this.val);
				this.isEnter = true;
				this.$emit('change', this.val);
				this.$nextTick(() => {
					this.isEnter = false;
				});
			},

			/**
			 * 娓呯悊鍐呭
			 * @param {Object} event
			 */
			onClear(event) {
				this.val = '';
				// TODO 鍏煎 vue2
				this.$emit('input', '');
				// TODO 鍏煎 vue2
				// TODO銆€鍏煎銆€vue3
				this.$emit('update:modelValue', '');
				// 鐐瑰嚮鍙夊彿瑙﹀彂
				this.$emit('clear');
			},

			/**
			 * 閿洏楂樺害鍙戠敓鍙樺寲鐨勬椂鍊欒Е鍙戞浜嬩欢
			 * 鍏煎鎬э細寰俊灏忕▼搴?.7.0+銆丄pp 3.1.0+
			 * @param {Object} event
			 */
			onkeyboardheightchange(event) {
				this.$emit('keyboardheightchange', event);
			},

			/**
			 * 鍘婚櫎绌烘牸
			 */
			trimStr(str, pos = 'both') {
				if (pos === 'both') {
					return str.trim();
				} else if (pos === 'left') {
					return str.trimLeft();
				} else if (pos === 'right') {
					return str.trimRight();
				} else if (pos === 'start') {
					return str.trimStart();
				} else if (pos === 'end') {
					return str.trimEnd();
				} else if (pos === 'all') {
					return str.replace(/\s+/g, '');
				} else if (pos === 'none') {
					return str;
				}
				return str;
			}
		}
	};
</script>

<style lang="scss">
	$uni-error: #e43d33;
	$uni-border-1: #dcdfe6 !default;

	.uni-easyinput {
		/* #ifndef APP-NVUE */
		width: 100%;
		/* #endif */
		flex: 1;
		position: relative;
		text-align: left;
		color: #333;
		font-size: 14px;
	}

	.uni-easyinput__content {
		flex: 1;
		/* #ifndef APP-NVUE */
		width: 100%;
		display: flex;
		box-sizing: border-box;
		// min-height: 36px;
		/* #endif */
		flex-direction: row;
		align-items: center;
		// 澶勭悊border鍔ㄧ敾鍒氬紑濮嬫樉绀洪粦鑹茬殑闂
		border-color: #fff;
		transition-property: border-color;
		transition-duration: 0.3s;
	}

	.uni-easyinput__content-input {
		/* #ifndef APP-NVUE */
		width: auto;
		/* #endif */
		position: relative;
		overflow: hidden;
		flex: 1;
		line-height: 1;
		font-size: 14px;
		height: 35px;
		// min-height: 36px;

		/*ifdef H5*/
		& ::-ms-reveal {
			display: none;
		}

		& ::-ms-clear {
			display: none;
		}

		& ::-o-clear {
			display: none;
		}

		/*endif*/
	}

	.uni-easyinput__placeholder-class {
		color: #999;
		font-size: 12px;
		// font-weight: 200;
	}

	.is-textarea {
		align-items: flex-start;
	}

	.is-textarea-icon {
		margin-top: 5px;
	}

	.uni-easyinput__content-textarea {
		position: relative;
		overflow: hidden;
		flex: 1;
		line-height: 1.5;
		font-size: 14px;
		margin: 6px;
		margin-left: 0;
		height: 80px;
		min-height: 80px;
		/* #ifndef APP-NVUE */
		min-height: 80px;
		width: auto;
		/* #endif */
	}

	.input-padding {
		padding-left: 10px;
	}

	.content-clear-icon {
		padding: 0 5px;
	}

	.label-icon {
		margin-right: 5px;
		margin-top: -1px;
	}

	// 鏄剧ず杈规
	.is-input-border {
		/* #ifndef APP-NVUE */
		display: flex;
		box-sizing: border-box;
		/* #endif */
		flex-direction: row;
		align-items: center;
		border: 1px solid $uni-border-1;
		border-radius: 4px;
		/* #ifdef MP-ALIPAY */
		overflow: hidden;
		/* #endif */
	}

	.uni-error-message {
		position: absolute;
		bottom: -17px;
		left: 0;
		line-height: 12px;
		color: $uni-error;
		font-size: 12px;
		text-align: left;
	}

	.uni-error-msg--boeder {
		position: relative;
		bottom: 0;
		line-height: 22px;
	}

	.is-input-error-border {
		border-color: $uni-error;

		.uni-easyinput__placeholder-class {
			color: mix(#fff, $uni-error, 50%);
		}
	}

	.uni-easyinput--border {
		margin-bottom: 0;
		padding: 10px 15px;
		// padding-bottom: 0;
		border-top: 1px #eee solid;
	}

	.uni-easyinput-error {
		padding-bottom: 0;
	}

	.is-first-border {
		/* #ifndef APP-NVUE */
		border: none;
		/* #endif */
		/* #ifdef APP-NVUE */
		border-width: 0;
		/* #endif */
	}

	.is-disabled {
		background-color: #f7f6f6;
		color: #d5d5d5;

		.uni-easyinput__placeholder-class {
			color: #d5d5d5;
			font-size: 12px;
		}
	}
</style>

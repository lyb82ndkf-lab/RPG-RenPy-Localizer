<template>
	<view class="uni-forms-item"
		:class="['is-direction-' + localLabelPos ,border?'uni-forms-item--border':'' ,border && isFirstBorder?'is-first-border':'']">
		<slot name="label">
			<view class="uni-forms-item__label" :class="{'no-label':!label && !required}"
				:style="{width:localLabelWidth,justifyContent: localLabelAlign}">
				<text v-if="required" class="is-required">*</text>
				<text>{{label}}</text>
			</view>
		</slot>
		<!-- #ifndef APP-NVUE -->
		<view class="uni-forms-item__content">
			<slot></slot>
			<view class="uni-forms-item__error" :class="{'msg--active':msg}">
				<text>{{msg}}</text>
			</view>
		</view>
		<!-- #endif -->
		<!-- #ifdef APP-NVUE -->
		<view class="uni-forms-item__nuve-content">
			<view class="uni-forms-item__content">
				<slot></slot>
			</view>
			<view class="uni-forms-item__error" :class="{'msg--active':msg}">
				<text class="error-text">{{msg}}</text>
			</view>
		</view>
		<!-- #endif -->
	</view>
</template>

<script>
	/**
	 * uni-fomrs-item 琛ㄥ崟瀛愮粍浠?
	 * @description uni-fomrs-item 琛ㄥ崟瀛愮粍浠讹紝鎻愪緵浜嗗熀纭€甯冨眬宸茬粡鏍￠獙鑳藉姏
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=2773
	 * @property {Boolean} required 鏄惁蹇呭～锛屽乏杈规樉绀虹孩鑹?*"鍙?
	 * @property {String } 	label 				杈撳叆妗嗗乏杈圭殑鏂囧瓧鎻愮ず
	 * @property {Number } 	labelWidth 			label鐨勫搴︼紝鍗曚綅px锛堥粯璁?0锛?
	 * @property {String } 	labelAlign = [left|center|right] label鐨勬枃瀛楀榻愭柟寮忥紙榛樿left锛?
	 * 	@value left		label 宸︿晶鏄剧ず
	 * 	@value center	label 灞呬腑
	 * 	@value right	label 鍙充晶瀵归綈
	 * @property {String } 	errorMessage 		鏄剧ず鐨勯敊璇彁绀哄唴瀹癸紝濡傛灉涓虹┖瀛楃涓叉垨鑰協alse锛屽垯涓嶆樉绀洪敊璇俊鎭?
	 * @property {String } 	name 				琛ㄥ崟鍩熺殑灞炴€у悕锛屽湪浣跨敤鏍￠獙瑙勫垯鏃跺繀濉?
	 * @property {String } 	leftIcon 			銆?.4.0搴熷純銆憀abel宸﹁竟鐨勫浘鏍囷紝闄?uni-ui 鐨勫浘鏍囧悕绉?
	 * @property {String } 	iconColor 		銆?.4.0搴熷純銆戝乏杈归€氳繃icon閰嶇疆鐨勫浘鏍囩殑棰滆壊锛堥粯璁?606266锛?
	 * @property {String} validateTrigger = [bind|submit|blur]	銆?.4.0搴熷純銆戞牎楠岃Е鍙戝櫒鏂瑰紡 榛樿 submit
	 * 	@value bind 	鍙戠敓鍙樺寲鏃惰Е鍙?
	 * 	@value submit 鎻愪氦鏃惰Е鍙?
	 * 	@value blur 	澶卞幓鐒︾偣瑙﹀彂
	 * @property {String } 	labelPosition = [top|left] 銆?.4.0搴熷純銆憀abel鐨勬枃瀛楃殑浣嶇疆锛堥粯璁eft锛?
	 * 	@value top	椤堕儴鏄剧ず label
	 * 	@value left	宸︿晶鏄剧ず label
	 */

	export default {
		name: 'uniFormsItem',
		options: {
			// #ifdef MP-TOUTIAO
			virtualHost: false,
			// #endif
			// #ifndef MP-TOUTIAO
			virtualHost: true
			// #endif
		},
		provide() {
			return {
				uniFormItem: this
			}
		},
		inject: {
			form: {
				from: 'uniForm',
				default: null
			},
		},
		props: {
			// 琛ㄥ崟鏍￠獙瑙勫垯
			rules: {
				type: Array,
				default () {
					return null;
				}
			},
			// 琛ㄥ崟鍩熺殑灞炴€у悕锛屽湪浣跨敤鏍￠獙瑙勫垯鏃跺繀濉?
			name: {
				type: [String, Array],
				default: ''
			},
			required: {
				type: Boolean,
				default: false
			},
			label: {
				type: String,
				default: ''
			},
			// label鐨勫搴?
			labelWidth: {
				type: [String, Number],
				default: ''
			},
			// label 灞呬腑鏂瑰紡锛岄粯璁?left 鍙栧€?left/center/right
			labelAlign: {
				type: String,
				default: ''
			},
			// 寮哄埗鏄剧ず閿欒淇℃伅
			errorMessage: {
				type: [String, Boolean],
				default: ''
			},
			// 1.4.0 寮冪敤锛岀粺涓€浣跨敤 form 鐨勬牎楠屾椂鏈?
			// validateTrigger: {
			// 	type: String,
			// 	default: ''
			// },
			// 1.4.0 寮冪敤锛岀粺涓€浣跨敤 form 鐨刲abel 浣嶇疆
			// labelPosition: {
			// 	type: String,
			// 	default: ''
			// },
			// 1.4.0 浠ヤ笅灞炴€у凡缁忓簾寮冿紝璇蜂娇鐢? #label 鎻掓Ы浠ｆ浛
			leftIcon: String,
			iconColor: {
				type: String,
				default: '#606266'
			},
		},
		data() {
			return {
				errMsg: '',
				userRules: null,
				localLabelAlign: 'left',
				localLabelWidth: '70px',
				localLabelPos: 'left',
				border: false,
				isFirstBorder: false,
			};
		},
		computed: {
			// 澶勭悊閿欒淇℃伅
			msg() {
				return this.errorMessage || this.errMsg;
			}
		},
		watch: {
			// 瑙勫垯鍙戠敓鍙樺寲閫氱煡瀛愮粍浠舵洿鏂?
			'form.formRules'(val) {
				// TODO 澶勭悊澶存潯vue3 watch涓嶇敓鏁堢殑闂
				// #ifndef MP-TOUTIAO
				this.init()
				// #endif
			},
			'form.labelWidth'(val) {
				// 瀹藉害
				this.localLabelWidth = this._labelWidthUnit(val)

			},
			'form.labelPosition'(val) {
				// 鏍囩浣嶇疆
				this.localLabelPos = this._labelPosition()
			},
			'form.labelAlign'(val) {

			}
		},
		created() {
			this.init(true)
			if (this.name && this.form) {
				// TODO 澶勭悊澶存潯vue3 watch涓嶇敓鏁堢殑闂
				// #ifdef MP-TOUTIAO
				this.$watch('form.formRules', () => {
					this.init()
				})
				// #endif

				// 鐩戝惉鍙樺寲
				this.$watch(
					() => {
						const val = this.form._getDataValue(this.name, this.form.localData)
						return val
					},
					(value, oldVal) => {
						const isEqual = this.form._isEqual(value, oldVal)
						// 绠€鍗曞垽鏂墠鍚庡€肩殑鍙樺寲锛屽彧鏈夊彂鐢熷彉鍖栨墠浼氬彂鐢熸牎楠?
						// TODO  濡傛灉 oldVal = undefined 锛岄偅涔堝ぇ姒傜巼鏄簮鏁版嵁閲屾病鏈夊€煎鑷?锛岃繖涓儏鍐典笉鍝︽牎楠?,鍙兘涓嶄弗璋?锛岄渶瑕佸湪鍋氳瀵?
						// fix by mehaotian 鏆傛椂鍙栨秷 && oldVal !== undefined 锛屽鏋渇ormData 涓笉瀛樺湪锛屽彲鑳戒細涓嶆牎楠?
						if (!isEqual) {
							const val = this.itemSetValue(value)
							this.onFieldChange(val, false)
						}
					}, {
						immediate: false
					}
				);
			}

		},
		// #ifndef VUE3
		destroyed() {
			if (this.__isUnmounted) return
			this.unInit()
		},
		// #endif
		// #ifdef VUE3
		unmounted() {
			this.__isUnmounted = true
			this.unInit()
		},
		// #endif
		methods: {
			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 璁剧疆瑙勫垯 锛屼富瑕佺敤浜庡皬绋嬪簭鑷畾涔夋楠岃鍒?
			 * @param {Array} rules 瑙勫垯婧愭暟鎹?
			 */
			setRules(rules = null) {
				this.userRules = rules
				this.init(false)
			},
			// 鍏煎鑰佺増鏈〃鍗曠粍浠?
			setValue() {
				// console.log('setValue 鏂规硶宸茬粡寮冪敤锛岃浣跨敤鏈€鏂扮増鏈殑 uni-forms 琛ㄥ崟缁勪欢浠ュ強鍏朵粬鍏宠仈缁勪欢銆?);
			},
			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 鏍￠獙鏁版嵁
			 * @param {any} value 闇€瑕佹牎楠岀殑鏁版嵁
			 * @param {boolean} 鏄惁绔嬪嵆鏍￠獙
			 * @return {Array|null} 鏍￠獙鍐呭
			 */
			async onFieldChange(value, formtrigger = true) {
				const {
					formData,
					localData,
					errShowType,
					validateCheck,
					validateTrigger,
					_isRequiredField,
					_realName
				} = this.form
				const name = _realName(this.name)
				if (!value) {
					value = this.form.formData[name]
				}
				// fixd by mehaotian 涓嶅湪鏍￠獙鍓嶆竻绌轰俊鎭紝瑙ｅ喅闂睆鐨勯棶棰?
				// this.errMsg = '';

				// fix by mehaotian 瑙ｅ喅娌℃湁妫€楠岃鍒欑殑鎯呭喌涓嬶紝鎶涘嚭閿欒鐨勯棶棰?
				const ruleLen = this.itemRules.rules && this.itemRules.rules.length
				if (!this.validator || !ruleLen || ruleLen === 0) return;

				// 妫€楠屾椂鏈?
				// let trigger = this.isTrigger(this.itemRules.validateTrigger, this.validateTrigger, validateTrigger);
				const isRequiredField = _isRequiredField(this.itemRules.rules || []);
				let result = null;
				// 鍙湁绛変簬 bind 鏃?锛屾墠鑳藉紑鍚椂瀹炴牎楠?
				if (validateTrigger === 'bind' || formtrigger) {
					// 鏍￠獙褰撳墠琛ㄥ崟椤?
					result = await this.validator.validateUpdate({
							[name]: value
						},
						formData
					);

					// 鍒ゆ柇鏄惁蹇呭～,闈炲繀濉紝涓嶅～涓嶆牎楠岋紝濉啓鎵嶆牎楠?,鏆傛椂鍙鐞?undefined  鍜岀┖鐨勬儏鍐?
					if (!isRequiredField && (value === undefined || value === '')) {
						result = null;
					}

					// 鍒ゆ柇閿欒淇℃伅鏄剧ず绫诲瀷
					if (result && result.errorMessage) {
						if (errShowType === 'undertext') {
							// 鑾峰彇閿欒淇℃伅
							this.errMsg = !result ? '' : result.errorMessage;
						}
						if (errShowType === 'toast') {
							uni.showToast({
								title: result.errorMessage || '鏍￠獙閿欒',
								icon: 'none'
							});
						}
						if (errShowType === 'modal') {
							uni.showModal({
								title: '鎻愮ず',
								content: result.errorMessage || '鏍￠獙閿欒'
							});
						}
					} else {
						this.errMsg = ''
					}
					// 閫氱煡 form 缁勪欢鏇存柊浜嬩欢
					validateCheck(result ? result : null)
				} else {
					this.errMsg = ''
				}
				return result ? result : null;
			},
			/**
			 * 鍒濆缁勪欢鏁版嵁
			 */
			init(type = false) {
				const {
					validator,
					formRules,
					childrens,
					formData,
					localData,
					_realName,
					labelWidth,
					_getDataValue,
					_setDataValue
				} = this.form || {}
				// 瀵归綈鏂瑰紡
				this.localLabelAlign = this._justifyContent()
				// 瀹藉害
				this.localLabelWidth = this._labelWidthUnit(labelWidth)
				// 鏍囩浣嶇疆
				this.localLabelPos = this._labelPosition()
				// 灏嗛渶瑕佹牎楠岀殑瀛愮粍浠跺姞鍏orm 闃熷垪
				this.form && type && childrens.push(this)

				if (!validator || !formRules) return
				// 鍒ゆ柇绗竴涓?item
				if (!this.form.isFirstBorder) {
					this.form.isFirstBorder = true;
					this.isFirstBorder = true;
				}

				// 鍒ゆ柇 group 閲岀殑绗竴涓?item
				if (this.group) {
					if (!this.group.isFirstBorder) {
						this.group.isFirstBorder = true;
						this.isFirstBorder = true;
					}
				}
				this.border = this.form.border;
				// 鑾峰彇瀛愬煙鐨勭湡瀹炲悕绉?
				const name = _realName(this.name)
				const itemRule = this.userRules || this.rules
				if (typeof formRules === 'object' && itemRule) {
					// 瀛愯鍒欐浛鎹㈢埗瑙勫垯
					formRules[name] = {
						rules: itemRule
					}
					validator.updateSchema(formRules);
				}
				// 娉ㄥ唽鏍￠獙瑙勫垯
				const itemRules = formRules[name] || {}
				this.itemRules = itemRules
				// 娉ㄥ唽鏍￠獙鍑芥暟
				this.validator = validator
				// 榛樿鍊艰祴浜?
				this.itemSetValue(_getDataValue(this.name, localData))
			},
			unInit() {
				if (this.form) {
					const {
						childrens,
						formData,
						_realName
					} = this.form
					childrens.forEach((item, index) => {
						if (item === this) {
							this.form.childrens.splice(index, 1)
							delete formData[_realName(item.name)]
						}
					})
				}
			},
			// 璁剧疆item 鐨勫€?
			itemSetValue(value) {
				const name = this.form._realName(this.name)
				const rules = this.itemRules.rules || []
				const val = this.form._getValue(name, value, rules)
				this.form._setDataValue(name, this.form.formData, val)
				return val
			},

			/**
			 * 绉婚櫎璇ヨ〃鍗曢」鐨勬牎楠岀粨鏋?
			 */
			clearValidate() {
				this.errMsg = '';
			},

			// 鏄惁鏄剧ず鏄熷彿
			_isRequired() {
				// TODO 涓嶆牴鎹鍒欐樉绀?鏄熷彿锛岃€冭檻鍚庣画鍏煎
				// if (this.form) {
				// 	if (this.form._isRequiredField(this.itemRules.rules || []) && this.required) {
				// 		return true
				// 	}
				// 	return false
				// }
				return this.required
			},

			// 澶勭悊瀵归綈鏂瑰紡
			_justifyContent() {
				if (this.form) {
					const {
						labelAlign
					} = this.form
					let labelAli = this.labelAlign ? this.labelAlign : labelAlign;
					if (labelAli === 'left') return 'flex-start';
					if (labelAli === 'center') return 'center';
					if (labelAli === 'right') return 'flex-end';
				}
				return 'flex-start';
			},
			// 澶勭悊 label瀹藉害鍗曚綅 ,缁ф壙鐖跺厓绱犵殑鍊?
			_labelWidthUnit(labelWidth) {

				// if (this.form) {
				// 	const {
				// 		labelWidth
				// 	} = this.form
				return this.num2px(this.labelWidth ? this.labelWidth : (labelWidth || (this.label ? 70 : 'auto')))
				// }
				// return '70px'
			},
			// 澶勭悊 label 浣嶇疆
			_labelPosition() {
				if (this.form) return this.form.labelPosition || 'left'
				return 'left'

			},

			/**
			 * 瑙﹀彂鏃舵満
			 * @param {Object} rule 褰撳墠瑙勫垯鍐呮椂鏈?
			 * @param {Object} itemRlue 褰撳墠缁勪欢鏃舵満
			 * @param {Object} parentRule 鐖剁粍浠舵椂鏈?
			 */
			isTrigger(rule, itemRlue, parentRule) {
				//  bind  submit
				if (rule === 'submit' || !rule) {
					if (rule === undefined) {
						if (itemRlue !== 'bind') {
							if (!itemRlue) {
								return parentRule === '' ? 'bind' : 'submit';
							}
							return 'submit';
						}
						return 'bind';
					}
					return 'submit';
				}
				return 'bind';
			},
			num2px(num) {
				if (typeof num === 'number') {
					return `${num}px`
				}
				return num
			}
		}
	};
</script>

<style lang="scss">
	.uni-forms-item {
		position: relative;
		display: flex;
		/* #ifdef APP-NVUE */
		// 鍦?nvue 涓紝浣跨敤 margin-bottom error 淇℃伅浼氳闅愯棌
		padding-bottom: 22px;
		/* #endif */
		/* #ifndef APP-NVUE */
		margin-bottom: 22px;
		/* #endif */
		flex-direction: row;

		&__label {
			display: flex;
			flex-direction: row;
			align-items: center;
			text-align: left;
			font-size: 14px;
			color: #606266;
			height: 36px;
			padding: 0 12px 0 0;
			/* #ifndef APP-NVUE */
			vertical-align: middle;
			flex-shrink: 0;
			/* #endif */

			/* #ifndef APP-NVUE */
			box-sizing: border-box;

			/* #endif */
			&.no-label {
				padding: 0;
			}
		}

		&__content {
			/* #ifndef MP-TOUTIAO */
			// display: flex;
			// align-items: center;
			/* #endif */
			position: relative;
			font-size: 14px;
			flex: 1;
			/* #ifndef APP-NVUE */
			box-sizing: border-box;
			/* #endif */
			flex-direction: row;

			/* #ifndef APP || H5 || MP-WEIXIN || APP-NVUE */
			// TODO 鍥犱负灏忕▼搴忓钩鍙颁細澶氫竴灞傛爣绛捐妭鐐?锛屾墍浠ラ渶瑕佸湪澶氫綑鑺傜偣缁ф壙褰撳墠鏍峰紡
			&>uni-easyinput,
			&>uni-data-picker {
				width: 100%;
			}

			/* #endif */

		}

		& .uni-forms-item__nuve-content {
			display: flex;
			flex-direction: column;
			flex: 1;
		}

		&__error {
			color: #f56c6c;
			font-size: 12px;
			line-height: 1;
			padding-top: 4px;
			position: absolute;
			/* #ifndef APP-NVUE */
			top: 100%;
			left: 0;
			transition: transform 0.3s;
			transform: translateY(-100%);
			/* #endif */
			/* #ifdef APP-NVUE */
			bottom: 5px;
			/* #endif */

			opacity: 0;

			.error-text {
				// 鍙湁 nvue 涓嬭繖涓牱寮忔墠鐢熸晥
				color: #f56c6c;
				font-size: 12px;
			}

			&.msg--active {
				opacity: 1;
				transform: translateY(0%);
			}
		}

		// 浣嶇疆淇グ鏍峰紡
		&.is-direction-left {
			flex-direction: row;
		}

		&.is-direction-top {
			flex-direction: column;

			.uni-forms-item__label {
				padding: 0 0 8px;
				line-height: 1.5715;
				text-align: left;
				/* #ifndef APP-NVUE */
				white-space: initial;
				/* #endif */
			}
		}

		.is-required {
			// color: $uni-color-error;
			color: #dd524d;
			font-weight: bold;
		}
	}


	.uni-forms-item--border {
		margin-bottom: 0;
		padding: 10px 0;
		// padding-bottom: 0;
		border-top: 1px #eee solid;

		/* #ifndef APP-NVUE */
		.uni-forms-item__content {
			flex-direction: column;
			justify-content: flex-start;
			align-items: flex-start;

			.uni-forms-item__error {
				position: relative;
				top: 5px;
				left: 0;
				padding-top: 0;
			}
		}

		/* #endif */

		/* #ifdef APP-NVUE */
		display: flex;
		flex-direction: column;

		.uni-forms-item__error {
			position: relative;
			top: 0px;
			left: 0;
			padding-top: 0;
			margin-top: 5px;
		}

		/* #endif */

	}

	.is-first-border {
		/* #ifndef APP-NVUE */
		border: none;
		/* #endif */
		/* #ifdef APP-NVUE */
		border-width: 0;
		/* #endif */
	}
</style>


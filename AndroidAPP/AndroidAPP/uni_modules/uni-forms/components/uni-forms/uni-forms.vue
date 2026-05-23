<template>
	<view class="uni-forms">
		<form>
			<slot></slot>
		</form>
	</view>
</template>

<script>
	import Validator from './validate.js';
	import {
		deepCopy,
		getValue,
		isRequiredField,
		setDataValue,
		getDataValue,
		realName,
		isRealName,
		rawData,
		isEqual
	} from './utils.js'

	// #ifndef VUE3
	// 鍚庣画浼氭參鎱㈠簾寮冭繖涓柟娉?
	import Vue from 'vue';
	Vue.prototype.binddata = function(name, value, formName) {
		if (formName) {
			this.$refs[formName].setValue(name, value);
		} else {
			let formVm;
			for (let i in this.$refs) {
				const vm = this.$refs[i];
				if (vm && vm.$options && vm.$options.name === 'uniForms') {
					formVm = vm;
					break;
				}
			}
			if (!formVm) return console.error('褰撳墠 uni-froms 缁勪欢缂哄皯 ref 灞炴€?);
			formVm.setValue(name, value);
		}
	};
	// #endif
	/**
	 * Forms 琛ㄥ崟
	 * @description 鐢辫緭鍏ユ銆侀€夋嫨鍣ㄣ€佸崟閫夋銆佸閫夋绛夋帶浠剁粍鎴愶紝鐢ㄤ互鏀堕泦銆佹牎楠屻€佹彁浜ゆ暟鎹?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=2773
	 * @property {Object} rules	琛ㄥ崟鏍￠獙瑙勫垯
	 * @property {String} validateTrigger = [bind|submit|blur]	鏍￠獙瑙﹀彂鍣ㄦ柟寮?榛樿 submit
	 * @value bind		鍙戠敓鍙樺寲鏃惰Е鍙?
	 * @value submit	鎻愪氦鏃惰Е鍙?
	 * @value blur	  澶卞幓鐒︾偣鏃惰Е鍙?
	 * @property {String} labelPosition = [top|left]	label 浣嶇疆 榛樿 left
	 * @value top		椤堕儴鏄剧ず label
	 * @value left	宸︿晶鏄剧ず label
	 * @property {String} labelWidth	label 瀹藉害锛岄粯璁?70px
	 * @property {String} labelAlign = [left|center|right]	label 灞呬腑鏂瑰紡  榛樿 left
	 * @value left		label 宸︿晶鏄剧ず
	 * @value center	label 灞呬腑
	 * @value right		label 鍙充晶瀵归綈
	 * @property {String} errShowType = [undertext|toast|modal]	鏍￠獙閿欒淇℃伅鎻愮ず鏂瑰紡
	 * @value undertext	閿欒淇℃伅鍦ㄥ簳閮ㄦ樉绀?
	 * @value toast			閿欒淇℃伅toast鏄剧ず
	 * @value modal			閿欒淇℃伅modal鏄剧ず
	 * @event {Function} submit	鎻愪氦鏃惰Е鍙?
	 * @event {Function} validate	鏍￠獙缁撴灉鍙戠敓鍙樺寲瑙﹀彂
	 */
	export default {
		name: 'uniForms',
		emits: ['validate', 'submit'],
		options: {
			// #ifdef MP-TOUTIAO
			virtualHost: false,
			// #endif
			// #ifndef MP-TOUTIAO
			virtualHost: true
			// #endif
		},
		props: {
			// 鍗冲皢寮冪敤
			value: {
				type: Object,
				default () {
					return null;
				}
			},
			// vue3 鏇挎崲 value 灞炴€?
			modelValue: {
				type: Object,
				default () {
					return null;
				}
			},
			// 1.4.0 寮€濮嬪皢涓嶆敮鎸?v-model 锛屼笖搴熷純 value 鍜?modelValue
			model: {
				type: Object,
				default () {
					return null;
				}
			},
			// 琛ㄥ崟鏍￠獙瑙勫垯
			rules: {
				type: Object,
				default () {
					return {};
				}
			},
			//鏍￠獙閿欒淇℃伅鎻愮ず鏂瑰紡 榛樿 undertext 鍙栧€?[undertext|toast|modal]
			errShowType: {
				type: String,
				default: 'undertext'
			},
			// 鏍￠獙瑙﹀彂鍣ㄦ柟寮?榛樿 bind 鍙栧€?[bind|submit]
			validateTrigger: {
				type: String,
				default: 'submit'
			},
			// label 浣嶇疆锛岄粯璁?left 鍙栧€? top/left
			labelPosition: {
				type: String,
				default: 'left'
			},
			// label 瀹藉害
			labelWidth: {
				type: [String, Number],
				default: ''
			},
			// label 灞呬腑鏂瑰紡锛岄粯璁?left 鍙栧€?left/center/right
			labelAlign: {
				type: String,
				default: 'left'
			},
			border: {
				type: Boolean,
				default: false
			}
		},
		provide() {
			return {
				uniForm: this
			}
		},
		data() {
			return {
				// 琛ㄥ崟鏈湴鍊肩殑璁板綍锛屼笉搴旇涓庝紶濡傜殑鍊艰繘琛屽叧鑱?
				formData: {},
				formRules: {}
			};
		},
		computed: {
			// 璁＄畻鏁版嵁婧愬彉鍖栫殑
			localData() {
				const localVal = this.model || this.modelValue || this.value
				if (localVal) {
					return deepCopy(localVal)
				}
				return {}
			}
		},
		watch: {
			// 鐩戝惉鏁版嵁鍙樺寲 ,鏆傛椂涓嶄娇鐢紝闇€瑕佸崟鐙祴鍊?
			// localData: {},
			// 鐩戝惉瑙勫垯鍙樺寲
			rules: {
				handler: function(val, oldVal) {
					this.setRules(val)
				},
				deep: true,
				immediate: true
			}
		},
		created() {
			// #ifdef VUE3
			let getbinddata = getApp().$vm.$.appContext.config.globalProperties.binddata
			if (!getbinddata) {
				getApp().$vm.$.appContext.config.globalProperties.binddata = function(name, value, formName) {
					if (formName) {
						this.$refs[formName].setValue(name, value);
					} else {
						let formVm;
						for (let i in this.$refs) {
							const vm = this.$refs[i];
							if (vm && vm.$options && vm.$options.name === 'uniForms') {
								formVm = vm;
								break;
							}
						}
						if (!formVm) return console.error('褰撳墠 uni-froms 缁勪欢缂哄皯 ref 灞炴€?);
						if(formVm.model)formVm.model[name] = value
						if(formVm.modelValue)formVm.modelValue[name] = value
						if(formVm.value)formVm.value[name] = value
					}
				}
			}
			// #endif

			// 瀛愮粍浠跺疄渚嬫暟缁?
			this.childrens = []
			// TODO 鍏煎鏃х増 uni-data-picker ,鏂扮増鏈腑鏃犳晥锛屽彧鏄伩鍏嶆姤閿?
			this.inputChildrens = []
			this.setRules(this.rules)
		},
		methods: {
			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 璁剧疆瑙勫垯 锛屼富瑕佺敤浜庡皬绋嬪簭鑷畾涔夋楠岃鍒?
			 * @param {Array} rules 瑙勫垯婧愭暟鎹?
			 */
			setRules(rules) {
				// TODO 鏈夊彲鑳藉瓙缁勪欢鍚堝苟瑙勫垯鐨勬椂鏈烘瘮杩欎釜瑕佹棭锛屾墍浠ラ渶瑕佸悎骞跺璞?锛岃€屼笉鏄洿鎺ヨ祴鍊硷紝鍙兘浼氳瑕嗙洊
				this.formRules = Object.assign({}, this.formRules, rules)
				// 鍒濆鍖栨牎楠屽嚱鏁?
				this.validator = new Validator(rules);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 璁剧疆鏁版嵁锛岀敤浜庤缃〃鍗曟暟鎹紝鍏紑缁欑敤鎴蜂娇鐢?锛?涓嶆敮鎸佸湪鍔ㄦ€佽〃鍗曚腑浣跨敤
			 * @param {Object} key
			 * @param {Object} value
			 */
			setValue(key, value) {
				let example = this.childrens.find(child => child.name === key);
				if (!example) return null;
				this.formData[key] = getValue(key, value, (this.formRules[key] && this.formRules[key].rules) || [])
				return example.onFieldChange(this.formData[key]);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 鎵嬪姩鎻愪氦鏍￠獙琛ㄥ崟
			 * 瀵规暣涓〃鍗曡繘琛屾牎楠岀殑鏂规硶锛屽弬鏁颁负涓€涓洖璋冨嚱鏁般€?
			 * @param {Array} keepitem 淇濈暀涓嶅弬涓庢牎楠岀殑瀛楁
			 * @param {type} callback 鏂规硶鍥炶皟
			 */
			validate(keepitem, callback) {
				return this.checkAll(this.formData, keepitem, callback);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 閮ㄥ垎琛ㄥ崟鏍￠獙
			 * @param {Array|String} props 闇€瑕佹牎楠岀殑瀛楁
			 * @param {Function} 鍥炶皟鍑芥暟
			 */
			validateField(props = [], callback) {
				props = [].concat(props);
				let invalidFields = {};
				this.childrens.forEach(item => {
					const name = realName(item.name)
					if (props.indexOf(name) !== -1) {
						invalidFields = Object.assign({}, invalidFields, {
							[name]: this.formData[name]
						});
					}
				});
				return this.checkAll(invalidFields, [], callback);
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶
			 * 绉婚櫎琛ㄥ崟椤圭殑鏍￠獙缁撴灉銆備紶鍏ュ緟绉婚櫎鐨勮〃鍗曢」鐨?prop 灞炴€ф垨鑰?prop 缁勬垚鐨勬暟缁勶紝濡備笉浼犲垯绉婚櫎鏁翠釜琛ㄥ崟鐨勬牎楠岀粨鏋?
			 * @param {Array|String} props 闇€瑕佺Щ闄ゆ牎楠岀殑瀛楁 锛屼笉濉负鎵€鏈?
			 */
			clearValidate(props = []) {
				props = [].concat(props);
				this.childrens.forEach(item => {
					if (props.length === 0) {
						item.errMsg = '';
					} else {
						const name = realName(item.name)
						if (props.indexOf(name) !== -1) {
							item.errMsg = '';
						}
					}
				});
			},

			/**
			 * 澶栭儴璋冪敤鏂规硶 锛屽嵆灏嗗簾寮?
			 * 鎵嬪姩鎻愪氦鏍￠獙琛ㄥ崟
			 * 瀵规暣涓〃鍗曡繘琛屾牎楠岀殑鏂规硶锛屽弬鏁颁负涓€涓洖璋冨嚱鏁般€?
			 * @param {Array} keepitem 淇濈暀涓嶅弬涓庢牎楠岀殑瀛楁
			 * @param {type} callback 鏂规硶鍥炶皟
			 */
			submit(keepitem, callback, type) {
				for (let i in this.dataValue) {
					const itemData = this.childrens.find(v => v.name === i);
					if (itemData) {
						if (this.formData[i] === undefined) {
							this.formData[i] = this._getValue(i, this.dataValue[i]);
						}
					}
				}

				if (!type) {
					console.warn('submit 鏂规硶鍗冲皢搴熷純锛岃浣跨敤validate鏂规硶浠ｆ浛锛?);
				}

				return this.checkAll(this.formData, keepitem, callback, 'submit');
			},

			// 鏍￠獙鎵€鏈?
			async checkAll(invalidFields, keepitem, callback, type) {
				// 涓嶅瓨鍦ㄦ牎楠岃鍒?锛屽垯鍋滄鏍￠獙娴佺▼
				if (!this.validator) return
				let childrens = []
				// 澶勭悊鍙備笌鏍￠獙鐨刬tem瀹炰緥
				for (let i in invalidFields) {
					const item = this.childrens.find(v => realName(v.name) === i)
					if (item) {
						childrens.push(item)
					}
				}

				// 濡傛灉validate绗竴涓弬鏁版槸funciont ,閭ｅ氨璧板洖璋?
				if (!callback && typeof keepitem === 'function') {
					callback = keepitem;
				}

				let promise;
				// 濡傛灉涓嶅瓨鍦ㄥ洖璋冿紝閭ｄ箞浣跨敤 Promise 鏂瑰紡杩斿洖
				if (!callback && typeof callback !== 'function' && Promise) {
					promise = new Promise((resolve, reject) => {
						callback = function(valid, invalidFields) {
							!valid ? resolve(invalidFields) : reject(valid);
						};
					});
				}

				let results = [];
				// 閬垮厤寮曠敤閿欎贡 锛屽缓璁嫹璐濆璞″鐞?
				let tempFormData = JSON.parse(JSON.stringify(invalidFields))
				// 鎵€鏈夊瓙缁勪欢鍙備笌鏍￠獙,浣跨敤 for 鍙互浣跨敤  awiat
				for (let i in childrens) {
					const child = childrens[i]
					let name = realName(child.name);
					const result = await child.onFieldChange(tempFormData[name]);
					if (result) {
						results.push(result);
						// toast ,modal 鍙渶瑕佹墽琛岀涓€娆″氨鍙互
						if (this.errShowType === 'toast' || this.errShowType === 'modal') break;
					}
				}


				if (Array.isArray(results)) {
					if (results.length === 0) results = null;
				}
				if (Array.isArray(keepitem)) {
					keepitem.forEach(v => {
						let vName = realName(v);
						let value = getDataValue(v, this.localData)
						if (value !== undefined) {
							tempFormData[vName] = value
						}
					});
				}

				// TODO submit 鍗冲皢搴熷純
				if (type === 'submit') {
					this.$emit('submit', {
						detail: {
							value: tempFormData,
							errors: results
						}
					});
				} else {
					this.$emit('validate', results);
				}

				// const resetFormData = rawData(tempFormData, this.localData, this.name)
				let resetFormData = {}
				resetFormData = rawData(tempFormData, this.name)
				callback && typeof callback === 'function' && callback(results, resetFormData);

				if (promise && callback) {
					return promise;
				} else {
					return null;
				}

			},

			/**
			 * 杩斿洖validate浜嬩欢
			 * @param {Object} result
			 */
			validateCheck(result) {
				this.$emit('validate', result);
			},
			_getValue: getValue,
			_isRequiredField: isRequiredField,
			_setDataValue: setDataValue,
			_getDataValue: getDataValue,
			_realName: realName,
			_isRealName: isRealName,
			_isEqual: isEqual
		}
	};
</script>

<style lang="scss">
	.uni-forms {}
</style>


<template>
	<view class="uni-searchbar">
		<view :style="{borderRadius:radius+'px',backgroundColor: bgColor}" class="uni-searchbar__box"
			@click="searchClick">
			<view class="uni-searchbar__box-icon-search">
				<slot name="searchIcon">
					<uni-icons color="#c0c4cc" size="18" type="search" />
				</slot>
			</view>
			<input v-if="show || searchVal" :focus="showSync" :disabled="readonly" :placeholder="placeholderText" :maxlength="maxlength"
				class="uni-searchbar__box-search-input" confirm-type="search" type="text" v-model="searchVal" :style="{color:textColor}"
				@confirm="confirm" @blur="blur" @focus="emitFocus"/>
			<text v-else class="uni-searchbar__text-placeholder">{{ placeholder }}</text>
			<view v-if="show && (clearButton==='always'||clearButton==='auto'&&searchVal!=='') &&!readonly"
				class="uni-searchbar__box-icon-clear" @click="clear">
				<slot name="clearIcon">
					<uni-icons color="#c0c4cc" size="20" type="clear" />
				</slot>
			</view>
		</view>
		<text @click="cancel" class="uni-searchbar__cancel"
			v-if="cancelButton ==='always' || show && cancelButton ==='auto'">{{cancelTextI18n}}</text>
	</view>
</template>

<script>
	import {
		initVueI18n
	} from '@dcloudio/uni-i18n'
	import messages from './i18n/index.js'
	const {
		t
	} = initVueI18n(messages)

	/**
	 * SearchBar 鎼滅储鏍?
	 * @description 鎼滅储鏍忕粍浠讹紝閫氬父鐢ㄤ簬鎼滅储鍟嗗搧銆佹枃绔犵瓑
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=866
	 * @property {Number} radius 鎼滅储鏍忓渾瑙?
	 * @property {Number} maxlength 杈撳叆鏈€澶ч暱搴?
	 * @property {String} placeholder 鎼滅储鏍廝laceholder
	 * @property {String} clearButton = [always|auto|none] 鏄惁鏄剧ず娓呴櫎鎸夐挳
	 * 	@value always 涓€鐩存樉绀?
	 * 	@value auto 杈撳叆妗嗕笉涓虹┖鏃舵樉绀?
	 * 	@value none 涓€鐩翠笉鏄剧ず
	 * @property {String} cancelButton = [always|auto|none] 鏄惁鏄剧ず鍙栨秷鎸夐挳
	 * 	@value always 涓€鐩存樉绀?
	 * 	@value auto 杈撳叆妗嗕笉涓虹┖鏃舵樉绀?
	 * 	@value none 涓€鐩翠笉鏄剧ず
	 * @property {String} cancelText 鍙栨秷鎸夐挳鐨勬枃瀛?
	 * @property {String} bgColor 杈撳叆妗嗚儗鏅鑹?
	 * @property {String} textColor 杈撳叆鏂囧瓧棰滆壊
	 * @property {Boolean} focus 鏄惁鑷姩鑱氱劍
	 * @property {Boolean} readonly 缁勪欢鍙锛屼笉鑳芥湁浠讳綍鎿嶄綔锛屽彧鍋氬睍绀?
	 * @event {Function} confirm uniSearchBar 鐨勮緭鍏ユ confirm 浜嬩欢锛岃繑鍥炲弬鏁颁负uniSearchBar鐨剉alue锛宔={value:Number}
	 * @event {Function} input uniSearchBar 鐨?value 鏀瑰彉鏃惰Е鍙戜簨浠讹紝杩斿洖鍙傛暟涓簎niSearchBar鐨剉alue锛宔=value
	 * @event {Function} cancel 鐐瑰嚮鍙栨秷鎸夐挳鏃惰Е鍙戜簨浠讹紝杩斿洖鍙傛暟涓簎niSearchBar鐨剉alue锛宔={value:Number}
	 * @event {Function} clear 鐐瑰嚮娓呴櫎鎸夐挳鏃惰Е鍙戜簨浠讹紝杩斿洖鍙傛暟涓簎niSearchBar鐨剉alue锛宔={value:Number}
	 * @event {Function} blur input澶卞幓鐒︾偣鏃惰Е鍙戜簨浠讹紝杩斿洖鍙傛暟涓簎niSearchBar鐨剉alue锛宔={value:Number}
	 */

	export default {
		name: "UniSearchBar",
		emits: ['input', 'update:modelValue', 'clear', 'cancel', 'confirm', 'blur', 'focus'],
		props: {
			placeholder: {
				type: String,
				default: ""
			},
			radius: {
				type: [Number, String],
				default: 5
			},
			clearButton: {
				type: String,
				default: "auto"
			},
			cancelButton: {
				type: String,
				default: "auto"
			},
			cancelText: {
				type: String,
				default: ""
			},
			bgColor: {
				type: String,
				default: "#F8F8F8"
			},
			textColor: {
				type: String,
				default: "#000000"
			},
			maxlength: {
				type: [Number, String],
				default: 100
			},
			value: {
				type: [Number, String],
				default: ""
			},
			modelValue: {
				type: [Number, String],
				default: ""
			},
			focus: {
				type: Boolean,
				default: false
			},
			readonly: {
				type: Boolean,
				default: false
			}
		},
		data() {
			return {
				show: false,
				showSync: false,
				searchVal: ''
			}
		},
		computed: {
			cancelTextI18n() {
				return this.cancelText || t("uni-search-bar.cancel")
			},
			placeholderText() {
				return this.placeholder || t("uni-search-bar.placeholder")
			}
		},
		watch: {
			// #ifndef VUE3
			value: {
				immediate: true,
				handler(newVal) {
					this.searchVal = newVal
					if (newVal) {
						this.show = true
					}
				}
			},
			// #endif
			// #ifdef VUE3
			modelValue: {
				immediate: true,
				handler(newVal) {
					this.searchVal = newVal
					if (newVal) {
						this.show = true
					}
				}
			},
			// #endif
			focus: {
				immediate: true,
				handler(newVal) {
					if (newVal) {
						if(this.readonly) return
						this.show = true;
						this.$nextTick(() => {
							this.showSync = true
						})
					}
				}
			},
			searchVal(newVal, oldVal) {
				this.$emit("input", newVal)
				// #ifdef VUE3
				this.$emit("update:modelValue", newVal)
				// #endif
			}
		},
		methods: {
			searchClick() {
				if(this.readonly) return
				if (this.show) {
					return
				}
				this.show = true;
				this.$nextTick(() => {
					this.showSync = true
				})
			},
			clear() {
				this.searchVal = ""
				this.$nextTick(() => {
					this.$emit("clear", { value: "" })
				})
			},
			cancel() {
				if(this.readonly) return
				this.$emit("cancel", {
					value: this.searchVal
				});
				this.searchVal = ""
				this.show = false
				this.showSync = false
				// #ifndef APP-PLUS
				uni.hideKeyboard()
				// #endif
				// #ifdef APP-PLUS
				plus.key.hideSoftKeybord()
				// #endif
			},
			confirm() {
				// #ifndef APP-PLUS
				uni.hideKeyboard();
				// #endif
				// #ifdef APP-PLUS
				plus.key.hideSoftKeybord()
				// #endif
				this.$emit("confirm", {
					value: this.searchVal
				})
			},
			blur() {
				// #ifndef APP-PLUS
				uni.hideKeyboard();
				// #endif
				// #ifdef APP-PLUS
				plus.key.hideSoftKeybord()
				// #endif
				this.$emit("blur", {
					value: this.searchVal
				})
			},
			emitFocus(e) {
				this.$emit("focus", e.detail)
			}
		}
	};
</script>

<style lang="scss">
	$uni-searchbar-height: 36px;

	.uni-searchbar {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		position: relative;
		padding: 10px;
		// background-color: #fff;
	}

	.uni-searchbar__box {
		/* #ifndef APP-NVUE */
		display: flex;
		box-sizing: border-box;
		justify-content: left;
		/* #endif */
		overflow: hidden;
		position: relative;
		flex: 1;
		flex-direction: row;
		align-items: center;
		height: $uni-searchbar-height;
		padding: 5px 8px 5px 0px;
	}

	.uni-searchbar__box-icon-search {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		// width: 32px;
		padding: 0 8px;
		justify-content: center;
		align-items: center;
		color: #B3B3B3;
	}

	.uni-searchbar__box-search-input {
		flex: 1;
		font-size: 14px;
		color: #333;
		margin-left: 5px;
		margin-top: 1px;
		/* #ifndef APP-NVUE */
		background-color: inherit;
		/* #endif */
	}

	.uni-searchbar__box-icon-clear {
		align-items: center;
		line-height: 24px;
		padding-left: 8px;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.uni-searchbar__text-placeholder {
		font-size: 14px;
		color: #B3B3B3;
		margin-left: 5px;
		text-align: left;
	}

	.uni-searchbar__cancel {
		padding-left: 10px;
		line-height: $uni-searchbar-height;
		font-size: 14px;
		color: #333333;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}
</style>


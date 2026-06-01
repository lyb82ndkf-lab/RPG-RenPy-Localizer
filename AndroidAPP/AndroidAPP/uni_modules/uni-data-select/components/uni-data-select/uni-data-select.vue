<template>
	<view class="uni-stat__select">
		<span v-if="label" class="uni-label-text hide-on-phone">{{label + '锛?}}</span>
		<view class="uni-stat-box" :class="{'uni-stat__actived': current}">
			<view class="uni-select" :class="{'uni-select--disabled':disabled}">
				<view class="uni-select__input-box" @click="toggleSelector">
					<view v-if="current" class="uni-select__input-text">{{textShow}}</view>
					<view v-else class="uni-select__input-text uni-select__input-placeholder">{{typePlaceholder}}</view>
					<view v-if="current && clear && !disabled" @click.stop="clearVal">
						<uni-icons type="clear" color="#c0c4cc" size="24" />
					</view>
					<view v-else>
						<uni-icons :type="showSelector? 'top' : 'bottom'" size="14" color="#999" />
					</view>
				</view>
				<view class="uni-select--mask" v-if="showSelector" @click="toggleSelector" />
				<view class="uni-select__selector" :style="getOffsetByPlacement" v-if="showSelector">
					<view :class="placement=='bottom'?'uni-popper__arrow_bottom':'uni-popper__arrow_top'"></view>
					<scroll-view scroll-y="true" class="uni-select__selector-scroll">
						<view class="uni-select__selector-empty" v-if="mixinDatacomResData.length === 0">
							<text>{{emptyTips}}</text>
						</view>
						<view v-else class="uni-select__selector-item" v-for="(item,index) in mixinDatacomResData" :key="index"
							@click="change(item)">
							<text :class="{'uni-select__selector__disabled': item.disable}">{{formatItemName(item)}}</text>
						</view>
					</scroll-view>
				</view>
			</view>
		</view>
	</view>
</template>

<script>
	/**
	 * DataChecklist 鏁版嵁閫夋嫨鍣?
	 * @description 閫氳繃鏁版嵁娓叉煋鐨勪笅鎷夋缁勪欢
	 * @tutorial https://uniapp.dcloud.io/component/uniui/uni-data-select
	 * @property {String} value 榛樿鍊?
	 * @property {Array} localdata 鏈湴鏁版嵁 锛屾牸寮?[{text:'',value:''}]
	 * @property {Boolean} clear 鏄惁鍙互娓呯┖宸查€夐」
	 * @property {Boolean} emptyText 娌℃湁鏁版嵁鏃舵樉绀虹殑鏂囧瓧 锛屾湰鍦版暟鎹棤鏁?
	 * @property {String} label 宸︿晶鏍囬
	 * @property {String} placeholder 杈撳叆妗嗙殑鎻愮ず鏂囧瓧
	 * @property {Boolean} disabled 鏄惁绂佺敤
	 * @property {String} placement 寮瑰嚭浣嶇疆
	 * 	@value top   		椤堕儴寮瑰嚭
	 * 	@value bottom		搴曢儴寮瑰嚭锛坉efault)
	 * @event {Function} change  閫変腑鍙戠敓鍙樺寲瑙﹀彂
	 */

	export default {
		name: "uni-data-select",
		mixins: [uniCloud.mixinDatacom || {}],
		props: {
			localdata: {
				type: Array,
				default () {
					return []
				}
			},
			value: {
				type: [String, Number],
				default: ''
			},
			modelValue: {
				type: [String, Number],
				default: ''
			},
			label: {
				type: String,
				default: ''
			},
			placeholder: {
				type: String,
				default: '璇烽€夋嫨'
			},
			emptyTips: {
				type: String,
				default: '鏃犻€夐」'
			},
			clear: {
				type: Boolean,
				default: true
			},
			defItem: {
				type: Number,
				default: 0
			},
			disabled: {
				type: Boolean,
				default: false
			},
			// 鏍煎紡鍖栬緭鍑?鐢ㄦ硶 field="_id as value, version as text, uni_platform as label" format="{label} - {text}"
			format: {
				type: String,
				default: ''
			},
			placement: {
				type: String,
				default: 'bottom'
			}
		},
		data() {
			return {
				showSelector: false,
				current: '',
				mixinDatacomResData: [],
				apps: [],
				channels: [],
				cacheKey: "uni-data-select-lastSelectedValue",
			};
		},
		created() {
			this.debounceGet = this.debounce(() => {
				this.query();
			}, 300);
			if (this.collection && !this.localdata.length) {
				this.debounceGet();
			}
		},
		computed: {
			typePlaceholder() {
				const text = {
					'opendb-stat-app-versions': '鐗堟湰',
					'opendb-app-channels': '娓犻亾',
					'opendb-app-list': '搴旂敤'
				}
				const common = this.placeholder
				const placeholder = text[this.collection]
				return placeholder ?
					common + placeholder :
					common
			},
			valueCom() {
				// #ifdef VUE3
				return this.modelValue;
				// #endif
				// #ifndef VUE3
				return this.value;
				// #endif
			},
			textShow() {
				// 闀挎枃鏈樉绀?
				let text = this.current;
				if (text.length > 10) {
					return text.slice(0, 25) + '...';
				}
				return text;
			},
			getOffsetByPlacement() {
				switch (this.placement) {
					case 'top':
						return "bottom:calc(100% + 12px);";
					case 'bottom':
						return "top:calc(100% + 12px);";
				}
			}
		},

		watch: {
			localdata: {
				immediate: true,
				handler(val, old) {
					if (Array.isArray(val) && old !== val) {
						this.mixinDatacomResData = val
					}
				}
			},
			valueCom(val, old) {
				this.initDefVal()
			},
			mixinDatacomResData: {
				immediate: true,
				handler(val) {
					if (val.length) {
						this.initDefVal()
					}
				}
			},

		},
		methods: {
			debounce(fn, time = 100) {
				let timer = null
				return function(...args) {
					if (timer) clearTimeout(timer)
					timer = setTimeout(() => {
						fn.apply(this, args)
					}, time)
				}
			},
			// 鎵ц鏁版嵁搴撴煡璇?
			query() {
				this.mixinDatacomEasyGet();
			},
			// 鐩戝惉鏌ヨ鏉′欢鍙樻洿浜嬩欢
			onMixinDatacomPropsChange() {
				if (this.collection) {
					this.debounceGet();
				}
			},
			initDefVal() {
				let defValue = ''
				if ((this.valueCom || this.valueCom === 0) && !this.isDisabled(this.valueCom)) {
					defValue = this.valueCom
				} else {
					let strogeValue
					if (this.collection) {
						strogeValue = this.getCache()
					}
					if (strogeValue || strogeValue === 0) {
						defValue = strogeValue
					} else {
						let defItem = ''
						if (this.defItem > 0 && this.defItem <= this.mixinDatacomResData.length) {
							defItem = this.mixinDatacomResData[this.defItem - 1].value
						}
						defValue = defItem
					}
					if (defValue || defValue === 0) {
						this.emit(defValue)
					}
				}
				const def = this.mixinDatacomResData.find(item => item.value === defValue)
				this.current = def ? this.formatItemName(def) : ''
			},

			/**
			 * @param {[String, Number]} value
			 * 鍒ゆ柇鐢ㄦ埛缁欑殑 value 鏄惁鍚屾椂涓虹鐢ㄧ姸鎬?
			 */
			isDisabled(value) {
				let isDisabled = false;

				this.mixinDatacomResData.forEach(item => {
					if (item.value === value) {
						isDisabled = item.disable
					}
				})

				return isDisabled;
			},

			clearVal() {
				this.emit('')
				if (this.collection) {
					this.removeCache()
				}
			},
			change(item) {
				if (!item.disable) {
					this.showSelector = false
					this.current = this.formatItemName(item)
					this.emit(item.value)
				}
			},
			emit(val) {
				this.$emit('input', val)
				this.$emit('update:modelValue', val)
				this.$emit('change', val)
				if (this.collection) {
					this.setCache(val);
				}
			},
			toggleSelector() {
				if (this.disabled) {
					return
				}

				this.showSelector = !this.showSelector
			},
			formatItemName(item) {
				let {
					text,
					value,
					channel_code
				} = item
				channel_code = channel_code ? `(${channel_code})` : ''

				if (this.format) {
					// 鏍煎紡鍖栬緭鍑?
					let str = "";
					str = this.format;
					for (let key in item) {
						str = str.replace(new RegExp(`{${key}}`, "g"), item[key]);
					}
					return str;
				} else {
					return this.collection.indexOf('app-list') > 0 ?
						`${text}(${value})` :
						(
							text ?
							text :
							`鏈懡鍚?{channel_code}`
						)
				}
			},
			// 鑾峰彇褰撳墠鍔犺浇鐨勬暟鎹?
			getLoadData() {
				return this.mixinDatacomResData;
			},
			// 鑾峰彇褰撳墠缂撳瓨key
			getCurrentCacheKey() {
				return this.collection;
			},
			// 鑾峰彇缂撳瓨
			getCache(name = this.getCurrentCacheKey()) {
				let cacheData = uni.getStorageSync(this.cacheKey) || {};
				return cacheData[name];
			},
			// 璁剧疆缂撳瓨
			setCache(value, name = this.getCurrentCacheKey()) {
				let cacheData = uni.getStorageSync(this.cacheKey) || {};
				cacheData[name] = value;
				uni.setStorageSync(this.cacheKey, cacheData);
			},
			// 鍒犻櫎缂撳瓨
			removeCache(name = this.getCurrentCacheKey()) {
				let cacheData = uni.getStorageSync(this.cacheKey) || {};
				delete cacheData[name];
				uni.setStorageSync(this.cacheKey, cacheData);
			},
		}
	}
</script>

<style lang="scss">
	$uni-base-color: #6a6a6a !default;
	$uni-main-color: #333 !default;
	$uni-secondary-color: #909399 !default;
	$uni-border-3: #e5e5e5;

	/* #ifndef APP-NVUE */
	@media screen and (max-width: 500px) {
		.hide-on-phone {
			display: none;
		}
	}

	/* #endif */
	.uni-stat__select {
		display: flex;
		align-items: center;
		// padding: 15px;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
		width: 100%;
		flex: 1;
		box-sizing: border-box;
	}

	.uni-stat-box {
		width: 100%;
		flex: 1;
	}

	.uni-stat__actived {
		width: 100%;
		flex: 1;
		// outline: 1px solid #2979ff;
	}

	.uni-label-text {
		font-size: 14px;
		font-weight: bold;
		color: $uni-base-color;
		margin: auto 0;
		margin-right: 5px;
	}

	.uni-select {
		font-size: 14px;
		border: 1px solid $uni-border-3;
		box-sizing: border-box;
		border-radius: 4px;
		padding: 0 5px;
		padding-left: 10px;
		position: relative;
		/* #ifndef APP-NVUE */
		display: flex;
		user-select: none;
		/* #endif */
		flex-direction: row;
		align-items: center;
		border-bottom: solid 1px $uni-border-3;
		width: 100%;
		flex: 1;
		height: 35px;

		&--disabled {
			background-color: #f5f7fa;
			cursor: not-allowed;
		}
	}

	.uni-select__label {
		font-size: 16px;
		// line-height: 22px;
		height: 35px;
		padding-right: 10px;
		color: $uni-secondary-color;
	}

	.uni-select__input-box {
		height: 35px;
		position: relative;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex: 1;
		flex-direction: row;
		align-items: center;
	}

	.uni-select__input {
		flex: 1;
		font-size: 14px;
		height: 22px;
		line-height: 22px;
	}

	.uni-select__input-plac {
		font-size: 14px;
		color: $uni-secondary-color;
	}

	.uni-select__selector {
		/* #ifndef APP-NVUE */
		box-sizing: border-box;
		/* #endif */
		position: absolute;
		left: 0;
		width: 100%;
		background-color: #FFFFFF;
		border: 1px solid #EBEEF5;
		border-radius: 6px;
		box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
		z-index: 3;
		padding: 4px 0;
	}

	.uni-select__selector-scroll {
		/* #ifndef APP-NVUE */
		max-height: 200px;
		box-sizing: border-box;
		/* #endif */
	}

	/* #ifdef H5 */
	@media (min-width: 768px) {
		.uni-select__selector-scroll {
			max-height: 600px;
		}
	}

	/* #endif */

	.uni-select__selector-empty,
	.uni-select__selector-item {
		/* #ifndef APP-NVUE */
		display: flex;
		cursor: pointer;
		/* #endif */
		line-height: 35px;
		font-size: 14px;
		text-align: center;
		/* border-bottom: solid 1px $uni-border-3; */
		padding: 0px 10px;
	}

	.uni-select__selector-item:hover {
		background-color: #f9f9f9;
	}

	.uni-select__selector-empty:last-child,
	.uni-select__selector-item:last-child {
		/* #ifndef APP-NVUE */
		border-bottom: none;
		/* #endif */
	}

	.uni-select__selector__disabled {
		opacity: 0.4;
		cursor: default;
	}

	/* picker 寮瑰嚭灞傞€氱敤鐨勬寚绀哄皬涓夎 */
	.uni-popper__arrow_bottom,
	.uni-popper__arrow_bottom::after,
	.uni-popper__arrow_top,
	.uni-popper__arrow_top::after,
	{
	position: absolute;
	display: block;
	width: 0;
	height: 0;
	border-color: transparent;
	border-style: solid;
	border-width: 6px;
	}

	.uni-popper__arrow_bottom {
		filter: drop-shadow(0 2px 12px rgba(0, 0, 0, 0.03));
		top: -6px;
		left: 10%;
		margin-right: 3px;
		border-top-width: 0;
		border-bottom-color: #EBEEF5;
	}

	.uni-popper__arrow_bottom::after {
		content: " ";
		top: 1px;
		margin-left: -6px;
		border-top-width: 0;
		border-bottom-color: #fff;
	}

	.uni-popper__arrow_top {
		filter: drop-shadow(0 2px 12px rgba(0, 0, 0, 0.03));
		bottom: -6px;
		left: 10%;
		margin-right: 3px;
		border-bottom-width: 0;
		border-top-color: #EBEEF5;
	}

	.uni-popper__arrow_top::after {
		content: " ";
		bottom: 1px;
		margin-left: -6px;
		border-bottom-width: 0;
		border-top-color: #fff;
	}


	.uni-select__input-text {
		// width: 280px;
		width: 100%;
		color: $uni-main-color;
		white-space: nowrap;
		text-overflow: ellipsis;
		-o-text-overflow: ellipsis;
		overflow: hidden;
	}

	.uni-select__input-placeholder {
		color: $uni-base-color;
		font-size: 12px;
	}

	.uni-select--mask {
		position: fixed;
		top: 0;
		bottom: 0;
		right: 0;
		left: 0;
		z-index: 2;
	}
</style>


<template>
	<view class="uni-data-checklist" :style="{'margin-top':isTop+'px'}">
		<template v-if="!isLocal">
			<view class="uni-data-loading">
				<uni-load-more v-if="!mixinDatacomErrorMessage" status="loading" iconType="snow" :iconSize="18"
					:content-text="contentText"></uni-load-more>
				<text v-else>{{mixinDatacomErrorMessage}}</text>
			</view>
		</template>
		<template v-else>
			<checkbox-group v-if="multiple" class="checklist-group" :class="{'is-list':mode==='list' || wrap}"
				@change="change">
				<label class="checklist-box"
					:class="['is--'+mode,item.selected?'is-checked':'',(disabled || !!item.disabled)?'is-disable':'',index!==0&&mode==='list'?'is-list-border':'']"
					:style="item.styleBackgroud" v-for="(item,index) in dataList" :key="index">
					<checkbox class="hidden" hidden :disabled="disabled || !!item.disabled" :value="item[map.value]+''"
						:checked="item.selected" />
					<view v-if="(mode !=='tag' && mode !== 'list') || ( mode === 'list' && icon === 'left')"
						class="checkbox__inner" :style="item.styleIcon">
						<view class="checkbox__inner-icon"></view>
					</view>
					<view class="checklist-content" :class="{'list-content':mode === 'list' && icon ==='left'}">
						<text class="checklist-text" :style="item.styleIconText">{{item[map.text]}}</text>
						<view v-if="mode === 'list' && icon === 'right'" class="checkobx__list" :style="item.styleBackgroud"></view>
					</view>
				</label>
			</checkbox-group>
			<radio-group v-else class="checklist-group" :class="{'is-list':mode==='list','is-wrap':wrap}" @change="change">
				<label class="checklist-box"
					:class="['is--'+mode,item.selected?'is-checked':'',(disabled || !!item.disabled)?'is-disable':'',index!==0&&mode==='list'?'is-list-border':'']"
					:style="item.styleBackgroud" v-for="(item,index) in dataList" :key="index">
					<radio class="hidden" hidden :disabled="disabled || item.disabled" :value="item[map.value]+''"
						:checked="item.selected" />
					<view v-if="(mode !=='tag' && mode !== 'list') || ( mode === 'list' && icon === 'left')" class="radio__inner"
						:style="item.styleBackgroud">
						<view class="radio__inner-icon" :style="item.styleIcon"></view>
					</view>
					<view class="checklist-content" :class="{'list-content':mode === 'list' && icon ==='left'}">
						<text class="checklist-text" :style="item.styleIconText">{{item[map.text]}}</text>
						<view v-if="mode === 'list' && icon === 'right'" :style="item.styleRightIcon" class="checkobx__list"></view>
					</view>
				</label>
			</radio-group>
		</template>
	</view>
</template>

<script>
	/**
	 * DataChecklist 鏁版嵁閫夋嫨鍣?
	 * @description 閫氳繃鏁版嵁娓叉煋 checkbox 鍜?radio
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=xxx
	 * @property {String} mode = [default| list | button | tag] 鏄剧ず妯″紡
	 * @value default  	榛樿妯帓妯″紡
	 * @value list		鍒楄〃妯″紡
	 * @value button	鎸夐挳妯″紡
	 * @value tag 		鏍囩妯″紡
	 * @property {Boolean} multiple = [true|false] 鏄惁澶氶€?
	 * @property {Array|String|Number} value 榛樿鍊?
	 * @property {Array} localdata 鏈湴鏁版嵁 锛屾牸寮?[{text:'',value:''}]
	 * @property {Number|String} min 鏈€灏忛€夋嫨涓暟 锛宮ultiple涓簍rue鏃剁敓鏁?
	 * @property {Number|String} max 鏈€澶ч€夋嫨涓暟 锛宮ultiple涓簍rue鏃剁敓鏁?
	 * @property {Boolean} wrap 鏄惁鎹㈣鏄剧ず
	 * @property {String} icon = [left|right]  list 鍒楄〃妯″紡涓媔con鏄剧ず浣嶇疆
	 * @property {Boolean} selectedColor 閫変腑棰滆壊
	 * @property {Boolean} emptyText 娌℃湁鏁版嵁鏃舵樉绀虹殑鏂囧瓧 锛屾湰鍦版暟鎹棤鏁?
	 * @property {Boolean} selectedTextColor 閫変腑鏂囨湰棰滆壊锛屽涓嶅～鍐欏垯鑷姩鏄剧ず
	 * @property {Object} map 瀛楁鏄犲皠锛?榛樿 map={text:'text',value:'value'}
	 * @value left 宸︿晶鏄剧ず
	 * @value right 鍙充晶鏄剧ず
	 * @event {Function} change  閫変腑鍙戠敓鍙樺寲瑙﹀彂
	 */

	export default {
		name: 'uniDataChecklist',
		mixins: [uniCloud.mixinDatacom || {}],
		emits: ['input', 'update:modelValue', 'change'],
		props: {
			mode: {
				type: String,
				default: 'default'
			},

			multiple: {
				type: Boolean,
				default: false
			},
			value: {
				type: [Array, String, Number],
				default () {
					return ''
				}
			},
			// TODO vue3
			modelValue: {
				type: [Array, String, Number],
				default () {
					return '';
				}
			},
			localdata: {
				type: Array,
				default () {
					return []
				}
			},
			min: {
				type: [Number, String],
				default: ''
			},
			max: {
				type: [Number, String],
				default: ''
			},
			wrap: {
				type: Boolean,
				default: false
			},
			icon: {
				type: String,
				default: 'left'
			},
			selectedColor: {
				type: String,
				default: ''
			},
			selectedTextColor: {
				type: String,
				default: ''
			},
			emptyText: {
				type: String,
				default: '鏆傛棤鏁版嵁'
			},
			disabled: {
				type: Boolean,
				default: false
			},
			map: {
				type: Object,
				default () {
					return {
						text: 'text',
						value: 'value'
					}
				}
			}
		},
		watch: {
			localdata: {
				handler(newVal) {
					this.range = newVal
					this.dataList = this.getDataList(this.getSelectedValue(newVal))
				},
				deep: true
			},
			mixinDatacomResData(newVal) {
				this.range = newVal
				this.dataList = this.getDataList(this.getSelectedValue(newVal))
			},
			value(newVal) {
				this.dataList = this.getDataList(newVal)
				// fix by mehaotian is_reset 鍦?uni-forms 涓畾涔?
				// if(!this.is_reset){
				// 	this.is_reset = false
				// 	this.formItem && this.formItem.setValue(newVal)
				// }
			},
			modelValue(newVal) {
				this.dataList = this.getDataList(newVal);
				// if(!this.is_reset){
				// 	this.is_reset = false
				// 	this.formItem && this.formItem.setValue(newVal)
				// }
			}
		},
		data() {
			return {
				dataList: [],
				range: [],
				contentText: {
					contentdown: '鏌ョ湅鏇村',
					contentrefresh: '鍔犺浇涓?,
					contentnomore: '娌℃湁鏇村'
				},
				isLocal: true,
				styles: {
					selectedColor: '#2979ff',
					selectedTextColor: '#666',
				},
				isTop: 0
			};
		},
		computed: {
			dataValue() {
				if (this.value === '') return this.modelValue
				if (this.modelValue === '') return this.value
				return this.value
			}
		},
		created() {
			// this.form = this.getForm('uniForms')
			// this.formItem = this.getForm('uniFormsItem')
			// this.formItem && this.formItem.setValue(this.value)

			// if (this.formItem) {
			// 	this.isTop = 6
			// 	if (this.formItem.name) {
			// 		// 濡傛灉瀛樺湪name娣诲姞榛樿鍊?鍚﹀垯formData 涓笉瀛樺湪杩欎釜瀛楁涓嶆牎楠?
			// 		if(!this.is_reset){
			// 			this.is_reset = false
			// 			this.formItem.setValue(this.dataValue)
			// 		}
			// 		this.rename = this.formItem.name
			// 		this.form.inputChildrens.push(this)
			// 	}
			// }

			if (this.localdata && this.localdata.length !== 0) {
				this.isLocal = true
				this.range = this.localdata
				this.dataList = this.getDataList(this.getSelectedValue(this.range))
			} else {
				if (this.collection) {
					this.isLocal = false
					this.loadData()
				}
			}
		},
		methods: {
			loadData() {
				this.mixinDatacomGet().then(res => {
					this.mixinDatacomResData = res.result.data
					if (this.mixinDatacomResData.length === 0) {
						this.isLocal = false
						this.mixinDatacomErrorMessage = this.emptyText
					} else {
						this.isLocal = true
					}
				}).catch(err => {
					this.mixinDatacomErrorMessage = err.message
				})
			},
			/**
			 * 鑾峰彇鐖跺厓绱犲疄渚?
			 */
			getForm(name = 'uniForms') {
				let parent = this.$parent;
				let parentName = parent.$options.name;
				while (parentName !== name) {
					parent = parent.$parent;
					if (!parent) return false
					parentName = parent.$options.name;
				}
				return parent;
			},
			change(e) {
				const values = e.detail.value

				let detail = {
					value: [],
					data: []
				}

				if (this.multiple) {
					this.range.forEach(item => {

						if (values.includes(item[this.map.value] + '')) {
							detail.value.push(item[this.map.value])
							detail.data.push(item)
						}
					})
				} else {
					const range = this.range.find(item => (item[this.map.value] + '') === values)
					if (range) {
						detail = {
							value: range[this.map.value],
							data: range
						}
					}
				}
				// this.formItem && this.formItem.setValue(detail.value)
				// TODO 鍏煎 vue2
				this.$emit('input', detail.value);
				// // TOTO 鍏煎 vue3
				this.$emit('update:modelValue', detail.value);
				this.$emit('change', {
					detail
				})
				if (this.multiple) {
					// 濡傛灉 v-model 娌℃湁缁戝畾 锛屽垯璧板唴閮ㄩ€昏緫
					// if (this.value.length === 0) {
					this.dataList = this.getDataList(detail.value, true)
					// }
				} else {
					this.dataList = this.getDataList(detail.value)
				}
			},

			/**
			 * 鑾峰彇娓叉煋鐨勬柊鏁扮粍
			 * @param {Object} value 閫変腑鍐呭
			 */
			getDataList(value) {
				// 瑙ｉ櫎寮曠敤鍏崇郴锛岀牬鍧忓師寮曠敤鍏崇郴锛岄伩鍏嶆薄鏌撴簮鏁版嵁
				let dataList = JSON.parse(JSON.stringify(this.range))
				let list = []
				if (this.multiple) {
					if (!Array.isArray(value)) {
						value = []
					}
				} else {
					if (Array.isArray(value) && value.length) {
						value = value[0]
					}
				}
				dataList.forEach((item, index) => {
					item.disabled = item.disable || item.disabled || false
					if (this.multiple) {
						if (value.length > 0) {
							let have = value.find(val => val === item[this.map.value])
							item.selected = have !== undefined
						} else {
							item.selected = false
						}
					} else {
						item.selected = value === item[this.map.value]
					}

					list.push(item)
				})
				return this.setRange(list)
			},
			/**
			 * 澶勭悊鏈€澶ф渶灏忓€?
			 * @param {Object} list
			 */
			setRange(list) {
				let selectList = list.filter(item => item.selected)
				let min = Number(this.min) || 0
				let max = Number(this.max) || ''
				list.forEach((item, index) => {
					if (this.multiple) {
						if (selectList.length <= min) {
							let have = selectList.find(val => val[this.map.value] === item[this.map.value])
							if (have !== undefined) {
								item.disabled = true
							}
						}

						if (selectList.length >= max && max !== '') {
							let have = selectList.find(val => val[this.map.value] === item[this.map.value])
							if (have === undefined) {
								item.disabled = true
							}
						}
					}
					this.setStyles(item, index)
					list[index] = item
				})
				return list
			},
			/**
			 * 璁剧疆 class
			 * @param {Object} item
			 * @param {Object} index
			 */
			setStyles(item, index) {
				//  璁剧疆鑷畾涔夋牱寮?
				item.styleBackgroud = this.setStyleBackgroud(item)
				item.styleIcon = this.setStyleIcon(item)
				item.styleIconText = this.setStyleIconText(item)
				item.styleRightIcon = this.setStyleRightIcon(item)
			},

			/**
			 * 鑾峰彇閫変腑鍊?
			 * @param {Object} range
			 */
			getSelectedValue(range) {
				if (!this.multiple) return this.dataValue
				let selectedArr = []
				range.forEach((item) => {
					if (item.selected) {
						selectedArr.push(item[this.map.value])
					}
				})
				return this.dataValue.length > 0 ? this.dataValue : selectedArr
			},

			/**
			 * 璁剧疆鑳屾櫙鏍峰紡
			 */
			setStyleBackgroud(item) {
				let styles = {}
				let selectedColor = this.selectedColor ? this.selectedColor : '#2979ff'
				if (this.selectedColor) {
					if (this.mode !== 'list') {
						styles['border-color'] = item.selected ? selectedColor : '#DCDFE6'
					}
					if (this.mode === 'tag') {
						styles['background-color'] = item.selected ? selectedColor : '#f5f5f5'
					}
				}
				let classles = ''
				for (let i in styles) {
					classles += `${i}:${styles[i]};`
				}
				return classles
			},
			setStyleIcon(item) {
				let styles = {}
				let classles = ''
				if (this.selectedColor) {
					let selectedColor = this.selectedColor ? this.selectedColor : '#2979ff'
					styles['background-color'] = item.selected ? selectedColor : '#fff'
					styles['border-color'] = item.selected ? selectedColor : '#DCDFE6'

					if (!item.selected && item.disabled) {
						styles['background-color'] = '#F2F6FC'
						styles['border-color'] = item.selected ? selectedColor : '#DCDFE6'
					}
				}
				for (let i in styles) {
					classles += `${i}:${styles[i]};`
				}
				return classles
			},
			setStyleIconText(item) {
				let styles = {}
				let classles = ''
				if (this.selectedColor) {
					let selectedColor = this.selectedColor ? this.selectedColor : '#2979ff'
					if (this.mode === 'tag') {
						styles.color = item.selected ? (this.selectedTextColor ? this.selectedTextColor : '#fff') : '#666'
					} else {
						styles.color = item.selected ? (this.selectedTextColor ? this.selectedTextColor : selectedColor) : '#666'
					}
					if (!item.selected && item.disabled) {
						styles.color = '#999'
					}
				}
				for (let i in styles) {
					classles += `${i}:${styles[i]};`
				}
				return classles
			},
			setStyleRightIcon(item) {
				let styles = {}
				let classles = ''
				if (this.mode === 'list') {
					styles['border-color'] = item.selected ? this.styles.selectedColor : '#DCDFE6'
				}
				for (let i in styles) {
					classles += `${i}:${styles[i]};`
				}

				return classles
			}
		}
	}
</script>

<style lang="scss">
	$uni-primary: #2979ff !default;
	$border-color: #DCDFE6;
	$disable: 0.4;

	@mixin flex {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
	}

	.uni-data-loading {
		@include flex;
		flex-direction: row;
		justify-content: center;
		align-items: center;
		height: 36px;
		padding-left: 10px;
		color: #999;
	}

	.uni-data-checklist {
		position: relative;
		z-index: 0;
		flex: 1;

		// 澶氶€夋牱寮?
		.checklist-group {
			@include flex;
			flex-direction: row;
			flex-wrap: wrap;

			&.is-list {
				flex-direction: column;
			}

			.checklist-box {
				@include flex;
				flex-direction: row;
				align-items: center;
				position: relative;
				margin: 5px 0;
				margin-right: 25px;

				.hidden {
					position: absolute;
					opacity: 0;
				}

				// 鏂囧瓧鏍峰紡
				.checklist-content {
					@include flex;
					flex: 1;
					flex-direction: row;
					align-items: center;
					justify-content: space-between;

					.checklist-text {
						font-size: 14px;
						color: #666;
						margin-left: 5px;
						line-height: 14px;
					}

					.checkobx__list {
						border-right-width: 1px;
						border-right-color: #007aff;
						border-right-style: solid;
						border-bottom-width: 1px;
						border-bottom-color: #007aff;
						border-bottom-style: solid;
						height: 12px;
						width: 6px;
						left: -5px;
						transform-origin: center;
						transform: rotate(45deg);
						opacity: 0;
					}
				}

				// 澶氶€夋牱寮?
				.checkbox__inner {
					/* #ifndef APP-NVUE */
					flex-shrink: 0;
					box-sizing: border-box;
					/* #endif */
					position: relative;
					width: 16px;
					height: 16px;
					border: 1px solid $border-color;
					border-radius: 4px;
					background-color: #fff;
					z-index: 1;

					.checkbox__inner-icon {
						position: absolute;
						/* #ifdef APP-NVUE */
						top: 2px;
						/* #endif */
						/* #ifndef APP-NVUE */
						top: 1px;
						/* #endif */
						left: 5px;
						height: 8px;
						width: 4px;
						border-right-width: 1px;
						border-right-color: #fff;
						border-right-style: solid;
						border-bottom-width: 1px;
						border-bottom-color: #fff;
						border-bottom-style: solid;
						opacity: 0;
						transform-origin: center;
						transform: rotate(40deg);
					}
				}

				// 鍗曢€夋牱寮?
				.radio__inner {
					@include flex;
					/* #ifndef APP-NVUE */
					flex-shrink: 0;
					box-sizing: border-box;
					/* #endif */
					justify-content: center;
					align-items: center;
					position: relative;
					width: 16px;
					height: 16px;
					border: 1px solid $border-color;
					border-radius: 16px;
					background-color: #fff;
					z-index: 1;

					.radio__inner-icon {
						width: 8px;
						height: 8px;
						border-radius: 10px;
						opacity: 0;
					}
				}

				// 榛樿鏍峰紡
				&.is--default {

					// 绂佺敤
					&.is-disable {
						/* #ifdef H5 */
						cursor: not-allowed;

						/* #endif */
						.checkbox__inner {
							background-color: #F2F6FC;
							border-color: $border-color;
							/* #ifdef H5 */
							cursor: not-allowed;
							/* #endif */
						}

						.radio__inner {
							background-color: #F2F6FC;
							border-color: $border-color;
						}

						.checklist-text {
							color: #999;
						}
					}

					// 閫変腑
					&.is-checked {
						.checkbox__inner {
							border-color: $uni-primary;
							background-color: $uni-primary;

							.checkbox__inner-icon {
								opacity: 1;
								transform: rotate(45deg);
							}
						}

						.radio__inner {
							border-color: $uni-primary;

							.radio__inner-icon {
								opacity: 1;
								background-color: $uni-primary;
							}
						}

						.checklist-text {
							color: $uni-primary;
						}

						// 閫変腑绂佺敤
						&.is-disable {
							.checkbox__inner {
								opacity: $disable;
							}

							.checklist-text {
								opacity: $disable;
							}

							.radio__inner {
								opacity: $disable;
							}
						}
					}
				}

				// 鎸夐挳鏍峰紡
				&.is--button {
					margin-right: 10px;
					padding: 5px 10px;
					border: 1px $border-color solid;
					border-radius: 3px;
					transition: border-color 0.2s;

					// 绂佺敤
					&.is-disable {
						/* #ifdef H5 */
						cursor: not-allowed;
						/* #endif */
						border: 1px #eee solid;
						opacity: $disable;

						.checkbox__inner {
							background-color: #F2F6FC;
							border-color: $border-color;
							/* #ifdef H5 */
							cursor: not-allowed;
							/* #endif */
						}

						.radio__inner {
							background-color: #F2F6FC;
							border-color: $border-color;
							/* #ifdef H5 */
							cursor: not-allowed;
							/* #endif */
						}

						.checklist-text {
							color: #999;
						}
					}

					&.is-checked {
						border-color: $uni-primary;

						.checkbox__inner {
							border-color: $uni-primary;
							background-color: $uni-primary;

							.checkbox__inner-icon {
								opacity: 1;
								transform: rotate(45deg);
							}
						}

						.radio__inner {
							border-color: $uni-primary;

							.radio__inner-icon {
								opacity: 1;
								background-color: $uni-primary;
							}
						}

						.checklist-text {
							color: $uni-primary;
						}

						// 閫変腑绂佺敤
						&.is-disable {
							opacity: $disable;
						}
					}
				}

				// 鏍囩鏍峰紡
				&.is--tag {
					margin-right: 10px;
					padding: 5px 10px;
					border: 1px $border-color solid;
					border-radius: 3px;
					background-color: #f5f5f5;

					.checklist-text {
						margin: 0;
						color: #666;
					}

					// 绂佺敤
					&.is-disable {
						/* #ifdef H5 */
						cursor: not-allowed;
						/* #endif */
						opacity: $disable;
					}

					&.is-checked {
						background-color: $uni-primary;
						border-color: $uni-primary;

						.checklist-text {
							color: #fff;
						}
					}
				}

				// 鍒楄〃鏍峰紡
				&.is--list {
					/* #ifndef APP-NVUE */
					display: flex;
					/* #endif */
					padding: 10px 15px;
					padding-left: 0;
					margin: 0;

					&.is-list-border {
						border-top: 1px #eee solid;
					}

					// 绂佺敤
					&.is-disable {
						/* #ifdef H5 */
						cursor: not-allowed;

						/* #endif */
						.checkbox__inner {
							background-color: #F2F6FC;
							border-color: $border-color;
							/* #ifdef H5 */
							cursor: not-allowed;
							/* #endif */
						}

						.checklist-text {
							color: #999;
						}
					}

					&.is-checked {
						.checkbox__inner {
							border-color: $uni-primary;
							background-color: $uni-primary;

							.checkbox__inner-icon {
								opacity: 1;
								transform: rotate(45deg);
							}
						}

						.radio__inner {
							border-color: $uni-primary;
							.radio__inner-icon {
								opacity: 1;
								background-color: $uni-primary;
							}
						}

						.checklist-text {
							color: $uni-primary;
						}

						.checklist-content {
							.checkobx__list {
								opacity: 1;
								border-color: $uni-primary;
							}
						}

						// 閫変腑绂佺敤
						&.is-disable {
							.checkbox__inner {
								opacity: $disable;
							}

							.checklist-text {
								opacity: $disable;
							}
						}
					}
				}
			}
		}
	}
</style>


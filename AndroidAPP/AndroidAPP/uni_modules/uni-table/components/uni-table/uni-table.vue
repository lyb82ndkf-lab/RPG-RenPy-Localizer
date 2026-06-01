<template>
	<view class="uni-table-scroll" :class="{ 'table--border': border, 'border-none': !noData }">
		<!-- #ifdef H5 -->
		<table class="uni-table" border="0" cellpadding="0" cellspacing="0" :class="{ 'table--stripe': stripe }" :style="{ 'min-width': minWidth + 'px' }">
			<slot></slot>
			<tr v-if="noData" class="uni-table-loading">
				<td class="uni-table-text" :class="{ 'empty-border': border }">{{ emptyText }}</td>
			</tr>
			<view v-if="loading" class="uni-table-mask" :class="{ 'empty-border': border }"><div class="uni-table--loader"></div></view>
		</table>
		<!-- #endif -->
		<!-- #ifndef H5 -->
		<view class="uni-table" :style="{ 'min-width': minWidth + 'px' }" :class="{ 'table--stripe': stripe }">
			<slot></slot>
			<view v-if="noData" class="uni-table-loading">
				<view class="uni-table-text" :class="{ 'empty-border': border }">{{ emptyText }}</view>
			</view>
			<view v-if="loading" class="uni-table-mask" :class="{ 'empty-border': border }"><div class="uni-table--loader"></div></view>
		</view>
		<!-- #endif -->
	</view>
</template>

<script>
/**
 * Table 琛ㄦ牸
 * @description 鐢ㄤ簬灞曠ず澶氭潯缁撴瀯绫讳技鐨勬暟鎹?
 * @tutorial https://ext.dcloud.net.cn/plugin?id=3270
 * @property {Boolean} 	border 				鏄惁甯︽湁绾靛悜杈规
 * @property {Boolean} 	stripe 				鏄惁鏄剧ず鏂戦┈绾?
 * @property {Boolean} 	type 					鏄惁寮€鍚閫?
 * @property {String} 	emptyText 			绌烘暟鎹椂鏄剧ず鐨勬枃鏈唴瀹?
 * @property {Boolean} 	loading 			鏄剧ず鍔犺浇涓?
 * @event {Function} 	selection-change 	寮€鍚閫夋椂锛屽綋閫夋嫨椤瑰彂鐢熷彉鍖栨椂浼氳Е鍙戣浜嬩欢
 */
export default {
	name: 'uniTable',
	options: {
		// #ifdef MP-TOUTIAO
		virtualHost: false,
		// #endif
		// #ifndef MP-TOUTIAO
		virtualHost: true
		// #endif
	},
	emits:['selection-change'],
	props: {
		data: {
			type: Array,
			default() {
				return []
			}
		},
		// 鏄惁鏈夌珫绾?
		border: {
			type: Boolean,
			default: false
		},
		// 鏄惁鏄剧ず鏂戦┈绾?
		stripe: {
			type: Boolean,
			default: false
		},
		// 澶氶€?
		type: {
			type: String,
			default: ''
		},
		// 娌℃湁鏇村鏁版嵁
		emptyText: {
			type: String,
			default: '娌℃湁鏇村鏁版嵁'
		},
		loading: {
			type: Boolean,
			default: false
		},
		rowKey: {
			type: String,
			default: ''
		}
	},
	data() {
		return {
			noData: true,
			minWidth: 0,
			multiTableHeads: []
		}
	},
	watch: {
		loading(val) {},
		data(newVal) {
			let theadChildren = this.theadChildren
			let rowspan = 1
			if (this.theadChildren) {
				rowspan = this.theadChildren.rowspan
			}

			// this.trChildren.length - rowspan
			this.noData = false
			// this.noData = newVal.length === 0
		}
	},
	created() {
		// 瀹氫箟tr鐨勫疄渚嬫暟缁?
		this.trChildren = []
		this.thChildren = []
		this.theadChildren = null
		this.backData = []
		this.backIndexData = []
	},

	methods: {
		isNodata() {
			let theadChildren = this.theadChildren
			let rowspan = 1
			if (this.theadChildren) {
				rowspan = this.theadChildren.rowspan
			}
			this.noData = this.trChildren.length - rowspan <= 0
		},
		/**
		 * 閫変腑鎵€鏈?		 */
		selectionAll() {
			let startIndex = 1
			let theadChildren = this.theadChildren
			if (!this.theadChildren) {
				theadChildren = this.trChildren[0]
			} else {
				startIndex = theadChildren.rowspan - 1
			}
			let isHaveData = this.data && this.data.length > 0
			theadChildren.checked = true
			theadChildren.indeterminate = false
			this.trChildren.forEach((item, index) => {
				if (!item.disabled) {
					item.checked = true
					if (isHaveData && item.keyValue) {
						const row = this.data.find(v => v[this.rowKey] === item.keyValue)
						if (!this.backData.find(v => v[this.rowKey] === row[this.rowKey])) {
							this.backData.push(row)
						}
					}
					if (index > (startIndex - 1) && this.backIndexData.indexOf(index - startIndex) === -1) {
						this.backIndexData.push(index - startIndex)
					}
				}
			})
			// this.backData = JSON.parse(JSON.stringify(this.data))
			this.$emit('selection-change', {
				detail: {
					value: this.backData,
					index: this.backIndexData
				}
			})
		},
		/**
		 * 鐢ㄤ簬澶氶€夎〃鏍硷紝鍒囨崲鏌愪竴琛岀殑閫変腑鐘舵€侊紝濡傛灉浣跨敤浜嗙浜屼釜鍙傛暟锛屽垯鏄缃繖涓€琛岄€変腑涓庡惁锛坰elected 涓?true 鍒欓€変腑锛?
		 */
		toggleRowSelection(row, selected) {
			// if (!this.theadChildren) return
			row = [].concat(row)

			this.trChildren.forEach((item, index) => {
				// if (item.keyValue) {

				const select = row.findIndex(v => {
					//
					if (typeof v === 'number') {
						return v === index - 1
					} else {
						return v[this.rowKey] === item.keyValue
					}
				})
				let ischeck = item.checked
				if (select !== -1) {
					if (typeof selected === 'boolean') {
						item.checked = selected
					} else {
						item.checked = !item.checked
					}
					if (ischeck !== item.checked) {
						this.check(item.rowData||item, item.checked, item.rowData?item.keyValue:null, true)
					}
				}
				// }
			})
			this.$emit('selection-change', {
				detail: {
					value: this.backData,
					index:this.backIndexData
				}
			})
		},

		/**
		 * 鐢ㄤ簬澶氶€夎〃鏍硷紝娓呯┖鐢ㄦ埛鐨勯€夋嫨
		 */
		clearSelection() {
			let theadChildren = this.theadChildren
			if (!this.theadChildren) {
				theadChildren = this.trChildren[0]
			}
			// if (!this.theadChildren) return
			theadChildren.checked = false
			theadChildren.indeterminate = false
			this.trChildren.forEach(item => {
				// if (item.keyValue) {
					item.checked = false
				// }
			})
			this.backData = []
			this.backIndexData = []
			this.$emit('selection-change', {
				detail: {
					value: [],
					index: []
				}
			})
		},
		/**
		 * 鐢ㄤ簬澶氶€夎〃鏍硷紝鍒囨崲鎵€鏈夎鐨勯€変腑鐘舵€?
		 */
		toggleAllSelection() {
			let list = []
			let startIndex = 1
			let theadChildren = this.theadChildren
			if (!this.theadChildren) {
				theadChildren = this.trChildren[0]
			} else {
				startIndex = theadChildren.rowspan - 1
			}
			this.trChildren.forEach((item, index) => {
				if (!item.disabled) {
					if (index > (startIndex - 1) ) {
						list.push(index-startIndex)
					}
				}
			})
			this.toggleRowSelection(list)
		},

		/**
		 * 閫変腑\鍙栨秷閫変腑
		 * @param {Object} child
		 * @param {Object} check
		 * @param {Object} rowValue
		 */
		check(child, check, keyValue, emit) {
			let theadChildren = this.theadChildren
			if (!this.theadChildren) {
				theadChildren = this.trChildren[0]
			}



			let childDomIndex = this.trChildren.findIndex((item, index) => child === item)
			if(childDomIndex < 0){
				childDomIndex = this.data.findIndex(v=>v[this.rowKey] === keyValue) + 1
			}
			const dataLen = this.trChildren.filter(v => !v.disabled && v.keyValue).length
			if (childDomIndex === 0) {
				check ? this.selectionAll() : this.clearSelection()
				return
			}

			if (check) {
				if (keyValue) {
					this.backData.push(child)
				}
				this.backIndexData.push(childDomIndex - 1)
			} else {
				const index = this.backData.findIndex(v => v[this.rowKey] === keyValue)
				const idx = this.backIndexData.findIndex(item => item === childDomIndex - 1)
				if (keyValue) {
					this.backData.splice(index, 1)
				}
				this.backIndexData.splice(idx, 1)
			}

			const domCheckAll = this.trChildren.find((item, index) => index > 0 && !item.checked && !item.disabled)
			if (!domCheckAll) {
				theadChildren.indeterminate = false
				theadChildren.checked = true
			} else {
				theadChildren.indeterminate = true
				theadChildren.checked = false
			}

			if (this.backIndexData.length === 0) {
				theadChildren.indeterminate = false
			}

			if (!emit) {
				this.$emit('selection-change', {
					detail: {
						value: this.backData,
						index: this.backIndexData
					}
				})
			}
		}
	}
}
</script>

<style lang="scss">
$border-color: #ebeef5;

.uni-table-scroll {
	width: 100%;
	/* #ifndef APP-NVUE */
	overflow-x: auto;
	/* #endif */
}

.uni-table {
	position: relative;
	width: 100%;
	border-radius: 5px;
	// box-shadow: 0px 0px 3px 1px rgba(0, 0, 0, 0.1);
	background-color: #fff;
	/* #ifndef APP-NVUE */
	box-sizing: border-box;
	display: table;
	overflow-x: auto;
	::v-deep .uni-table-tr:nth-child(n + 2) {
		&:hover {
			background-color: #f5f7fa;
		}
	}
	::v-deep .uni-table-thead {
		.uni-table-tr {
			// background-color: #f5f7fa;
			&:hover {
				background-color:#fafafa;
			}
		}
	}
	/* #endif */
}

.table--border {
	border: 1px $border-color solid;
	border-right: none;
}

.border-none {
	/* #ifndef APP-NVUE */
	border-bottom: none;
	/* #endif */
}

.table--stripe {
	/* #ifndef APP-NVUE */
	::v-deep .uni-table-tr:nth-child(2n + 3) {
		background-color: #fafafa;
	}
	/* #endif */
}

/* 琛ㄦ牸鍔犺浇銆佹棤鏁版嵁鏍峰紡 */
.uni-table-loading {
	position: relative;
	/* #ifndef APP-NVUE */
	display: table-row;
	/* #endif */
	height: 50px;
	line-height: 50px;
	overflow: hidden;
	box-sizing: border-box;
}
.empty-border {
	border-right: 1px $border-color solid;
}
.uni-table-text {
	position: absolute;
	right: 0;
	left: 0;
	text-align: center;
	font-size: 14px;
	color: #999;
}

.uni-table-mask {
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	right: 0;
	background-color: rgba(255, 255, 255, 0.8);
	z-index: 99;
	/* #ifndef APP-NVUE */
	display: flex;
	margin: auto;
	transition: all 0.5s;
	/* #endif */
	justify-content: center;
	align-items: center;
}

.uni-table--loader {
	width: 30px;
	height: 30px;
	border: 2px solid #aaa;
	// border-bottom-color: transparent;
	border-radius: 50%;
	/* #ifndef APP-NVUE */
	animation: 2s uni-table--loader linear infinite;
	/* #endif */
	position: relative;
}

@keyframes uni-table--loader {
	0% {
		transform: rotate(360deg);
	}

	10% {
		border-left-color: transparent;
	}

	20% {
		border-bottom-color: transparent;
	}

	30% {
		border-right-color: transparent;
	}

	40% {
		border-top-color: transparent;
	}

	50% {
		transform: rotate(0deg);
	}

	60% {
		border-top-color: transparent;
	}

	70% {
		border-left-color: transparent;
	}

	80% {
		border-bottom-color: transparent;
	}

	90% {
		border-right-color: transparent;
	}

	100% {
		transform: rotate(-360deg);
	}
}
</style>


<template>
	<!-- #ifdef H5 -->
	<th :rowspan="rowspan" :colspan="colspan" class="uni-table-th" :class="{ 'table--border': border }" :style="{ width: customWidth + 'px', 'text-align': align }">
		<view class="uni-table-th-row">
			<view class="uni-table-th-content" :style="{ 'justify-content': contentAlign }" @click="sort">
				<slot></slot>
				<view v-if="sortable" class="arrow-box">
					<text class="arrow up" :class="{ active: ascending }" @click.stop="ascendingFn"></text>
					<text class="arrow down" :class="{ active: descending }" @click.stop="descendingFn"></text>
				</view>
			</view>
			<dropdown v-if="filterType || filterData.length" :filterDefaultValue="filterDefaultValue" :filterData="filterData" :filterType="filterType" @change="ondropdown"></dropdown>
		</view>
	</th>
	<!-- #endif -->
	<!-- #ifndef H5 -->
	<view class="uni-table-th" :class="{ 'table--border': border }" :style="{ width: customWidth + 'px', 'text-align': align }"><slot></slot></view>
	<!-- #endif -->
</template>

<script>
	// #ifdef H5
	import dropdown from './filter-dropdown.vue'
	// #endif
/**
 * Th 琛ㄥご
 * @description 琛ㄦ牸鍐呯殑琛ㄥご鍗曞厓鏍肩粍浠?
 * @tutorial https://ext.dcloud.net.cn/plugin?id=3270
 * @property {Number | String} 	width 	鍗曞厓鏍煎搴︼紙鏀寔绾暟瀛椼€佹惡甯﹀崟浣峱x鎴杛px锛?
 * @property {Boolean} 	sortable 					鏄惁鍚敤鎺掑簭
 * @property {Number} 	align = [left|center|right]	鍗曞厓鏍煎榻愭柟寮?
 * @value left   	鍗曞厓鏍兼枃瀛楀乏渚у榻?
 * @value center	鍗曞厓鏍兼枃瀛楀眳涓?
 * @value right		鍗曞厓鏍兼枃瀛楀彸渚у榻?
 * @property {Array}	filterData 绛涢€夋暟鎹?
 * @property {String}	filterType	[search|select] 绛涢€夌被鍨?
 * @value search	鍏抽敭瀛楁悳绱?
 * @value select	鏉′欢閫夋嫨
 * @event {Function} sort-change 鎺掑簭瑙﹀彂浜嬩欢
 */
export default {
	name: 'uniTh',
	options: {
		// #ifdef MP-TOUTIAO
		virtualHost: false,
		// #endif
		// #ifndef MP-TOUTIAO
		virtualHost: true
		// #endif
	},
	components: {
		// #ifdef H5
		dropdown
		// #endif
	},
	emits:['sort-change','filter-change'],
	props: {
		width: {
			type: [String, Number],
			default: ''
		},
		align: {
			type: String,
			default: 'left'
		},
		rowspan: {
			type: [Number, String],
			default: 1
		},
		colspan: {
			type: [Number, String],
			default: 1
		},
		sortable: {
			type: Boolean,
			default: false
		},
		filterType: {
			type: String,
			default: ""
		},
		filterData: {
			type: Array,
			default () {
				return []
			}
		},
		filterDefaultValue: {
			type: [Array,String],
			default () {
				return ""
			}
		}
	},
	data() {
		return {
			border: false,
			ascending: false,
			descending: false
		}
	},
	computed: {
		// 鏍规嵁props涓殑width灞炴€?鑷姩鍖归厤褰撳墠th鐨勫搴?px)
		customWidth(){
			if(typeof this.width === 'number'){
				return this.width
			} else if(typeof this.width === 'string') {
				let regexHaveUnitPx = new RegExp(/^[1-9][0-9]*px$/g)
				let regexHaveUnitRpx = new RegExp(/^[1-9][0-9]*rpx$/g)
				let regexHaveNotUnit = new RegExp(/^[1-9][0-9]*$/g)
				if (this.width.match(regexHaveUnitPx) !== null) { // 鎼哄甫浜?px
					return this.width.replace('px', '')
				} else if (this.width.match(regexHaveUnitRpx) !== null) { // 鎼哄甫浜?rpx
					let numberRpx = Number(this.width.replace('rpx', ''))
					// #ifdef MP-WEIXIN
					let widthCoe = uni.getWindowInfo().screenWidth / 750
					// #endif
					// #ifndef MP-WEIXIN
					let widthCoe = uni.getSystemInfoSync().screenWidth / 750
					// #endif
					return Math.round(numberRpx * widthCoe)
				} else if (this.width.match(regexHaveNotUnit) !== null) { // 鏈惡甯?rpx鎴杙x 鐨勭函鏁板瓧 String
					return this.width
				} else { // 涓嶇鍚堟牸寮?
					return ''
				}
			} else {
				return ''
			}
		},
		contentAlign() {
			let align = 'left'
			switch (this.align) {
				case 'left':
					align = 'flex-start'
					break
				case 'center':
					align = 'center'
					break
				case 'right':
					align = 'flex-end'
					break
			}
			return align
		}
	},
	created() {
		this.root = this.getTable('uniTable')
		this.rootTr = this.getTable('uniTr')
		this.rootTr.minWidthUpdate(this.customWidth ? this.customWidth : 140)
		this.border = this.root.border
		this.root.thChildren.push(this)
	},
	methods: {
		sort() {
			if (!this.sortable) return
			this.clearOther()
			if (!this.ascending && !this.descending) {
				this.ascending = true
				this.$emit('sort-change', { order: 'ascending' })
				return
			}
			if (this.ascending && !this.descending) {
				this.ascending = false
				this.descending = true
				this.$emit('sort-change', { order: 'descending' })
				return
			}

			if (!this.ascending && this.descending) {
				this.ascending = false
				this.descending = false
				this.$emit('sort-change', { order: null })
			}
		},
		ascendingFn() {
			this.clearOther()
			this.ascending = !this.ascending
			this.descending = false
			this.$emit('sort-change', { order: this.ascending ? 'ascending' : null })
		},
		descendingFn() {
			this.clearOther()
			this.descending = !this.descending
			this.ascending = false
			this.$emit('sort-change', { order: this.descending ? 'descending' : null })
		},
		clearOther() {
			this.root.thChildren.map(item => {
				if (item !== this) {
					item.ascending = false
					item.descending = false
				}
				return item
			})
		},
		ondropdown(e) {
			this.$emit("filter-change", e)
		},
		/**
		 * 鑾峰彇鐖跺厓绱犲疄渚?
		 */
		getTable(name) {
			let parent = this.$parent
			let parentName = parent.$options.name
			while (parentName !== name) {
				parent = parent.$parent
				if (!parent) return false
				parentName = parent.$options.name
			}
			return parent
		}
	}
}
</script>

<style lang="scss">
$border-color: #ebeef5;
$uni-primary: #007aff !default;

.uni-table-th {
	padding: 12px 10px;
	/* #ifndef APP-NVUE */
	display: table-cell;
	box-sizing: border-box;
	/* #endif */
	font-size: 14px;
	font-weight: bold;
	color: #909399;
	border-bottom: 1px $border-color solid;
}

.uni-table-th-row {
	/* #ifndef APP-NVUE */
	display: flex;
	/* #endif */
	flex-direction: row;
}

.table--border {
	border-right: 1px $border-color solid;
}
.uni-table-th-content {
	display: flex;
	align-items: center;
	flex: 1;
}
.arrow-box {
}
.arrow {
	display: block;
	position: relative;
	width: 10px;
	height: 8px;
	// border: 1px red solid;
	left: 5px;
	overflow: hidden;
	cursor: pointer;
}
.down {
	top: 3px;
	::after {
		content: '';
		width: 8px;
		height: 8px;
		position: absolute;
		left: 2px;
		top: -5px;
		transform: rotate(45deg);
		background-color: #ccc;
	}
	&.active {
		::after {
			background-color: $uni-primary;
		}
	}
}
.up {
	::after {
		content: '';
		width: 8px;
		height: 8px;
		position: absolute;
		left: 2px;
		top: 5px;
		transform: rotate(45deg);
		background-color: #ccc;
	}
	&.active {
		::after {
			background-color: $uni-primary;
		}
	}
}
</style>


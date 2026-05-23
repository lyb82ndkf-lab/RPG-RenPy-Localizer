<template>
	<view class="uni-grid-wrap">
		<view :id="elId" ref="uni-grid" class="uni-grid" :class="{ 'uni-grid--border': showBorder }" :style="{ 'border-left-color':borderColor}">
			<slot />
		</view>
	</view>
</template>

<script>
	// #ifdef APP-NVUE
	const dom = uni.requireNativePlugin('dom');
	// #endif

	/**
	 * Grid 瀹牸
	 * @description 瀹牸缁勪欢
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=27
	 * @property {Number} column 姣忓垪鏄剧ず涓暟
	 * @property {String} borderColor 杈规棰滆壊
	 * @property {Boolean} showBorder 鏄惁鏄剧ず杈规
	 * @property {Boolean} square 鏄惁鏂瑰舰鏄剧ず
	 * @property {Boolean} Boolean 鐐瑰嚮鑳屾櫙鏄惁楂樹寒
	 * @event {Function} change 鐐瑰嚮 grid 瑙﹀彂锛宔={detail:{index:0}}锛宨ndex 涓哄綋鍓嶇偣鍑?gird 涓嬫爣
	 */
	export default {
		name: 'UniGrid',
		emits:['change'],
		props: {
			// 姣忓垪鏄剧ず涓暟
			column: {
				type: Number,
				default: 3
			},
			// 鏄惁鏄剧ず杈规
			showBorder: {
				type: Boolean,
				default: true
			},
			// 杈规棰滆壊
			borderColor: {
				type: String,
				default: '#D2D2D2'
			},
			// 鏄惁姝ｆ柟褰㈡樉绀?榛樿涓?true
			square: {
				type: Boolean,
				default: true
			},
			highlight: {
				type: Boolean,
				default: true
			}
		},
		provide() {
			return {
				grid: this
			}
		},
		data() {
			const elId = `Uni_${Math.ceil(Math.random() * 10e5).toString(36)}`
			return {
				elId,
				width: 0
			}
		},
		created() {
			this.children = []
		},
		mounted() {
			this.$nextTick(()=>{
				this.init()
			})
		},
		methods: {
			init() {
				setTimeout(() => {
					this._getSize((width) => {
						this.children.forEach((item, index) => {
							item.width = width
						})
					})
				}, 50)
			},
			change(e) {
				this.$emit('change', e)
			},
			_getSize(fn) {
				// #ifndef APP-NVUE
				uni.createSelectorQuery()
					.in(this)
					.select(`#${this.elId}`)
					.boundingClientRect()
					.exec(ret => {
						this.width = parseInt((ret[0].width - 1) / this.column) + 'px'
						fn(this.width)
					})
				// #endif
				// #ifdef APP-NVUE
				dom.getComponentRect(this.$refs['uni-grid'], (ret) => {
					this.width = parseInt((ret.size.width - 1) / this.column) + 'px'
					fn(this.width)
				})
				// #endif
			}
		}
	}
</script>

<style lang="scss" scoped>
	.uni-grid-wrap {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex: 1;
		flex-direction: column;
		/* #ifdef H5 */
		width: 100%;
		/* #endif */
	}

	.uni-grid {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		// flex: 1;
		flex-direction: row;
		flex-wrap: wrap;
	}

	.uni-grid--border {
		position: relative;
		/* #ifdef APP-NVUE */
		border-left-color: #D2D2D2;
		border-left-style: solid;
		border-left-width: 0.5px;
		/* #endif */
		/* #ifndef APP-NVUE */
		z-index: 1;
		border-left: 1px #D2D2D2 solid;
		/* #endif */
	}
</style>


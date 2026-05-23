<template>
	<view v-if="show" class="uni-noticebar" :style="{ backgroundColor }" @click="onClick">
		<uni-icons v-if="showIcon === true || showIcon === 'true'" class="uni-noticebar-icon" type="sound"
			:color="color" :size="fontSize * 1.5" />
		<view ref="textBox" class="uni-noticebar__content-wrapper"
			:class="{
				'uni-noticebar__content-wrapper--scrollable': scrollable,
				'uni-noticebar__content-wrapper--single': !scrollable && (single || moreText)
			}"
			:style="{ height: scrollable ? fontSize * 1.5 + 'px' : 'auto' }"
		>
			<view :id="elIdBox" class="uni-noticebar__content"
				:class="{
					'uni-noticebar__content--scrollable': scrollable,
					'uni-noticebar__content--single': !scrollable && (single || moreText)
				}"
			>
				<text :id="elId" ref="animationEle" class="uni-noticebar__content-text" 
					:class="{
						'uni-noticebar__content-text--scrollable': scrollable,
						'uni-noticebar__content-text--single': !scrollable && (single || showGetMore)
					}" 
					:style="{
						color: color,
						fontSize: fontSize + 'px',
						lineHeight: fontSize * 1.5 + 'px',
						width: wrapWidth + 'px',
						'animationDuration': animationDuration,
						'-webkit-animationDuration': animationDuration,
						animationPlayState: webviewHide ? 'paused' : animationPlayState,
						'-webkit-animationPlayState': webviewHide ? 'paused' : animationPlayState,
						animationDelay: animationDelay,
						'-webkit-animationDelay': animationDelay
					}"
				>{{text}}</text>
			</view>
		</view>
		<view v-if="isShowGetMore" class="uni-noticebar__more uni-cursor-point"
			@click="clickMore">
			<text v-if="moreText.length > 0" :style="{ color: moreColor, fontSize: fontSize + 'px' }">{{ moreText }}</text>
			<uni-icons v-else type="right" :color="moreColor" :size="fontSize * 1.1" />
		</view>
		<view class="uni-noticebar-close uni-cursor-point" v-if="isShowClose">
			<uni-icons type="closeempty" :color="color" :size="fontSize * 1.1" @click="close" />
		</view>
	</view>
</template>

<script>
	// #ifdef APP-NVUE
	const dom = weex.requireModule('dom');
	const animation = weex.requireModule('animation');
	// #endif

	/**
	 * NoticeBar 鑷畾涔夊鑸爮
	 * @description 閫氬憡鏍忕粍浠?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=30
	 * @property {Number} speed 鏂囧瓧婊氬姩鐨勯€熷害锛岄粯璁?00px/绉?
	 * @property {String} text 鏄剧ず鏂囧瓧
	 * @property {String} backgroundColor 鑳屾櫙棰滆壊
	 * @property {String} color 鏂囧瓧棰滆壊
	 * @property {String} moreColor 鏌ョ湅鏇村鏂囧瓧鐨勯鑹?
	 * @property {String} moreText 璁剧疆鈥滄煡鐪嬫洿澶氣€濈殑鏂囨湰
	 * @property {Boolean} single = [true|false] 鏄惁鍗曡
	 * @property {Boolean} scrollable = [true|false] 鏄惁婊氬姩锛屼负true鏃讹紝NoticeBar涓哄崟琛?
	 * @property {Boolean} showIcon = [true|false] 鏄惁鏄剧ず宸︿晶鍠囧彮鍥炬爣
	 * @property {Boolean} showClose = [true|false] 鏄惁鏄剧ず宸︿晶鍏抽棴鎸夐挳
	 * @property {Boolean} showGetMore = [true|false] 鏄惁鏄剧ず鍙充晶鏌ョ湅鏇村鍥炬爣锛屼负true鏃讹紝NoticeBar涓哄崟琛?
	 * @event {Function} click 鐐瑰嚮 NoticeBar 瑙﹀彂浜嬩欢
	 * @event {Function} close 鍏抽棴 NoticeBar 瑙﹀彂浜嬩欢
	 * @event {Function} getmore 鐐瑰嚮鈥濇煡鐪嬫洿澶氣€滄椂瑙﹀彂浜嬩欢
	 */

	export default {
		name: 'UniNoticeBar',
		emits: ['click', 'getmore', 'close'],
		props: {
			text: {
				type: String,
				default: ''
			},
			moreText: {
				type: String,
				default: ''
			},
			backgroundColor: {
				type: String,
				default: '#FFF9EA'
			},
			speed: {
				// 榛樿1s婊氬姩100px
				type: Number,
				default: 100
			},
			color: {
				type: String,
				default: '#FF9A43'
			},
			fontSize: {
				type: Number,
				default: 14
			},
			moreColor: {
				type: String,
				default: '#FF9A43'
			},
			single: {
				// 鏄惁鍗曡
				type: [Boolean, String],
				default: false
			},
			scrollable: {
				// 鏄惁婊氬姩锛屾坊鍔犲悗鎺у埗鍗曡鏁堟灉鍙栨秷
				type: [Boolean, String],
				default: false
			},
			showIcon: {
				// 鏄惁鏄剧ず宸︿晶icon
				type: [Boolean, String],
				default: false
			},
			showGetMore: {
				// 鏄惁鏄剧ず鍙充晶鏌ョ湅鏇村
				type: [Boolean, String],
				default: false
			},
			showClose: {
				// 鏄惁鏄剧ず宸︿晶鍏抽棴鎸夐挳
				type: [Boolean, String],
				default: false
			}
		},
		data() {
			const elId = `Uni_${Math.ceil(Math.random() * 10e5).toString(36)}`
			const elIdBox = `Uni_${Math.ceil(Math.random() * 10e5).toString(36)}`
			return {
				textWidth: 0,
				boxWidth: 0,
				wrapWidth: '',
				webviewHide: false,
				// #ifdef APP-NVUE
				stopAnimation: false,
				// #endif
				elId: elId,
				elIdBox: elIdBox,
				show: true,
				animationDuration: 'none',
				animationPlayState: 'paused',
				animationDelay: '0s'
			}
		},
		watch:{
			text:function(newValue,oldValue){
				this.initSize();
			}
		},
		computed: {
			isShowGetMore() {
				return this.showGetMore === true || this.showGetMore === 'true'
			},
			isShowClose() {
				return (this.showClose === true || this.showClose === 'true') 
					&& (this.showGetMore === false || this.showGetMore === 'false')
			}
		},
		mounted() {
			// #ifdef APP-PLUS
			var pages = getCurrentPages();
			var page = pages[pages.length - 1];
			var currentWebview = page.$getAppWebview();
			currentWebview.addEventListener('hide', () => {
				this.webviewHide = true
			})
			currentWebview.addEventListener('show', () => {
				this.webviewHide = false
			})
			// #endif
			this.$nextTick(() => {
				this.initSize()
			})
		},
		// #ifdef APP-NVUE
		beforeDestroy() {
			this.stopAnimation = true
		},
		// #endif
		methods: {
			initSize() {
				if (this.scrollable) {
					// #ifndef APP-NVUE
					let query = [],
						boxWidth = 0,
						textWidth = 0;
					let textQuery = new Promise((resolve, reject) => {
						uni.createSelectorQuery()
							// #ifndef MP-ALIPAY
							.in(this)
							// #endif
							.select(`#${this.elId}`)
							.boundingClientRect()
							.exec(ret => {
								this.textWidth = ret[0].width
								resolve()
							})
					})
					let boxQuery = new Promise((resolve, reject) => {
						uni.createSelectorQuery()
							// #ifndef MP-ALIPAY
							.in(this)
							// #endif
							.select(`#${this.elIdBox}`)
							.boundingClientRect()
							.exec(ret => {
								this.boxWidth = ret[0].width
								resolve()
							})
					})
					query.push(textQuery)
					query.push(boxQuery)
					Promise.all(query).then(() => {
						this.animationDuration = `${this.textWidth / this.speed}s`
						this.animationDelay = `-${this.boxWidth / this.speed}s`
						setTimeout(() => {
							this.animationPlayState = 'running'
						}, 1000)
					})
					// #endif
					// #ifdef APP-NVUE
					dom.getComponentRect(this.$refs['animationEle'], (res) => {
						let winWidth = uni.getSystemInfoSync().windowWidth
						this.textWidth = res.size.width
						animation.transition(this.$refs['animationEle'], {
							styles: {
								transform: `translateX(-${winWidth}px)`
							},
							duration: 0,
							timingFunction: 'linear',
							delay: 0
						}, () => {
							if (!this.stopAnimation) {
								animation.transition(this.$refs['animationEle'], {
									styles: {
										transform: `translateX(-${this.textWidth}px)`
									},
									timingFunction: 'linear',
									duration: (this.textWidth - winWidth) / this.speed * 1000,
									delay: 1000
								}, () => {
									if (!this.stopAnimation) {
										this.loopAnimation()
									}
								});
							}
						});
					})
					// #endif
				}
				// #ifdef APP-NVUE
				if (!this.scrollable && (this.single || this.moreText)) {
					dom.getComponentRect(this.$refs['textBox'], (res) => {
						this.wrapWidth = res.size.width
					})
				}
				// #endif
			},
			loopAnimation() {
				// #ifdef APP-NVUE
				animation.transition(this.$refs['animationEle'], {
					styles: {
						transform: `translateX(0px)`
					},
					duration: 0
				}, () => {
					if (!this.stopAnimation) {
						animation.transition(this.$refs['animationEle'], {
							styles: {
								transform: `translateX(-${this.textWidth}px)`
							},
							duration: this.textWidth / this.speed * 1000,
							timingFunction: 'linear',
							delay: 0
						}, () => {
							if (!this.stopAnimation) {
								this.loopAnimation()
							}
						});
					}
				});
				// #endif
			},
			clickMore() {
				this.$emit('getmore')
			},
			close() {
				this.show = false;
				this.$emit('close')
			},
			onClick() {
				this.$emit('click')
			}
		}
	}
</script>

<style lang="scss" scoped>
	.uni-noticebar {
		/* #ifndef APP-NVUE */
		display: flex;
		width: 100%;
		box-sizing: border-box;
		/* #endif */
		flex-direction: row;
		align-items: center;
		padding: 10px 12px;
		margin-bottom: 10px;
	}

	.uni-cursor-point {
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.uni-noticebar-close {
		margin-left: 8px;
		margin-right: 5px;
	}

	.uni-noticebar-icon {
		margin-right: 5px;
	}

	.uni-noticebar__content-wrapper {
		flex: 1;
		flex-direction: column;
		overflow: hidden;
	}

	.uni-noticebar__content-wrapper--single {
		/* #ifndef APP-NVUE */
		line-height: 18px;
		/* #endif */
	}

	.uni-noticebar__content-wrapper--single,
	.uni-noticebar__content-wrapper--scrollable {
		flex-direction: row;
	}

	/* #ifndef APP-NVUE */
	.uni-noticebar__content-wrapper--scrollable {
		position: relative;
	}

	/* #endif */

	.uni-noticebar__content--scrollable {
		/* #ifdef APP-NVUE */
		flex: 0;
		/* #endif */
		/* #ifndef APP-NVUE */
		flex: 1;
		display: block;
		overflow: hidden;
		/* #endif */
	}

	.uni-noticebar__content--single {
		/* #ifndef APP-NVUE */
		display: flex;
		flex: none;
		width: 100%;
		justify-content: center;
		/* #endif */
	}

	.uni-noticebar__content-text {
		font-size: 14px;
		line-height: 18px;
		/* #ifndef APP-NVUE */
		word-break: break-all;
		/* #endif */
	}

	.uni-noticebar__content-text--single {
		/* #ifdef APP-NVUE */
		lines: 1;
		/* #endif */
		/* #ifndef APP-NVUE */
		display: block;
		width: 100%;
		white-space: nowrap;
		/* #endif */
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.uni-noticebar__content-text--scrollable {
		/* #ifdef APP-NVUE */
		lines: 1;
		padding-left: 750rpx;
		/* #endif */
		/* #ifndef APP-NVUE */
		position: absolute;
		display: block;
		height: 18px;
		line-height: 18px;
		white-space: nowrap;
		padding-left: 100%;
		animation: notice 10s 0s linear infinite both;
		animation-play-state: paused;
		/* #endif */
	}

	.uni-noticebar__more {
		/* #ifndef APP-NVUE */
		display: inline-flex;
		/* #endif */
		flex-direction: row;
		flex-wrap: nowrap;
		align-items: center;
		padding-left: 5px;
	}

	@keyframes notice {
		100% {
			transform: translate3d(-100%, 0, 0);
		}
	}
</style>


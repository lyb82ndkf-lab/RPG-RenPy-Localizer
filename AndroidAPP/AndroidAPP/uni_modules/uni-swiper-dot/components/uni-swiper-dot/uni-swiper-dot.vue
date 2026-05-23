<template>
	<view class="uni-swiper__warp">
		<slot />
		<view v-if="mode === 'default'" :style="{'bottom':dots.bottom + 'px'}" class="uni-swiper__dots-box" key='default'>
			<view v-for="(item,index) in info" @click="clickItem(index)" :style="{
        'width': (index === current? dots.width*2:dots.width ) + 'px','height':dots.width/2 +'px' ,'background-color':index !== current?dots.backgroundColor:dots.selectedBackgroundColor,'border-radius':'0px'}"
			 :key="index" class="uni-swiper__dots-item uni-swiper__dots-bar" />
		</view>
		<view v-if="mode === 'dot'" :style="{'bottom':dots.bottom + 'px'}" class="uni-swiper__dots-box" key='dot'>
			<view v-for="(item,index) in info" @click="clickItem(index)" :style="{
        'width': dots.width + 'px','height':dots.height +'px' ,'background-color':index !== current?dots.backgroundColor:dots.selectedBackgroundColor,'border':index !==current ? dots.border:dots.selectedBorder}"
			 :key="index" class="uni-swiper__dots-item" />
		</view>
		<view v-if="mode === 'round'" :style="{'bottom':dots.bottom + 'px'}" class="uni-swiper__dots-box" key='round'>
			<view v-for="(item,index) in info" @click="clickItem(index)" :class="[index === current&&'uni-swiper__dots-long']" :style="{
		    'width':(index === current? dots.width*3:dots.width ) + 'px','height':dots.height +'px' ,'background-color':index !== current?dots.backgroundColor:dots.selectedBackgroundColor,'border':index !==current ? dots.border:dots.selectedBorder}"
			 :key="index" class="uni-swiper__dots-item " />
		</view>
		<view v-if="mode === 'nav'" key='nav' :style="{'background-color':dotsStyles.backgroundColor,'bottom':'0'}" class="uni-swiper__dots-box uni-swiper__dots-nav">
			<text :style="{'color':dotsStyles.color}" class="uni-swiper__dots-nav-item">{{ (current+1)+"/"+info.length +' ' +info[current][field] }}</text>
		</view>
		<view v-if="mode === 'indexes'" key='indexes' :style="{'bottom':dots.bottom + 'px'}" class="uni-swiper__dots-box">
			<view v-for="(item,index) in info" @click="clickItem(index)" :style="{
        'width':dots.width + 'px','height':dots.height +'px' ,'color':index === current?dots.selectedColor:dots.color,'background-color':index !== current?dots.backgroundColor:dots.selectedBackgroundColor,'border':index !==current ? dots.border:dots.selectedBorder}"
			 :key="index" class="uni-swiper__dots-item uni-swiper__dots-indexes"><text class="uni-swiper__dots-indexes-text">{{ index+1 }}</text></view>
		</view>
	</view>
</template>

<script>

	/**
	 * SwiperDod 杞挱鍥炬寚绀虹偣
	 * @description 鑷畾涔夎疆鎾浘鎸囩ず鐐?	 * @tutorial https://ext.dcloud.net.cn/plugin?id=284
	 * @property {Number} current 褰撳墠鎸囩ず鐐圭储寮曪紝蹇呴』鏄€氳繃 `swiper` 鐨?`change` 浜嬩欢鑾峰彇鍒扮殑 `e.detail.current`
	 * @property {String} mode = [default|round|nav|indexes] 鎸囩ず鐐圭殑绫诲瀷
	 * 	@value defualt 榛樿鎸囩ず鐐?	 * 	@value round 鍦嗗舰鎸囩ず鐐?	 * 	@value nav 鏉″舰鎸囩ず鐐?	 * 	@value indexes 绱㈠紩鎸囩ず鐐?	 * @property {String} field mode 涓?nav 鏃讹紝鏄剧ず鐨勫唴瀹瑰瓧娈碉紙mode = nav 鏃跺繀濉級
	 * @property {String} info 杞挱鍥剧殑鏁版嵁锛岄€氳繃鏁扮粍闀垮害鍐冲畾鎸囩ず鐐逛釜鏁?	 * @property {Object} dotsStyles 鎸囩ず鐐规牱寮?	 * @event {Function} clickItem 缁勪欢瑙﹀彂鐐瑰嚮浜嬩欢鏃惰Е鍙戯紝e={currentIndex}
	 */

	export default {
		name: 'UniSwiperDot',
		emits:['clickItem'],
		props: {
			info: {
				type: Array,
				default () {
					return []
				}
			},
			current: {
				type: Number,
				default: 0
			},
			dotsStyles: {
				type: Object,
				default () {
					return {}
				}
			},
			// 绫诲瀷 锛歞efault(榛樿) indexes long nav
			mode: {
				type: String,
				default: 'default'
			},
			// 鍙湪 nav 妯″紡涓嬬敓鏁堬紝鍙橀噺鍚嶇О
			field: {
				type: String,
				default: ''
			}
		},
		data() {
			return {
				dots: {
					width: 6,
					height: 6,
					bottom: 10,
					color: '#fff',
					backgroundColor: 'rgba(0, 0, 0, .3)',
					border: '1px rgba(0, 0, 0, .3) solid',
					selectedBackgroundColor: '#333',
					selectedBorder: '1px rgba(0, 0, 0, .9) solid'
				}
			}
		},
		watch: {
			dotsStyles(newVal) {
				this.dots = Object.assign(this.dots, this.dotsStyles)
			},
			mode(newVal) {
				if (newVal === 'indexes') {
					this.dots.width = 14
					this.dots.height = 14
				} else {
					this.dots.width = 6
					this.dots.height = 6
				}
			}

		},
		created() {
			if (this.mode === 'indexes') {
				this.dots.width = 12
				this.dots.height = 12
			}
			this.dots = Object.assign(this.dots, this.dotsStyles)
		},
		methods: {
			clickItem(index) {
				this.$emit('clickItem', index)
			}
		}
	}
</script>

<style lang="scss" scoped>
	.uni-swiper__warp {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex: 1;
		flex-direction: column;
		position: relative;
		overflow: hidden;
	}

	.uni-swiper__dots-box {
		position: absolute;
		bottom: 10px;
		left: 0;
		right: 0;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex: 1;
		flex-direction: row;
		justify-content: center;
		align-items: center;
	}

	.uni-swiper__dots-item {
		width: 8px;
		border-radius: 100px;
		margin-left: 6px;
		background-color: rgba(0, 0, 0, 0.4);
		/* #ifndef APP-NVUE */
		cursor: pointer;
		/* #endif */
		/* #ifdef H5 */
		// border-width: 5px 0;
		// border-style: solid;
		// border-color: transparent;
		// background-clip: padding-box;
		/* #endif */
		// transition: width 0.2s linear;  涓嶈鍙栨秷娉ㄩ噴锛屼笉鐒朵細涓嶈兘鍙樿壊
	}

	.uni-swiper__dots-item:first-child {
		margin: 0;
	}

	.uni-swiper__dots-default {
		border-radius: 100px;
	}

	.uni-swiper__dots-long {
		border-radius: 50px;
	}

	.uni-swiper__dots-bar {
		border-radius: 50px;
	}

	.uni-swiper__dots-nav {
		bottom: 0px;
		// height: 26px;
		padding: 8px 0;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex: 1;
		flex-direction: row;
		justify-content: flex-start;
		align-items: center;
		background-color: rgba(0, 0, 0, 0.2);
	}

	.uni-swiper__dots-nav-item {
		/* overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap; */
		font-size: 14px;
		color: #fff;
		margin: 0 15px;
	}

	.uni-swiper__dots-indexes {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		// flex: 1;
		justify-content: center;
		align-items: center;
	}

	.uni-swiper__dots-indexes-text {
		color: #fff;
		font-size: 12px;
		line-height: 14px;
	}
</style>


<template>
	<view :class="[circle === true || circle === 'true' ? 'uni-fav--circle' : '']" :style="[{ backgroundColor: checked ? bgColorChecked : bgColor }]"
	 @click="onClick" class="uni-fav">
		<!-- #ifdef MP-ALIPAY -->
		<view class="uni-fav-star" v-if="!checked && (star === true || star === 'true')">
			<uni-icons :color="fgColor" :style="{color: checked ? fgColorChecked : fgColor}" size="14" type="star-filled" />
		</view>
		<!-- #endif -->
		<!-- #ifndef MP-ALIPAY -->
		<uni-icons :color="fgColor" :style="{color: checked ? fgColorChecked : fgColor}" class="uni-fav-star" size="14" type="star-filled"
		 v-if="!checked && (star === true || star === 'true')" />
		<!-- #endif -->
		<text :style="{color: checked ? fgColorChecked : fgColor}" class="uni-fav-text">{{ checked ? contentFav : contentDefault }}</text>
	</view>
</template>

<script>

	/**
	 * Fav 鏀惰棌鎸夐挳
	 * @description 鐢ㄤ簬鏀惰棌鍔熻兘锛屽彲鐐瑰嚮鍒囨崲閫変腑銆佷笉閫変腑鐨勭姸鎬?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=864
	 * @property {Boolean} star = [true|false] 鎸夐挳鏄惁甯︽槦鏄?
	 * @property {String} bgColor 鏈敹钘忔椂鐨勮儗鏅壊
	 * @property {String} bgColorChecked 宸叉敹钘忔椂鐨勮儗鏅壊
	 * @property {String} fgColor 鏈敹钘忔椂鐨勬枃瀛楅鑹?
	 * @property {String} fgColorChecked 宸叉敹钘忔椂鐨勬枃瀛楅鑹?
	 * @property {Boolean} circle = [true|false] 鏄惁涓哄渾瑙?
	 * @property {Boolean} checked = [true|false] 鏄惁涓哄凡鏀惰棌
	 * @property {Object} contentText = [true|false] 鏀惰棌鎸夐挳鏂囧瓧
	 * @property {Boolean} stat 鏄惁寮€鍚粺璁″姛鑳?
	 * @event {Function} click 鐐瑰嚮 fav鎸夐挳瑙﹀彂浜嬩欢
	 * @example <uni-fav :checked="true"/>
	 */

	import {
		initVueI18n
	} from '@dcloudio/uni-i18n'
	import messages from './i18n/index.js'
	const {	t	} = initVueI18n(messages)

	export default {
		name: "UniFav",
		// TODO 鍏煎 vue3锛岄渶瑕佹敞鍐屼簨浠?
		emits: ['click'],
		props: {
			star: {
				type: [Boolean, String],
				default: true
			},
			bgColor: {
				type: String,
				default: "#eeeeee"
			},
			fgColor: {
				type: String,
				default: "#666666"
			},
			bgColorChecked: {
				type: String,
				default: "#007aff"
			},
			fgColorChecked: {
				type: String,
				default: "#FFFFFF"
			},
			circle: {
				type: [Boolean, String],
				default: false
			},
			checked: {
				type: Boolean,
				default: false
			},
			contentText: {
				type: Object,
				default () {
					return {
						contentDefault: "",
						contentFav: ""
					};
				}
			},
			stat:{
				type: Boolean,
				default: false
			}
		},
		computed: {
			contentDefault() {
				return this.contentText.contentDefault || t("uni-fav.collect")
			},
			contentFav() {
				return this.contentText.contentFav || t("uni-fav.collected")
			},
		},
		watch: {
			checked() {
				if (uni.report && this.stat) {
					if (this.checked) {
						uni.report("鏀惰棌", "鏀惰棌");
					} else {
						uni.report("鍙栨秷鏀惰棌", "鍙栨秷鏀惰棌");
					}
				}
			}
		},
		methods: {
			onClick() {
				this.$emit("click");
			}
		}
	};
</script>

<style lang="scss" >
	$fav-height: 25px;

	.uni-fav {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		align-items: center;
		justify-content: center;
		width: 60px;
		height: $fav-height;
		line-height: $fav-height;
		text-align: center;
		border-radius: 3px;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	.uni-fav--circle {
		border-radius: 30px;
	}

	.uni-fav-star {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		height: $fav-height;
		line-height: 24px;
		margin-right: 3px;
		align-items: center;
		justify-content: center;
	}

	.uni-fav-text {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		height: $fav-height;
		line-height: $fav-height;
		align-items: center;
		justify-content: center;
		font-size: 12px;
	}
</style>


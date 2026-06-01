<template>
	<view :class="[ 'uni-row', typeClass , justifyClass, alignClass, ]" :style="{
		marginLeft:`${Number(marginValue)}rpx`,
		marginRight:`${Number(marginValue)}rpx`,
	}">
		<slot></slot>
	</view>
</template>

<script>
	const ComponentClass = 'uni-row';
	const modifierSeparator = '--';
	/**
	 * Row	甯冨眬-琛?
	 * @description	娴佸紡鏍呮牸绯荤粺锛岄殢鐫€灞忓箷鎴栬鍙ｅ垎涓?24 浠斤紝鍙互杩呴€熺畝渚垮湴鍒涘缓甯冨眬銆?
	 * @tutorial	https://ext.dcloud.net.cn/plugin?id=3958
	 *
	 * @property	{gutter} type = Number 鏍呮牸闂撮殧
	 * @property	{justify} type = String flex 甯冨眬涓嬬殑姘村钩鎺掑垪鏂瑰紡
	 * 						鍙€?start/end/center/space-around/space-between	start
	 * 						榛樿鍊?start
	 * @property	{align} type = String flex 甯冨眬涓嬬殑鍨傜洿鎺掑垪鏂瑰紡
	 * 						鍙€?top/middle/bottom
	 * 						榛樿鍊?top
	 * @property	{width} type = String|Number nvue涓嬮渶瑕佽嚜琛岄厤缃搴︾敤浜庤绠?
	 * 						榛樿鍊?750
	 */


	export default {
		name: 'uniRow',
		componentName: 'uniRow',
		// #ifdef MP-WEIXIN
		options: {
			virtualHost: true // 鍦ㄥ井淇″皬绋嬪簭涓皢缁勪欢鑺傜偣娓叉煋涓鸿櫄鎷熻妭鐐癸紝鏇村姞鎺ヨ繎Vue缁勪欢鐨勮〃鐜帮紝鍙娇鐢╢lex甯冨眬
		},
		// #endif
		props: {
			type: String,
			gutter: Number,
			justify: {
				type: String,
				default: 'start'
			},
			align: {
				type: String,
				default: 'top'
			},
			// nvue濡傛灉浣跨敤span绛夊睘鎬э紝闇€瑕侀厤缃搴?
			width: {
				type: [String, Number],
				default: 750
			}
		},
		created() {
			// #ifdef APP-NVUE
			this.type = 'flex';
			// #endif
		},
		computed: {
			marginValue() {
				// #ifndef APP-NVUE
				if (this.gutter) {
					return -(this.gutter / 2);
				}
				// #endif
				return 0;
			},
			typeClass() {
				return this.type === 'flex' ? `${ComponentClass + modifierSeparator}flex` : '';
			},
			justifyClass() {
				return this.justify !== 'start' ? `${ComponentClass + modifierSeparator}flex-justify-${this.justify}` : ''
			},
			alignClass() {
				return this.align !== 'top' ? `${ComponentClass + modifierSeparator}flex-align-${this.align}` : ''
			}
		}
	};
</script>

<style lang="scss">
	$layout-namespace: ".uni-";
	$row:$layout-namespace+"row";
	$modifier-separator: "--";

	@mixin utils-clearfix {
		$selector: &;

		@at-root {

			/* #ifndef APP-NVUE */
			#{$selector}::before,
			#{$selector}::after {
				display: table;
				content: "";
			}

			#{$selector}::after {
				clear: both;
			}

			/* #endif */
		}

	}

	@mixin utils-flex ($direction: row) {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: $direction;
	}

	@mixin set-flex($state) {
		@at-root &-#{$state} {
			@content
		}
	}

	#{$row} {
		position: relative;
		flex-direction: row;

		/* #ifdef APP-NVUE */
		flex: 1;
		/* #endif */

		/* #ifndef APP-NVUE */
		box-sizing: border-box;
		/* #endif */

		// 闈瀗vue浣跨敤float甯冨眬
		@include utils-clearfix;

		// 鍦≦Q銆佸瓧鑺傘€佺櫨搴﹀皬绋嬪簭骞冲彴锛岀紪璇戝悗浣跨敤shadow dom锛屼笉鍙娇鐢╢lex甯冨眬锛屼娇鐢╢loat
		@at-root {

			/* #ifndef MP-QQ || MP-TOUTIAO || MP-BAIDU */
			&#{$modifier-separator}flex {
				@include utils-flex;
				flex-wrap: wrap;
				flex: 1;

				&:before,
				&:after {
					/* #ifndef APP-NVUE */
					display: none;
					/* #endif */
				}

				@include set-flex(justify-center) {
					justify-content: center;
				}

				@include set-flex(justify-end) {
					justify-content: flex-end;
				}

				@include set-flex(justify-space-between) {
					justify-content: space-between;
				}

				@include set-flex(justify-space-around) {
					justify-content: space-around;
				}

				@include set-flex(align-middle) {
					align-items: center;
				}

				@include set-flex(align-bottom) {
					align-items: flex-end;
				}
			}

			/* #endif */
		}

	}

	// 瀛楄妭銆丵Q閰嶇疆鍚庝笉鐢熸晥
	// 姝ゅ鐢ㄦ硶鏃犳硶浣跨敤scoped
	/* #ifdef MP-WEIXIN || MP-TOUTIAO || MP-QQ */
	:host {
		display: block;
	}

	/* #endif */
</style>


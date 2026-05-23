<template>
	<view class="uni-tooltip">
		<slot></slot>
		<view v-if="content || $slots.content" class="uni-tooltip-popup" :style="initPlacement">
			<slot name="content">
				{{content}}
			</slot>
		</view>
	</view>
</template>


<script>
	/**
	 * Tooltip 鎻愮ず鏂囧瓧
	 * @description 甯哥敤浜庡睍绀洪紶鏍?hover 鏃剁殑鎻愮ず淇℃伅銆?
	 * @tutorial https://uniapp.dcloud.io/component/uniui/uni-tooltip
	 * @property {String} content   寮瑰嚭灞傛樉绀虹殑鍐呭
	 * @property {String}  placement鍑虹幇浣嶇疆, 鐩墠鏀寔锛歭eft right top bottom
	 */
	export default {
		name: "uni-tooltip",
		data() {
			return {

			};
		},
		methods: {},
		computed: {
			initPlacement() {
				let style = {};
				switch (this.placement) {
					case 'left':
						style = {
							top: '50%',
							transform: 'translateY(-50%)',
							right: '100%',
							"margin-right": '10rpx',
						}
						break;
					case 'right':
						style = {
							top: '50%',
							transform: 'translateY(-50%)',
							left: '100%',
							"margin-left": '10rpx',
						}
						break;
					case 'top':
						style = {
							bottom: '100%',
							transform: 'translateX(-50%)',
							left: '50%',
							"margin-bottom": '10rpx',
						}
						break;
					case 'bottom':
						style = {
							top: '100%',
							transform: 'translateX(-50%)',
							left: '50%',
							"margin-top": '10rpx',
						}
						break;
				}
				return style;
			}
		},
		props: {
			content: {
				type: String,
				default: ''
			},

			placement: {
				type: String,
				default: 'bottom'
			},
		}
	}
</script>

<style>
	.uni-tooltip {
		position: relative;
		cursor: pointer;
		display: inline-block;
	}

	.uni-tooltip-popup {
		z-index: 1;
		display: none;
		position: absolute;
		background-color: #333;
		border-radius: 8px;
		color: #fff;
		font-size: 12px;
		text-align: left;
		line-height: 16px;
		padding: 12px;
		overflow: auto;
	}


	.uni-tooltip:hover .uni-tooltip-popup {
		display: block;
	}
</style>


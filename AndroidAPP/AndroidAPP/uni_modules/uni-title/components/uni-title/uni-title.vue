<template>
	<view class="uni-title__box" :style="{'align-items':textAlign}">
		<text class="uni-title__base" :class="['uni-'+type]" :style="{'color':color}">{{title}}</text>
	</view>
</template>

<script>
	/**
	 * Title 鏍囬
	 * @description 鏍囬锛岄€氬父鐢ㄤ簬璁板綍椤甸潰鏍囬锛屼娇鐢ㄥ綋鍓嶇粍浠讹紝uni-app 濡傛灉寮€鍚粺璁★紝灏嗕細鑷姩缁熻椤甸潰鏍囬
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=1066
	 * @property {String} type = [h1|h2|h3|h4|h5] 鏍囬绫诲瀷
	 * 	@value h1 涓€绾ф爣棰?	 * 	@value h2 浜岀骇鏍囬
	 * 	@value h3 涓夌骇鏍囬
	 * 	@value h4 鍥涚骇鏍囬
	 * 	@value h5 浜旂骇鏍囬
	 * @property {String} title 鏍囬鍐呭
	 * @property {String} align = [left|center|right] 瀵归綈鏂瑰紡
	 * 	@value left 鍋氬榻?	 * 	@value center 灞呬腑瀵归綈
	 * 	@value right 鍙冲榻?	 * @property {String} color 瀛椾綋棰滆壊
	 * @property {Boolean} stat = [true|false] 鏄惁寮€鍚粺璁″姛鑳藉憿锛屽涓嶅～鍐檛ype鍊硷紝榛樿涓哄紑鍚紝濉啓 type 灞炴€э紝榛樿涓哄叧闂?	 */
	export default {
		name:"UniTitle",
		props: {
			type: {
				type: String,
				default: ''
			},
			title: {
				type: String,
				default: ''
			},
			align: {
				type: String,
				default: 'left'
			},
			color: {
				type: String,
				default: '#333333'
			},
			stat: {
				type: [Boolean, String],
				default: ''
			}
		},
		data() {
			return {

			};
		},
		computed: {
			textAlign() {
				let align = 'center';
				switch (this.align) {
					case 'left':
						align = 'flex-start'
						break;
					case 'center':
						align = 'center'
						break;
					case 'right':
						align = 'flex-end'
						break;
				}
				return align
			}
		},
		watch: {
			title(newVal) {
				if (this.isOpenStat()) {
					// 涓婃姤鏁版嵁
					if (uni.report) {
						uni.report('title', this.title)
					}
				}
			}
		},
		mounted() {
			if (this.isOpenStat()) {
				// 涓婃姤鏁版嵁
				if (uni.report) {
					uni.report('title', this.title)
				}
			}
		},
		methods: {
			isOpenStat() {
				if (this.stat === '') {
					this.isStat = false
				}
				let stat_type = (typeof(this.stat) === 'boolean' && this.stat) || (typeof(this.stat) === 'string' && this.stat !==
					'')
				if (this.type === "") {
					this.isStat = true
					if (this.stat.toString() === 'false') {
						this.isStat = false
					}
				}

				if (this.type !== '') {
					this.isStat = true
					if (stat_type) {
						this.isStat = true
					} else {
						this.isStat = false
					}
				}
				return this.isStat
			}
		}
	}
</script>

<style>
	/* .uni-title {

	} */
	.uni-title__box {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: column;
		align-items: flex-start;
		justify-content: center;
		padding: 8px 0;
		flex: 1;
	}

	.uni-title__base {
		font-size: 15px;
		color: #333;
		font-weight: 500;
	}

	.uni-h1 {
		font-size: 20px;
		color: #333;
		font-weight: bold;
	}

	.uni-h2 {
		font-size: 18px;
		color: #333;
		font-weight: bold;
	}

	.uni-h3 {
		font-size: 16px;
		color: #333;
		font-weight: bold;
		/* font-weight: 400; */
	}

	.uni-h4 {
		font-size: 14px;
		color: #333;
		font-weight: bold;
		/* font-weight: 300; */
	}

	.uni-h5 {
		font-size: 12px;
		color: #333;
		font-weight: bold;
		/* font-weight: 200; */
	}
</style>


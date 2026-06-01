<template>
	<!-- #ifdef APP-NVUE -->
	<text :style="styleObj" class="uni-icons" @click="_onClick">{{unicode}}</text>
	<!-- #endif -->
	<!-- #ifndef APP-NVUE -->
	<text :style="styleObj" class="uni-icons" :class="['uniui-'+type,customPrefix,customPrefix?type:'']" @click="_onClick">
		<slot></slot>
	</text>
	<!-- #endif -->
</template>

<script>
	import { fontData } from './uniicons_file_vue.js';

	const getVal = (val) => {
		const reg = /^[0-9]*$/g
		return (typeof val === 'number' || reg.test(val)) ? val + 'px' : val;
	}

	// #ifdef APP-NVUE
	var domModule = weex.requireModule('dom');
	import iconUrl from './uniicons.ttf'
	domModule.addRule('fontFace', {
		'fontFamily': "uniicons",
		'src': "url('" + iconUrl + "')"
	});
	// #endif

	/**
	 * Icons 鍥炬爣
	 * @description 鐢ㄤ簬灞曠ず icons 鍥炬爣
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=28
	 * @property {Number} size 鍥炬爣澶у皬
	 * @property {String} type 鍥炬爣鍥炬锛屽弬鑰冪ず渚?
	 * @property {String} color 鍥炬爣棰滆壊
	 * @property {String} customPrefix 鑷畾涔夊浘鏍?
	 * @event {Function} click 鐐瑰嚮 Icon 瑙﹀彂浜嬩欢
	 */
	export default {
		name: 'UniIcons',
		emits: ['click'],
		props: {
			type: {
				type: String,
				default: ''
			},
			color: {
				type: String,
				default: '#333333'
			},
			size: {
				type: [Number, String],
				default: 16
			},
			customPrefix: {
				type: String,
				default: ''
			},
			fontFamily: {
				type: String,
				default: ''
			}
		},
		data() {
			return {
				icons: fontData
			}
		},
		computed: {
			unicode() {
				let code = this.icons.find(v => v.font_class === this.type)
				if (code) {
					return code.unicode
				}
				return ''
			},
			iconSize() {
				return getVal(this.size)
			},
			styleObj() {
				if (this.fontFamily !== '') {
					return `color: ${this.color}; font-size: ${this.iconSize}; font-family: ${this.fontFamily};`
				}
				return `color: ${this.color}; font-size: ${this.iconSize};`
			}
		},
		methods: {
			_onClick() {
				this.$emit('click')
			}
		}
	}
</script>

<style lang="scss">
	/* #ifndef APP-NVUE */
	@import './uniicons.css';

	@font-face {
		font-family: uniicons;
		src: url('./uniicons.ttf');
	}

	/* #endif */
	.uni-icons {
		font-family: uniicons;
		text-decoration: none;
		text-align: center;
	}
</style>


<template>
  <!-- #ifndef APP-NVUE -->
  <view v-show="isShow" ref="ani" :animation="animationData" :class="customClass" :style="transformStyles" @click="onClick"><slot></slot></view>
  <!-- #endif -->
  <!-- #ifdef APP-NVUE -->
  <view v-if="isShow" ref="ani" :animation="animationData" :class="customClass" :style="transformStyles" @click="onClick"><slot></slot></view>
  <!-- #endif -->
</template>

<script>
import { createAnimation } from './createAnimation'

/**
 * Transition 杩囨浮鍔ㄧ敾
 * @description 绠€鍗曡繃娓″姩鐢荤粍浠?
 * @tutorial https://ext.dcloud.net.cn/plugin?id=985
 * @property {Boolean} show = [false|true] 鎺у埗缁勪欢鏄剧ず鎴栭殣钘?
 * @property {Array|String} modeClass = [fade|slide-top|slide-right|slide-bottom|slide-left|zoom-in|zoom-out] 杩囨浮鍔ㄧ敾绫诲瀷
 *  @value fade 娓愰殣娓愬嚭杩囨浮
 *  @value slide-top 鐢变笂鑷充笅杩囨浮
 *  @value slide-right 鐢卞彸鑷冲乏杩囨浮
 *  @value slide-bottom 鐢变笅鑷充笂杩囨浮
 *  @value slide-left 鐢卞乏鑷冲彸杩囨浮
 *  @value zoom-in 鐢卞皬鍒板ぇ杩囨浮
 *  @value zoom-out 鐢卞ぇ鍒板皬杩囨浮
 * @property {Number} duration 杩囨浮鍔ㄧ敾鎸佺画鏃堕棿
 * @property {Object} styles 缁勪欢鏍峰紡锛屽悓 css 鏍峰紡锛屾敞鎰忓甫鈥?鈥樿繛鎺ョ鐨勫睘鎬ч渶瑕佷娇鐢ㄥ皬椹煎嘲鍐欐硶濡傦細`backgroundColor:red`
 */
export default {
	name: 'uniTransition',
	emits:['click','change'],
	props: {
		show: {
			type: Boolean,
			default: false
		},
		modeClass: {
			type: [Array, String],
			default() {
				return 'fade'
			}
		},
		duration: {
			type: Number,
			default: 300
		},
		styles: {
			type: Object,
			default() {
				return {}
			}
		},
		customClass:{
			type: String,
			default: ''
		},
		onceRender:{
			type:Boolean,
			default:false
		},
	},
	data() {
		return {
			isShow: false,
			transform: '',
			opacity: 1,
			animationData: {},
			durationTime: 300,
			config: {}
		}
	},
	watch: {
		show: {
			handler(newVal) {
				if (newVal) {
					this.open()
				} else {
					// 閬垮厤涓婃潵灏辨墽琛?close,瀵艰嚧鍔ㄧ敾閿欎贡
					if (this.isShow) {
						this.close()
					}
				}
			},
			immediate: true
		}
	},
	computed: {
		// 鐢熸垚鏍峰紡鏁版嵁
		stylesObject() {
			let styles = {
				...this.styles,
				'transition-duration': this.duration / 1000 + 's'
			}
			let transform = ''
			for (let i in styles) {
				let line = this.toLine(i)
				transform += line + ':' + styles[i] + ';'
			}
			return transform
		},
		// 鍒濆鍖栧姩鐢绘潯浠?
		transformStyles() {
			return 'transform:' + this.transform + ';' + 'opacity:' + this.opacity + ';' + this.stylesObject
		}
	},
	created() {
		// 鍔ㄧ敾榛樿閰嶇疆
		this.config = {
			duration: this.duration,
			timingFunction: 'ease',
			transformOrigin: '50% 50%',
			delay: 0
		}
		this.durationTime = this.duration
	},
	methods: {
		/**
		 *  ref 瑙﹀彂 鍒濆鍖栧姩鐢?
		 */
		init(obj = {}) {
			if (obj.duration) {
				this.durationTime = obj.duration
			}
			this.animation = createAnimation(Object.assign(this.config, obj),this)
		},
		/**
		 * 鐐瑰嚮缁勪欢瑙﹀彂鍥炶皟
		 */
		onClick() {
			this.$emit('click', {
				detail: this.isShow
			})
		},
		/**
		 * ref 瑙﹀彂 鍔ㄧ敾鍒嗙粍
		 * @param {Object} obj
		 */
		step(obj, config = {}) {
			if (!this.animation) return
			for (let i in obj) {
				try {
					if(typeof obj[i] === 'object'){
						this.animation[i](...obj[i])
					}else{
						this.animation[i](obj[i])
					}
				} catch (e) {
					console.error(`鏂规硶 ${i} 涓嶅瓨鍦╜)
				}
			}
			this.animation.step(config)
			return this
		},
		/**
		 *  ref 瑙﹀彂 鎵ц鍔ㄧ敾
		 */
		run(fn) {
			if (!this.animation) return
			this.animation.run(fn)
		},
		// 寮€濮嬭繃搴﹀姩鐢?
		open() {
			clearTimeout(this.timer)
			this.transform = ''
			this.isShow = true
			let { opacity, transform } = this.styleInit(false)
			if (typeof opacity !== 'undefined') {
				this.opacity = opacity
			}
			this.transform = transform
			// 纭繚鍔ㄦ€佹牱寮忓凡缁忕敓鏁堝悗锛屾墽琛屽姩鐢伙紝濡傛灉涓嶅姞 nextTick 锛屼細瀵艰嚧 wx 鍔ㄧ敾鎵ц寮傚父
			this.$nextTick(() => {
				// TODO 瀹氭椂鍣ㄤ繚璇佸姩鐢诲畬鍏ㄦ墽琛岋紝鐩墠鏈変簺闂锛屽悗闈細鍙栨秷瀹氭椂鍣?
				this.timer = setTimeout(() => {
					this.animation = createAnimation(this.config, this)
					this.tranfromInit(false).step()
					this.animation.run()
					this.$emit('change', {
						detail: this.isShow
					})
				}, 20)
			})
		},
		// 鍏抽棴杩囧害鍔ㄧ敾
		close(type) {
			if (!this.animation) return
			this.tranfromInit(true)
				.step()
				.run(() => {
					this.isShow = false
					this.animationData = null
					this.animation = null
					let { opacity, transform } = this.styleInit(false)
					this.opacity = opacity || 1
					this.transform = transform
					this.$emit('change', {
						detail: this.isShow
					})
				})
		},
		// 澶勭悊鍔ㄧ敾寮€濮嬪墠鐨勯粯璁ゆ牱寮?
		styleInit(type) {
			let styles = {
				transform: ''
			}
			let buildStyle = (type, mode) => {
				if (mode === 'fade') {
					styles.opacity = this.animationType(type)[mode]
				} else {
					styles.transform += this.animationType(type)[mode] + ' '
				}
			}
			if (typeof this.modeClass === 'string') {
				buildStyle(type, this.modeClass)
			} else {
				this.modeClass.forEach(mode => {
					buildStyle(type, mode)
				})
			}
			return styles
		},
		// 澶勭悊鍐呯疆缁勫悎鍔ㄧ敾
		tranfromInit(type) {
			let buildTranfrom = (type, mode) => {
				let aniNum = null
				if (mode === 'fade') {
					aniNum = type ? 0 : 1
				} else {
					aniNum = type ? '-100%' : '0'
					if (mode === 'zoom-in') {
						aniNum = type ? 0.8 : 1
					}
					if (mode === 'zoom-out') {
						aniNum = type ? 1.2 : 1
					}
					if (mode === 'slide-right') {
						aniNum = type ? '100%' : '0'
					}
					if (mode === 'slide-bottom') {
						aniNum = type ? '100%' : '0'
					}
				}
				this.animation[this.animationMode()[mode]](aniNum)
			}
			if (typeof this.modeClass === 'string') {
				buildTranfrom(type, this.modeClass)
			} else {
				this.modeClass.forEach(mode => {
					buildTranfrom(type, mode)
				})
			}

			return this.animation
		},
		animationType(type) {
			return {
				fade: type ? 0 : 1,
				'slide-top': `translateY(${type ? '0' : '-100%'})`,
				'slide-right': `translateX(${type ? '0' : '100%'})`,
				'slide-bottom': `translateY(${type ? '0' : '100%'})`,
				'slide-left': `translateX(${type ? '0' : '-100%'})`,
				'zoom-in': `scaleX(${type ? 1 : 0.8}) scaleY(${type ? 1 : 0.8})`,
				'zoom-out': `scaleX(${type ? 1 : 1.2}) scaleY(${type ? 1 : 1.2})`
			}
		},
		// 鍐呯疆鍔ㄧ敾绫诲瀷涓庡疄闄呭姩鐢诲搴斿瓧鍏?
		animationMode() {
			return {
				fade: 'opacity',
				'slide-top': 'translateY',
				'slide-right': 'translateX',
				'slide-bottom': 'translateY',
				'slide-left': 'translateX',
				'zoom-in': 'scale',
				'zoom-out': 'scale'
			}
		},
		// 椹煎嘲杞腑妯嚎
		toLine(name) {
			return name.replace(/([A-Z])/g, '-$1').toLowerCase()
		}
	}
}
</script>

<style></style>


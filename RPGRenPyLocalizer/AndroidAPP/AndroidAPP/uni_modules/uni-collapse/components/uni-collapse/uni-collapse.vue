<template>
	<view class="uni-collapse">
		<slot />
	</view>
</template>
<script>
	/**
	 * Collapse 鎶樺彔闈㈡澘
	 * @description 灞曠ず鍙互鎶樺彔 / 灞曞紑鐨勫唴瀹瑰尯鍩?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=23
	 * @property {String|Array} value 褰撳墠婵€娲婚潰鏉挎敼鍙樻椂瑙﹀彂(濡傛灉鏄墜椋庣惔妯″紡锛屽弬鏁扮被鍨嬩负string锛屽惁鍒欎负array)
	 * @property {Boolean} accordion = [true|false] 鏄惁寮€鍚墜椋庣惔鏁堟灉鏄惁寮€鍚墜椋庣惔鏁堟灉
	 * @event {Function} change 鍒囨崲闈㈡澘鏃惰Е鍙戯紝濡傛灉鏄墜椋庣惔妯″紡锛岃繑鍥炵被鍨嬩负string锛屽惁鍒欎负array
	 */
	export default {
		name: 'uniCollapse',
		emits:['change','activeItem','input','update:modelValue'],
		props: {
			value: {
				type: [String, Array],
				default: ''
			},
			modelValue: {
				type: [String, Array],
				default: ''
			},
			accordion: {
				// 鏄惁寮€鍚墜椋庣惔鏁堟灉
				type: [Boolean, String],
				default: false
			},
		},
		data() {
			return {}
		},
		computed: {
			// TODO 鍏煎 vue2 鍜?vue3
			dataValue() {
				let value = (typeof this.value === 'string' && this.value === '') ||
					(Array.isArray(this.value) && this.value.length === 0)
				let modelValue = (typeof this.modelValue === 'string' && this.modelValue === '') ||
					(Array.isArray(this.modelValue) && this.modelValue.length === 0)
				if (value) {
					return this.modelValue
				}
				if (modelValue) {
					return this.value
				}

				return this.value
			}
		},
		watch: {
			dataValue(val) {
				this.setOpen(val)
			}
		},
		created() {
			this.childrens = []
			this.names = []
		},
		mounted() {
			this.$nextTick(()=>{
				this.setOpen(this.dataValue)
			})
		},
		methods: {
			setOpen(val) {
				let str = typeof val === 'string'
				let arr = Array.isArray(val)
				this.childrens.forEach((vm, index) => {
					if (str) {
						if (val === vm.nameSync) {
							if (!this.accordion) {
								console.warn('accordion 灞炴€т负 false ,v-model 绫诲瀷搴旇涓?array')
								return
							}
							vm.isOpen = true
						}
					}
					if (arr) {
						val.forEach(v => {
							if (v === vm.nameSync) {
								if (this.accordion) {
									console.warn('accordion 灞炴€т负 true ,v-model 绫诲瀷搴旇涓?string')
									return
								}
								vm.isOpen = true
							}
						})
					}
				})
				this.emit(val)
			},
			setAccordion(self) {
				if (!this.accordion) return
				this.childrens.forEach((vm, index) => {
					if (self !== vm) {
						vm.isOpen = false
					}
				})
			},
			resize() {
				this.childrens.forEach((vm, index) => {
					// #ifndef APP-NVUE
					vm.getCollapseHeight()
					// #endif
					// #ifdef APP-NVUE
					vm.getNvueHwight()
					// #endif
				})
			},
			onChange(isOpen, self) {
				let activeItem = []

				if (this.accordion) {
					activeItem = isOpen ? self.nameSync : ''
				} else {
					this.childrens.forEach((vm, index) => {
						if (vm.isOpen) {
							activeItem.push(vm.nameSync)
						}
					})
				}
				this.$emit('change', activeItem)
				this.emit(activeItem)
			},
			emit(val){
				this.$emit('input', val)
				this.$emit('update:modelValue', val)
			}
		}
	}
</script>
<style lang="scss" >
	.uni-collapse {
		/* #ifndef APP-NVUE */
		width: 100%;
		display: flex;
		/* #endif */
		/* #ifdef APP-NVUE */
		flex: 1;
		/* #endif */
		flex-direction: column;
		background-color: #fff;
	}
</style>


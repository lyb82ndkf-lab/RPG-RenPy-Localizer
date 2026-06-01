<template>
	<view>
		<slot></slot>
	</view>
</template>

<script>
	/**
	 * SwipeAction 婊戝姩鎿嶄綔
	 * @description 閫氳繃婊戝姩瑙﹀彂閫夐」鐨勫鍣?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=181
	 */
	export default {
		name:"uniSwipeAction",
		data() {
			return {};
		},
		created() {
			this.children = [];
		},
		methods: {
			// 鍏紑缁欑敤鎴蜂娇鐢紝閲嶅埗缁勪欢鏍峰紡
			resize(){
				// wxs 浼氳嚜宸辫绠楃粍浠跺ぇ灏忥紝鎵€浠ユ棤闇€鎵ц涓嬮潰浠ｇ爜
				// #ifndef APP-VUE || H5 || MP-WEIXIN
				this.children.forEach(vm=>{
					vm.init()
				})
				// #endif
			},
			// 鍏紑缁欑敤鎴蜂娇鐢紝鍏抽棴鍏ㄩ儴 宸茬粡鎵撳紑鐨勭粍浠?			closeAll(){
				this.children.forEach(vm=>{
					// #ifdef APP-VUE || H5 || MP-WEIXIN
					vm.is_show = 'none'
					// #endif

					// #ifndef APP-VUE || H5 || MP-WEIXIN
					vm.close()
					// #endif
				})
			},
			closeOther(vm) {
				if (this.openItem && this.openItem !== vm) {
					// #ifdef APP-VUE || H5 || MP-WEIXIN
					this.openItem.is_show = 'none'
					// #endif

					// #ifndef APP-VUE || H5 || MP-WEIXIN
					this.openItem.close()
					// #endif
				}
				// 璁板綍涓婁竴涓墦寮€鐨?swipe-action-item ,鐢ㄤ簬 auto-close
				this.openItem = vm
			}
		}
	};
</script>

<style></style>


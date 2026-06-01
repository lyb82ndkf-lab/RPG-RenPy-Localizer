<template>
	<view class="uni-breadcrumb">
		<slot />
	</view>
</template>
<script>
	/**
	 * Breadcrumb 闈㈠寘灞戝鑸埗缁勪欢
	 * @description 鏄剧ず褰撳墠椤甸潰鐨勮矾寰勶紝蹇€熻繑鍥炰箣鍓嶇殑浠绘剰椤甸潰
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=xxx
	 * @property {String} separator 鍒嗛殧绗︼紝榛樿涓烘枩鏉?/'
	 * @property {String} separatorClass 鍥炬爣鍒嗛殧绗?class
	 */
	export default {
		options: {
			virtualHost: true
		},
		props: {
			separator: {
				type: String,
				default: '/'
			},
			separatorClass: {
				type: String,
				default: ''
			}
		},

		provide() {
			return {
				uniBreadcrumb: this
			}
		}

	}
</script>
<style lang="scss">
	.uni-breadcrumb {
		display: flex;
	}
</style>


<template>
	<view class="uni-breadcrumb-item">
		<view :class="{
			'uni-breadcrumb-item--slot': true,
			'uni-breadcrumb-item--slot-link': to && currentPage !== to
			}" @click="navTo">
			<slot />
		</view>
		<i v-if="separatorClass" class="uni-breadcrumb-item--separator" :class="separatorClass" />
		<text v-else class="uni-breadcrumb-item--separator">{{ separator }}</text>
	</view>
</template>
<script>
	/**
	 * BreadcrumbItem 闈㈠寘灞戝鑸瓙缁勪欢
	 * @property {String/Object} to 璺敱璺宠浆椤甸潰璺緞/瀵硅薄
	 * @property {Boolean} replace 鍦ㄤ娇鐢?to 杩涜璺敱璺宠浆鏃讹紝鍚敤 replace 灏嗕笉浼氬悜 history 娣诲姞鏂拌褰?浠?h5 鏀寔锛?
	 */
	export default {
		data() {
			return {
				currentPage: ""
			}
		},
		options: {
			virtualHost: true
		},
		props: {
			to: {
				type: String,
				default: ''
			},
			replace:{
				type: Boolean,
				default: false
			}
		},
		inject: {
			uniBreadcrumb: {
				from: "uniBreadcrumb",
				default: null
			}
		},
		created(){
			const pages = getCurrentPages()
			const page = pages[pages.length-1]

			if(page){
				this.currentPage = `/${page.route}`
			}
		},
		computed: {
			separator() {
				return this.uniBreadcrumb.separator
			},
			separatorClass() {
				return this.uniBreadcrumb.separatorClass
			}
		},
		methods: {
			navTo() {
				const { to } = this

				if (!to || this.currentPage === to){
					return
				}

				if(this.replace){
					uni.redirectTo({
						url:to
					})
				}else{
					uni.navigateTo({
						url:to
					})
				}
			}
		}
	}
</script>
<style lang="scss">
	$uni-primary: #2979ff !default;
	$uni-base-color: #6a6a6a !default;
	$uni-main-color: #3a3a3a !default;
	.uni-breadcrumb-item {
		display: flex;
		align-items: center;
		white-space: nowrap;
		font-size: 14px;

		&--slot {
			color: $uni-base-color;
			padding: 0 10px;

			&-link {
				color: $uni-main-color;
				font-weight: bold;
				/* #ifndef APP-NVUE */
				cursor: pointer;
				/* #endif */

				&:hover {
					color: $uni-primary;
				}
			}
		}

		&--separator {
			font-size: 12px;
			color: $uni-base-color;
		}

		&:first-child &--slot {
			padding-left: 0;
		}
		
		&:last-child &--separator {
			display: none;
		}
	}
</style>


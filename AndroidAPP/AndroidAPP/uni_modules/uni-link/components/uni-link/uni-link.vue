<template>
	<a v-if="isShowA" class="uni-link" :href="href"
		:class="{'uni-link--withline':showUnderLine===true||showUnderLine==='true'}"
		:style="{color,fontSize:fontSize+'px'}" :download="download">
		<slot>{{text}}</slot>
	</a>
	<!-- #ifndef APP-NVUE -->
	<text v-else class="uni-link" :class="{'uni-link--withline':showUnderLine===true||showUnderLine==='true'}"
		:style="{color,fontSize:fontSize+'px'}" @click="openURL">
		<slot>{{text}}</slot>
	</text>
	<!-- #endif -->
	<!-- #ifdef APP-NVUE -->
	<text v-else class="uni-link" :class="{'uni-link--withline':showUnderLine===true||showUnderLine==='true'}"
		:style="{color,fontSize:fontSize+'px'}" @click="openURL">
		{{text}}
	</text>
	<!-- #endif -->
</template>

<script>
	/**
	 * Link 澶栭儴缃戦〉瓒呴摼鎺ョ粍浠?
	 * @description uni-link鏄竴涓閮ㄧ綉椤佃秴閾炬帴缁勪欢锛屽湪灏忕▼搴忓唴澶嶅埗url锛屽湪app鍐呮墦寮€澶栭儴娴忚鍣紝鍦╤5绔墦寮€鏂扮綉椤?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=1182
	 * @property {String} href 鐐瑰嚮鍚庢墦寮€鐨勫閮ㄧ綉椤祏rl
	 * @property {String} text 鏄剧ず鐨勬枃瀛?
	 * @property {String} downlaod H5骞冲彴涓嬭浇鏂囦欢鍚?
	 * @property {Boolean} showUnderLine 鏄惁鏄剧ず涓嬪垝绾?
	 * @property {String} copyTips 鍦ㄥ皬绋嬪簭绔鍒堕摼鎺ユ椂鏄剧ず鐨勬彁绀鸿
	 * @property {String} color 閾炬帴鏂囧瓧棰滆壊
	 * @property {String} fontSize 閾炬帴鏂囧瓧澶у皬
	 * @example * <uni-link href="https://ext.dcloud.net.cn" text="https://ext.dcloud.net.cn"></uni-link>
	 */
	export default {
		name: 'uniLink',
		props: {
			href: {
				type: String,
				default: ''
			},
			text: {
				type: String,
				default: ''
			},
			download: {
				type: String,
				default: ''
			},
			showUnderLine: {
				type: [Boolean, String],
				default: true
			},
			copyTips: {
				type: String,
				default: '宸茶嚜鍔ㄥ鍒剁綉鍧€锛岃鍦ㄦ墜鏈烘祻瑙堝櫒閲岀矘璐磋缃戝潃'
			},
			color: {
				type: String,
				default: '#999999'
			},
			fontSize: {
				type: [Number, String],
				default: 14
			}
		},
		computed: {
			isShowA() {
				// #ifdef H5
				this._isH5 = true;
				// #endif
				if ((this.isMail() || this.isTel()) && this._isH5 === true) {
					return true;
				}
				return false;
			}
		},
		created() {
			this._isH5 = null;
		},
		methods: {
			isMail() {
				return this.href.startsWith('mailto:');
			},
			isTel() {
				return this.href.startsWith('tel:');
			},
			openURL() {
				// #ifdef APP-PLUS
				if (this.isTel()) {
					this.makePhoneCall(this.href.replace('tel:', ''));
				} else {
					plus.runtime.openURL(this.href);
				}
				// #endif
				// #ifdef H5
				window.open(this.href)
				// #endif
				// #ifdef MP
				uni.setClipboardData({
					data: this.href
				});
				uni.showModal({
					content: this.copyTips,
					showCancel: false
				});
				// #endif
			},
			makePhoneCall(phoneNumber) {
				uni.makePhoneCall({
					phoneNumber
				})
			}
		}
	}
</script>

<style>
	/* #ifndef APP-NVUE */
	.uni-link {
		cursor: pointer;
	}

	/* #endif */
	.uni-link--withline {
		text-decoration: underline;
	}
</style>


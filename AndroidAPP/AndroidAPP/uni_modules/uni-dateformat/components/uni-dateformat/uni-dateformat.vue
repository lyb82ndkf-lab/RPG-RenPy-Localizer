<template>
	<text>{{dateShow}}</text>
</template>

<script>
	import {friendlyDate} from './date-format.js'
	/**
	 * Dateformat 鏃ユ湡鏍煎紡鍖?
	 * @description 鏃ユ湡鏍煎紡鍖栫粍浠?
	 * @tutorial https://ext.dcloud.net.cn/plugin?id=3279
	 * @property {Object|String|Number} date 鏃ユ湡瀵硅薄/鏃ユ湡瀛楃涓?鏃堕棿鎴?
	 * @property {String} locale 鏍煎紡鍖栦娇鐢ㄧ殑璇█
	 * 	@value zh 涓枃
	 * 	@value en 鑻辨枃
	 * @property {Array} threshold 搴旂敤涓嶅悓绫诲瀷鏍煎紡鍖栫殑闃堝€?
	 * @property {String} format 杈撳嚭鏃ユ湡瀛楃涓叉椂鐨勬牸寮?
	 */
	export default {
		name: 'uniDateformat',
		props: {
			date: {
				type: [Object, String, Number],
				default () {
					return '-'
				}
			},
			locale: {
				type: String,
				default: 'zh',
			},
			threshold: {
				type: Array,
				default () {
					return [0, 0]
				}
			},
			format: {
				type: String,
				default: 'yyyy/MM/dd hh:mm:ss'
			},
			// refreshRate浣跨敤涓嶅綋鍙兘瀵艰嚧鎬ц兘闂锛岃皑鎱庝娇鐢?
			refreshRate: {
				type: [Number, String],
				default: 0
			}
		},
		data() {
			return {
				refreshMark: 0
			}
		},
		computed: {
			dateShow() {
				this.refreshMark
				return friendlyDate(this.date, {
					locale: this.locale,
					threshold: this.threshold,
					format: this.format
				})
			}
		},
		watch: {
			refreshRate: {
				handler() {
					this.setAutoRefresh()
				},
				immediate: true
			}
		},
		methods: {
			refresh() {
				this.refreshMark++
			},
			setAutoRefresh() {
				clearInterval(this.refreshInterval)
				if (this.refreshRate) {
					this.refreshInterval = setInterval(() => {
						this.refresh()
					}, parseInt(this.refreshRate))
				}
			}
		}
	}
</script>

<style>

</style>


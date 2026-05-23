<template>
	<view class="mask flex-center">
		<view class="content botton-radius">
			<view class="content-top">
				<text class="content-top-text">{{title}}</text>
				<image class="content-top" style="top: 0;" width="100%" height="100%" src="/uni_modules/uni-upgrade-center-app/static/bg_top.png">
				</image>
			</view>
			<view class="content-header"></view>
			<view class="content-body">
				<view class="title">
					<text>{{subTitle}}</text>
					<text class="content-body-version">{{version}}</text>
				</view>
				<view class="body">
					<scroll-view class="box-des-scroll" scroll-y="true">
						<text class="box-des">
							{{contents}}
						</text>
					</scroll-view>
				</view>
				<view class="footer flex-center">
					<template v-if="isAppStore">
						<button class="content-button" style="border: none;color: #fff;" plain @click="jumpToAppStore">
							{{downLoadBtnTextiOS}}
						</button>
					</template>
					<template v-else>
						<template v-if="!downloadSuccess">
							<view class="progress-box flex-column" v-if="downloading">
								<progress class="progress" :percent="downLoadPercent" activeColor="#3DA7FF" show-info
									stroke-width="10"/>
								<view style="width:100%;font-size: 28rpx;display: flex;justify-content: space-around;">
									<text>{{downLoadingText}}</text>
									<text>({{downloadedSize}}/{{packageFileSize}}M)</text>
								</view>
							</view>

							<button v-else class="content-button" style="border: none;color: #fff;" plain @click="updateApp">
								{{downLoadBtnText}}
							</button>
						</template>
						<button v-else-if="downloadSuccess && !installed" class="content-button" style="border: none;color: #fff;"
							plain :loading="installing" :disabled="installing" @click="installPackage">
							{{installing ? '姝ｅ湪瀹夎鈥︹€? : '涓嬭浇瀹屾垚锛岀珛鍗冲畨瑁?}}
						</button>
						<button v-else-if="installed && !isWGT" class="content-button" style="border: none;color: #fff;"
							plain :loading="installing" :disabled="installing" @click="installPackage">
							瀹夎鏈畬鎴愶紝鐐瑰嚮瀹夎
						</button>

						<button v-else-if="installed && isWGT" class="content-button" style="border: none;color: #fff;" plain
							@click="restart">
							瀹夎瀹屾瘯锛岀偣鍑婚噸鍚?
						</button>
					</template>
				</view>
			</view>

			<image v-if="!is_mandatory" class="close-img" src="/uni_modules/uni-upgrade-center-app/static/app_update_close.png" @click.stop="closeUpdate">
			</image>
		</view>
	</view>
</template>

<script>
	// #ifdef APP
  import { createNotificationProgress, cancelNotificationProgress, finishNotificationProgress } from '@/uni_modules/uts-progressNotification'
	// #endif
	const localFilePathKey = 'UNI_ADMIN_UPGRADE_CENTER_LOCAL_FILE_PATH'
	const platform_iOS = 'iOS';
	const platform_Android = 'Android';
	let downloadTask = null;
	let openSchemePromise

	/**
	 * 瀵规瘮鐗堟湰鍙凤紝濡傞渶瑕侊紝璇疯嚜琛屼慨鏀瑰垽鏂鍒?
	 * 鏀寔姣斿	("3.0.0.0.0.1.0.1", "3.0.0.0.0.1")	("3.0.0.1", "3.0")	("3.1.1", "3.1.1.1") 涔嬬被鐨?
	 * @param {Object} v1
	 * @param {Object} v2
	 * v1 > v2 return 1
	 * v1 < v2 return -1
	 * v1 == v2 return 0
	 */
	function compare(v1 = '0', v2 = '0') {
		v1 = String(v1).split('.')
		v2 = String(v2).split('.')
		const minVersionLens = Math.min(v1.length, v2.length);

		let result = 0;
		for (let i = 0; i < minVersionLens; i++) {
			const curV1 = Number(v1[i])
			const curV2 = Number(v2[i])

			if (curV1 > curV2) {
				result = 1
				break;
			} else if (curV1 < curV2) {
				result = -1
				break;
			}
		}

		if (result === 0 && (v1.length !== v2.length)) {
			const v1BiggerThenv2 = v1.length > v2.length;
			const maxLensVersion = v1BiggerThenv2 ? v1 : v2;
			for (let i = minVersionLens; i < maxLensVersion.length; i++) {
				const curVersion = Number(maxLensVersion[i])
				if (curVersion > 0) {
					v1BiggerThenv2 ? result = 1 : result = -1
					break;
				}
			}
		}

		return result;
	}

	export default {
		data() {
			return {
				// 浠庝箣鍓嶄笅杞藉畨瑁?
				installForBeforeFilePath: '',

				// 瀹夎
				installed: false,
				installing: false,

				// 涓嬭浇
				downloadSuccess: false,
				downloading: false,

				downLoadPercent: 0,
				downloadedSize: 0,
				packageFileSize: 0,

				tempFilePath: '', // 瑕佸畨瑁呯殑鏈湴鍖呭湴鍧€

				// 榛樿瀹夎鍖呬俊鎭?
				title: '鏇存柊鏃ュ織',
				contents: '',
				version: '',
				is_mandatory: false,
				url: '',
				platform: [],
				store_list: null,

				// 鍙嚜瀹氫箟灞炴€?
				subTitle: '鍙戠幇鏂扮増鏈?,
				downLoadBtnTextiOS: '绔嬪嵆璺宠浆鏇存柊',
				downLoadBtnText: '绔嬪嵆涓嬭浇鏇存柊',
				downLoadingText: '瀹夎鍖呬笅杞戒腑锛岃绋嶅悗'
			}
		},
		onLoad({
			local_storage_key
		}) {
			if (!local_storage_key) {
				console.error('local_storage_key涓虹┖锛岃妫€鏌ュ悗閲嶈瘯')
				uni.navigateBack()
				return;
			};

			const localPackageInfo = uni.getStorageSync(local_storage_key);
			if (!localPackageInfo) {
				console.error('瀹夎鍖呬俊鎭负绌猴紝璇锋鏌ュ悗閲嶈瘯')
				uni.navigateBack()
				return;
			};

			const requiredKey = ['version', 'url', 'type']
			for (let key in localPackageInfo) {
				if (requiredKey.indexOf(key) !== -1 && !localPackageInfo[key]) {
					console.error(`鍙傛暟 ${key} 蹇呭～锛岃妫€鏌ュ悗閲嶈瘯`)
					uni.navigateBack()
					return;
				}
			}

			Object.assign(this, localPackageInfo)
			this.checkLocalStoragePackage()
		},
		onBackPress() {
			// 寮哄埗鏇存柊涓嶅厑璁歌繑鍥?
			if (this.is_mandatory) return true
			if (!this.needNotificationProgress) downloadTask && downloadTask.abort()
		},
		onHide() {
			openSchemePromise = null
		},
		computed: {
			isWGT() {
				return this.type === 'wgt'
			},
			isiOS() {
				return !this.isWGT ? this.platform.indexOf(platform_iOS) !== -1 : false;
			},
			isAndroid() {
				return this.platform.indexOf(platform_Android) !== -1
			},
			isAppStore() {
				return this.isiOS || (!this.isiOS && !this.isWGT && this.url.indexOf('.apk') === -1)
			},
			needNotificationProgress() {
				return this.platform.indexOf(platform_iOS) === -1 && !this.is_mandatory
			}
		},
		methods: {
			checkLocalStoragePackage() {
				// 濡傛灉宸茬粡鏈変笅杞藉ソ鐨勫寘锛屽垯鐩存帴鎻愮ず瀹夎
				const localFilePathRecord = uni.getStorageSync(localFilePathKey)
				if (localFilePathRecord) {
					const {
						version,
						savedFilePath,
						installed
					} = localFilePathRecord

					// 姣斿鐗堟湰
					if (!installed && compare(version, this.version) === 0) {
						this.downloadSuccess = true;
						this.installForBeforeFilePath = savedFilePath;
						this.tempFilePath = savedFilePath
					} else {
						// 濡傛灉淇濆瓨鐨勫寘鐗堟湰灏?鎴?宸插畨瑁呰繃锛屽垯鐩存帴鍒犻櫎
						this.deleteSavedFile(savedFilePath)
					}
				}
			},
			askAbortDownload() {
				uni.showModal({
					title: '鏄惁鍙栨秷涓嬭浇锛?,
					cancelText: '鍚?,
					confirmText: '鏄?,
					success: res => {
						if (res.confirm) {
							downloadTask && downloadTask.abort()
              cancelNotificationProgress()
							uni.navigateBack()
						}
					}
				});
			},
			async closeUpdate() {
				if (this.downloading) {
					if (this.is_mandatory) {
						return uni.showToast({
							title: '涓嬭浇涓紝璇风◢鍚庘€︹€?,
							icon: 'none',
							duration: 500
						})
					}
					if (!this.needNotificationProgress) {
						this.askAbortDownload()
						return;
					}
				}

				if (!this.needNotificationProgress && this.downloadSuccess && this.tempFilePath) {
					// 鍖呭凡缁忎笅杞藉畬姣曪紝绋嶅悗瀹夎锛屽皢鍖呬繚瀛樺湪鏈湴
					await this.saveFile(this.tempFilePath, this.version)
				}

				uni.navigateBack()
			},
			updateApp() {
				this.checkStoreScheme()
          .catch(() => {
            this.downloadPackage()
          })
          .finally(() => {
            openSchemePromise = null
          })
			},
			// 璺宠浆搴旂敤鍟嗗簵
			checkStoreScheme() {
				const storeList = (this.store_list || []).filter(item => item.enable)
				if (storeList && storeList.length) {
					storeList
						.sort((cur, next) => next.priority - cur.priority)
						.map(item => item.scheme)
						.reduce((promise, cur, curIndex) => {
							openSchemePromise = (promise || (promise = Promise.reject())).catch(() => {
								return new Promise((resolve, reject) => {
									plus.runtime.openURL(cur, (err) => {
										reject(err)
									})
								})
							})
							return openSchemePromise
						}, openSchemePromise)
					return openSchemePromise
				}

				return Promise.reject()
			},
			downloadPackage() {
				this.downloading = true;

				//涓嬭浇鍖?
				downloadTask = uni.downloadFile({
					url: this.url,
					success: res => {
						if (res.statusCode == 200) {
							// fix: wgt 鏂囦欢涓嬭浇瀹屾垚鍚庡悗缂€涓嶆槸 wgt
							if (this.isWGT && res.tempFilePath.split('.').slice(-1)[0] !== 'wgt') {
								const failCallback = (e) => {
									console.log('[FILE RENAME FAIL]锛?, JSON.stringify(e));
								}
								plus.io.resolveLocalFileSystemURL(res.tempFilePath, (entry) => {
									entry.getParent((parent) => {
										const newName = `new_wgt_${Date.now()}.wgt`
										entry.copyTo(parent, newName, (res) => {
											this.tempFilePath = res.fullPath
											this.downLoadComplete()
										}, failCallback)
									}, failCallback)
								}, failCallback);
							} else {
								this.tempFilePath = res.tempFilePath
								this.downLoadComplete()
							}
						}
					}
				});

				downloadTask.onProgressUpdate(res => {
					this.downLoadPercent = res.progress;
					this.downloadedSize = (res.totalBytesWritten / Math.pow(1024, 2)).toFixed(2);
					this.packageFileSize = (res.totalBytesExpectedToWrite / Math.pow(1024, 2)).toFixed(2);

					if (this.needNotificationProgress && !this.downloadSuccess) {
						createNotificationProgress({
							title: "鍗囩骇涓績姝ｅ湪涓嬭浇瀹夎鍖呪€︹€?,
							content: `${this.downLoadPercent}%`,
							progress: this.downLoadPercent,
							onClick: () => {
								this.askAbortDownload()
							}
						})
					}
				});
				if (this.needNotificationProgress) {
					uni.navigateBack()
				}
			},
			downLoadComplete() {
				this.downloadSuccess = true;
				this.downloading = false;

				this.downLoadPercent = 0
				this.downloadedSize = 0
				this.packageFileSize = 0

				downloadTask = null;

				if (this.needNotificationProgress) {
					finishNotificationProgress({
						title: "瀹夎鍗囩骇鍖?,
						content: "涓嬭浇瀹屾垚"
					})

					this.installPackage();
					return
				}

				// 寮哄埗鏇存柊锛岀洿鎺ュ畨瑁?
				if (this.is_mandatory) {
					this.installPackage();
				}
			},
			installPackage() {
				// #ifdef APP-PLUS
				// wgt璧勬簮鍖呭畨瑁?
				if (this.isWGT) {
					this.installing = true;
				}
				plus.runtime.install(this.tempFilePath, {
					force: false
				}, async res => {
					this.installing = false;
					this.installed = true;

					// wgt鍖咃紝瀹夎鍚庝細鎻愮ず 瀹夎鎴愬姛锛屾槸鍚﹂噸鍚?
					if (this.isWGT) {
						// 寮哄埗鏇存柊瀹夎瀹屾垚閲嶅惎
						if (this.is_mandatory) {
							uni.showLoading({
								icon: 'none',
								title: '瀹夎鎴愬姛锛屾鍦ㄩ噸鍚€︹€?
							})

							setTimeout(() => {
								uni.hideLoading()
								this.restart();
							}, 1000)
						}
					} else {
						const localFilePathRecord = uni.getStorageSync(localFilePathKey)
						uni.setStorageSync(localFilePathKey, {
							...localFilePathRecord,
							installed: true
						})
					}
				}, async err => {
					// 濡傛灉鏄畨瑁呬箣鍓嶇殑鍖咃紝瀹夎澶辫触鍚庡垹闄や箣鍓嶇殑鍖?
					if (this.installForBeforeFilePath) {
						await this.deleteSavedFile(this.installForBeforeFilePath)
						this.installForBeforeFilePath = '';
					}

					// 瀹夎澶辫触闇€瑕侀噸鏂颁笅杞藉畨瑁呭寘
					this.installing = false;
					this.installed = false;

					uni.showModal({
						title: '鏇存柊澶辫触锛岃閲嶆柊涓嬭浇',
						content: err.message,
						showCancel: false
					});
				});

				// 闈瀢gt鍖咃紝瀹夎璺冲嚭瑕嗙洊瀹夎锛屾澶勭洿鎺ヨ繑鍥炰笂涓€椤?
				if (!this.isWGT && !this.is_mandatory) {
					uni.navigateBack()
				}
				// #endif
			},
			restart() {
				this.installed = false;
				// #ifdef APP-PLUS
				//鏇存柊瀹岄噸鍚痑pp
				plus.runtime.restart();
				// #endif
			},
			saveFile(tempFilePath, version) {
				return new Promise((resolve, reject) => {
					uni.saveFile({
						tempFilePath,
						success({
							savedFilePath
						}) {
							uni.setStorageSync(localFilePathKey, {
								version,
								savedFilePath
							})
						},
						complete() {
							resolve()
						}
					})
				})
			},
			deleteSavedFile(filePath) {
				uni.removeStorageSync(localFilePathKey)
				return uni.removeSavedFile({
					filePath
				})
			},
			jumpToAppStore() {
				plus.runtime.openURL(this.url);
			}
		}
	}
</script>

<style>
	page {
		background: transparent;
	}

	.flex-center {
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		justify-content: center;
		align-items: center;
	}

	.mask {
		position: fixed;
		left: 0;
		top: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, .65);
	}

	.botton-radius {
		border-bottom-left-radius: 30rpx;
		border-bottom-right-radius: 30rpx;
	}

	.content {
		position: relative;
		top: 0;
		width: 600rpx;
		background-color: #fff;
		box-sizing: border-box;
		padding: 0 50rpx;
		font-family: Source Han Sans CN;
	}

	.text {
		/* #ifndef APP-NVUE */
		display: block;
		/* #endif */
		line-height: 200px;
		text-align: center;
		color: #FFFFFF;
	}

	.content-top {
		position: absolute;
		top: -195rpx;
		left: 0;
		width: 600rpx;
		height: 270rpx;
	}

	.content-top-text {
		font-size: 45rpx;
		font-weight: bold;
		color: #F8F8FA;
		position: absolute;
		top: 120rpx;
		left: 50rpx;
		z-index: 1;
	}

	.content-header {
		height: 70rpx;
	}

	.title {
		font-size: 33rpx;
		font-weight: bold;
		color: #3DA7FF;
		line-height: 38px;
	}

	.content-body-version {
		padding-left: 10px;
		color: #fff;
		font-size: 10px;
		margin-left: 5px;
		padding: 2px 4px;
		border-radius: 10px;
		background: #50aefd;
	}

	.footer {
		height: 150rpx;
		display: flex;
		align-items: center;
		justify-content: space-around;
	}

	.box-des-scroll {
		box-sizing: border-box;
		padding: 0 40rpx;
		height: 200rpx;
		text-align: left;
	}

	.box-des {
		font-size: 26rpx;
		color: #000000;
		line-height: 50rpx;
	}

	.progress-box {
		width: 100%;
	}

	.progress {
		width: 90%;
		height: 40rpx;
		/* border-radius: 35px; */
	}

	.close-img {
		width: 70rpx;
		height: 70rpx;
		z-index: 1000;
		position: absolute;
		bottom: -120rpx;
		left: calc(50% - 70rpx / 2);
	}

	.content-button {
		text-align: center;
		flex: 1;
		font-size: 30rpx;
		font-weight: 400;
		color: #FFFFFF;
		border-radius: 40rpx;
		margin: 0 18rpx;

		height: 80rpx;
		line-height: 80rpx;

		background: linear-gradient(to right, #1785ff, #3DA7FF);
	}

	.flex-column {
		display: flex;
		flex-direction: column;
		align-items: center;
	}
</style>


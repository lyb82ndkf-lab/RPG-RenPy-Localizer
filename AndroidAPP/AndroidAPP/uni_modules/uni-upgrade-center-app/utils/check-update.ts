import callCheckVersion, { UniUpgradeCenterResult } from "./call-check-version"
// #ifdef UNI-APP-X
import { openSchema } from './utils.uts'
// #endif

// 鎺ㄨ崘鍐岮pp.vue涓娇鐢?
const PACKAGE_INFO_KEY = '__package_info__'

// uni-app 椤圭洰鏃犳硶浠?vue 涓鍑?ComponentPublicInstance 绫诲瀷锛屾晠浣跨敤鏉′欢缂栬瘧
// #ifdef UNI-APP-X
export default function (component : ComponentPublicInstance | null = null) : Promise<UniUpgradeCenterResult> {
// #endif
// #ifndef UNI-APP-X
export default function () : Promise<UniUpgradeCenterResult> {
// #endif
	return new Promise<UniUpgradeCenterResult>((resolve, reject) => {
		callCheckVersion().then(async (uniUpgradeCenterResult) => {
			// NOTE uni-app x 3.96 瑙ｆ瀯鏈夐棶棰?
			const code = uniUpgradeCenterResult.code
			const message = uniUpgradeCenterResult.message
			const url = uniUpgradeCenterResult.url // 瀹夎鍖呬笅杞藉湴鍧€

        // 姝ゅ閫昏緫浠呬负绀轰緥锛屽彲鑷缂栧啓
        if (code > 0) {
          // 鑵捐浜戝拰闃块噷浜戜笅杞介摼鎺ヤ笉鍚岋紝闇€瑕佸鐞嗕竴涓嬶紝闃块噷浜戜細鍘熸牱杩斿洖
          const tcbRes = await uniCloud.getTempFileURL({ fileList: [url] });
          if (typeof tcbRes.fileList[0].tempFileURL !== 'undefined') uniUpgradeCenterResult.url = tcbRes.fileList[0].tempFileURL;

          /**
           * 鎻愮ず鍗囩骇涓€
           * 浣跨敤 uni.showModal
           */
          // return updateUseModal(uniUpgradeCenterResult)

          // #ifndef UNI-APP-X
          // 闈欓粯鏇存柊锛屽彧鏈墂gt鏈?
          if (uniUpgradeCenterResult.is_silently) {
            uni.downloadFile({
              url,
              success: res => {
                if (res.statusCode == 200) {
                  // 涓嬭浇濂界洿鎺ュ畨瑁咃紝涓嬫鍚姩鐢熸晥
                  plus.runtime.install(res.tempFilePath, {
                    force: false
                  });
                }
              }
            });
            return;
          }
          // #endif

          /**
           * 鎻愮ず鍗囩骇浜?
           * 瀹樻柟閫傞厤鐨勫崌绾у脊绐楋紝鍙嚜琛屾浛鎹㈣祫婧愰€傞厤UI椋庢牸
           */
          // #ifndef UNI-APP-X
          uni.setStorageSync(PACKAGE_INFO_KEY, uniUpgradeCenterResult)
          uni.navigateTo({
            url: `/uni_modules/uni-upgrade-center-app/pages/upgrade-popup?local_storage_key=${PACKAGE_INFO_KEY}`,
            fail: (err) => {
              console.error('鏇存柊寮规璺宠浆澶辫触', err)
              uni.removeStorageSync(PACKAGE_INFO_KEY)
            }
          })
          // #endif
          // #ifdef UNI-APP-X
          component?.$callMethod('show', true, uniUpgradeCenterResult)
          // #endif

          return resolve(uniUpgradeCenterResult)
        } else if (code < 0) {
          console.error(message)
          return reject(uniUpgradeCenterResult)
        }
        return resolve(uniUpgradeCenterResult)
      }).catch((err) => {
        reject(err)
      })
    });
  }

/**
 * 浣跨敤 uni.showModal 鍗囩骇
 */
function updateUseModal(packageInfo : UniUpgradeCenterResult) : void {
	// #ifdef APP
	const {
		title, // 鏍囬
		contents, // 鍗囩骇鍐呭
		is_mandatory, // 鏄惁寮哄埗鏇存柊
		url, // 瀹夎鍖呬笅杞藉湴鍧€
		type,
		platform
	} = packageInfo;

	let isWGT = type === 'wgt'
	let isiOS = !isWGT ? platform.includes('iOS') : false;

	// #ifndef UNI-APP-X
	let confirmText = isiOS ? '绔嬪嵆璺宠浆鏇存柊' : '绔嬪嵆涓嬭浇鏇存柊'
	// #endif
	// #ifdef UNI-APP-X
	let confirmText = '绔嬪嵆涓嬭浇鏇存柊'
	// #endif

    return uni.showModal({
      title,
      content: contents,
      showCancel: !is_mandatory,
      confirmText,
      success: res => {
        if (res.cancel) return;

			if (isiOS) {
				// iOS 骞冲彴璺宠浆 AppStore
				// #ifndef UNI-APP-X
				plus.runtime.openURL(url);
				// #endif
				// #ifdef UNI-APP-X
				openSchema(url)
				// #endif
				return;
			}

        uni.showToast({
          title: '鍚庡彴涓嬭浇涓€︹€?,
          duration: 1000
        });

			// wgt 鍜?瀹夊崜涓嬭浇鏇存柊
			uni.downloadFile({
				url,
				success: res => {
					if (res.statusCode !== 200) {
						console.error('涓嬭浇瀹夎鍖呭け璐?);
						return;
					}
					// 涓嬭浇濂界洿鎺ュ畨瑁咃紝涓嬫鍚姩鐢熸晥
          // uni-app x 椤圭洰娌℃湁 plus5+ 鏁呬娇鐢ㄦ潯浠剁紪璇?
					// #ifndef UNI-APP-X
					plus.runtime.install(res.tempFilePath, {
						force: false
					}, () => {
						if (is_mandatory) {
							//鏇存柊瀹岄噸鍚痑pp
							plus.runtime.restart();
							return;
						}
						uni.showModal({
							title: '瀹夎鎴愬姛鏄惁閲嶅惎锛?,
							success: res => {
								if (res.confirm) {
									//鏇存柊瀹岄噸鍚痑pp
									plus.runtime.restart();
								}
							}
						});
					}, err => {
						uni.showModal({
							title: '鏇存柊澶辫触',
							content: err
								.message,
							showCancel: false
						});
					});
					// #endif

          // #ifdef UNI-APP-X
          uni.installApk({
          	filePath: res.tempFilePath,
          	success: () => {
          		uni.showModal({
          			title: '瀹夎鎴愬姛璇锋墜鍔ㄩ噸鍚?
          		});
          	},
          	fail: err => {
          		uni.showModal({
          			title: '鏇存柊澶辫触',
          			content: err.message,
          			showCancel: false
          		});
          	}
          });
          // #endif
				}
			});
		}
	});
	// #endif
}


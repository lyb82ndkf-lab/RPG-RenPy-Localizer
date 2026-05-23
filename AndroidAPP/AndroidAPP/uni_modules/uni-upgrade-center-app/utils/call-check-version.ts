export type StoreListItem = {
	enable : boolean
	id : string
	name : string
	scheme : string
	priority : number // 浼樺厛绾?
}

export type UniUpgradeCenterResult = {
	_id : string
	appid : string
	name : string
	title : string
	contents : string
	url : string // 瀹夎鍖呬笅杞藉湴鍧€
	platform : Array<string> // Array<'Android' | 'iOS'>
	version : string // 鐗堟湰鍙?1.0.0
	uni_platform : string // "android" | "ios" // 鐗堟湰鍙?1.0.0
	stable_publish : boolean // 鏄惁鏄ǔ瀹氱増
	is_mandatory : boolean // 鏄惁寮哄埗鏇存柊
	is_silently : boolean | null	// 鏄惁闈欓粯鏇存柊
	create_env : string // "upgrade-center"
	create_date : number
	message : string
	code : number

	type : string // "native_app" | "wgt"
	store_list : StoreListItem[] | null
	min_uni_version : string | null  // 鍗囩骇 wgt 鐨勬渶浣?uni-app 鐗堟湰
}

export default function () : Promise<UniUpgradeCenterResult> {
	// #ifdef APP
	return new Promise<UniUpgradeCenterResult>((resolve, reject) => {
		const systemInfo = uni.getSystemInfoSync()
		const appId = systemInfo.appId
		const appVersion = systemInfo.appVersion //systemInfo.appVersion
		// #ifndef UNI-APP-X
		if (typeof appId === 'string' && typeof appVersion === 'string' && appId.length > 0 && appVersion.length > 0) {
			plus.runtime.getProperty(appId, function (widgetInfo) {
				if (widgetInfo.version) {
					let data = {
						action: 'checkVersion',
						appid: appId,
						appVersion: appVersion,
						wgtVersion: widgetInfo.version
					}
					uniCloud.callFunction({
						name: 'uni-upgrade-center',
						data,
						success: (e) => {
							resolve(e.result as UniUpgradeCenterResult)
						},
						fail: (error) => {
							reject(error)
						}
					})
				} else {
					reject('widgetInfo.version is EMPTY')
				}
			})
		} else {
			reject('plus.runtime.appid is EMPTY')
		}
		// #endif
		// #ifdef UNI-APP-X
		if (typeof appId === 'string' && typeof appVersion === 'string' && appId.length > 0 && appVersion.length > 0) {
			let data = {
				action: 'checkVersion',
				appid: appId,
				appVersion: appVersion,
				is_uniapp_x: true,
				wgtVersion: '0.0.0.0.0.1'
			}
			try {
				uniCloud.callFunction({
					name: 'uni-upgrade-center',
					data: data
				}).then(res => {
					const code = res.result['code']
					const codeIsNumber = ['Int', 'Long', 'number'].includes(typeof code)
					if (codeIsNumber) {
					  if ((code as number) == 0) {
					    reject({
					      code: res.result['code'],
					      message: res.result['message']
					    })
					  } else if ((code as number) < 0) {
					    reject({
					      code: res.result['code'],
					      message: res.result['message']
					    })
					  } else {
              const result = JSON.parse<UniUpgradeCenterResult>(JSON.stringify(res.result)) as UniUpgradeCenterResult
              resolve(result)
            }
					}
				}).catch<void>((err : any | null) => {
					const error = err as UniCloudError
					if (error.errMsg == '鏈尮閰嶅埌浜戝嚱鏁癧uni-upgrade-center]')
						error.errMsg = '銆恥ni-upgrade-center-app銆戞湭閰嶇疆uni-upgrade-center锛屾棤娉曞崌绾с€傚弬鑰? https://uniapp.dcloud.net.cn/uniCloud/upgrade-center.html'
					reject(error.errMsg)
				})
			} catch (e) {
				reject(e.message)
			}
		} else {
			reject('invalid appid or appVersion')
		}
		// #endif
	})
	// #endif
	// #ifndef APP-PLUS
	return new Promise((resolve, reject) => {
		reject({
			message: '璇峰湪App涓娇鐢?
		})
	})
	// #endif
}


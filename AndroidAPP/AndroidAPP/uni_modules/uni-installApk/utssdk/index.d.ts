declare namespace UniNamespace {

interface InstallApkSuccess {
	/**
	 * 瀹夎鎴愬姛娑堟伅
	 */
	errMsg : string
}

type InstallApkErrorCode = 1300002
interface InstallApkFail {
	errCode : InstallApkErrorCode
}

type InstallApkComplete = any

type InstallApkSuccessCallback = (res : InstallApkSuccess) => void
type InstallApkFailCallback = (err : InstallApkFail) => void
type InstallApkCompleteCallback = (res : InstallApkComplete) => void

interface InstallApkOptions {
	/**
	 * apk鏂囦欢鍦板潃
	 */
	filePath : string,
	/**
	 * 鎺ュ彛璋冪敤鎴愬姛鐨勫洖璋冨嚱鏁?
	 * @defaultValue null
	 */
	success ?: InstallApkSuccessCallback | null,
	/**
	 * 鎺ュ彛璋冪敤澶辫触鐨勫洖璋冨嚱鏁?
	 * @defaultValue null
	 */
	fail ?: InstallApkFailCallback | null,
	/**
	 * 鎺ュ彛璋冪敤缁撴潫鐨勫洖璋冨嚱鏁帮紙璋冪敤鎴愬姛銆佸け璐ラ兘浼氭墽琛岋級
	 * @defaultValue null
	 */
	complete ?: InstallApkCompleteCallback | null
}

}


declare interface Uni {
  /**
    * installApk()
    * @description
    * 瀹夎apk
    * @param {InstallApkOptions}
    * @return {void}
    * @uniPlatform {
    *    "app": {
    *        "android": {
    *            "osVer": "4.4",
    *  		  	 "uniVer": "3.94+",
    * 			 "unixVer": "3.94+"
    *        },
    *        "ios": {
    *            "osVer": "x",
    *  		  	 "uniVer": "x",
    * 			 "unixVer": "x"
    *        }
    *    }
    * }
    * @example
     ```typescript
    uni.installApk({
      filePath: "/xx/xx/xx.apk",
      complete: (res: any) => {
        console.log("complete => " + JSON.stringify(res));
      }
    });
     ```
    */
  installApk(options : UniNamespace.InstallApkOptions) : void
}


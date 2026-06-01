# Android Offline Build

This offline Android project is generated from DCloud UniApp Android offline SDK.

## DCloud AppKey

DCloud Android offline runtime requires a valid `dcloud_appkey` generated in the DCloud developer console.

Use these values when applying for the key:

- AppID: `__UNI__C81328E`
- Android package name: `com.rpgrtl.localizer`
- SHA1: `86:69:A8:13:E6:A5:0F:0E:BC:9B:73:C7:86:F3:D5:FB:D2:05:31:08`
- SHA256: `72:D9:57:C0:98:86:22:C4:5A:0A:2C:4A:0D:2F:0F:BD:4E:0C:CE:72:B1:F7:2E:84:74:19:C1:BD:65:DC:10:DA`
- Keystore: `AndroidAPP/certs/rpgrtl-release.keystore`
- Alias: `rpgrtl`

After receiving the AppKey, create:

```properties
# HBuilder-Integrate-AS/local.properties
dcloudAppKey=YOUR_DCLOUD_ANDROID_OFFLINE_APPKEY
```

Then rebuild with:

```powershell
$env:ANDROID_HOME='D:\Android SDK'
$env:ANDROID_SDK_ROOT='D:\Android SDK'
$env:JAVA_HOME='D:\java'
& 'D:\gradle-9.5.1\bin\gradle.bat' --no-daemon assembleRelease
```

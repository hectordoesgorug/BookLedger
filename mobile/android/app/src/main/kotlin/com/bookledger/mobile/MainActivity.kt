package com.bookledger.mobile

import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.WindowManager
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.net.Inet4Address
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var scanToneGenerator: ToneGenerator? = null
    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var discoveryResult: MethodChannel.Result? = null
    private var installResult: MethodChannel.Result? = null
    private var expectedInstallVersionCode: Long? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private val discoveryTimeout = Runnable { finishDiscovery(null) }

    override fun onResume() {
        super.onResume()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onPause() {
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        super.onPause()
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL_NAME)
            .setMethodCallHandler { call, result ->
                if (call.method != "playSuccessBeep") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }

                try {
                    val tone = scanToneGenerator ?: ToneGenerator(
                        AudioManager.STREAM_NOTIFICATION,
                        TONE_VOLUME,
                    ).also { scanToneGenerator = it }
                    if (tone.startTone(ToneGenerator.TONE_PROP_BEEP, TONE_DURATION_MS)) {
                        result.success(null)
                    } else {
                        result.error("BEEP_UNAVAILABLE", "Could not start the scan beep.", null)
                    }
                } catch (error: RuntimeException) {
                    result.error("BEEP_UNAVAILABLE", error.message, null)
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, EXTERNAL_URL_CHANNEL)
            .setMethodCallHandler { call, result ->
                val url = call.arguments as? String
                val allowed = (call.method == "openGithub" && url == GITHUB_URL) ||
                    (call.method == "openRelease" && url != null &&
                        Regex("https://github\\.com/hectordoesgorug/BookLedger/releases/tag/v?[0-9A-Za-z.+-]+$").matches(url))
                if (!allowed) {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    result.success(true)
                } catch (_: ActivityNotFoundException) {
                    result.success(false)
                } catch (_: SecurityException) {
                    result.success(false)
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, UPDATE_INSTALL_CHANNEL)
            .setMethodCallHandler { call, result ->
                val values = call.arguments as? Map<*, *>
                val path = values?.get("path") as? String
                val sha256 = values?.get("sha256") as? String
                if (BuildConfig.DEBUG || path == null || sha256 == null) {
                    result.error("INVALID_UPDATE", "This update cannot be installed.", null)
                    return@setMethodCallHandler
                }
                Thread({
                    try {
                        val (apk, info) = verifiedUpdateApk(path, sha256)
                        when (call.method) {
                            "inspectVerifiedApk" -> {
                                val installedCode = (values["installedVersionCode"] as? Number)?.toLong()
                                if (installedCode == null || installedCode != BuildConfig.VERSION_CODE.toLong()) {
                                    throw IllegalArgumentException("Installed version information changed.")
                                }
                                if (info.packageName != packageName || apkVersionCode(info) <= installedCode) {
                                    throw IllegalArgumentException("APK package or version is not eligible.")
                                }
                                mainHandler.post {
                                    result.success(mapOf("packageName" to info.packageName, "versionCode" to apkVersionCode(info)))
                                }
                            }
                            "installVerifiedApk" -> {
                                val versionCode = (values["versionCode"] as? Number)?.toLong()
                                if (
                                    info.packageName != packageName || versionCode == null ||
                                    apkVersionCode(info) != versionCode || versionCode <= BuildConfig.VERSION_CODE
                                ) {
                                    throw IllegalArgumentException("APK package or version is not eligible.")
                                }
                                mainHandler.post { beginUpdateInstall(apk, versionCode, result) }
                            }
                            else -> mainHandler.post { result.notImplemented() }
                        }
                    } catch (error: Exception) {
                        mainHandler.post {
                            result.error("INVALID_UPDATE", error.message ?: "The APK could not be verified.", null)
                        }
                    }
                }, "update-apk-verification").start()
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, APP_SETTINGS_CHANNEL)
            .setMethodCallHandler { call, result ->
                val preferences = getSharedPreferences(APP_SETTINGS_PREFERENCES, MODE_PRIVATE)
                when (call.method) {
                    "getUpdateFreeBytes" -> result.success(filesDir.usableSpace)
                    "getAppSettings" -> result.success(
                        mapOf(
                            "version" to BuildConfig.VERSION_NAME,
                            "versionCode" to BuildConfig.VERSION_CODE,
                            "releaseBuild" to !BuildConfig.DEBUG,
                            "packageName" to packageName,
                            "theme" to preferences.getString(THEME_KEY, "default"),
                            "cameraGuideMode" to (
                                runCatching {
                                    preferences.getString(CAMERA_GUIDE_KEY, "lFrame")
                                }.getOrNull()?.takeIf { it in CAMERA_GUIDE_MODES } ?: "lFrame"
                            ),
                            "cameraZoom" to (
                                runCatching {
                                    preferences.getFloat(CAMERA_ZOOM_KEY, 1.0f).toDouble()
                                }.getOrNull()?.takeIf { it in CAMERA_ZOOM_LEVELS } ?: 1.0
                            ),
                        ),
                    )
                    "setTheme" -> {
                        val theme = call.arguments as? String
                        if (theme != "default" && theme != "dark") {
                            result.success(false)
                        } else {
                            result.success(preferences.edit().putString(THEME_KEY, theme).commit())
                        }
                    }
                    "setCameraPreferences" -> {
                        val values = call.arguments as? Map<*, *>
                        val guideMode = values?.get("guideMode") as? String
                        val zoom = (values?.get("zoom") as? Number)?.toDouble()
                        if (
                            guideMode == null || guideMode !in CAMERA_GUIDE_MODES ||
                            zoom == null || zoom !in CAMERA_ZOOM_LEVELS
                        ) {
                            result.success(false)
                        } else {
                            result.success(
                                preferences.edit()
                                    .putString(CAMERA_GUIDE_KEY, guideMode)
                                    .putFloat(CAMERA_ZOOM_KEY, zoom.toFloat())
                                    .commit(),
                            )
                        }
                    }
                    else -> result.notImplemented()
                }
            }

        nsdManager = getSystemService(NSD_SERVICE) as? NsdManager
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, DISCOVERY_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "discoverDesktop" -> startDiscovery(result)
                    "stopDiscovery" -> {
                        finishDiscovery(null)
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun startDiscovery(result: MethodChannel.Result) {
        finishDiscovery(null)
        val manager = nsdManager
        if (manager == null) {
            result.error("NSD_UNAVAILABLE", "Android network discovery is unavailable.", null)
            return
        }

        discoveryResult = result
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                finishDiscovery(null)
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                finishDiscovery(null)
            }

            override fun onServiceFound(service: NsdServiceInfo) {
                if (!service.serviceType.startsWith(SERVICE_TYPE)) return
                manager.resolveService(service, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit

                    override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                        val properties = serviceInfo.attributes
                        if (
                            properties["protocol"]?.decodeToString() != "bookledger-mobile" ||
                            properties["version"]?.decodeToString() != "1"
                        ) {
                            return
                        }
                        val address = serviceInfo.host
                        if (address is Inet4Address) {
                            finishDiscovery(
                                mapOf("address" to address.hostAddress, "port" to serviceInfo.port),
                            )
                        }
                    }
                })
            }

            override fun onServiceLost(service: NsdServiceInfo) = Unit
        }
        discoveryListener = listener
        try {
            manager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
            mainHandler.postDelayed(discoveryTimeout, DISCOVERY_TIMEOUT_MS)
        } catch (error: RuntimeException) {
            finishDiscovery(null)
        }
    }

    private fun finishDiscovery(endpoint: Map<String, Any>?) {
        mainHandler.removeCallbacks(discoveryTimeout)
        val manager = nsdManager
        val listener = discoveryListener
        discoveryListener = null
        if (manager != null && listener != null) {
            try {
                manager.stopServiceDiscovery(listener)
            } catch (_: IllegalArgumentException) {
                // Discovery may already have stopped after a system callback.
            }
        }
        val result = discoveryResult
        discoveryResult = null
        result?.success(endpoint)
    }

    override fun onDestroy() {
        finishDiscovery(null)
        scanToneGenerator?.release()
        scanToneGenerator = null
        super.onDestroy()
    }

    @Deprecated("Deprecated in Android, retained for the package-installer result contract")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != UPDATE_INSTALL_REQUEST) return
        val expected = expectedInstallVersionCode
        expectedInstallVersionCode = null
        val result = installResult
        installResult = null
        val installed = runCatching {
            val info = packageManager.getPackageInfo(packageName, 0)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.longVersionCode else info.versionCode.toLong()
        }.getOrNull()
        when {
            expected != null && installed != null && installed >= expected -> result?.success("installed")
            resultCode == RESULT_CANCELED -> result?.success("canceled")
            else -> result?.success("notConfirmed")
        }
    }

    private fun verifiedUpdateApk(path: String, expectedSha256: String): Pair<File, PackageInfo> {
        require(Regex("[0-9a-f]{64}").matches(expectedSha256)) { "APK checksum is invalid." }
        val updateRoot = File(filesDir, "updates").canonicalFile
        val apk = File(path).canonicalFile
        require(apk.isFile && apk.name.matches(Regex("BookLedger-v?[0-9]+\\.[0-9]+\\.[0-9]+-Android\\.apk"))) {
            "The verified APK is missing or has an unexpected name."
        }
        require(apk.toPath().startsWith(updateRoot.toPath()) && apk.parentFile?.parentFile == updateRoot) {
            "Only an APK in BookLedger's private update storage can be installed."
        }
        require(apk.length() in 1..(256L * 1024 * 1024)) { "APK size is invalid." }
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(apk).use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        require(digest.digest().joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') } == expectedSha256) {
            "The APK changed after download verification. Download it again."
        }
        val info = packageManager.getPackageArchiveInfo(apk.path, 0)
            ?: throw IllegalArgumentException("Android could not read this APK.")
        return apk to info
    }

    private fun apkVersionCode(info: PackageInfo): Long =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.longVersionCode else info.versionCode.toLong()

    private fun beginUpdateInstall(apk: File, versionCode: Long, result: MethodChannel.Result) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
                result.success("permissionRequired")
            } catch (_: ActivityNotFoundException) {
                result.success("unavailable")
            } catch (_: SecurityException) {
                result.success("unavailable")
            }
            return
        }
        try {
            val contentUri = FileProvider.getUriForFile(this, "$packageName.update-files", apk)
            val intent = Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
                data = contentUri
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                putExtra(Intent.EXTRA_RETURN_RESULT, true)
            }
            expectedInstallVersionCode = versionCode
            installResult = result
            startActivityForResult(intent, UPDATE_INSTALL_REQUEST)
        } catch (_: ActivityNotFoundException) {
            expectedInstallVersionCode = null
            installResult = null
            result.success("unavailable")
        } catch (_: IllegalArgumentException) {
            expectedInstallVersionCode = null
            installResult = null
            result.success("unavailable")
        } catch (_: SecurityException) {
            expectedInstallVersionCode = null
            installResult = null
            result.success("unavailable")
        }
    }

    private companion object {
        const val CHANNEL_NAME = "com.bookledger.mobile/scan_feedback"
        const val EXTERNAL_URL_CHANNEL = "com.bookledger.mobile/external_url"
        const val UPDATE_INSTALL_CHANNEL = "com.bookledger.mobile/update_installer"
        const val UPDATE_INSTALL_REQUEST = 7014
        const val GITHUB_URL = "https://github.com/hectordoesgorug/BookLedger"
        const val APP_SETTINGS_CHANNEL = "com.bookledger.mobile/app_settings"
        const val APP_SETTINGS_PREFERENCES = "bookledger_mobile_preferences"
        const val THEME_KEY = "theme"
        const val CAMERA_GUIDE_KEY = "camera_guide_mode"
        const val CAMERA_ZOOM_KEY = "camera_zoom"
        val CAMERA_GUIDE_MODES = setOf("lFrame", "grid3x3", "grid4x4", "off")
        val CAMERA_ZOOM_LEVELS = setOf(0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
        const val DISCOVERY_CHANNEL = "com.bookledger.mobile/desktop_discovery"
        const val SERVICE_TYPE = "_bookledger._tcp."
        const val DISCOVERY_TIMEOUT_MS = 8_000L
        const val TONE_DURATION_MS = 160
        const val TONE_VOLUME = 85
    }
}

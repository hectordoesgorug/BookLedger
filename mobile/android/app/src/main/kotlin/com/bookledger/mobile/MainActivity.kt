package com.bookledger.mobile

import android.content.ActivityNotFoundException
import android.content.Intent
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import java.net.Inet4Address
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var scanToneGenerator: ToneGenerator? = null
    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var discoveryResult: MethodChannel.Result? = null
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
                if (call.method != "openGithub" || call.arguments != GITHUB_URL) {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(GITHUB_URL)))
                    result.success(true)
                } catch (_: ActivityNotFoundException) {
                    result.success(false)
                } catch (_: SecurityException) {
                    result.success(false)
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, APP_SETTINGS_CHANNEL)
            .setMethodCallHandler { call, result ->
                val preferences = getSharedPreferences(APP_SETTINGS_PREFERENCES, MODE_PRIVATE)
                when (call.method) {
                    "getAppSettings" -> result.success(
                        mapOf(
                            "version" to BuildConfig.VERSION_NAME,
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

    private companion object {
        const val CHANNEL_NAME = "com.bookledger.mobile/scan_feedback"
        const val EXTERNAL_URL_CHANNEL = "com.bookledger.mobile/external_url"
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

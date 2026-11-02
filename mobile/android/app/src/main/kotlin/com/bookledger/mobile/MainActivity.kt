package com.bookledger.mobile

import android.media.AudioManager
import android.media.ToneGenerator
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper
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
        const val DISCOVERY_CHANNEL = "com.bookledger.mobile/desktop_discovery"
        const val SERVICE_TYPE = "_bookledger._tcp."
        const val DISCOVERY_TIMEOUT_MS = 8_000L
        const val TONE_DURATION_MS = 160
        const val TONE_VOLUME = 85
    }
}

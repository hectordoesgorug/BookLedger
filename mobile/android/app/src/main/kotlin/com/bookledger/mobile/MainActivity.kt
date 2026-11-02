package com.bookledger.mobile

import android.media.AudioManager
import android.media.ToneGenerator
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var scanToneGenerator: ToneGenerator? = null

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
    }

    override fun onDestroy() {
        scanToneGenerator?.release()
        scanToneGenerator = null
        super.onDestroy()
    }

    private companion object {
        const val CHANNEL_NAME = "com.bookledger.mobile/scan_feedback"
        const val TONE_DURATION_MS = 160
        const val TONE_VOLUME = 85
    }
}

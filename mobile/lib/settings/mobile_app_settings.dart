import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../capture/photo_camera_configuration.dart';

const _settingsChannel = MethodChannel('com.bookledger.mobile/app_settings');
const _cameraGuideModes = {'lFrame', 'grid3x3', 'grid4x4', 'off'};

String mobileVersionLabel(String? version) => version == null
    ? 'BookLedger Mobile • Version unavailable'
    : 'BookLedger Mobile • v$version';

class MobileAppSettings extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.light;
  String? _version;
  Future<void>? _initialization;
  Future<void> _cameraPreferenceWrites = Future<void>.value();
  String _cameraGuideMode = 'lFrame';
  double _cameraZoom = 1.0;
  bool _disposed = false;

  ThemeMode get themeMode => _themeMode;
  String? get version => _version;
  String get cameraGuideMode => _cameraGuideMode;
  double get cameraZoom => _cameraZoom;

  Future<void> initialize() => _initialization ??= _load();

  Future<void> _load() async {
    try {
      final values = await _settingsChannel.invokeMapMethod<String, Object?>(
        'getAppSettings',
      );
      final version = values?['version'];
      _version = version is String ? version : null;
      _themeMode = values?['theme'] == 'dark'
          ? ThemeMode.dark
          : ThemeMode.light;
      final guideMode = values?['cameraGuideMode'];
      _cameraGuideMode =
          guideMode is String && _cameraGuideModes.contains(guideMode)
          ? guideMode
          : 'lFrame';
      final zoom = values?['cameraZoom'];
      _cameraZoom =
          zoom is num && discreteCameraZoomLevels.contains(zoom.toDouble())
          ? zoom.toDouble()
          : 1.0;
    } on MissingPluginException {
      _version = null;
    } on PlatformException {
      _version = null;
    } on Object {
      _version = null;
    }
    _notifyIfActive();
  }

  Future<void> setThemeMode(ThemeMode themeMode) async {
    await initialize();
    final saved = await _settingsChannel.invokeMethod<bool>(
      'setTheme',
      themeMode == ThemeMode.dark ? 'dark' : 'default',
    );
    if (saved != true) {
      throw PlatformException(
        code: 'THEME_SAVE_FAILED',
        message: 'The theme preference could not be saved.',
      );
    }
    _themeMode = themeMode;
    _notifyIfActive();
  }

  Future<bool> setCameraGuideMode(String guideMode) {
    if (!_cameraGuideModes.contains(guideMode)) return Future.value(false);
    return _saveCameraPreferences(guideMode: guideMode);
  }

  Future<bool> setCameraZoom(double zoom) {
    if (!discreteCameraZoomLevels.contains(zoom)) return Future.value(false);
    return _saveCameraPreferences(zoom: zoom);
  }

  Future<bool> _saveCameraPreferences({String? guideMode, double? zoom}) async {
    await initialize();
    if (_disposed) return false;

    final nextGuideMode = guideMode ?? _cameraGuideMode;
    final nextZoom = zoom ?? _cameraZoom;
    _cameraGuideMode = nextGuideMode;
    _cameraZoom = nextZoom;

    final result = Completer<bool>();
    _cameraPreferenceWrites = _cameraPreferenceWrites.then((_) async {
      var saved = false;
      try {
        saved =
            await _settingsChannel.invokeMethod<bool>('setCameraPreferences', {
              'guideMode': nextGuideMode,
              'zoom': nextZoom,
            }) ==
            true;
      } on Object {
        saved = false;
      }
      result.complete(saved);
    });
    return result.future;
  }

  void _notifyIfActive() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

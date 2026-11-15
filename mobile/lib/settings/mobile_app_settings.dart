import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const _settingsChannel = MethodChannel('com.bookledger.mobile/app_settings');

String mobileVersionLabel(String? version) => version == null
    ? 'BookLedger Mobile • Version unavailable'
    : 'BookLedger Mobile • v$version';

class MobileAppSettings extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.light;
  String? _version;
  Future<void>? _initialization;

  ThemeMode get themeMode => _themeMode;
  String? get version => _version;

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
    } on MissingPluginException {
      _version = null;
    } on PlatformException {
      _version = null;
    }
    notifyListeners();
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
    notifyListeners();
  }
}

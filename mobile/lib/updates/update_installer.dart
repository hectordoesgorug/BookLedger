import 'package:flutter/services.dart';

import 'update_service.dart';

const _channel = MethodChannel('com.bookledger.mobile/update_installer');

class UpdateApkEligibility {
  const UpdateApkEligibility({
    required this.packageName,
    required this.versionCode,
  });

  final String packageName;
  final int versionCode;
}

abstract interface class UpdateInstaller {
  Future<UpdateApkEligibility> inspect(
    VerifiedUpdateDownload download,
    int installedVersionCode,
  );

  Future<String> install(VerifiedUpdateDownload download, int versionCode);
}

class PlatformUpdateInstaller implements UpdateInstaller {
  const PlatformUpdateInstaller();

  @override
  Future<UpdateApkEligibility> inspect(
    VerifiedUpdateDownload download,
    int installedVersionCode,
  ) async {
    final result = await _channel.invokeMapMethod<String, Object?>(
      'inspectVerifiedApk',
      {
        'path': download.file.path,
        'sha256': download.sha256,
        'installedVersionCode': installedVersionCode,
      },
    );
    final packageName = result?['packageName'];
    final versionCode = result?['versionCode'];
    if (packageName is! String || versionCode is! int) {
      throw const FormatException('Android could not verify this APK.');
    }
    return UpdateApkEligibility(
      packageName: packageName,
      versionCode: versionCode,
    );
  }

  @override
  Future<String> install(
    VerifiedUpdateDownload download,
    int versionCode,
  ) async =>
      await _channel.invokeMethod<String>('installVerifiedApk', {
        'path': download.file.path,
        'sha256': download.sha256,
        'versionCode': versionCode,
      }) ??
      'unavailable';
}

import 'dart:async';
import 'dart:developer' as developer;

import 'package:flutter/services.dart';

import 'isbn_validator.dart';

const _scanFeedbackChannel = MethodChannel(
  'com.bookledger.mobile/scan_feedback',
);

Future<void> playIsbnSuccessBeep() async {
  try {
    await _scanFeedbackChannel.invokeMethod<void>('playSuccessBeep');
  } on PlatformException catch (error, stackTrace) {
    developer.log(
      'Native ISBN scan beep failed.',
      name: 'BookLedger.scan',
      error: error,
      stackTrace: stackTrace,
    );
  } on MissingPluginException catch (error, stackTrace) {
    developer.log(
      'Native ISBN scan beep is unavailable on this platform.',
      name: 'BookLedger.scan',
      error: error,
      stackTrace: stackTrace,
    );
  }
}

String? normalizeIsbnAndPlaySuccessBeep(
  String? rawValue, {
  required Future<void> Function() playBeep,
}) {
  final isbn = IsbnValidator.normalizeAndValidate(rawValue);
  if (isbn == null) {
    return null;
  }

  try {
    unawaited(
      Future<void>.sync(playBeep)
          .catchError((Object error, StackTrace stackTrace) {
            developer.log(
              'ISBN scan beep callback failed.',
              name: 'BookLedger.scan',
              error: error,
              stackTrace: stackTrace,
            );
          }),
    );
  } catch (error, stackTrace) {
    developer.log(
      'ISBN scan beep callback failed.',
      name: 'BookLedger.scan',
      error: error,
      stackTrace: stackTrace,
    );
  }
  return isbn;
}

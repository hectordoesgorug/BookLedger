import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/isbn_scan_feedback.dart';

void main() {
  group('ISBN scan feedback', () {
    test('valid ISBN triggers one beep without waiting for playback', () {
      var beepCount = 0;
      final playback = Completer<void>();

      final isbn = normalizeIsbnAndPlaySuccessBeep(
        '9780306406157',
        playBeep: () {
          beepCount++;
          return playback.future;
        },
      );

      expect(isbn, '9780306406157');
      expect(beepCount, 1);
      expect(playback.isCompleted, isFalse);
      playback.complete();
    });

    test('invalid barcode does not trigger a beep', () {
      var beepCount = 0;

      final isbn = normalizeIsbnAndPlaySuccessBeep(
        '9780306406158',
        playBeep: () async => beepCount++,
      );

      expect(isbn, isNull);
      expect(beepCount, 0);
    });

    test('a later valid rescan can beep again', () {
      var beepCount = 0;
      Future<void> beep() async {
        beepCount++;
      }

      expect(
        normalizeIsbnAndPlaySuccessBeep('0306406152', playBeep: beep),
        '0306406152',
      );
      expect(
        normalizeIsbnAndPlaySuccessBeep('9780306406157', playBeep: beep),
        '9780306406157',
      );
      expect(beepCount, 2);
    });
  });
}

import 'package:camera/camera.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/photo_camera_configuration.dart';

void main() {
  test('photo camera targets the highest available resolution', () {
    expect(photoCameraResolutionPreset, ResolutionPreset.max);
  });

  test('discrete zoom stops are half steps capped at 3x', () {
    expect(discreteCameraZoomLevels, [0.5, 1, 1.5, 2, 2.5, 3]);
    expect(
      supportedCameraZoomLevels(minimum: 0.5, maximum: 10),
      discreteCameraZoomLevels,
    );
  });

  test('levels below the camera minimum are omitted', () {
    expect(supportedCameraZoomLevels(minimum: 1.0, maximum: 3.0), [
      1.0,
      1.5,
      2.0,
      2.5,
      3.0,
    ]);
  });

  test('levels above the camera maximum are omitted', () {
    expect(supportedCameraZoomLevels(minimum: 1.0, maximum: 2.2), [
      1.0,
      1.5,
      2.0,
    ]);
  });

  test('minimum below 1x is not treated as proof that 0.5x is supported', () {
    expect(supportedCameraZoomLevels(minimum: 0.6, maximum: 3.0).first, 1.0);
  });

  test('saved zoom resolves to the nearest supported stop', () {
    expect(nearestCameraZoomLevel(1.0, [0.5, 1, 1.5, 2, 2.5, 3]), 1.0);
    expect(nearestCameraZoomLevel(2.5, [1, 1.5, 2]), 2.0);
    expect(nearestCameraZoomLevel(1.0, []), 1.0);
  });

  test('invalid zoom limits offer no discrete stop', () {
    expect(supportedCameraZoomLevels(minimum: 4.0, maximum: 2.0), isEmpty);
    expect(
      supportedCameraZoomLevels(minimum: double.nan, maximum: 2.0),
      isEmpty,
    );
    expect(
      supportedCameraZoomLevels(minimum: 1, maximum: double.infinity),
      isEmpty,
    );
  });
}

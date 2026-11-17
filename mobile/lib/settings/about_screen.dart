import 'dart:async';

import 'package:flutter/material.dart';

import 'mobile_app_settings.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({
    required this.settings,
    required this.onVisitGitHub,
    super.key,
  });

  final MobileAppSettings settings;
  final Future<void> Function() onVisitGitHub;

  Widget _section(BuildContext context, String title, List<Widget> children) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            ...children,
          ],
        ),
      );

  Widget _steps(BuildContext context, List<String> steps) => Column(
    children: [
      for (var index = 0; index < steps.length; index++)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 24,
                child: Text(
                  '${index + 1}.',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Expanded(child: Text(steps[index])),
            ],
          ),
        ),
    ],
  );

  Widget _paragraph(String text) =>
      Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(text));

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('About')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
        children: [
          _section(context, 'About BookLedger Mobile', [
            _paragraph(
              'BookLedger Mobile is a companion to the BookLedger desktop inventory manager. '
              'Use it to scan or enter book identifiers, photograph covers, and send captures '
              'to the desktop over a local connection. The desktop is the catalog and inventory; '
              'the mobile app is not a standalone book catalog.',
            ),
          ]),
          _section(context, 'Getting Started', [
            _steps(context, [
              'Open BookLedger on the desktop and open Settings → Mobile App Setup.',
              'On your phone, open Settings → Pairing.',
              'Scan the desktop QR code, or enter its local IPv4 address, port, and temporary pairing code.',
              'Wait for the phone to show Connected.',
            ]),
          ]),
          _section(context, 'Single Entry', [
            _steps(context, [
              'Choose Single Entry, then scan an ISBN, enter it manually, or choose No ISBN.',
              'Save the identifier, photograph the book cover, review the photo, and choose Save.',
              'When connected, choose Send and keep the app open until the desktop acknowledges receipt.',
              'Complete the book details in the desktop form. A successful transfer sends the capture; cataloging happens on the desktop.',
            ]),
          ]),
          _section(context, 'Bulk Entry', [
            _steps(context, [
              'Choose Bulk Entry and select a queue size from 5 to 20.',
              'For each book, scan or enter its ISBN (or choose No ISBN), photograph the cover, then choose Save and Queue.',
              'The queue shows how many captures are ready. It sends when full; to send fewer, hold Queue to finish the batch early.',
              'Choose Send and keep the app open for the desktop acknowledgement. Unacknowledged captures remain available for retry.',
              'Complete each received book in the desktop form. The queue does not provide per-entry removal.',
            ]),
          ]),
          _section(context, 'Camera Controls', [
            _paragraph(
              'Camera controls are available during the live cover preview and disappear after a photo is captured.',
            ),
            _paragraph(
              'Torch: tap the torch icon to switch continuous camera lighting on or off. It is available only when the camera supports it.',
            ),
            _paragraph(
              'Zoom: use 0.5× steps from 0.5× up to 3.0×, limited to levels supported by the active camera. Some cameras, including cameras with a 1.0× minimum, do not offer 0.5×. Your selected zoom is remembered.',
            ),
            _paragraph(
              'Guide: tap the icon to cycle through L-shaped corner guides, a 3×3 yellow grid with a red center dot, a 4×4 yellow grid with a red center dot, and Off. Your selection is remembered.',
            ),
            _paragraph(
              'Guides are visual alignment references only; overlays do not crop, straighten, or otherwise change captured photographs.',
            ),
          ]),
          _section(context, 'Pairing and Connectivity', [
            _paragraph(
              'The phone and desktop must be able to reach each other on the same trusted Wi-Fi network or a compatible hotspot. '
              'Use the QR code or manual address and temporary code in Pairing. The app retries the saved connection while it is in use. '
              'If the desktop address changes, use Reconnect now; automatic discovery may find it, otherwise pair again with the current address. '
              'Forget Pairing removes credentials from this phone. It does not revoke the desktop authorization.',
            ),
          ]),
          _section(context, 'Troubleshooting', [
            _paragraph(
              'Camera permission denied: allow Camera access in Android app settings, then try again. '
              'Barcode not detected: improve the lighting, steady the phone, and fit the barcode inside the scan area.',
            ),
            _paragraph(
              'Desktop not found or pairing fails: keep BookLedger desktop open on Mobile App Setup, check both devices’ local network access '
              'and the desktop firewall, then try QR or manual pairing. For a lost connection, choose Reconnect now or wait for automatic retry. '
              'Clear Data is not needed for routine network problems.',
            ),
            _paragraph(
              'Transfer interrupted: keep pending captures and retry after reconnecting. Clear Data permanently deletes pending local ISBNs and photos '
              'and forgets pairing on this phone. Books already saved on the desktop are not affected.',
            ),
          ]),
          _section(context, 'Version and Project Information', [
            AnimatedBuilder(
              animation: settings,
              builder: (context, _) =>
                  Text(mobileVersionLabel(settings.version)),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () => unawaited(onVisitGitHub()),
              icon: Image.asset(
                'assets/github-mark.png',
                width: 22,
                height: 22,
                semanticLabel: 'GitHub logo',
              ),
              label: const Text('BookLedger on GitHub'),
            ),
          ]),
        ],
      ),
    ),
  );
}

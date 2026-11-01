import 'package:flutter/material.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seedColor = Color(0xFF346B63);
    return MaterialApp(
      title: 'BookLedger Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: seedColor,
          surface: const Color(0xFFF7F7F3),
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF7F7F3),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF7F7F3),
          foregroundColor: Color(0xFF202A28),
          centerTitle: false,
        ),
      ),
      home: const HomeScreen(),
    );
  }
}

enum _HomeMenuAction { about, settings, exit }

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  void _openPlaceholder(BuildContext context, String title) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => PlaceholderScreen(title: title)),
    );
  }

  void _handleMenu(BuildContext context, _HomeMenuAction action) {
    switch (action) {
      case _HomeMenuAction.about:
        _openPlaceholder(context, 'About');
      case _HomeMenuAction.settings:
        _openPlaceholder(context, 'Settings');
      case _HomeMenuAction.exit:
        showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Exit'),
            content: const Text(
              'Exit controls will be available in a later version.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Close'),
              ),
            ],
          ),
        );
    }
  }

  void _openSingleEntry(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const CaptureScreen(mode: CaptureMode.single),
      ),
    );
  }

  void _openBulkEntry(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute<void>(builder: (_) => const QueueSizeScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: PopupMenuButton<_HomeMenuAction>(
          tooltip: 'Menu',
          icon: const Icon(Icons.menu),
          onSelected: (action) => _handleMenu(context, action),
          itemBuilder: (context) => const [
            PopupMenuItem(value: _HomeMenuAction.about, child: Text('About')),
            PopupMenuItem(
              value: _HomeMenuAction.settings,
              child: Text('Settings'),
            ),
            PopupMenuItem(value: _HomeMenuAction.exit, child: Text('Exit')),
          ],
        ),
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'BookLedger',
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.5,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Capture books and send them to your desktop library.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const Spacer(),
                    Row(
                      children: [
                        Expanded(
                          child: _EntryCard(
                            label: 'Single Entry',
                            description: 'Capture one book',
                            icon: Icons.book_outlined,
                            onTap: () => _openSingleEntry(context),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: _EntryCard(
                            label: 'Bulk Entry',
                            description: 'Capture a queue',
                            icon: Icons.library_books_outlined,
                            onTap: () => _openBulkEntry(context),
                          ),
                        ),
                      ],
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
            const ConnectionStatus(),
          ],
        ),
      ),
    );
  }
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({
    required this.label,
    required this.description,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final String description;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: colors.primaryContainer,
      borderRadius: BorderRadius.circular(20),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: SizedBox(
          height: 168,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Icon(icon, size: 30, color: colors.onPrimaryContainer),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: colors.onPrimaryContainer,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: Theme.of(context).textTheme.bodySmall
                          ?.copyWith(color: colors.onPrimaryContainer),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

enum CaptureMode { single, bulk }

class CaptureScreen extends StatelessWidget {
  const CaptureScreen({required this.mode, this.queueTarget, super.key});

  final CaptureMode mode;
  final int? queueTarget;

  bool get _isBulk => mode == CaptureMode.bulk;

  @override
  Widget build(BuildContext context) {
    final labels = <String>[
      'Scan',
      'Take Photo',
      'Retake',
      'Save',
      _isBulk ? 'Queue' : 'Send',
      'Clear',
    ];
    return Scaffold(
      appBar: AppBar(title: Text(_isBulk ? 'Bulk Entry' : 'Single Entry')),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            if (_isBulk)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: Row(
                  children: [
                    Text(
                      'Queue',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Spacer(),
                    Text(
                      '0 / ${queueTarget ?? 5}',
                      key: const ValueKey('queue-counter'),
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            Expanded(
              child: Container(
                width: double.infinity,
                margin: const EdgeInsets.fromLTRB(16, 4, 16, 14),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Semantics(
                  label: 'Camera preview area',
                  child: SizedBox.expand(),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: labels.length,
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 3,
                  mainAxisExtent: 62,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                ),
                itemBuilder: (context, index) {
                  final enabled = index == 0;
                  return ElevatedButton(
                    onPressed: enabled ? () {} : null,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Text(labels[index]),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            const ConnectionStatus(),
          ],
        ),
      ),
    );
  }
}

class QueueSizeScreen extends StatefulWidget {
  const QueueSizeScreen({super.key});

  @override
  State<QueueSizeScreen> createState() => _QueueSizeScreenState();
}

class _QueueSizeScreenState extends State<QueueSizeScreen> {
  static const int _minimum = 5;
  static const int _maximum = 20;
  int _queueSize = _minimum;

  void _continue() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) =>
            CaptureScreen(mode: CaptureMode.bulk, queueTarget: _queueSize),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bulk Entry')),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              Text(
                'Queue size',
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                'Choose how many books to capture in this queue.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 36),
              Center(
                child: Text(
                  '$_queueSize',
                  key: const ValueKey('selected-queue-size'),
                  style: Theme.of(context).textTheme.displayMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              Slider(
                value: _queueSize.toDouble(),
                min: _minimum.toDouble(),
                max: _maximum.toDouble(),
                divisions: _maximum - _minimum,
                label: '$_queueSize',
                onChanged: (value) =>
                    setState(() => _queueSize = value.round()),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: const [Text('$_minimum'), Text('$_maximum')],
              ),
              const Spacer(),
              FilledButton(onPressed: _continue, child: const Text('OK')),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}

class ConnectionStatus extends StatelessWidget {
  const ConnectionStatus({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.circle,
            size: 10,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(width: 10),
          Text(
            'Not connected',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({required this.title, super.key});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(child: Text('$title will be available in a later version.')),
    );
  }
}

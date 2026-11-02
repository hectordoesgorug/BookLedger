import 'package:flutter/material.dart';

class QueueActionButton extends StatefulWidget {
  const QueueActionButton({
    required this.label,
    required this.onTap,
    required this.onLongPress,
    required this.canTap,
    required this.canLongPress,
    super.key,
  });

  final String label;
  final VoidCallback onTap;
  final VoidCallback onLongPress;
  final bool canTap;
  final bool canLongPress;

  @override
  State<QueueActionButton> createState() => _QueueActionButtonState();
}

class _QueueActionButtonState extends State<QueueActionButton> {
  bool _holding = false;

  void _setHolding(bool value) {
    if (_holding != value && mounted) {
      setState(() => _holding = value);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final enabled = widget.canTap || widget.canLongPress;
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      hint: widget.canLongPress
          ? 'Hold to finish the batch early.'
          : widget.canTap
          ? 'Add this capture to the queue.'
          : 'Capture an ISBN and photo first.',
      child: Listener(
        onPointerDown: widget.canLongPress ? (_) => _setHolding(true) : null,
        onPointerUp: widget.canLongPress ? (_) => _setHolding(false) : null,
        onPointerCancel: widget.canLongPress ? (_) => _setHolding(false) : null,
        child: Material(
          color: enabled
              ? (_holding ? colors.primary : colors.primaryContainer)
              : colors.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(14),
          child: InkWell(
            key: const ValueKey('queue-action'),
            borderRadius: BorderRadius.circular(14),
            onTap: widget.canTap ? widget.onTap : null,
            onLongPress: widget.canLongPress ? widget.onLongPress : null,
            onTapCancel: () => _setHolding(false),
            onHighlightChanged: _setHolding,
            child: Center(
              child: AnimatedDefaultTextStyle(
                duration: const Duration(milliseconds: 120),
                style: Theme.of(context).textTheme.labelLarge!.copyWith(
                  color: enabled
                      ? (_holding
                            ? colors.onPrimary
                            : colors.onPrimaryContainer)
                      : colors.onSurface.withValues(alpha: 0.38),
                  fontWeight: FontWeight.w600,
                ),
                child: Text(_holding ? 'Hold…' : widget.label),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

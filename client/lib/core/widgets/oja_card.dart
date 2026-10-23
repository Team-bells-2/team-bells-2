import 'package:flutter/material.dart';

import '../theme.dart';

class OjaCard extends StatelessWidget {
  const OjaCard({super.key, required this.child, this.color = Colors.white});

  final Widget child;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: ojaLine),
      ),
      child: child,
    );
  }
}

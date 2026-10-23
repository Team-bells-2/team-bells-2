import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../core/widgets/oja_card.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key, this.liveApi = false, this.apiBaseUrl});

  final bool liveApi;
  final String? apiBaseUrl;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        const Text('Profile', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ojaInk)),
        const SizedBox(height: 16),
        const OjaCard(
          child: Row(
            children: [
              CircleAvatar(
                radius: 26,
                backgroundColor: ojaGreenSoft,
                child: Text('IB', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w800)),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Iya Basira', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ojaInk)),
                    Text('Iya Basira Foodstuffs', style: TextStyle(color: ojaMuted)),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        const OjaCard(
          child: Column(
            children: [
              _ProfileRow(label: 'Market', value: 'Mile 12, Lagos'),
              Divider(height: 20, color: ojaLine),
              _ProfileRow(label: 'Sector', value: 'Foodstuff'),
              Divider(height: 20, color: ojaLine),
              _ProfileRow(label: 'Language', value: 'Pidgin and English'),
            ],
          ),
        ),
        const SizedBox(height: 10),
        OjaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('API', style: TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
              const SizedBox(height: 6),
              Text(
                liveApi ? 'Connected to live backend' : 'Local demo book (tests / offline)',
                style: const TextStyle(color: ojaMuted),
              ),
              if (apiBaseUrl != null) ...[
                const SizedBox(height: 4),
                Text(apiBaseUrl!, style: const TextStyle(color: ojaInk, fontSize: 13)),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(label, style: const TextStyle(color: ojaMuted)),
        const Spacer(),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600, color: ojaInk)),
      ],
    );
  }
}

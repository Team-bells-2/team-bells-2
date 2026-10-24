import 'package:flutter/material.dart';

import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';
import '../../core/widgets/oja_card.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key, required this.book, this.liveApi = false, this.apiBaseUrl, this.onLogOut});

  final OjaBook book;
  final bool liveApi;
  final String? apiBaseUrl;
  final Future<void> Function()? onLogOut;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        const Text('Profile', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ojaInk)),
        const SizedBox(height: 16),
        OjaCard(
          child: Row(
            children: [
              CircleAvatar(
                radius: 26,
                backgroundColor: ojaGreenSoft,
                child: Text(_initials(book.traderName), style: const TextStyle(color: ojaGreen, fontWeight: FontWeight.w800)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(book.traderName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ojaInk)),
                    Text(book.businessName, style: const TextStyle(color: ojaMuted)),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        OjaCard(
          child: Column(
            children: [
              _ProfileRow(label: 'Market', value: '${book.market}, Lagos'),
              if (book.phone.isNotEmpty) ...[
                const Divider(height: 20, color: ojaLine),
                _ProfileRow(label: 'Phone', value: book.phone),
              ],
              const Divider(height: 20, color: ojaLine),
              const _ProfileRow(label: 'Sector', value: 'Foodstuff'),
              const Divider(height: 20, color: ojaLine),
              const _ProfileRow(label: 'Language', value: 'Pidgin and English'),
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
                liveApi ? 'Connected to OJA' : 'Local demo book (tests / offline)',
                style: const TextStyle(color: ojaMuted),
              ),
              if (apiBaseUrl != null) ...[
                const SizedBox(height: 4),
                Text(apiBaseUrl!, style: const TextStyle(color: ojaInk, fontSize: 13)),
              ],
            ],
          ),
        ),
        if (onLogOut != null) ...[
          const SizedBox(height: 16),
          OutlinedButton.icon(
            key: const Key('logout'),
            onPressed: () => onLogOut!(),
            icon: const Icon(Icons.logout),
            label: const Text('Log out'),
            style: OutlinedButton.styleFrom(
              foregroundColor: ojaOut,
              side: const BorderSide(color: ojaLine),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ],
      ],
    );
  }
}

String _initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  final letters = parts.length == 1 ? parts.first.substring(0, 1) : '${parts.first[0]}${parts.last[0]}';
  return letters.toUpperCase();
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

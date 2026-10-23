import 'package:flutter/material.dart';

import '../core/ledger/ledger.dart';
import '../core/theme.dart';
import '../features/assistant/assistant_page.dart';
import '../features/home/home_page.dart';
import '../features/inventory/inventory_page.dart';
import '../features/profile/profile_page.dart';

class OjaApp extends StatefulWidget {
  const OjaApp({super.key});

  @override
  State<OjaApp> createState() => _OjaAppState();
}

class _OjaAppState extends State<OjaApp> {
  final _book = OjaBook.demo();
  var _tab = 0;

  void _openRestock(String item) {
    setState(() {
      _book.marketItem = item;
      _tab = 2;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OJA',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: ojaPage,
        colorScheme: ColorScheme.fromSeed(seedColor: ojaGreen, primary: ojaGreen, surface: Colors.white),
      ),
      home: Scaffold(
        body: SafeArea(
          bottom: false,
          child: IndexedStack(
            index: _tab,
            children: [
              HomePage(book: _book, onVoice: () => setState(() => _tab = 1), onRestock: _openRestock),
              AssistantPage(book: _book, onChanged: () => setState(() {})),
              InventoryPage(book: _book, onItem: (item) => setState(() => _book.marketItem = item)),
              const ProfilePage(),
            ],
          ),
        ),
        bottomNavigationBar: _NavBar(index: _tab, onSelect: (value) => setState(() => _tab = value)),
      ),
    );
  }
}

class _NavBar extends StatelessWidget {
  const _NavBar({required this.index, required this.onSelect});

  final int index;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 68,
          child: Row(
            children: [
              _NavButton(label: 'Home', icon: Icons.home_outlined, selectedIcon: Icons.home, selected: index == 0, onTap: () => onSelect(0)),
              _MicButton(selected: index == 1, onTap: () => onSelect(1)),
              _NavButton(
                label: 'Inventory',
                icon: Icons.inventory_2_outlined,
                selectedIcon: Icons.inventory_2,
                selected: index == 2,
                buttonKey: const Key('tab-inventory'),
                onTap: () => onSelect(2),
              ),
              _NavButton(
                label: 'Profile',
                icon: Icons.person_outline,
                selectedIcon: Icons.person,
                selected: index == 3,
                onTap: () => onSelect(3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.selected,
    required this.onTap,
    this.buttonKey,
  });

  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final bool selected;
  final VoidCallback onTap;
  final Key? buttonKey;

  @override
  Widget build(BuildContext context) {
    final color = selected ? ojaGreen : ojaMuted;
    return Expanded(
      child: InkWell(
        key: buttonKey,
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(selected ? selectedIcon : icon, color: color, size: 22),
            const SizedBox(height: 2),
            Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: selected ? FontWeight.w600 : FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton({required this.selected, required this.onTap});

  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        key: const Key('tab-assistant'),
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: const BoxDecoration(color: ojaGreen, shape: BoxShape.circle),
              child: const Icon(Icons.mic, color: Colors.white, size: 22),
            ),
            const SizedBox(height: 2),
            Text(
              'Assistant',
              style: TextStyle(
                color: selected ? ojaGreen : ojaMuted,
                fontSize: 11,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

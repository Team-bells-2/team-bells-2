import 'package:flutter/material.dart';

import '../core/api/oja_api.dart';
import '../core/ledger/ledger.dart';
import '../core/theme.dart';
import '../features/assistant/assistant_page.dart';
import '../features/home/home_page.dart';
import '../features/inventory/inventory_page.dart';
import '../features/profile/profile_page.dart';

class OjaApp extends StatefulWidget {
  const OjaApp({super.key, this.useLiveApi});

  /// When null, live API is used outside widget tests.
  final bool? useLiveApi;

  @override
  State<OjaApp> createState() => _OjaAppState();
}

class _OjaAppState extends State<OjaApp> {
  late final bool _live;
  late final OjaBook _book;
  OjaApi? _api;
  var _tab = 0;
  var _booting = false;
  var _historyLoaded = false;
  String? _bootError;

  @override
  void initState() {
    super.initState();
    _live = widget.useLiveApi ?? !_runningUnderTest;
    if (_live) {
      _api = OjaApi();
      _book = OjaBook.live(_api!);
      _booting = true;
      _refresh();
    } else {
      _book = OjaBook.demo();
    }
  }

  @override
  void dispose() {
    _api?.close();
    super.dispose();
  }

  bool get _runningUnderTest =>
      WidgetsBinding.instance.runtimeType.toString().contains('TestWidgetsFlutterBinding');

  Future<void> _refresh() async {
    try {
      await _book.refreshFromApi();
      if (!_historyLoaded) {
        await _book.loadChatHistory();
        _historyLoaded = true;
      }
      if (!mounted) return;
      setState(() {
        _booting = false;
        _bootError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _booting = false;
        _bootError = error.toString();
      });
    }
  }

  Future<void> _openRestock(String item) async {
    if (_live) {
      await _book.loadMarketOffers(item);
    } else {
      _book.marketItem = item;
    }
    if (!mounted) return;
    setState(() => _tab = 2);
  }

  void _onBookChanged() => setState(() {});

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
          child: _booting
              ? const Center(child: CircularProgressIndicator(color: ojaGreen))
              : Column(
                  children: [
                    if (_bootError != null || _book.statusMessage != null)
                      Material(
                        color: ojaGreenSoft,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  _bootError ?? _book.statusMessage!,
                                  style: const TextStyle(color: ojaInk, fontSize: 13),
                                ),
                              ),
                              if (_live)
                                TextButton(
                                  onPressed: () {
                                    setState(() {
                                      _booting = true;
                                      _bootError = null;
                                    });
                                    _refresh();
                                  },
                                  child: const Text('Retry'),
                                ),
                            ],
                          ),
                        ),
                      ),
                    Expanded(
                      child: IndexedStack(
                        index: _tab,
                        children: [
                          HomePage(
                            book: _book,
                            onVoice: () => setState(() => _tab = 1),
                            onRestock: _openRestock,
                            onRefresh: _live ? _refresh : null,
                          ),
                          AssistantPage(book: _book, onChanged: _onBookChanged),
                          InventoryPage(
                            book: _book,
                            onItem: (item) async {
                              if (_live) {
                                await _book.loadMarketOffers(item);
                              } else {
                                _book.marketItem = item;
                              }
                              if (mounted) setState(() {});
                            },
                          ),
                          ProfilePage(liveApi: _live, apiBaseUrl: _api?.baseUrl),
                        ],
                      ),
                    ),
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

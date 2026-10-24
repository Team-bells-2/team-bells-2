import 'package:flutter/material.dart';

import '../../core/catalog.dart';
import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';
import '../../core/widgets/oja_card.dart';

class HomePage extends StatelessWidget {
  const HomePage({
    super.key,
    required this.book,
    required this.onVoice,
    required this.onRestock,
    this.onRefresh,
  });

  final OjaBook book;
  final VoidCallback onVoice;
  final ValueChanged<String> onRestock;
  final Future<void> Function()? onRefresh;

  @override
  Widget build(BuildContext context) {
    final low = book.isLive
        ? book.apiLowStock
        : [
            for (final item in reorderLevels.keys)
              if ((book.stock[item] ?? 0) <= reorderLevels[item]!) item,
          ];
    final debtor = _topDebtor(book);
    final periodDetail = book.profitPeriodLabel ?? (book.isLive ? 'From API' : 'Today');
    final body = ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        const Text('OJA', style: TextStyle(color: ojaGreen, fontSize: 22, fontWeight: FontWeight.w800)),
        Text(
          book.isLive ? 'Mile 12 Market, Lagos · live API' : 'Mile 12 Market, Lagos',
          style: const TextStyle(color: ojaMuted),
        ),
        const SizedBox(height: 16),
        Text(_greeting(), style: const TextStyle(color: ojaMuted)),
        const Text('Iya Basira', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ojaInk)),
        const SizedBox(height: 14),
        OjaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Text('NET PROFIT', style: TextStyle(color: ojaMuted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.4)),
                  const Spacer(),
                  Text('+${naira(book.profit)}', style: const TextStyle(color: ojaGreen, fontWeight: FontWeight.w700)),
                ],
              ),
              const SizedBox(height: 6),
              Text(naira(book.sales), style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: ojaInk)),
              const Text('sales', style: TextStyle(color: ojaMuted)),
              const SizedBox(height: 8),
              Text('Cash ${naira(book.cashSales)}   ·   Credit ${naira(book.creditSales)}', style: const TextStyle(color: ojaInk)),
              const SizedBox(height: 10),
              Container(height: 6, decoration: BoxDecoration(color: ojaGreen, borderRadius: BorderRadius.circular(6))),
            ],
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _MiniStat(label: 'Total expenses', value: naira(book.expenses), detail: periodDetail)),
            const SizedBox(width: 10),
            Expanded(child: _MiniStat(label: 'Customer debt', value: naira(book.owed), detail: debtor ?? 'Nobody owes you')),
          ],
        ),
        const SizedBox(height: 10),
        Material(
          color: ojaGreen,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            onTap: onVoice,
            borderRadius: BorderRadius.circular(16),
            child: const Padding(
              padding: EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.mic, color: Colors.white),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Talk to OJA', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                        SizedBox(height: 2),
                        Text('Tell me what you sold, who paid, or where you fit buy.', style: TextStyle(color: Colors.white)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        if (low.isNotEmpty) ...[
          const SizedBox(height: 10),
          _RestockCard(
            item: low.first,
            left: book.stock[low.first] ?? 0,
            onOpen: () => onRestock(low.first),
            book: book,
          ),
        ],
        const SizedBox(height: 18),
        Text('Items logged  ${book.entries.length}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ojaInk)),
        const SizedBox(height: 10),
        if (book.entries.isEmpty)
          const Text('Nothing saved yet.', style: TextStyle(color: ojaMuted))
        else
          for (final entry in book.entries.reversed) _LoggedItem(entry: entry),
      ],
    );
    if (onRefresh == null) return body;
    return RefreshIndicator(color: ojaGreen, onRefresh: onRefresh!, child: body);
  }
}

class _RestockCard extends StatelessWidget {
  const _RestockCard({required this.item, required this.left, required this.onOpen, required this.book});

  final String item;
  final double left;
  final VoidCallback onOpen;
  final OjaBook book;

  @override
  Widget build(BuildContext context) {
    final ranked = book.isLive && book.marketOffers.isNotEmpty && book.marketItem == item
        ? book.marketOffers
        : rankOffers(item);
    final offer = ranked.first.offer;
    final unit = left == 1 ? offer.unit : (offer.unit.endsWith('s') ? offer.unit : '${offer.unit}s');
    final place = offer.km > 0 ? '${offer.supplier}  ·  ${offer.km} km  ·  ' : '${offer.supplier}  ·  ';
    return OjaCard(
      color: ojaGreenSoft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${itemTitle(item)} is low  ·  ${formatQty(left)} $unit left', style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
          const SizedBox(height: 6),
          Text('$place${naira(offer.price)}  ·  Grade ${offer.grade}', style: const TextStyle(color: ojaInk)),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: onOpen,
              style: TextButton.styleFrom(foregroundColor: ojaGreenDark, padding: const EdgeInsets.only(top: 6)),
              child: const Text('View restock'),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoggedItem extends StatelessWidget {
  const _LoggedItem({required this.entry});

  final LedgerEntry entry;

  @override
  Widget build(BuildContext context) {
    final expense = entry.kind == EntryKind.expense;
    final amount = entry.amountNgn == null ? '' : '${expense ? '-' : '+'}${naira(entry.amountNgn!)}';
    final detail = [
      if (entry.quantity != null && entry.itemLabel != null) '${formatQty(entry.quantity!)} ${entry.unit} ${entry.itemLabel}',
      _kindLabel(entry.kind),
    ].join('  ·  ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: OjaCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(entry.customer ?? entry.itemLabel ?? _kindLabel(entry.kind), style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
                  const SizedBox(height: 2),
                  Text(detail, style: const TextStyle(color: ojaMuted)),
                  const SizedBox(height: 4),
                  Text(entry.rawText, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: ojaMuted, fontSize: 13)),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(amount, style: TextStyle(color: expense ? ojaOut : ojaGreen, fontWeight: FontWeight.w800)),
          ],
        ),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.label, required this.value, required this.detail});

  final String label;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return OjaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: ojaMuted, fontSize: 13)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: ojaInk)),
          const SizedBox(height: 2),
          Text(detail, style: const TextStyle(color: ojaMuted, fontSize: 13)),
        ],
      ),
    );
  }
}

String _greeting() {
  final hour = DateTime.now().hour;
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

String _kindLabel(EntryKind kind) {
  return switch (kind) {
    EntryKind.cashSale => 'Cash sale',
    EntryKind.creditSale => 'Credit sale',
    EntryKind.payment => 'Payment',
    EntryKind.expense => 'Expense',
  };
}

String? _topDebtor(OjaBook book) {
  String? name;
  var highest = 0;
  final seen = <String>{};
  for (final entry in book.entries) {
    final customer = entry.customer;
    if (customer == null || !seen.add(customer)) continue;
    final balance = book.balanceOf(customer);
    if (balance > highest) {
      highest = balance;
      name = customer;
    }
  }
  return name;
}

import 'package:flutter/material.dart';

import '../../core/catalog.dart';
import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';
import '../../core/widgets/oja_card.dart';

class InventoryPage extends StatelessWidget {
  const InventoryPage({super.key, required this.book, required this.onItem});

  final OjaBook book;
  final ValueChanged<String> onItem;

  @override
  Widget build(BuildContext context) {
    final ranked = rankOffers(book.marketItem);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        const Text('Inventory', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ojaInk)),
        const Text('Mile 12 Market', style: TextStyle(color: ojaMuted)),
        const SizedBox(height: 14),
        for (final item in stockItems)
          _StockTile(
            item: item,
            quantity: book.stock[item] ?? 0,
            selected: book.marketItem == item,
            low: (book.stock[item] ?? 0) <= (reorderLevels[item] ?? 0),
            onTap: () => onItem(item),
          ),
        const SizedBox(height: 8),
        Text('Where to buy ${itemTitle(book.marketItem)}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        const Text('Demo prices.', style: TextStyle(color: ojaMuted)),
        const SizedBox(height: 10),
        for (final row in ranked) _OfferTile(row: row),
      ],
    );
  }
}

class _StockTile extends StatelessWidget {
  const _StockTile({
    required this.item,
    required this.quantity,
    required this.selected,
    required this.low,
    required this.onTap,
  });

  final String item;
  final double quantity;
  final bool selected;
  final bool low;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final unit = item == 'oil' ? 'kegs' : 'bags';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: selected ? ojaGreen : ojaLine, width: selected ? 1.5 : 1),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(itemTitle(item), style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
                      const SizedBox(height: 2),
                      Text('${formatQty(quantity)} $unit', style: const TextStyle(color: ojaMuted)),
                    ],
                  ),
                ),
                if (low) const Text('Low', style: TextStyle(color: ojaGreen, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _OfferTile extends StatelessWidget {
  const _OfferTile({required this.row});

  final RankedOffer row;

  @override
  Widget build(BuildContext context) {
    final offer = row.offer;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: OjaCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(offer.supplier, style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
            const SizedBox(height: 4),
            Text('${offer.area}  ·  ${offer.km} km', style: const TextStyle(color: ojaMuted)),
            const SizedBox(height: 4),
            Text('${naira(offer.price)} a ${offer.unit}  ·  Grade ${offer.grade}  ·  ${offer.rating}', style: const TextStyle(color: ojaInk)),
            const SizedBox(height: 6),
            Text(row.reason, style: const TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}

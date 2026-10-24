import 'package:flutter/material.dart';

import '../../core/catalog.dart';
import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';
import '../../core/widgets/oja_card.dart';
import 'stock_sheets.dart';

enum _InventoryFilter { all, low, grains, oil }

class InventoryPage extends StatefulWidget {
  const InventoryPage({
    super.key,
    required this.book,
    required this.onItem,
    this.onRefresh,
    this.onChanged,
  });

  final OjaBook book;
  final ValueChanged<String> onItem;
  final Future<void> Function()? onRefresh;

  /// Called after a stock change is saved, so Home and the rest of the app redraw.
  final VoidCallback? onChanged;

  @override
  State<InventoryPage> createState() => _InventoryPageState();
}

class _InventoryPageState extends State<InventoryPage> {
  final _search = TextEditingController();
  var _filter = _InventoryFilter.all;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<InventoryLine> get _lines {
    final query = _search.text.trim().toLowerCase();
    return [
      for (final line in widget.book.inventoryLines)
        if (_matchesFilter(line) && (query.isEmpty || line.name.toLowerCase().contains(query) || line.key.contains(query))) line,
    ];
  }

  bool _matchesFilter(InventoryLine line) {
    final low = line.isLow || widget.book.apiLowStock.contains(line.key);
    return switch (_filter) {
      _InventoryFilter.all => true,
      _InventoryFilter.low => low,
      _InventoryFilter.grains => inventoryCategoryFor(line.key) == 'grains',
      _InventoryFilter.oil => inventoryCategoryFor(line.key) == 'oil',
    };
  }

  @override
  Widget build(BuildContext context) {
    final book = widget.book;
    final lines = _lines;
    final lowCount = book.lowStockLines.length;
    final ranked = book.isLive ? book.marketOffers : rankOffers(book.marketItem);
    final notice = book.isLive ? (book.marketNotice ?? 'Market prices from API.') : 'Demo prices.';
    final lowLabel = lowCount == 1
        ? (book.lowStockLines.isNotEmpty ? book.lowStockLines.first.name : '1 item')
        : '$lowCount items';

    final body = ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
          decoration: BoxDecoration(
            color: ojaGreen,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.storefront, color: Colors.white, size: 20),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'LIVE STALL INVENTORY',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        fontSize: 13,
                        letterSpacing: 0.6,
                      ),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(book.market, style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: _StatCard(
                      label: 'Stock Value',
                      value: compactNaira(book.stockValueNgn),
                      detail: 'Estimated market',
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _StatCard(
                      label: 'Active Items',
                      value: '${book.activeItemCount}',
                      detail: 'Commodities',
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _StatCard(
                      label: 'Low Stock',
                      value: lowCount == 0 ? '0' : (lowCount == 1 ? '1 Item' : '$lowCount'),
                      detail: lowCount == 0 ? 'All good' : lowLabel,
                      alert: lowCount > 0,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _search,
                onChanged: (_) => setState(() {}),
                style: const TextStyle(color: ojaInk),
                decoration: InputDecoration(
                  hintText: 'Search grains, bags, oil…',
                  hintStyle: const TextStyle(color: ojaMuted),
                  prefixIcon: const Icon(Icons.search, color: ojaMuted),
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: ojaLine)),
                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: ojaLine)),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: const BorderSide(color: ojaGreen, width: 1.5),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
              key: const Key('add-commodity'),
              onPressed: () => book.isLive ? _addCommodity() : _showAddHint(context),
              style: FilledButton.styleFrom(
                backgroundColor: ojaGreen,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              ),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Commodity'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _FilterChip(
                label: 'All Items (${book.inventoryLines.length})',
                selected: _filter == _InventoryFilter.all,
                onTap: () => setState(() => _filter = _InventoryFilter.all),
              ),
              _FilterChip(
                label: 'Low Stock ($lowCount)',
                selected: _filter == _InventoryFilter.low,
                alert: lowCount > 0,
                onTap: () => setState(() => _filter = _InventoryFilter.low),
              ),
              _FilterChip(
                label: 'Grains',
                selected: _filter == _InventoryFilter.grains,
                onTap: () => setState(() => _filter = _InventoryFilter.grains),
              ),
              _FilterChip(
                label: 'Oil',
                selected: _filter == _InventoryFilter.oil,
                onTap: () => setState(() => _filter = _InventoryFilter.oil),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        if (lines.isEmpty)
          OjaCard(
            child: Text(
              book.inventoryLines.isEmpty
                  ? 'No stock on the books yet. Log a buy in Assistant (e.g. “I buy 5 bags rice 40k”).'
                  : 'No items match this filter.',
              style: const TextStyle(color: ojaMuted),
            ),
          )
        else
          for (final line in lines)
            _CommodityTile(
              line: line,
              selected: book.marketItem == line.key,
              low: line.isLow || book.apiLowStock.contains(line.key),
              onTap: () => widget.onItem(line.key),
              onStock: book.isLive && line.id != null ? () => _changeStock(line) : null,
            ),
        const SizedBox(height: 18),
        Text(
          'Where to buy ${itemTitle(book.marketItem)}',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ojaInk),
        ),
        const SizedBox(height: 4),
        Text(notice, style: const TextStyle(color: ojaMuted, fontSize: 13)),
        const SizedBox(height: 10),
        if (ranked.isEmpty)
          const Text('No market offers yet.', style: TextStyle(color: ojaMuted))
        else
          for (final row in ranked) _OfferTile(row: row, showDistance: !book.isLive),
      ],
    );

    if (widget.onRefresh == null) return body;
    return RefreshIndicator(color: ojaGreen, onRefresh: widget.onRefresh!, child: body);
  }

  Future<void> _addCommodity() async {
    final added = await showAddCommoditySheet(context, widget.book);
    if (!mounted || !added) return;
    _saved('Commodity added.');
  }

  Future<void> _changeStock(InventoryLine line) async {
    final saved = await showStockSheet(context, widget.book, line);
    if (!mounted || !saved) return;
    _saved('${line.name} updated.');
  }

  void _saved(String message) {
    widget.onChanged?.call();
    setState(() {});
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(backgroundColor: ojaGreen, content: Text(message)));
  }

  void _showAddHint(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        backgroundColor: ojaGreen,
        content: Text('Add stock in Assistant — say “I buy 5 bags rice 40k”.'),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.value,
    required this.detail,
    this.alert = false,
  });

  final String label;
  final String value;
  final String detail;
  final bool alert;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: alert ? const Color(0xFFC2410C) : Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(
            detail,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 11),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.alert = false,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final bool alert;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: selected ? ojaGreen : (alert ? const Color(0xFFFFE4D6) : Colors.white),
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: selected ? ojaGreen : ojaLine),
            ),
            child: Text(
              label,
              style: TextStyle(
                color: selected ? Colors.white : ojaInk,
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CommodityTile extends StatelessWidget {
  const _CommodityTile({
    required this.line,
    required this.selected,
    required this.low,
    required this.onTap,
    this.onStock,
  });

  final InventoryLine line;
  final bool selected;
  final bool low;
  final VoidCallback onTap;

  /// Opens the stock form (live only).
  final VoidCallback? onStock;

  @override
  Widget build(BuildContext context) {
    final unit = line.quantity == 1 ? line.unit : (line.unit.endsWith('s') ? line.unit : '${line.unit}s');
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
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(color: ojaGreenSoft, borderRadius: BorderRadius.circular(12)),
                  child: Icon(
                    inventoryCategoryFor(line.key) == 'oil' ? Icons.water_drop_outlined : Icons.inventory_2_outlined,
                    color: ojaGreen,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(line.name, style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
                      const SizedBox(height: 2),
                      Text(
                        '${formatQty(line.quantity)} $unit'
                        '${line.unitCostNgn > 0 ? '  ·  ${naira(line.unitCostNgn.round())} / ${line.unit}' : ''}',
                        style: const TextStyle(color: ojaMuted, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (line.valueNgn > 0)
                      Text(compactNaira(line.valueNgn), style: const TextStyle(fontWeight: FontWeight.w800, color: ojaInk)),
                    if (low) ...[
                      const SizedBox(height: 4),
                      const Text('Low', style: TextStyle(color: Color(0xFFC2410C), fontWeight: FontWeight.w700)),
                    ],
                  ],
                ),
                if (onStock != null) ...[
                  const SizedBox(width: 8),
                  OutlinedButton(
                    key: Key('stock-${line.key}'),
                    onPressed: onStock,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: ojaGreenDark,
                      side: const BorderSide(color: ojaLine),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('Stock', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _OfferTile extends StatelessWidget {
  const _OfferTile({required this.row, this.showDistance = true});

  final RankedOffer row;
  final bool showDistance;

  @override
  Widget build(BuildContext context) {
    final offer = row.offer;
    final place = showDistance && offer.km > 0 ? '${offer.area}  ·  ${offer.km} km' : offer.area;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: OjaCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(offer.supplier, style: const TextStyle(fontWeight: FontWeight.w700, color: ojaInk)),
            if (place.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(place, style: const TextStyle(color: ojaMuted)),
            ],
            const SizedBox(height: 4),
            Text(
              '${naira(offer.price)} a ${offer.unit}  ·  Grade ${offer.grade}'
              '${offer.rating > 0 ? '  ·  ${offer.rating}' : ''}',
              style: const TextStyle(color: ojaInk),
            ),
            const SizedBox(height: 6),
            Text(row.reason, style: const TextStyle(color: ojaGreen, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}

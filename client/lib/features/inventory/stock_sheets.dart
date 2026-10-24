import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api/oja_api.dart';
import '../../core/ledger/ledger.dart';
import '../../core/theme.dart';

/// Inventory screen actions (FR-C15): add a commodity, and record opening stock, a restock or an
/// adjustment, or edit an item's details. Every figure is saved by the server and then reloaded.

/// Opens the "Add commodity" form. Returns true when an item was added.
Future<bool> showAddCommoditySheet(BuildContext context, OjaBook book) async {
  final added = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: ojaPage,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => _AddCommodityForm(book: book),
  );
  return added ?? false;
}

/// Opens the stock form for one item. Returns true when something was saved.
Future<bool> showStockSheet(BuildContext context, OjaBook book, InventoryLine line) async {
  final saved = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: ojaPage,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => _StockForm(book: book, line: line),
  );
  return saved ?? false;
}

String _friendly(OjaApiException error) {
  return switch (error.code) {
    'item_exists' => 'You already have this commodity. Use its Stock button to add more.',
    'negative_stock' => 'Stock can\'t go below 0. Check the number.',
    _ => error.message,
  };
}

double? _number(String text) {
  final value = text.trim().replaceAll(',', '');
  return value.isEmpty ? null : double.tryParse(value);
}

InputDecoration _decoration(String label, {String? hint, String? suffix}) {
  OutlineInputBorder border(Color color, [double width = 1]) =>
      OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: color, width: width));
  return InputDecoration(
    labelText: label,
    hintText: hint,
    suffixText: suffix,
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    border: border(ojaLine),
    enabledBorder: border(ojaLine),
    focusedBorder: border(ojaGreen, 1.5),
  );
}

final _decimal = [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))];
final _signedDecimal = [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,\-]'))];

class _Sheet extends StatelessWidget {
  const _Sheet({required this.title, required this.subtitle, required this.children});

  final String title;
  final String subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(color: ojaLine, borderRadius: BorderRadius.circular(2)),
                ),
              ),
              const SizedBox(height: 14),
              Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: ojaInk)),
              const SizedBox(height: 4),
              Text(subtitle, style: const TextStyle(color: ojaMuted)),
              const SizedBox(height: 16),
              ...children,
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  const _ErrorBox(this.message);

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: const Color(0xFFFDEDE7), borderRadius: BorderRadius.circular(12)),
      child: Text(message, key: const Key('stock-error'), style: const TextStyle(color: ojaOut)),
    );
  }
}

class _SaveButton extends StatelessWidget {
  const _SaveButton({required this.label, required this.busy, required this.onPressed, this.buttonKey});

  final String label;
  final bool busy;
  final VoidCallback onPressed;
  final Key? buttonKey;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      key: buttonKey,
      onPressed: busy ? null : onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: ojaGreen,
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      child: busy
          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
          : Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
    );
  }
}

class _AddCommodityForm extends StatefulWidget {
  const _AddCommodityForm({required this.book});

  final OjaBook book;

  @override
  State<_AddCommodityForm> createState() => _AddCommodityFormState();
}

class _AddCommodityFormState extends State<_AddCommodityForm> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _unit = TextEditingController(text: 'bag');
  final _onHand = TextEditingController();
  final _unitCost = TextEditingController();
  final _reorderLevel = TextEditingController();
  var _busy = false;
  String? _error;

  @override
  void dispose() {
    for (final c in [_name, _unit, _onHand, _unitCost, _reorderLevel]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _error = null);
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await widget.book.addInventoryItem(
        name: _name.text.trim(),
        unit: _unit.text.trim(),
        unitCostNgn: _number(_unitCost.text),
        reorderLevel: _number(_reorderLevel.text),
        openingQuantity: _number(_onHand.text),
      );
      if (mounted) Navigator.of(context).pop(true);
    } on OjaApiException catch (error) {
      if (mounted) setState(() => _error = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String? _optionalNumber(String? value) {
    final text = (value ?? '').trim();
    if (text.isEmpty) return null;
    final n = _number(text);
    return n == null || n < 0 ? 'Enter a number (0 or more).' : null;
  }

  @override
  Widget build(BuildContext context) {
    return _Sheet(
      title: 'Add commodity',
      subtitle: 'Sales of it will take stock out; purchases will add stock.',
      children: [
        Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                key: const Key('add-name'),
                controller: _name,
                enabled: !_busy,
                textCapitalization: TextCapitalization.none,
                decoration: _decoration('Name', hint: 'e.g. yam, tomatoes, palm oil'),
                validator: (v) => (v ?? '').trim().isEmpty ? 'Enter a name.' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('add-unit'),
                controller: _unit,
                enabled: !_busy,
                decoration: _decoration('Unit', hint: 'bag, keg, basket, tuber…'),
                validator: (v) => (v ?? '').trim().isEmpty ? 'Enter a unit.' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('add-on-hand'),
                controller: _onHand,
                enabled: !_busy,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: _decimal,
                decoration: _decoration('How many do you have now?', hint: '0'),
                validator: _optionalNumber,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      key: const Key('add-unit-cost'),
                      controller: _unitCost,
                      enabled: !_busy,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: _decimal,
                      decoration: _decoration('Cost each (₦)', hint: 'optional'),
                      validator: _optionalNumber,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextFormField(
                      key: const Key('add-reorder-level'),
                      controller: _reorderLevel,
                      enabled: !_busy,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: _decimal,
                      decoration: _decoration('Warn me at', hint: 'optional'),
                      validator: _optionalNumber,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (_error != null) _ErrorBox(_error!),
        const SizedBox(height: 18),
        _SaveButton(label: 'Add commodity', busy: _busy, onPressed: _save, buttonKey: const Key('add-save')),
      ],
    );
  }
}

enum _StockAction { restock, opening, adjustment, details }

class _StockForm extends StatefulWidget {
  const _StockForm({required this.book, required this.line});

  final OjaBook book;
  final InventoryLine line;

  @override
  State<_StockForm> createState() => _StockFormState();
}

class _StockFormState extends State<_StockForm> {
  final _formKey = GlobalKey<FormState>();
  final _quantity = TextEditingController();
  late final _unitCost = TextEditingController(text: _plain(widget.line.unitCostNgn));
  late final _reorderLevel = TextEditingController(text: _plain(widget.line.reorderLevel));
  late final _reorderQuantity = TextEditingController(text: _plain(widget.line.reorderQuantity));
  var _action = _StockAction.restock;
  var _busy = false;
  String? _error;

  static String _plain(double value) => value == 0 ? '' : formatQty(value);

  @override
  void dispose() {
    for (final c in [_quantity, _unitCost, _reorderLevel, _reorderQuantity]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _error = null);
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    final id = widget.line.id!;
    try {
      if (_action == _StockAction.details) {
        await widget.book.editInventoryItem(id, {
          'unit_cost_ngn': _number(_unitCost.text),
          'reorder_level': _number(_reorderLevel.text) ?? 0,
          'reorder_quantity': _number(_reorderQuantity.text) ?? 0,
        });
      } else {
        await widget.book.changeStock(
          id,
          quantityChange: _number(_quantity.text)!,
          reason: switch (_action) {
            _StockAction.opening => 'opening',
            _StockAction.adjustment => 'adjustment',
            _ => 'restock',
          },
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } on OjaApiException catch (error) {
      if (mounted) setState(() => _error = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String? _validateQuantity(String? value) {
    final n = _number(value ?? '');
    if (n == null) return 'Enter a number.';
    if (_action == _StockAction.adjustment) return n == 0 ? 'Enter a number other than 0.' : null;
    return n <= 0 ? 'Enter a number above 0.' : null;
  }

  String? _optionalNumber(String? value) {
    final text = (value ?? '').trim();
    if (text.isEmpty) return null;
    final n = _number(text);
    return n == null || n < 0 ? 'Enter a number (0 or more).' : null;
  }

  @override
  Widget build(BuildContext context) {
    final line = widget.line;
    final units = line.unit.endsWith('s') ? line.unit : '${line.unit}s';
    final hint = switch (_action) {
      _StockAction.restock => 'How many $units did you add?',
      _StockAction.opening => 'How many $units did you start with?',
      _StockAction.adjustment => 'Use − to remove (e.g. -2 for spoilt or missing)',
      _StockAction.details => '',
    };
    return _Sheet(
      title: line.name,
      subtitle: 'In stock: ${formatQty(line.quantity)} ${line.quantity == 1 ? line.unit : units}',
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final (action, label) in [
              (_StockAction.restock, 'Restock +'),
              (_StockAction.opening, 'Opening stock'),
              (_StockAction.adjustment, 'Adjust ±'),
              (_StockAction.details, 'Edit details'),
            ])
              ChoiceChip(
                key: Key('stock-${action.name}'),
                label: Text(label),
                selected: _action == action,
                onSelected: _busy
                    ? null
                    : (_) => setState(() {
                          _action = action;
                          _error = null;
                        }),
                selectedColor: ojaGreen,
                labelStyle: TextStyle(color: _action == action ? Colors.white : ojaInk, fontWeight: FontWeight.w600),
                backgroundColor: Colors.white,
                side: BorderSide(color: _action == action ? ojaGreen : ojaLine),
                showCheckmark: false,
              ),
          ],
        ),
        const SizedBox(height: 16),
        Form(
          key: _formKey,
          child: _action == _StockAction.details
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextFormField(
                      key: const Key('stock-unit-cost'),
                      controller: _unitCost,
                      enabled: !_busy,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: _decimal,
                      decoration: _decoration('Cost each (₦)'),
                      validator: _optionalNumber,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      key: const Key('stock-reorder-level'),
                      controller: _reorderLevel,
                      enabled: !_busy,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: _decimal,
                      decoration: _decoration('Warn me when stock reaches', suffix: units),
                      validator: _optionalNumber,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      key: const Key('stock-reorder-quantity'),
                      controller: _reorderQuantity,
                      enabled: !_busy,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      inputFormatters: _decimal,
                      decoration: _decoration('Usually buy', suffix: units),
                      validator: _optionalNumber,
                    ),
                  ],
                )
              : TextFormField(
                  key: const Key('stock-quantity'),
                  controller: _quantity,
                  enabled: !_busy,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                  inputFormatters: _action == _StockAction.adjustment ? _signedDecimal : _decimal,
                  decoration: _decoration('Quantity', hint: hint, suffix: units),
                  validator: _validateQuantity,
                ),
        ),
        if (_error != null) _ErrorBox(_error!),
        const SizedBox(height: 18),
        _SaveButton(label: 'Save', busy: _busy, onPressed: _save, buttonKey: const Key('stock-save')),
      ],
    );
  }
}

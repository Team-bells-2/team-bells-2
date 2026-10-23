import '../api/oja_api.dart';
import '../catalog.dart';

class ChatLine {
  ChatLine(this.fromTrader, this.text);

  final bool fromTrader;
  final String text;
}

enum EntryKind { cashSale, creditSale, payment, expense }

class LedgerEntry {
  LedgerEntry({
    required this.id,
    required this.kind,
    required this.rawText,
    this.itemKey,
    this.itemLabel,
    this.quantity,
    this.unit,
    this.amountNgn,
    this.customer,
  });

  final int id;
  final EntryKind kind;
  String rawText;
  String? itemKey;
  String? itemLabel;
  double? quantity;
  String? unit;
  int? amountNgn;
  String? customer;
}

class Offer {
  const Offer({
    required this.item,
    required this.supplier,
    required this.area,
    required this.km,
    required this.price,
    required this.unit,
    required this.rating,
    required this.reviews,
    required this.grade,
    required this.available,
  });

  final String item;
  final String supplier;
  final String area;
  final double km;
  final int price;
  final String unit;
  final double rating;
  final int reviews;
  final String grade;
  final int available;
}

class RankedOffer {
  const RankedOffer(this.offer, this.reason);

  final Offer offer;
  final String reason;
}

class _Draft {
  EntryKind? kind;
  String? itemKey;
  String? itemLabel;
  double? quantity;
  String? unit;
  int? amountNgn;
  String? customer;
  String rawText = '';
}

const _aliases = <(String, String)>[
  ('the rice woman', 'Mama Ngozi'),
  ('rice woman', 'Mama Ngozi'),
  ('mama ngozi', 'Mama Ngozi'),
  ('ngozi', 'Mama Ngozi'),
  ('papa emeka', 'Papa Emeka'),
  ('emeka', 'Papa Emeka'),
  ('papa chidi', 'Papa Chidi'),
  ('chidi', 'Papa Chidi'),
];

const _items = <(String, String, String)>[
  ('groundnut oil', 'oil', 'Groundnut oil'),
  ('oil', 'oil', 'Groundnut oil'),
  ('garri', 'garri', 'Garri'),
  ('beans', 'beans', 'Beans'),
  ('rice', 'rice', 'Rice'),
];

const offers = <Offer>[
  Offer(
    item: 'rice',
    supplier: 'Alhaji Musa Grains',
    area: 'Mile 12 Depot',
    km: 0.8,
    price: 76500,
    unit: 'bag',
    rating: 4.8,
    reviews: 38,
    grade: 'A',
    available: 45,
  ),
  Offer(
    item: 'rice',
    supplier: 'Mama Chinyere',
    area: 'Oyingbo',
    km: 3.5,
    price: 75500,
    unit: 'bag',
    rating: 4.5,
    reviews: 17,
    grade: 'A',
    available: 8,
  ),
  Offer(
    item: 'rice',
    supplier: 'Balogun Brothers',
    area: 'Ketu',
    km: 2.1,
    price: 77000,
    unit: 'bag',
    rating: 4.2,
    reviews: 21,
    grade: 'B',
    available: 30,
  ),
  Offer(
    item: 'rice',
    supplier: 'Short Stock Shed',
    area: 'Mile 12',
    km: 0.4,
    price: 70000,
    unit: 'bag',
    rating: 4.9,
    reviews: 12,
    grade: 'A',
    available: 1,
  ),
  Offer(
    item: 'beans',
    supplier: 'Iya Wura Stores',
    area: 'Mile 12',
    km: 0.6,
    price: 95000,
    unit: 'bag',
    rating: 4.6,
    reviews: 19,
    grade: 'A',
    available: 20,
  ),
  Offer(
    item: 'beans',
    supplier: 'Ketu Beans Line',
    area: 'Ketu',
    km: 2.4,
    price: 92000,
    unit: 'bag',
    rating: 4.1,
    reviews: 11,
    grade: 'B',
    available: 16,
  ),
  Offer(
    item: 'beans',
    supplier: 'Oshodi Depot',
    area: 'Oshodi',
    km: 6.2,
    price: 89000,
    unit: 'bag',
    rating: 3.8,
    reviews: 9,
    grade: 'C',
    available: 40,
  ),
  Offer(
    item: 'garri',
    supplier: 'Ijebu Garri Shed',
    area: 'Mile 12',
    km: 1.1,
    price: 32000,
    unit: 'bag',
    rating: 4.7,
    reviews: 24,
    grade: 'A',
    available: 50,
  ),
  Offer(
    item: 'garri',
    supplier: 'White Sack Market',
    area: 'Ketu',
    km: 2.8,
    price: 30000,
    unit: 'bag',
    rating: 4.0,
    reviews: 8,
    grade: 'B',
    available: 18,
  ),
  Offer(
    item: 'garri',
    supplier: 'Farmside Garri',
    area: 'Ikorodu',
    km: 11,
    price: 28000,
    unit: 'bag',
    rating: 4.4,
    reviews: 14,
    grade: 'A',
    available: 2,
  ),
  Offer(
    item: 'oil',
    supplier: 'Kings Oil',
    area: 'Mile 12',
    km: 0.9,
    price: 45000,
    unit: 'keg',
    rating: 4.5,
    reviews: 16,
    grade: 'A',
    available: 22,
  ),
  Offer(
    item: 'oil',
    supplier: 'Yellow Jerry Can',
    area: 'Oshodi',
    km: 5.4,
    price: 43000,
    unit: 'keg',
    rating: 4.0,
    reviews: 7,
    grade: 'B',
    available: 12,
  ),
  Offer(
    item: 'oil',
    supplier: 'Lagos Keg Depot',
    area: 'Apapa',
    km: 14,
    price: 41000,
    unit: 'keg',
    rating: 3.6,
    reviews: 5,
    grade: 'C',
    available: 30,
  ),
];

const _wordNumbers = <String, int>{
  'one': 1,
  'two': 2,
  'three': 3,
  'four': 4,
  'five': 5,
  'six': 6,
  'seven': 7,
  'eight': 8,
  'nine': 9,
  'ten': 10,
  'twenty': 20,
  'thirty': 30,
  'forty': 40,
  'fifty': 50,
  'sixty': 60,
  'seventy': 70,
  'eighty': 80,
  'ninety': 90,
};

String naira(int amount) {
  final negative = amount < 0;
  final digits = amount.abs().toString();
  final buf = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buf.write(',');
    buf.write(digits[i]);
  }
  return '${negative ? '-' : ''}₦$buf';
}

String formatQty(double quantity) {
  if (quantity == quantity.roundToDouble()) return quantity.toInt().toString();
  return quantity.toString();
}

String itemTitle(String key) {
  for (final item in _items) {
    if (item.$2 == key) return item.$3;
  }
  return key;
}

List<RankedOffer> rankOffers(String item, {int needed = 5}) {
  final matching = offers.where((offer) => offer.item == item).toList();
  matching.sort((a, b) {
    final byScore = _score(b, needed).compareTo(_score(a, needed));
    if (byScore != 0) return byScore;
    return a.supplier.compareTo(b.supplier);
  });
  final top = matching.take(3).toList();
  return [for (final offer in top) RankedOffer(offer, _reason(offer, top, needed))];
}

double _score(Offer offer, int needed) {
  final canFill = offer.available >= needed ? 5.0 : 0.0;
  final distance = 2 / (1 + offer.km);
  final rating = (offer.rating / 5) * 2;
  final grade = switch (offer.grade) {
    'A' => 1.5,
    'B' => 0.9,
    _ => 0.3,
  };
  final price = 1000 / offer.price;
  return canFill + distance + rating + grade + price;
}

String _reason(Offer offer, List<Offer> peers, int needed) {
  if (offer.available < needed) {
    return 'Has ${offer.available} ${offer.unit}s. You need $needed.';
  }
  final closest = peers.every((peer) => offer.km <= peer.km);
  final cheapest = peers.every((peer) => offer.price <= peer.price);
  if (closest) return 'Closest to Mile 12.';
  if (offer.grade == 'A') return 'Grade A.';
  if (cheapest) return 'Lowest price of these.';
  return 'Rated ${offer.rating} from ${offer.reviews} reviews.';
}

class OjaBook {
  final lines = <ChatLine>[
    ChatLine(false, 'Tell me what you sold, who paid, or where you fit buy.'),
  ];
  final entries = <LedgerEntry>[];
  final stock = <String, double>{'rice': 10, 'beans': 8, 'garri': 14, 'oil': 6};

  String marketItem = 'rice';
  _Draft? _pending;
  int _nextId = 1;

  /// When set, home/assistant/inventory load from the live Render API.
  OjaApi? api;
  String conversationId = 'oja-flutter';
  String? statusMessage;
  bool busy = false;
  int? _apiSales;
  int? _apiExpenses;
  int? _apiProfit;
  int? _apiOwed;

  OjaBook();

  factory OjaBook.demo() {
    final book = OjaBook();
    book.stock['rice'] = 4.5;
    book.send('I sell 2.5 bags rice for Mama Ngozi 60k');
    book.send('The rice woman don pay 30k');
    book.send('I sell 1 bag garri cash for Papa Emeka 50k');
    book.send('I buy 5 bags beans 40k');
    return book;
  }

  factory OjaBook.live(OjaApi api) {
    final book = OjaBook();
    book.api = api;
    for (final item in stockItems) {
      book.stock[item] = 0;
    }
    return book;
  }

  bool get isLive => api != null;

  int get cashSales => _sum(EntryKind.cashSale);

  int get creditSales => _sum(EntryKind.creditSale);

  int get sales => _apiSales ?? (cashSales + creditSales);

  int _sum(EntryKind kind) => entries
      .where((entry) => entry.kind == kind)
      .fold(0, (sum, entry) => sum + (entry.amountNgn ?? 0));

  int get expenses => _apiExpenses ??
      entries.where((entry) => entry.kind == EntryKind.expense).fold(0, (sum, entry) => sum + (entry.amountNgn ?? 0));

  int get profit => _apiProfit ?? (sales - expenses);

  int get owed {
    if (_apiOwed != null) return _apiOwed!;
    var total = 0;
    for (final name in _customers()) {
      final balance = balanceOf(name);
      if (balance > 0) total += balance;
    }
    return total;
  }

  Future<void> refreshFromApi() async {
    final client = api;
    if (client == null) return;
    busy = true;
    statusMessage = null;
    try {
      final profit = await client.getProfit();
      final customers = await client.getCustomers();
      final remoteEntries = await client.getEntries();
      final inventory = await client.getInventory();

      _apiSales = (profit['sales_ngn'] as num?)?.toInt() ?? 0;
      _apiExpenses = (profit['expenses_ngn'] as num?)?.toInt() ?? 0;
      _apiProfit = (profit['estimated_profit_ngn'] as num?)?.toInt() ?? 0;
      _apiOwed = customers.fold<int>(0, (sum, row) => sum + ((row['amount_owed_ngn'] as num?)?.toInt() ?? 0));

      entries
        ..clear()
        ..addAll(remoteEntries.reversed.map(_entryFromApi));
      _nextId = entries.fold(1, (maxId, entry) => entry.id >= maxId ? entry.id + 1 : maxId);

      for (final item in stockItems) {
        stock[item] = 0;
      }
      for (final row in inventory) {
        final name = (row['item'] as String? ?? '').toLowerCase();
        if (name.isEmpty) continue;
        stock[name] = (row['quantity_on_hand'] as num?)?.toDouble() ?? 0;
      }
    } on OjaApiException catch (error) {
      statusMessage = error.message;
      rethrow;
    } finally {
      busy = false;
    }
  }

  /// Live API path for the assistant. Falls back to local rules when [api] is null.
  Future<void> sendAsync(String raw) async {
    final text = raw.trim();
    if (text.isEmpty) return;
    if (api == null) {
      send(text);
      return;
    }

    lines.add(ChatLine(true, text));
    final normalized = _norm(text);
    busy = true;
    statusMessage = null;
    try {
      if (_isWho(normalized)) {
        final result = await api!.ask(text);
        lines.add(ChatLine(false, (result['answer'] as String?)?.trim().isNotEmpty == true
            ? result['answer'] as String
            : 'Nobody owes you.'));
        await refreshFromApi();
        return;
      }
      if (_isWhere(normalized)) {
        lines.add(ChatLine(false, _where(text)));
        return;
      }

      final result = await api!.sendMessage(text: text, conversationId: conversationId);
      lines.add(ChatLine(false, _formatRemoteMessage(result)));
      await refreshFromApi();
    } on OjaApiException catch (error) {
      statusMessage = error.message;
      lines.add(ChatLine(false, error.message));
    } finally {
      busy = false;
    }
  }

  String _formatRemoteMessage(Map<String, dynamic> result) {
    final status = result['status'];
    if (status == 'needs_clarification') {
      return (result['question'] as String?)?.trim().isNotEmpty == true
          ? result['question'] as String
          : 'Tell me a bit more.';
    }
    if (status == 'corrected' || status == 'recorded') {
      final entry = result['entry'];
      if (entry is Map) {
        final mapped = _entryFromApi(Map<String, dynamic>.from(entry));
        return _confirm(mapped, updated: status == 'corrected');
      }
      final action = result['action'];
      if (action is Map) {
        final item = action['item'] ?? 'stock';
        final qty = action['quantity_on_hand'] ?? action['quantity'];
        return 'Saved. $item is now $qty.';
      }
    }
    return 'Saved.';
  }

  LedgerEntry _entryFromApi(Map<String, dynamic> row) {
    return LedgerEntry(
      id: (row['id'] as num?)?.toInt() ?? _nextId++,
      kind: _kindFromApi(row['type'] as String?),
      rawText: row['raw_text'] as String? ?? '',
      itemKey: (row['item'] as String?)?.toLowerCase(),
      itemLabel: row['item'] as String?,
      quantity: (row['quantity'] as num?)?.toDouble(),
      unit: row['unit'] as String?,
      amountNgn: (row['amount_ngn'] as num?)?.toInt(),
      customer: row['customer'] as String?,
    );
  }

  EntryKind _kindFromApi(String? type) {
    return switch (type) {
      'credit_sale' => EntryKind.creditSale,
      'payment_received' => EntryKind.payment,
      'expense' => EntryKind.expense,
      _ => EntryKind.cashSale,
    };
  }

  int balanceOf(String customer) {
    var balance = 0;
    for (final entry in entries) {
      if (entry.customer != customer) continue;
      if (entry.kind == EntryKind.creditSale) balance += entry.amountNgn ?? 0;
      if (entry.kind == EntryKind.payment) balance -= entry.amountNgn ?? 0;
    }
    return balance;
  }

  void send(String raw) {
    final text = raw.trim();
    if (text.isEmpty) return;
    lines.add(ChatLine(true, text));
    lines.add(ChatLine(false, _reply(text)));
  }

  String _reply(String raw) {
    final text = _norm(raw);
    if (_isWho(text)) return _whoOwes();
    if (_isWhere(text)) return _where(text);
    if (_pending != null && !_isNewCommand(text)) return _fillPending(text);
    if (_isCorrection(text)) return _correct(text);
    return _capture(text);
  }

  String _capture(String text) {
    final draft = _extract(text);
    if (draft.kind == null) {
      return 'I did not catch that. Tell me what you sold, who paid, or where you fit buy.';
    }
    final question = _missing(draft);
    if (question != null) {
      _pending = draft;
      return question;
    }
    return _save(draft);
  }

  String _fillPending(String text) {
    final pending = _pending!;
    final patch = _extract(text);
    pending.kind ??= patch.kind;
    pending.itemKey ??= patch.itemKey;
    pending.itemLabel ??= patch.itemLabel;
    pending.unit ??= patch.unit;
    pending.customer ??= patch.customer;
    if (patch.quantity != null) {
      pending.quantity = patch.quantity;
      pending.unit = patch.unit ?? pending.unit;
    }
    if (patch.amountNgn != null) pending.amountNgn = patch.amountNgn;
    pending.rawText = '${pending.rawText} $text'.trim();
    final question = _missing(pending);
    if (question != null) return question;
    _pending = null;
    return _save(pending);
  }

  String _correct(String text) {
    if (entries.isEmpty) return 'There is no entry to correct yet.';
    final last = entries.last;
    final patch = _extract(text);
    _applyStock(last, reverse: true);
    if (patch.quantity != null) {
      last.quantity = patch.quantity;
      last.unit = patch.unit ?? last.unit;
    }
    if (patch.amountNgn != null) last.amountNgn = patch.amountNgn;
    if (patch.itemKey != null) {
      last.itemKey = patch.itemKey;
      last.itemLabel = patch.itemLabel;
    }
    if (patch.customer != null) last.customer = patch.customer;
    last.rawText = text;
    _applyStock(last, reverse: false);
    return _confirm(last, updated: true);
  }

  String _save(_Draft draft) {
    final entry = LedgerEntry(
      id: _nextId++,
      kind: draft.kind ?? EntryKind.cashSale,
      rawText: draft.rawText,
      itemKey: draft.itemKey,
      itemLabel: draft.itemLabel,
      quantity: draft.quantity,
      unit: draft.unit,
      amountNgn: draft.amountNgn,
      customer: draft.customer,
    );
    entries.add(entry);
    _applyStock(entry, reverse: false);
    return _confirm(entry, updated: false);
  }

  void _applyStock(LedgerEntry entry, {required bool reverse}) {
    if (entry.itemKey == null || entry.quantity == null) return;
    final sign = reverse ? -1 : 1;
    final current = stock[entry.itemKey!] ?? 0;
    if (entry.kind == EntryKind.cashSale || entry.kind == EntryKind.creditSale) {
      stock[entry.itemKey!] = current - (sign * entry.quantity!);
    } else if (entry.kind == EntryKind.expense) {
      stock[entry.itemKey!] = current + (sign * entry.quantity!);
    }
  }

  String _whoOwes() {
    final names = _customers().where((name) => balanceOf(name) > 0).toList();
    if (names.isEmpty) return 'Nobody owes you.';
    return names.map((name) => '$name owes ${naira(balanceOf(name))}.').join('\n');
  }

  String _where(String text) {
    marketItem = _itemIn(text)?.$2 ?? marketItem;
    final ranked = rankOffers(marketItem);
    final body = ranked.map((row) {
      final offer = row.offer;
      return '${offer.supplier}, ${offer.km} km, ${naira(offer.price)} a ${offer.unit}, grade ${offer.grade}.';
    }).join('\n');
    return 'For ${itemTitle(marketItem)}:\n$body';
  }

  List<String> _customers() {
    final names = <String>[];
    for (final entry in entries) {
      final name = entry.customer;
      if (name != null && !names.contains(name)) names.add(name);
    }
    return names;
  }

  String? _missing(_Draft draft) {
    if (draft.amountNgn == null) {
      if (draft.quantity != null) {
        final unit = draft.unit ?? 'bags';
        return 'How much did you collect for the ${formatQty(draft.quantity!)} $unit?';
      }
      return 'How much was it?';
    }
    if (draft.kind == EntryKind.payment && draft.customer == null) return 'Who paid?';
    return null;
  }

  String _confirm(LedgerEntry entry, {required bool updated}) {
    final head = updated ? 'Updated' : 'Saved';
    final kind = switch (entry.kind) {
      EntryKind.cashSale => 'Cash sale',
      EntryKind.creditSale => 'Credit sale',
      EntryKind.payment => 'Payment',
      EntryKind.expense => 'Expense',
    };
    final buf = StringBuffer('$head. $kind');
    if (entry.quantity != null && entry.itemLabel != null) {
      buf.write(' of ${formatQty(entry.quantity!)} ${entry.unit} of ${entry.itemLabel}');
    } else if (entry.itemLabel != null) {
      buf.write(' of ${entry.itemLabel}');
    } else if (entry.quantity != null) {
      buf.write(' of ${formatQty(entry.quantity!)} ${entry.unit ?? ''}'.trimRight());
    }
    if (entry.customer != null) {
      buf.write(entry.kind == EntryKind.payment ? ' from ${entry.customer}' : ' for ${entry.customer}');
    }
    if (entry.amountNgn != null) buf.write(', ${naira(entry.amountNgn!)}');
    buf.write('.');
    return buf.toString();
  }
}

_Draft _extract(String raw) {
  final text = _norm(raw);
  final draft = _Draft()..rawText = text;
  draft.amountNgn = _amount(text);
  final quantity = _quantity(text);
  if (quantity != null) {
    draft.quantity = quantity.$1;
    draft.unit = quantity.$2;
  }
  final item = _itemIn(text);
  if (item != null) {
    draft.itemKey = item.$2;
    draft.itemLabel = item.$3;
  }
  draft.customer = _customer(text);
  draft.kind = _kind(text, draft.customer);
  return draft;
}

EntryKind? _kind(String text, String? customer) {
  if (RegExp(r'\b(don pay|paid|pay)\b').hasMatch(text)) return EntryKind.payment;
  if (RegExp(r'\b(buy|bought|spend|spent|transport)\b').hasMatch(text)) return EntryKind.expense;
  if (RegExp(r'\b(sell|sold)\b').hasMatch(text)) {
    if (text.contains('cash') || customer == null) return EntryKind.cashSale;
    return EntryKind.creditSale;
  }
  return null;
}

bool _isWho(String text) => text.contains('who owe') || text.contains('who dey owe');

bool _isWhere(String text) {
  return text.contains('where') && (text.contains('buy') || text.contains('restock') || text.contains('fit'));
}

bool _isCorrection(String text) {
  return text.startsWith('no') || text.contains('i mean') || text.contains('make am');
}

bool _isNewCommand(String text) {
  return RegExp(r'\b(sell|sold|pay|paid|don pay|buy|bought|spend|spent)\b').hasMatch(text);
}

String _norm(String value) => value.toLowerCase().replaceAll(RegExp(r'\s+'), ' ').trim();

int? _amount(String text) {
  final wordK = RegExp('(${_wordNumbers.keys.join('|')})\\s*k\\b').firstMatch(text);
  if (wordK != null) return _wordNumbers[wordK.group(1)]! * 1000;

  final numberK = RegExp(r'(\d+(?:\.\d+)?)\s*k\b').firstMatch(text);
  if (numberK != null) return (double.parse(numberK.group(1)!) * 1000).round();

  final symbol = RegExp(r'₦\s*(\d{1,3}(?:,\d{3})+|\d+)').firstMatch(text);
  if (symbol != null) return int.parse(symbol.group(1)!.replaceAll(',', ''));
  return null;
}

(double, String)? _quantity(String text) {
  const number = r'((?:one|two|three|four|five|six|seven|eight|nine|ten)|\d+(?:\.\d+)?)';
  const unit = r'(bags?|kegs?|tins?)';
  final halfAfter = RegExp('$number\\s+$unit\\s+and\\s+(?:a\\s+)?half').firstMatch(text);
  if (halfAfter != null) {
    final quantity = _number(halfAfter.group(1)!) + 0.5;
    return (quantity, _unit(halfAfter.group(2)!, quantity));
  }
  final halfBefore = RegExp('$number(?:\\s+and\\s+(?:a\\s+)?half)?\\s+$unit').firstMatch(text);
  if (halfBefore != null) {
    final extra = halfBefore.group(0)!.contains('half') ? 0.5 : 0.0;
    final quantity = _number(halfBefore.group(1)!) + extra;
    return (quantity, _unit(halfBefore.group(2)!, quantity));
  }
  return null;
}

double _number(String token) => double.tryParse(token) ?? (_wordNumbers[token] ?? 0).toDouble();

String _unit(String token, double quantity) {
  final one = quantity == 1;
  if (token.startsWith('keg')) return one ? 'keg' : 'kegs';
  if (token.startsWith('tin')) return one ? 'tin' : 'tins';
  return one ? 'bag' : 'bags';
}

(String, String, String)? _itemIn(String text) {
  for (final item in _items) {
    if (text.contains(item.$1)) return item;
  }
  return null;
}

String? _customer(String text) {
  for (final alias in _aliases) {
    if (text.contains(alias.$1)) return alias.$2;
  }
  return null;
}

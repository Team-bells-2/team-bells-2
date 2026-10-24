const stockItems = ['rice', 'beans', 'garri', 'oil'];

const reorderLevels = {'rice': 4.0, 'beans': 4.0, 'garri': 6.0, 'oil': 3.0};

const demoUnitCosts = {'rice': 76500.0, 'beans': 42000.0, 'garri': 28000.0, 'oil': 32000.0};

/// App stock keys → product names accepted by `POST /markets/recommend`.
const marketProductByItem = {
  'rice': 'foreign rice',
  'beans': 'white beans',
  'garri': 'white garri',
  'oil': 'vegetable oil',
};

/// Local filter groups for the inventory UI (API has no categories yet).
const inventoryCategories = <String, List<String>>{
  'grains': ['rice', 'beans', 'garri', 'maize', 'millet'],
  'oil': ['oil', 'palm oil', 'vegetable oil', 'groundnut oil'],
};

String inventoryCategoryFor(String key) {
  final lower = key.toLowerCase();
  for (final entry in inventoryCategories.entries) {
    if (entry.value.any((name) => lower.contains(name) || name.contains(lower))) {
      return entry.key;
    }
  }
  return 'other';
}

String compactNaira(int amount) {
  final negative = amount < 0;
  final value = amount.abs();
  final sign = negative ? '-' : '';
  if (value >= 1000000) {
    final m = value / 1000000;
    final text = m == m.roundToDouble() ? m.toInt().toString() : m.toStringAsFixed(1);
    return '$sign₦${text}m';
  }
  if (value >= 1000) {
    final k = value / 1000;
    final text = k == k.roundToDouble() ? k.toInt().toString() : k.toStringAsFixed(1);
    return '$sign₦${text}k';
  }
  return '$sign₦$value';
}

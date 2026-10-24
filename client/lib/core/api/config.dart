/// OJA API (`server/`) on Render. Override for a laptop on the same Wi-Fi:
/// `flutter run --dart-define=OJA_API_BASE_URL=http://192.168.x.x:8000`
const ojaApiBaseUrl = String.fromEnvironment(
  'OJA_API_BASE_URL',
  defaultValue: 'https://oja-eehu.onrender.com',
);

/// The server's seeded markets; signup must use one of these names.
const ojaMarkets = ['Mile 12', 'Oyingbo', 'Ketu', 'Agege', 'Mushin', 'Yaba', 'Oshodi', 'Ajah'];

/// Every new trader's main items. Sales of these take stock out and purchases restock them;
/// anything else is saved and flagged "not in inventory". Stock starts at 0 until a purchase is logged.
const ojaStartingItems = [
  {'name': 'rice', 'unit': 'bag', 'reorder_level': 4, 'reorder_quantity': 10},
  {'name': 'beans', 'unit': 'bag', 'reorder_level': 4, 'reorder_quantity': 10},
  {'name': 'garri', 'unit': 'bag', 'reorder_level': 6, 'reorder_quantity': 10},
  {'name': 'oil', 'unit': 'keg', 'reorder_level': 3, 'reorder_quantity': 10},
];

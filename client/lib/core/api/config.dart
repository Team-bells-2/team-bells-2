/// OJA API (`server/`) on Render. Override for a laptop on the same Wi-Fi:
/// `flutter run --dart-define=OJA_API_BASE_URL=http://192.168.x.x:8000`
const ojaApiBaseUrl = String.fromEnvironment(
  'OJA_API_BASE_URL',
  defaultValue: 'https://oja-eehu.onrender.com',
);

/// The trader this app signs in as (phone + PIN login). On first launch, when the phone
/// is not registered yet, the app onboards this trader with [ojaStartingItems].
/// Override with `--dart-define=OJA_TRADER_PHONE=... --dart-define=OJA_TRADER_PIN=...`.
const ojaTraderPhone = String.fromEnvironment('OJA_TRADER_PHONE', defaultValue: '08012345678');
const ojaTraderPin = String.fromEnvironment('OJA_TRADER_PIN', defaultValue: '1234');

const ojaTraderName = 'Iya Basira';
const ojaBusinessName = 'Iya Basira Foodstuffs';

/// One of the server's seeded markets (Mile 12, Oyingbo, Ketu, Agege, Mushin, Yaba, Oshodi, Ajah).
const ojaLocationName = 'Mile 12';

/// Main items created at onboarding. Sales of these take stock out and purchases restock them;
/// anything else is saved and flagged "not in inventory".
const ojaStartingItems = [
  {'name': 'rice', 'unit': 'bag', 'opening_quantity': 10, 'reorder_level': 4, 'reorder_quantity': 10},
  {'name': 'beans', 'unit': 'bag', 'opening_quantity': 8, 'reorder_level': 4, 'reorder_quantity': 10},
  {'name': 'garri', 'unit': 'bag', 'opening_quantity': 14, 'reorder_level': 6, 'reorder_quantity': 10},
  {'name': 'oil', 'unit': 'keg', 'opening_quantity': 6, 'reorder_level': 3, 'reorder_quantity': 10},
];

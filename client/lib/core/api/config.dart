/// Live MerchantPal / legacy prototype API on Render.
///
/// Note: this is `backend.py`, not the newer `server/` OJA contract.
const ojaApiBaseUrl = String.fromEnvironment(
  'OJA_API_BASE_URL',
  defaultValue: 'https://oja-eehu.onrender.com',
);

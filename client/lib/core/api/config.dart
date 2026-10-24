/// Live deployed API (Render): "OJA Prototype API" from `backend.py`.
///
/// Confirmed live routes include `/reports/profit`, `/insights`, `/markets`,
/// `/markets/recommend`, `/entries`, `/messages`, `/transcribe`, `/ask`, etc.
///
/// The newer `server/` app in this repo (FRONTEND_HANDOFF: `/home`, `/suggestions`,
/// onboarding auth) is a different contract and is not what this host serves today.
const ojaApiBaseUrl = String.fromEnvironment(
  'OJA_API_BASE_URL',
  defaultValue: 'https://oja-eehu.onrender.com',
);

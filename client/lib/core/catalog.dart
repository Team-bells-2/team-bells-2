const stockItems = ['rice', 'beans', 'garri', 'oil'];

const reorderLevels = {'rice': 4.0, 'beans': 4.0, 'garri': 6.0, 'oil': 3.0};

/// App stock keys → product names accepted by `POST /markets/recommend`.
const marketProductByItem = {
  'rice': 'foreign rice',
  'beans': 'white beans',
  'garri': 'white garri',
  'oil': 'vegetable oil',
};

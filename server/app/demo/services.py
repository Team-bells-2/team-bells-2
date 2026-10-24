from decimal import Decimal
from typing import Any

# SYNTHETIC DEMO DATA (FR-S29, D8). Names, prices, stock and reviews are invented for the demo;
# coordinates are approximate area centres in Lagos. Labelled "Demo data" by the API.

LOCATIONS: list[dict[str, Any]] = [
    {"name": "Mile 12", "latitude": 6.6050, "longitude": 3.3980},
    {"name": "Oyingbo", "latitude": 6.4880, "longitude": 3.3850},
    {"name": "Ketu", "latitude": 6.5960, "longitude": 3.3920},
    {"name": "Agege", "latitude": 6.6180, "longitude": 3.3260},
    {"name": "Mushin", "latitude": 6.5270, "longitude": 3.3500},
    {"name": "Yaba", "latitude": 6.5095, "longitude": 3.3711},
    {"name": "Oshodi", "latitude": 6.5550, "longitude": 3.3430},
    {"name": "Ajah", "latitude": 6.4698, "longitude": 3.5852},
]

# (item, unit, unit price, quantity available, quality grade) per supplier.
SUPPLIERS: list[dict[str, Any]] = [
    {
        "name": "Iya Bisi Foodstuff",
        "area": "Mile 12",
        "latitude": 6.6062,
        "longitude": 3.3967,
        "offers": [
            ("rice", "bag", "78000", "40", "A"),
            ("beans", "bag", "65000", "25", "B"),
            ("garri", "bag", "38000", "30", "B"),
            ("oil", "keg", "52000", "20", "A"),
        ],
        "reviews": [(5, "Rice was clean, no stones."), (4, "Fair price, slow loading."), (5, "Always has stock.")],
    },
    {
        "name": "Alhaji Musa Grains",
        "area": "Oyingbo",
        "latitude": 6.4871,
        "longitude": 3.3862,
        "offers": [
            ("rice", "bag", "74000", "60", "B"),
            ("beans", "bag", "62000", "50", "A"),
            ("garri", "bag", "36000", "15", "C"),
            ("oil", "keg", "50000", "10", "B"),
        ],
        "reviews": [(4, "Big stock of beans."), (3, "Rice had some chaff."), (4, "Honest weights.")],
    },
    {
        "name": "Mama Chioma Stores",
        "area": "Ketu",
        "latitude": 6.5948,
        "longitude": 3.3931,
        "offers": [
            ("rice", "bag", "80000", "12", "A"),
            ("beans", "bag", "68000", "8", "A"),
            ("garri", "bag", "40000", "40", "A"),
            ("oil", "keg", "55000", "30", "A"),
        ],
        "reviews": [(5, "Best garri around."), (5, "Very neat shop."), (4, "A bit pricey but quality.")],
    },
    {
        "name": "Oshodi Wholesale Hub",
        "area": "Oshodi",
        "latitude": 6.5561,
        "longitude": 3.3415,
        "offers": [
            ("rice", "bag", "72000", "100", "C"),
            ("beans", "bag", "60000", "70", "C"),
            ("garri", "bag", "34000", "80", "B"),
            ("oil", "keg", "48000", "60", "C"),
        ],
        "reviews": [(3, "Cheap but check quality."), (3, "Crowded, long wait."), (4, "Good for bulk.")],
    },
    {
        "name": "Agege Market Traders Union",
        "area": "Agege",
        "latitude": 6.6172,
        "longitude": 3.3274,
        "offers": [
            ("rice", "bag", "76000", "35", "B"),
            ("beans", "bag", "64000", "30", "B"),
            ("garri", "bag", "37000", "25", "A"),
            ("oil", "keg", "51000", "25", "B"),
        ],
        "reviews": [(4, "Reliable every week."), (4, "Garri dry and fresh."), (3, "Oil kegs sometimes short.")],
    },
    {
        "name": "Yaba Provisions Depot",
        "area": "Yaba",
        "latitude": 6.5101,
        "longitude": 3.3725,
        "offers": [
            ("rice", "bag", "79000", "20", "A"),
            ("beans", "bag", "66000", "20", "B"),
            ("garri", "bag", "39000", "18", "B"),
            ("oil", "keg", "53000", "15", "A"),
        ],
        "reviews": [(4, "Close to the road, easy pickup."), (5, "Polite staff."), (4, "Good oil.")],
    },
]


def as_decimal(value: str) -> Decimal:
    return Decimal(value)


# SYNTHETIC DEMO TRADER for POST /demo/seed (FR-C10, BR-D1). Garri starts below its reorder level so
# the restock card shows on Home (golden path step 7).
DEMO_TRADER: dict[str, str] = {
    "name": "Tolu Adeyemi",
    "phone": "08030000001",
    "business_name": "Tolu Foodstuff Store",
    "sector": "foodstuff",
    "location_name": "Mushin",
}
DEMO_PIN = "1234"
# (name, unit, unit cost, opening quantity, reorder level, reorder quantity)
DEMO_ITEMS: list[tuple[str, str, str, str, str, str]] = [
    ("rice", "bag", "58000", "10", "3", "10"),
    ("beans", "bag", "68000", "6", "2", "5"),
    ("garri", "bag", "25000", "2", "3", "8"),
    ("oil", "keg", "36000", "5", "2", "4"),
]
DEMO_CUSTOMERS: dict[str, list[str]] = {
    "Mama Ngozi": ["Ngozi", "the rice woman"],
    "Mr Bayo": ["Bayo", "Oga Bayo"],
    "Aunty Funke": ["Funke"],
    "Iya Sade": ["Sade", "the pepper seller"],
}

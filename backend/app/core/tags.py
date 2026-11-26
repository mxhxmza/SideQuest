"""Category dictionary: fixed category key -> OSM filters + name hints + default dwell (D3).

Parsers (rules or LLM) only ever emit a category key from this table; mapping to
OSM tags is deterministic code so an LLM cannot invent tags.
"""
from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass, field

ANY = "*"


@dataclass(frozen=True)
class CategoryDef:
    key: str
    label: str
    icon: str
    # Each filter is an AND of key -> allowed values; filters are OR'ed.
    filters: tuple[dict[str, tuple[str, ...]], ...]
    name_keywords: tuple[str, ...] = ()
    dwell_min: float = 15
    kind: str = "shop"  # meal | prayer | shop | service | leisure
    # Synonyms used by the rules parser (lower-case; multi-word allowed).
    synonyms: tuple[str, ...] = field(default=())


_MUSLIM_WORSHIP = {"amenity": ("place_of_worship",), "religion": ("muslim",)}

CATEGORIES: dict[str, CategoryDef] = {
    c.key: c
    for c in [
        CategoryDef(
            "meal", "Meal", "🍽",
            ({"amenity": ("restaurant", "fast_food", "food_court", "cafe")},),
            dwell_min=45, kind="meal",
            synonyms=("lunch", "dinner", "breakfast", "brunch", "supper", "meal", "food", "eat",
                      "makan", "restaurant", "bite", "something to eat", "grab food", "dine"),
        ),
        CategoryDef(
            "hawker", "Hawker centre / food court", "🥢",
            ({"amenity": ("food_court",)}, {"amenity": ("marketplace",)}),
            name_keywords=("hawker", "food centre", "food center", "kopitiam", "food court"),
            dwell_min=40, kind="meal",
            synonyms=("hawker", "hawker centre", "hawker center", "food court", "kopitiam", "food centre"),
        ),
        CategoryDef(
            "cafe", "Café / coffee", "☕",
            ({"amenity": ("cafe",)},),
            dwell_min=20, kind="meal",
            synonyms=("coffee", "cafe", "café", "kopi", "tea", "bubble tea"),
        ),
        CategoryDef(
            "ice_cream", "Ice cream / dessert", "🍨",
            ({"amenity": ("ice_cream",)}, {"shop": ("ice_cream",)},
             {"cuisine": ("ice_cream", "frozen_yogurt", "gelato", "dessert")}),
            name_keywords=("ice cream", "gelato", "gelateria", "froyo", "frozen yogurt", "creamery", "llaollao",
                           "swensen", "baskin", "udders", "sogurt", "dessert"),
            dwell_min=15, kind="meal",
            synonyms=("ice cream", "ice-cream", "icecream", "gelato", "dessert", "desserts", "frozen yogurt",
                      "froyo", "sundae", "soft serve", "something sweet", "cendol", "ice kacang", "sorbet"),
        ),
        CategoryDef(
            "mosque", "Mosque", "🕌",
            (_MUSLIM_WORSHIP,),
            name_keywords=("masjid", "mosque"),
            dwell_min=20, kind="prayer",
            synonyms=("mosque", "masjid", "jumaah", "jummah", "friday prayer"),
        ),
        CategoryDef(
            "prayer_room", "Prayer room / surau", "🕌",
            (_MUSLIM_WORSHIP,),
            name_keywords=("surau", "musolla", "musalla", "musollah", "prayer room"),
            dwell_min=20, kind="prayer",
            synonyms=("surau", "musolla", "musalla", "musollah", "prayer room", "prayer space",
                      "place to pray", "somewhere to pray", "pray", "solat", "salah", "salat", "prayer"),
        ),
        CategoryDef(
            "charger", "Phone charger / electronics", "🔌",
            ({"shop": ("electronics", "mobile_phone", "computer")},),
            name_keywords=("challenger", "best denki", "courts", "harvey norman", "gain city"),
            dwell_min=15,
            synonyms=("phone charger", "charger", "charging cable", "cable", "power bank", "powerbank",
                      "electronics", "phone accessories", "phone shop", "phone case", "screen protector", "adapter", "usb"),
        ),
        CategoryDef(
            "ev_charging", "EV charging", "⚡",
            ({"amenity": ("charging_station",)},),
            dwell_min=30, kind="service",
            synonyms=("ev charging", "ev charger", "charge my car", "car charging", "charging station"),
        ),
        CategoryDef(
            "atm", "ATM / bank", "🏧",
            ({"amenity": ("atm",)}, {"amenity": ("bank",)}),
            dwell_min=5, kind="service",
            synonyms=("atm", "cash", "withdraw", "money", "bank"),
        ),
        CategoryDef(
            "toilet", "Toilet", "🚻",
            ({"amenity": ("toilets",)},),
            dwell_min=5, kind="service",
            synonyms=("toilet", "restroom", "bathroom", "washroom", "loo", "wc"),
        ),
        CategoryDef(
            "petrol", "Petrol station", "⛽",
            ({"amenity": ("fuel",)},),
            dwell_min=10, kind="service",
            synonyms=("petrol", "fuel", "gas station", "petrol station", "refuel", "top up fuel", "pump"),
        ),
        CategoryDef(
            "pharmacy", "Pharmacy", "💊",
            ({"amenity": ("pharmacy",)}, {"shop": ("chemist",)}),
            name_keywords=("guardian", "watsons", "unity"),
            dwell_min=10,
            synonyms=("pharmacy", "chemist", "medicine", "panadol", "plasters", "guardian", "watsons"),
        ),
        CategoryDef(
            "supermarket", "Supermarket", "🛒",
            ({"shop": ("supermarket",)},),
            name_keywords=("fairprice", "cold storage", "sheng siong", "giant"),
            dwell_min=20,
            synonyms=("supermarket", "groceries", "grocery", "fairprice", "sheng siong", "cold storage"),
        ),
        CategoryDef(
            "convenience", "Convenience store", "🏪",
            ({"shop": ("convenience",)},),
            name_keywords=("7-eleven", "cheers"),
            dwell_min=5,
            synonyms=("convenience store", "7-eleven", "7 eleven", "seven eleven", "cheers", "snacks", "drinks", "water"),
        ),
        CategoryDef(
            "bakery", "Bakery", "🥐",
            ({"shop": ("bakery",)},),
            dwell_min=10, kind="meal",  # food: dietary constraints apply ("halal cake")
            synonyms=("bakery", "bread", "pastries", "cake", "cakes"),
        ),
        CategoryDef(
            "florist", "Florist", "💐",
            ({"shop": ("florist",)},),
            dwell_min=10,
            synonyms=("florist", "flowers", "bouquet"),
        ),
        CategoryDef(
            "bookshop", "Bookshop", "📚",
            ({"shop": ("books",)},),
            name_keywords=("popular", "kinokuniya"),
            dwell_min=20,
            synonyms=("bookshop", "bookstore", "books", "stationery"),
        ),
        CategoryDef(
            "clinic", "Clinic", "🩺",
            ({"amenity": ("clinic", "doctors")},),
            dwell_min=30, kind="service",
            synonyms=("clinic", "doctor", "gp", "polyclinic"),
        ),
        CategoryDef(
            "park", "Park", "🌳",
            ({"leisure": ("park",)},),
            dwell_min=30, kind="leisure",
            synonyms=("park", "stretch my legs", "walk in the park", "garden"),
        ),
        # Fallback for anything without a category: name search only (no invented tags, D3).
        # name_keywords come from the request itself (see normalize_stop).
        CategoryDef(
            "keyword", "Search by name", "🔎",
            (),
            dwell_min=15, kind="search",
        ),
        CategoryDef(
            "mall", "Shopping mall", "🛍",
            ({"shop": ("mall",)},),
            dwell_min=45, kind="leisure",
            synonyms=("mall", "shopping mall", "shopping centre", "shopping center", "shopping"),
        ),
        CategoryDef(
            "parking", "Parking", "🅿",
            ({"amenity": ("parking",)},),
            dwell_min=0, kind="service",
            synonyms=("parking", "car park", "carpark"),
        ),
    ]
}

CATEGORY_KEYS: tuple[str, ...] = tuple(CATEGORIES)

DIETARY_KEYS: tuple[str, ...] = ("halal", "vegetarian", "vegan")

# kinds where a dietary requirement makes sense
DIETARY_KINDS = ("meal", "search")

DIETARY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "halal": ("halal", "muslim-friendly", "muslim friendly", "no pork no lard", "no pork"),
    "vegetarian": ("vegetarian", "veggie", "meatless"),
    "vegan": ("vegan", "plant-based", "plant based"),
}

# Cuisine hints are *weak* evidence (D9).
HALAL_CUISINE_HINTS = ("malay", "indonesian", "middle_eastern", "turkish", "arab", "lebanese",
                       "pakistani", "persian", "afghan", "nasi_padang", "indian_muslim")
HALAL_NAME_HINTS = ("halal", "nasi padang", "nasi lemak", "prata", "briyani", "biryani", "murtabak",
                    "mee rebus", "ayam penyet", "kebab", "warung", "muslim")
# Chains widely known to hold MUIS certification in Singapore. Shown only as a
# weak "brand list" hint — the app never claims certification (DESIGN §9).
HALAL_BRAND_HINTS = ("mcdonald", "kfc", "burger king", "subway", "old chang kee", "ya kun",
                     "pizza hut", "mos burger", "long john silver", "popeyes", "4fingers",
                     "swensen", "the soup spoon", "encik tan", "jollibee", "texas chicken",
                     "a&w", "stuff'd", "nando")

NOT_PRAYER_HINTS = ("keramat", "makam", "tomb", "shrine", "cemetery", "kubur")

VEG_NAME_HINTS = ("vegetarian", "veggie", "vegan", "loving hut", "greendot", "su shi")


def get(key: str) -> CategoryDef:
    return CATEGORIES[key]


def default_dwell(key: str) -> float:
    c = CATEGORIES.get(key)
    return c.dwell_min if c else 15


def matches_filters(tags: dict[str, str], filters) -> bool:
    """True if `tags` satisfies any filter (each filter is an AND of key -> values)."""
    for f in filters:
        items = f.items() if isinstance(f, dict) else f.tags.items()
        ok = True
        for k, values in items:
            v = tags.get(k)
            if v is None:
                ok = False
                break
            if ANY in values:
                continue
            # OSM multi-values like "restaurant;cafe"
            if not any(part.strip() in values for part in v.split(";")):
                ok = False
                break
        if ok:
            return True
    return False


def matches_name(name: str | None, keywords) -> bool:
    """Whole-word, case-insensitive keyword match on a place name."""
    if not name or not keywords:
        return False
    return _kw_regex(tuple(keywords)).search(name.lower()) is not None


@lru_cache(maxsize=512)
def _kw_regex(keywords: tuple[str, ...]) -> re.Pattern:
    alt = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    return re.compile(r"(?<![a-z])(?:" + alt + r")(?![a-z])")


def name_match_allowed(cat: CategoryDef, tags: dict[str, str]) -> bool:
    """A name hint alone is only trusted for places of a plausible kind
    (e.g. 'Courts' must be a shop, not a 'Food Courts' sign)."""
    if cat.kind == "shop":
        return "shop" in tags
    if cat.kind == "prayer":
        return tags.get("religion") in (None, "muslim")
    return True

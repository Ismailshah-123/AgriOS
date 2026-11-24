"""Deterministic query understanding (works with the LLM disabled).

- language: 'ur' (Urdu script), 'ur-Latn' (Roman Urdu, marker words), else 'en'
- glossary: Urdu / Roman-Urdu agricultural terms -> English retrieval terms. A small, hand-made
  list: it widens recall for full-text search; it is NOT a translation of the question and
  does not guarantee terminology (the multilingual embedding / LLM rewrite do the rest).
- domain + crops: lexicon matching over the 10 knowledge domains (models.DOMAINS)
- farm intent: the user asks about THEIR records ("my field", "میرا کھیت")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

GLOSSARY: dict[str, str] = {
    # crops
    "ٹماٹر": "tomato",
    "tamatar": "tomato",
    "timatar": "tomato",
    "گندم": "wheat",
    "gandum": "wheat",
    "kanak": "wheat",
    "کپاس": "cotton",
    "kapas": "cotton",
    "phutti": "cotton",
    "چاول": "rice",
    "chawal": "rice",
    "dhan": "rice",
    "دھان": "rice",
    "مکئی": "maize",
    "makai": "maize",
    "makki": "maize",
    "گنا": "sugarcane",
    "ganna": "sugarcane",
    "آلو": "potato",
    "aloo": "potato",
    "پیاز": "onion",
    "pyaz": "onion",
    "مرچ": "chilli",
    "mirch": "chilli",
    # plant parts / symptoms
    "پتے": "leaves",
    "پتوں": "leaves",
    "patte": "leaves",
    "patay": "leaves",
    "pattay": "leaves",
    "پیلے": "yellow",
    "پیلا": "yellow",
    "peelay": "yellow",
    "peele": "yellow",
    "peela": "yellow",
    "دھبے": "spots",
    "دھبّے": "spots",
    "dhabbay": "spots",
    "dhabbe": "spots",
    "dhabe": "spots",
    "مرجھا": "wilting",
    "murjha": "wilting",
    "سڑ": "rot",
    "jhulsa": "blight",
    "جھلسا": "blight",
    "بیماری": "disease",
    "bimari": "disease",
    "beemari": "disease",
    "rog": "disease",
    "کیڑے": "pests insects",
    "keeray": "pests insects",
    "keere": "pests insects",
    "سنڈی": "caterpillar bollworm",
    "sundi": "caterpillar bollworm",
    # inputs, soil, water
    "کھاد": "fertilizer nutrient",
    "khad": "fertilizer nutrient",
    "khaad": "fertilizer nutrient",
    "یوریا": "urea nitrogen",
    "urea": "urea nitrogen",
    "مٹی": "soil",
    "mitti": "soil",
    "zameen": "soil land",
    "زمین": "soil land",
    "کلر": "salinity saline soil",
    "kallar": "salinity saline soil",
    "shor": "salinity",
    "پانی": "water",
    "pani": "water",
    "paani": "water",
    "آبپاشی": "irrigation",
    "abpashi": "irrigation",
    "aabpashi": "irrigation",
    "بارش": "rainfall",
    "barish": "rainfall",
    "گرمی": "heat",
    "garmi": "heat",
    "پیداوار": "yield production",
    "paidawar": "yield production",
    "fasal": "crop",
    "فصل": "crop",
    "بیج": "seed",
    "beej": "seed",
    "منافع": "profit",
    "munafa": "profit",
    "خرچ": "cost expense",
    "kharcha": "cost expense",
    "قیمت": "price",
    "qeemat": "price",
}
ROMAN_URDU_MARKERS = {
    "hai", "hain", "kya", "kyun", "kyon", "kaise", "kaisay", "mein", "mai", "ki", "ka", "ke",
    "ko", "se", "aur", "nahi", "mera", "meri", "mere", "hamara", "kab", "kitna", "kitni",
}  # fmt: skip

CROPS: dict[str, tuple[str, ...]] = {
    "tomato": ("tomato", "tomatoes", "ٹماٹر", "tamatar"),
    "wheat": ("wheat", "گندم", "gandum", "kanak"),
    "cotton": ("cotton", "کپاس", "kapas", "bollworm"),
    "rice": ("rice", "paddy", "چاول", "chawal", "دھان"),
    "maize": ("maize", "corn", "مکئی", "makai"),
    "sugarcane": ("sugarcane", "گنا", "ganna"),
    "potato": ("potato", "potatoes", "آلو", "aloo"),
}
DOMAIN_LEXICON: dict[str, tuple[str, ...]] = {
    "plant_protection": ("disease", "pest", "blight", "spot", "rust", "wilt", "virus", "fung",
                         "bacteri", "insect", "aphid", "mite", "whitefly", "ipm", "nematode",
                         "symptom", "leaf curl", "mold", "mould", "rot", "bollworm"),
    "nutrient_management": ("fertili", "nutrient", "nitrogen", "phosph", "potass", "npk",
                            "urea", "deficien", "micronutrient", "zinc", "manure", "compost"),
    "soil_science": ("soil", "ph ", "salinity", "saline", "sodic", "organic matter",
                     "texture", "electrical conductivity", "erosion", "gypsum"),
    "irrigation_water": ("irrigat", "water", "drip", "sprinkler", "flood", "et0", "etc",
                         "evapotranspiration", "kc", "crop coefficient", "drainage",
                         "moisture"),
    "weather_climate": ("weather", "rain", "temperature", "heat", "frost", "drought",
                        "climate", "humidity", "wind", "forecast"),
    "economics_business": ("profit", "cost", "price", "market", "revenue", "budget",
                           "break-even", "income", "loan", "insurance", "export", "business",
                           "per acre"),
    "crop_science": ("variety", "varieties", "sowing", "planting", "seed", "germination",
                     "growth stage", "yield", "harvest", "spacing", "rotation", "calendar"),
    "farm_operations": ("machinery", "tractor", "labour", "labor", "weed", "post-harvest",
                        "storage", "transport", "safety", "land preparation"),
    "livestock_allied": ("livestock", "dairy", "cattle", "buffalo", "poultry", "goat",
                         "sheep", "fish", "aquaculture", "beekeeping", "animal"),
    "research_policy": ("policy", "subsidy", "regulation", "standard", "organic certif",
                        "food safety", "research", "government"),
}  # fmt: skip
FARM_INTENT = re.compile(
    r"\b(my|our)\s+(farm|farms|field|fields|crop|crops|soil|cycle|cycles|expenses?|harvest|"
    r"season|records?|case|cases|irrigation|water)\b|\bmera\b|\bmeri\b|\bmere\b|\bhamara\b|"
    r"میرا|میری|میرے|ہمارا|ہمارے",
    re.IGNORECASE,
)
DOSE_INTENT = re.compile(
    r"\b(how much|how many|dose|dosage|rate|quantity|per acre|per hectare|kitna|kitni|"
    r"kitne|miqdar)\b|مقدار|کتنا|کتنی|کتنے",
    re.IGNORECASE,
)
INPUTS = re.compile(
    r"fungicide|pesticide|insecticide|herbicide|weedicide|fertili[sz]er|urea|dap|spray|"
    r"chemical|copper|khad|dawa|dawai|سپرے|کھاد|دوا|یوریا",
    re.IGNORECASE,
)
VET = re.compile(r"\b(cow|buffalo|goat|sheep|poultry|chicken|cattle|animal|calf)\b", re.I)


@dataclass
class QueryInfo:
    language: str
    retrieval_terms: str
    domains: list[str] = field(default_factory=list)
    crops: list[str] = field(default_factory=list)
    farm_intent: bool = False
    veterinary: bool = False
    dose_request: bool = False
    parts: int = 1


def detect_language(q: str) -> str:
    letters = [c for c in q if c.isalpha()]
    if letters and sum(1 for c in letters if "؀" <= c <= "ۿ") / len(letters) > 0.3:
        return "ur"
    words = set(re.findall(r"[a-z]+", q.lower()))
    return "ur-Latn" if len(words & ROMAN_URDU_MARKERS) >= 2 else "en"


def _tokens(q: str) -> list[str]:
    return re.findall(r"[\w؀-ۿ]+", q.lower())


def glossary_terms(q: str) -> list[str]:
    return [GLOSSARY[t] for t in _tokens(q) if t in GLOSSARY]


def analyse(q: str) -> QueryInfo:
    lang = detect_language(q)
    low = f" {q.lower()} "
    extra = glossary_terms(q)
    hay = low + " " + " ".join(extra)
    crops = [c for c, names in CROPS.items() if any(n in hay for n in names)]
    scored = []
    for dom, words in DOMAIN_LEXICON.items():
        hits = sum(1 for w in words if w in hay)
        if hits:
            scored.append((hits, dom))
    domains = [d for _, d in sorted(scored, key=lambda x: -x[0])]
    terms = q if lang == "en" else " ".join([q, *extra])
    parts = max(1, len([p for p in re.split(r"\?|\bوالا\b|؟", q) if len(p.split()) >= 3]))
    return QueryInfo(
        language=lang,
        retrieval_terms=terms,
        domains=domains,
        crops=crops,
        farm_intent=bool(FARM_INTENT.search(q)),
        veterinary=bool(VET.search(q)),
        dose_request=bool(DOSE_INTENT.search(q) and INPUTS.search(q)),
        parts=parts,
    )


def is_ambiguous(q: str, info: QueryInfo) -> bool:
    """Too little to retrieve on: very short, and no crop and no domain recognised."""
    content = [t for t in _tokens(q) if len(t) > 2]
    return len(content) < 2 and not info.crops and not info.domains

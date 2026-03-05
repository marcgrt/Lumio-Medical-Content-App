"""MedIntel configuration — sources, scoring weights, specialties."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "medintel.db"

# ---------------------------------------------------------------------------
# Journal tiers  (name‑fragment → score)
# ---------------------------------------------------------------------------
JOURNAL_TIERS: dict[str, int] = {
    # Tier 1 (90‑100)
    "new england journal of medicine": 100,
    "nejm": 100,
    "lancet": 95,
    "jama": 93,
    "bmj": 90,
    "nature medicine": 92,
    "nature": 91,
    # Tier 2 (70‑89)
    "annals of internal medicine": 85,
    "circulation": 82,
    "journal of clinical oncology": 80,
    "european heart journal": 78,
    "jco": 80,
    # Tier 3 (50‑69)
    "deutsches ärzteblatt": 65,
    "deutsches arzteblatt": 65,
    "aerzteblatt": 65,
    "gut": 68,
    "chest": 62,
    "blood": 66,
    "diabetes care": 64,
    "brain": 63,
    # Tier 4 — default peer‑reviewed: 40
    # Tier 5 — preprints
    "medrxiv": 25,
    "biorxiv": 25,
    # Tier 6 — news
    "google news": 10,
    "who disease outbreak": 15,
}

DEFAULT_JOURNAL_SCORE = 40  # peer‑reviewed fallback

# ---------------------------------------------------------------------------
# Study‑design keywords → score
# ---------------------------------------------------------------------------
STUDY_DESIGN_KEYWORDS: list[tuple[list[str], int]] = [
    (["meta-analysis", "meta analysis", "systematic review"], 100),
    (["randomized", "randomised", "rct", "randomized controlled"], 90),
    (["cohort study", "cohort"], 70),
    (["case-control", "case control"], 60),
    (["cross-sectional", "cross sectional", "prevalence study"], 50),
    (["case report", "case series"], 30),
    (["editorial", "opinion", "commentary", "letter to the editor"], 20),
    (["news", "press release"], 10),
]

DEFAULT_STUDY_DESIGN_SCORE = 40

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
WEIGHT_JOURNAL = 0.35
WEIGHT_STUDY_DESIGN = 0.30
WEIGHT_RECENCY = 0.20
WEIGHT_KEYWORD_BOOST = 0.15

# Keyword boost values
SAFETY_KEYWORDS = [
    "rückruf", "rote-hand-brief", "rote hand brief", "bfarm",
    "sicherheitswarnung", "contraindicated", "black box warning",
    "arzneimittelrückruf", "urgent safety",
]
GUIDELINE_KEYWORDS = [
    "leitlinie", "guideline", "s3-leitlinie", "s3 leitlinie",
    "nice guideline", "esc guideline", "awmf",
]
LANDMARK_KEYWORDS = [
    "breakthrough", "first-in-class", "first in class",
    "phase iii", "phase 3", "fda approval", "ema approval",
    "game changer", "paradigm shift",
]

SAFETY_BOOST = 20
GUIDELINE_BOOST = 15
LANDMARK_BOOST = 10

# ---------------------------------------------------------------------------
# Specialty → MeSH descriptor mapping
# ---------------------------------------------------------------------------
SPECIALTY_MESH: dict[str, list[str]] = {
    "Kardiologie": [
        "heart", "cardiac", "cardiovascular", "myocardial", "coronary",
        "atrial", "ventricular", "arrhythmia", "hypertension", "heart failure",
        "aortic", "stent", "angina",
    ],
    "Onkologie": [
        "cancer", "tumor", "tumour", "neoplasm", "oncolog", "carcinoma",
        "lymphoma", "leukemia", "melanoma", "metastas", "chemotherapy",
        "immunotherapy", "checkpoint inhibitor",
    ],
    "Neurologie": [
        "neurol", "brain", "stroke", "alzheimer", "parkinson", "epilepsy",
        "multiple sclerosis", "dementia", "migraine", "neuropathy",
        "cerebrovascular",
    ],
    "Diabetologie/Endokrinologie": [
        "diabet", "insulin", "glycem", "hba1c", "glp-1", "sglt2",
        "thyroid", "endocrin", "obesity", "metabolic syndrome",
    ],
    "Pneumologie": [
        "lung", "pulmonary", "respiratory", "copd", "asthma", "pneumonia",
        "bronch", "ventilat", "oxygen therapy", "fibrosis",
    ],
    "Gastroenterologie": [
        "gastro", "liver", "hepat", "bowel", "colon", "crohn",
        "colitis", "pancreat", "celiac", "cirrhosis", "ibd",
    ],
    "Infektiologie": [
        "infect", "antibiot", "antimicrobial", "sepsis", "hiv", "aids",
        "tuberculosis", "malaria", "hepatitis", "covid", "sars-cov",
        "influenza", "pathogen", "resistant",
    ],
    "Dermatologie": [
        "dermat", "skin", "psoriasis", "eczema", "atopic", "melanoma",
        "acne", "wound healing", "cutaneous",
    ],
    "Psychiatrie": [
        "psychiatr", "depression", "anxiety", "schizophreni", "bipolar",
        "psychosis", "antidepressant", "mental health", "ptsd", "adhd",
    ],
    "Allgemeinmedizin": [
        "primary care", "general practice", "family medicine",
        "screening", "prevention", "vaccination", "vaccine",
    ],
    "Orthopädie": [
        "orthop", "fracture", "joint", "arthroplasty", "spine",
        "osteoporosis", "musculoskeletal", "knee", "hip replacement",
    ],
    "Urologie": [
        "urolog", "prostate", "bladder", "kidney", "renal",
        "nephr", "dialysis", "transplant",
    ],
    "Pädiatrie": [
        "pediatr", "paediatr", "child", "neonat", "infant",
        "adolescent", "childhood",
    ],
}

# ---------------------------------------------------------------------------
# RSS feed sources
# ---------------------------------------------------------------------------
RSS_FEEDS: dict[str, str] = {
    "NEJM": "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "The Lancet": "https://www.thelancet.com/rssfeed/lancet_current.xml",
    "BMJ": "https://www.bmj.com/rss/recent.xml",
    "JAMA": "https://jamanetwork.com/rss/site_3/67.xml",
    "Deutsches Ärzteblatt": "https://www.aerzteblatt.de/rss/news.asp",
}

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=Medizin+Studie+Arzt&hl=de&gl=DE&ceid=DE:de"
)

# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_PAGE_SIZE = 100

# ---------------------------------------------------------------------------
# medRxiv / bioRxiv
# ---------------------------------------------------------------------------
MEDRXIV_API_BASE = "https://api.medrxiv.org/details/medrxiv"
BIORXIV_API_BASE = "https://api.medrxiv.org/details/biorxiv"

# ---------------------------------------------------------------------------
# WHO Disease Outbreak News
# ---------------------------------------------------------------------------
WHO_DON_API = "https://www.who.int/api/news/diseaseoutbreaknews"

# ---------------------------------------------------------------------------
# Deduplication thresholds
# ---------------------------------------------------------------------------
DEDUP_TITLE_LEVENSHTEIN_THRESHOLD = 5
DEDUP_COSINE_THRESHOLD = 0.92

# ---------------------------------------------------------------------------
# Alert keywords  (→ status = "ALERT")
# ---------------------------------------------------------------------------
ALERT_KEYWORDS = [
    "rückruf", "rote-hand-brief", "rote hand brief", "bfarm",
    "sicherheitswarnung", "contraindicated", "black box warning",
]

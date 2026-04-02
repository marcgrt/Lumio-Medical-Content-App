"""Lumio configuration — sources, scoring weights, specialties."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "lumio.db"

# ---------------------------------------------------------------------------
# Pipeline settings (automated, not user-facing)
# ---------------------------------------------------------------------------
PIPELINE_DAYS_BACK = 1        # How many days to look back per run
PIPELINE_INTERVAL_HOURS = 6   # Auto-run interval (used by cron/scheduler)

# ---------------------------------------------------------------------------
# Journal tiers  (name‑fragment → score)
# ---------------------------------------------------------------------------
JOURNAL_TIERS: dict[str, int] = {
    # Tier 1 — Global flagship (90‑100)
    "new england journal of medicine": 100,
    "nejm": 100,
    "lancet": 95,
    "jama": 93,
    "bmj": 90,
    "nature medicine": 92,
    "nature": 91,
    # Tier 2 — Leading specialty (78‑89)
    "annals of internal medicine": 85,
    "circulation": 82,
    "journal of clinical oncology": 80,
    "european heart journal": 78,
    "jco": 80,
    # Tier 2b — Leading German clinical sources (75‑79)
    # For our target audience (German physicians), these are the
    # authoritative clinical voice. Peer‑reviewed, editorially curated.
    "deutsches ärzteblatt": 78,
    "deutsches arzteblatt": 78,
    "aerzteblatt": 78,
    # Tier 3 — Strong specialty journals (62‑74)
    "gut": 68,
    "blood": 66,
    "diabetes care": 64,
    "brain": 63,
    "chest": 62,
    # Tier 3b — German medical press (55‑64)
    "ärzte zeitung": 62,
    "aerztezeitung": 62,
    "pharmazeutische zeitung": 60,
    "apotheke adhoc": 55,
    # Tier 3c — Arztgerecht aufbereitete Quellen (55‑68)
    "arznei-telegramm": 68,  # Hohes Vertrauen trotz kleiner Reichweite
    "medscape deutschland": 58,
    "medscape de": 58,
    "medscape": 58,
    "medical tribune": 55,
    # Tier 3d — Berufspolitik & Behörden (50‑70)
    "g-ba": 70,   # Regulierungsbehörde mit direkter Bindungswirkung
    "iqwig": 65,   # Wissenschaftliche Bewertungsinstanz
    "kbv": 58,     # Offizielle Quelle, aber keine Primärforschung
    "marburger bund": 55,
    # Tier 3e — Fachgesellschaften (55‑60)
    "dgim": 58,
    "dgk": 58,
    "degam": 58,
    # Tier 4 — default peer‑reviewed: 40
    # Tier 5 — preprints
    "medrxiv": 30,
    "biorxiv": 30,
    # Tier 6 — aggregated news
    "google news": 40,
    "who disease outbreak": 50,
}

DEFAULT_JOURNAL_SCORE = 40  # peer‑reviewed fallback

# ---------------------------------------------------------------------------
# Study‑design keywords → score  (first match wins — order matters!)
# ---------------------------------------------------------------------------
STUDY_DESIGN_KEYWORDS: list[tuple[list[str], int]] = [
    # Tier S: Synthesised evidence
    (["meta-analysis", "meta analysis", "systematic review"], 100),
    # Tier A: Primary experimental evidence
    (["randomized", "randomised", "rct", "randomized controlled"], 90),
    # Tier A‑: Clinical guidelines
    (["leitlinie", "guideline", "s3-leitlinie", "s3 leitlinie",
      "s2k-leitlinie", "s2e-leitlinie", "s1-leitlinie",
      "nice guideline", "esc guideline", "awmf",
      "practice guideline", "clinical practice guideline",
      "behandlungsempfehlung", "therapieempfehlung",
      "handlungsempfehlung"], 85),
    # Tier B+: Clinical reviews / Fachartikel
    (["clinical review", "klinische übersicht", "klinischer überblick",
      "narrative review", "state of the art", "state-of-the-art",
      "current concepts", "clinical update", "therapieübersicht",
      "übersichtsarbeit", "fachartikel", "fortbildung",
      "current treatment", "management of", "behandlung von",
      "therapie des", "therapie der", "therapie bei",
      "diagnosis and treatment", "diagnostik und therapie",
      "update on", "advances in", "aktuelle therapie",
      "praxisempfehlung"], 75),
    # Tier B: Observational evidence
    (["cohort study", "cohort"], 70),
    # Tier B‑: Other controlled designs
    (["case-control", "case control"], 60),
    # Tier C+: Descriptive / survey
    (["cross-sectional", "cross sectional", "prevalence study"], 55),
    # Tier C: Expert analysis with substance (peer‑reviewed editorials)
    (["editorial", "perspective", "viewpoint", "expert review",
      "kommentar", "standpunkt", "experteninterview"], 50),
    # Tier C‑: Case‑level evidence
    (["case report", "case series"], 40),
    # Tier D+: News reporting
    (["news", "press release", "nachricht", "meldung"], 35),
    # Tier D: Pure opinion / letters
    (["opinion", "letter to the editor", "correspondence",
      "leserbrief"], 30),
]

DEFAULT_STUDY_DESIGN_SCORE = 45  # benefit of the doubt

# ---------------------------------------------------------------------------
# Scoring weights  (sum = 1.0)
# ---------------------------------------------------------------------------
WEIGHT_JOURNAL = 0.30
WEIGHT_STUDY_DESIGN = 0.25
WEIGHT_RECENCY = 0.20
WEIGHT_KEYWORD_BOOST = 0.15
WEIGHT_ARZTRELEVANZ = 0.10

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
# Arztrelevanz — rewards content relevant to practicing physicians
# (highest match wins, scaled to 0‑100 in scorer)
# ---------------------------------------------------------------------------
ARZTRELEVANZ_KEYWORDS: list[tuple[list[str], int]] = [
    # Therapy / treatment focus (strongest signal → 100)
    (["therapie", "therapy", "treatment", "behandlung",
      "medikament", "medication", "drug", "dosierung", "dosing",
      "verschreibung", "prescription", "first-line", "second-line",
      "therapieoptionen", "treatment options"], 15),
    # Diagnostics / screening (→ 80)
    (["diagnose", "diagnosis", "diagnostik", "screening",
      "differentialdiagnose", "differential diagnosis",
      "früherkennung", "early detection"], 12),
    # Health policy / professional politics (→ 80)
    (["krankenhausreform", "gesundheitspolitik", "ärztemangel",
      "honorar", "vergütung", "kbv", "kassenärztlich", "gkv", "pkv",
      "budgetierung", "berufspolitik", "approbation", "weiterbildung",
      "versorgungsstruktur", "notfallreform", "klinikreform",
      "gesundheitsminister", "bundesgesundheitsministerium",
      "health policy", "physician shortage"], 12),
    # Practice / digital / legal (→ 67)
    (["praxis", "klinischer alltag", "clinical practice",
      "patientenversorgung", "patient care", "patient management",
      "nachsorge", "follow-up", "monitoring",
      "digitalisierung", "telematik", "epa", "elektronische patientenakte",
      "medizinrecht", "haftung", "aufklärungspflicht", "datenschutz",
      "ethik", "sterbehilfe", "organspende"], 10),
]

# ---------------------------------------------------------------------------
# Redaktions‑Bonus — editorial curation bonus for physician‑focused sources
# (journal name‑fragment → flat bonus points added to final score)
# ---------------------------------------------------------------------------
REDAKTIONS_BONUS: dict[str, int] = {
    "ärzteblatt": 8,
    "aerzteblatt": 8,
    "ärzte zeitung": 6,
    "aerztezeitung": 6,
    "pharmazeutische zeitung": 5,
    "apotheke adhoc": 3,
    "arznei-telegramm": 7,
    "medscape": 5,
    "medical tribune": 4,
    "kbv": 5,
    "marburger bund": 4,
    "g-ba": 6,
    "iqwig": 5,
}

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
        "transplant", "urinary",
    ],
    "Pädiatrie": [
        "pediatr", "paediatr", "child", "neonat", "infant",
        "adolescent", "childhood",
    ],
    "Gynäkologie": [
        "gynecol", "gynaecol", "obstetric", "pregnan", "maternal",
        "endometri", "ovarian", "cervical", "breast cancer", "menopaus",
        "contracepti", "fertility", "ivf",
    ],
    "Rheumatologie": [
        "rheumat", "arthritis", "lupus", "vasculitis", "gout",
        "spondylitis", "autoimmune", "biologics", "jak inhibitor",
    ],
    "Chirurgie": [
        "surgery", "surgical", "surgeon", "laparoscop", "minimally invasive",
        "resection", "transplant", "operative", "perioperative",
    ],
    "Nephrologie": [
        "nephr", "kidney", "renal", "dialysis", "glomerulo",
        "chronic kidney", "ckd", "hemodialysis", "peritoneal",
    ],
    "Anästhesiologie": [
        "anesthes", "anaesthes", "analgesi", "sedation", "pain management",
        "regional anesthesia", "perioperative", "airway",
    ],
    "Intensivmedizin": [
        "intensive care", "critical care", "icu", "mechanical ventilat",
        "sepsis", "ards", "resuscitation", "vasopressor", "ecmo",
    ],
    "HNO": [
        "otolaryngol", "otorhinolaryngol", "ear nose throat",
        "hearing loss", "cochlear", "tinnitus", "sinusitis",
        "laryngeal", "tonsil", "head and neck",
    ],
    "Augenheilkunde": [
        "ophthalmol", "retinal", "glaucoma", "cataract", "macular",
        "ocular", "corneal", "intraocular", "anti-vegf", "vision loss",
    ],
    "Geriatrie": [
        "geriatr", "elderly", "aging", "ageing", "frailty",
        "polypharmacy", "fall prevention", "sarcopenia", "dementia care",
    ],
    "Notfallmedizin": [
        "emergency medicine", "emergency department", "trauma",
        "resuscitation", "triage", "acute care", "polytrauma",
    ],
    "Radiologie": [
        "radiolog", "imaging", "ct scan", "mri", "mammograph",
        "ultrasound", "x-ray", "interventional radiology", "pet scan",
    ],
    "Palliativmedizin": [
        "palliative", "end of life", "hospice", "terminal care",
        "symptom management", "advance directive",
    ],
    "Allergologie": [
        "allerg", "anaphylax", "immunoglobulin e", "ige",
        "desensitization", "food allergy", "hay fever", "urticaria",
    ],
}

# ---------------------------------------------------------------------------
# Feed configuration — unified registry for all sources
# ---------------------------------------------------------------------------

@dataclass
class FeedConfig:
    """Configuration for a single feed source."""
    name: str
    url: str
    feed_type: str = "rss"  # rss | api | scrape
    source_category: str = ""
    language: str = "en"
    active: bool = True
    # Rollout wave: 1 = sofort, 2 = nach 2-3 Tagen, 3 = nach 1 Woche
    wave: int = 1


# --- RSS feed sources (journals + German medical press) ---

RSS_FEEDS: dict[str, str] = {
    # International — Top Journals
    "NEJM": "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "The Lancet": "https://www.thelancet.com/rssfeed/lancet_current.xml",
    "BMJ": "https://www.bmj.com/rss/recent.xml",
    "JAMA": "https://jamanetwork.com/rss/site_3/67.xml",
    # Specialty Journals (neu)
    "European Heart Journal": "https://academic.oup.com/rss/site_5375/3236.xml",
    "Lancet Oncology": "https://www.thelancet.com/rssfeed/lanonc_current.xml",
    "JCO": "https://ascopubs.org/action/showFeed?type=etoc&feed=rss&jc=jco",
    "Diabetes Care": "https://diabetesjournals.org/rss/site_1000003/1000004.xml",
    # Deutsche Fachquellen
    "Deutsches Ärzteblatt": "https://www.aerzteblatt.de/rss/news.asp",
    "Ärzte Zeitung": "https://www.aerztezeitung.de/News.rss",
    "Ärzte Zeitung Medizin": "https://www.aerztezeitung.de/medizin.rss",
    "Pharmazeutische Zeitung": "https://www.pharmazeutische-zeitung.de/fileadmin/rss/pz_online_rss.php",
    "Apotheke Adhoc": "https://www.apotheke-adhoc.de/nachrichten/rss.xml",
}

# Multiple Google News queries for broader German coverage
GOOGLE_NEWS_RSS_FEEDS: dict[str, str] = {
    "Google News (Medizin)": (
        "https://news.google.com/rss/search?"
        "q=Medizin+Studie+Arzt&hl=de&gl=DE&ceid=DE:de"
    ),
    "Google News (Leitlinie)": (
        "https://news.google.com/rss/search?"
        "q=Leitlinie+Therapie+klinische+Studie&hl=de&gl=DE&ceid=DE:de"
    ),
    "Google News (Arzneimittel)": (
        "https://news.google.com/rss/search?"
        "q=Arzneimittel+Zulassung+BfArM&hl=de&gl=DE&ceid=DE:de"
    ),
}

# --- Full feed registry with metadata ---
# This is the authoritative list of all feeds. Ingestion modules
# use RSS_FEEDS / GOOGLE_NEWS_RSS_FEEDS for backward-compat,
# but the registry adds source_category and active flags.

FEED_REGISTRY: dict[str, FeedConfig] = {
    # Top Journals
    "NEJM": FeedConfig("NEJM", RSS_FEEDS["NEJM"], source_category="top_journal"),
    "The Lancet": FeedConfig("The Lancet", RSS_FEEDS["The Lancet"], source_category="top_journal"),
    "BMJ": FeedConfig("BMJ", RSS_FEEDS["BMJ"], source_category="top_journal"),
    "JAMA": FeedConfig("JAMA", RSS_FEEDS["JAMA"], source_category="top_journal"),
    # Specialty Journals (neu, Welle 1)
    "European Heart Journal": FeedConfig("European Heart Journal", RSS_FEEDS["European Heart Journal"], source_category="specialty_journal"),
    "Lancet Oncology": FeedConfig("Lancet Oncology", RSS_FEEDS["Lancet Oncology"], source_category="specialty_journal"),
    "JCO": FeedConfig("JCO", RSS_FEEDS["JCO"], source_category="specialty_journal"),
    "Diabetes Care": FeedConfig("Diabetes Care", RSS_FEEDS["Diabetes Care"], source_category="specialty_journal"),
    # Deutsche Fachpresse
    "Deutsches Ärzteblatt": FeedConfig("Deutsches Ärzteblatt", RSS_FEEDS["Deutsches Ärzteblatt"], source_category="fachpresse_de", language="de"),
    "Ärzte Zeitung": FeedConfig("Ärzte Zeitung", RSS_FEEDS["Ärzte Zeitung"], source_category="fachpresse_de", language="de"),
    "Ärzte Zeitung Medizin": FeedConfig("Ärzte Zeitung Medizin", RSS_FEEDS["Ärzte Zeitung Medizin"], source_category="fachpresse_de", language="de"),
    "Pharmazeutische Zeitung": FeedConfig("Pharmazeutische Zeitung", RSS_FEEDS["Pharmazeutische Zeitung"], source_category="fachpresse_de", language="de"),
    "Apotheke Adhoc": FeedConfig("Apotheke Adhoc", RSS_FEEDS["Apotheke Adhoc"], source_category="fachpresse_de", language="de"),
    # Aufbereitete Quellen
    "Medical Tribune": FeedConfig("Medical Tribune", "https://www.medical-tribune.de/medizin-und-forschung", feed_type="scrape", source_category="fachpresse_aufbereitet", language="de"),
    # Google News
    "Google News (Medizin)": FeedConfig("Google News (Medizin)", GOOGLE_NEWS_RSS_FEEDS["Google News (Medizin)"], source_category="news_aggregation", language="de"),
    "Google News (Leitlinie)": FeedConfig("Google News (Leitlinie)", GOOGLE_NEWS_RSS_FEEDS["Google News (Leitlinie)"], source_category="news_aggregation", language="de"),
    "Google News (Arzneimittel)": FeedConfig("Google News (Arzneimittel)", GOOGLE_NEWS_RSS_FEEDS["Google News (Arzneimittel)"], source_category="news_aggregation", language="de"),
    # API sources (URLs hardcoded to avoid forward-reference to constants below)
    "Europe PMC": FeedConfig("Europe PMC", "https://www.ebi.ac.uk/europepmc/webservices/rest/search", feed_type="api", source_category="literaturdatenbank"),
    "medRxiv": FeedConfig("medRxiv", "https://api.medrxiv.org/details/medrxiv", feed_type="api", source_category="preprint"),
    # Deaktiviert in v2: Biologie-Preprints ohne klinischen Bezug produzieren konsistent Scores <35 im neuen Scoring-Modell
    "bioRxiv": FeedConfig("bioRxiv", "https://api.medrxiv.org/details/biorxiv", feed_type="api", source_category="preprint", active=False),
    "WHO DON": FeedConfig("WHO DON", "https://www.who.int/api/news/diseaseoutbreaknews", feed_type="api", source_category="behoerde"),
    # Scrape/RSS sources with own modules
    "BfArM": FeedConfig("BfArM", "https://www.bfarm.de/SiteGlobals/Functions/RSSFeed/DE/Pharmakovigilanz/Rote-Hand-Briefe/RSSNewsfeed.xml", source_category="behoerde", language="de"),
    "EMA": FeedConfig("EMA", "https://www.ema.europa.eu/en/news.xml", source_category="behoerde"),
    "Cochrane": FeedConfig("Cochrane", "https://www.cochranelibrary.com/cdsr/table-of-contents/rss.xml", source_category="literaturdatenbank"),
    "AWMF": FeedConfig("AWMF", "https://www.awmf.org/leitlinien/aktuelle-leitlinien", feed_type="scrape", source_category="behoerde", language="de"),
    "RKI": FeedConfig("RKI", "https://www.rki.de/SiteGlobals/Functions/RSS/RSS-EpidBull.xml", source_category="behoerde", language="de"),
    # Berufspolitik & Behörden (korrigierte URLs, verifiziert 2026-03-21)
    "G-BA": FeedConfig("G-BA", "https://www.g-ba.de/beschluesse/letzte-aenderungen/?rss=1", source_category="behoerde", language="de"),
    "IQWiG": FeedConfig("IQWiG", "https://www.iqwig.de/presse/pressemitteilungen/", feed_type="scrape", source_category="behoerde", language="de"),
    "KBV": FeedConfig("KBV", "https://www.kbv.de/praxis/tools-und-services/praxisnachrichten", feed_type="scrape", source_category="berufspolitik", language="de"),
    "Marburger Bund": FeedConfig("Marburger Bund", "https://www.marburger-bund.de/rss.xml", source_category="berufspolitik", language="de"),
    # Fachgesellschaften
    "DGIM": FeedConfig("DGIM", "https://www.dgim.de/presse/", feed_type="scrape", source_category="fachgesellschaft", language="de"),
    "DGK": FeedConfig("DGK", "https://dgk.org/presse/", feed_type="scrape", source_category="fachgesellschaft", language="de"),
    "DEGAM": FeedConfig("DEGAM", "https://www.degam.de/", feed_type="scrape", source_category="fachgesellschaft", language="de"),
    # Aufbereitete Quellen
    "Medscape DE": FeedConfig("Medscape DE", "https://deutsch.medscape.com", feed_type="scrape", source_category="fachpresse_aufbereitet", language="de"),
    "Medscape EN": FeedConfig("Medscape EN", "https://www.medscape.com/index/list_13470_rss", source_category="fachpresse_aufbereitet"),
    "arznei-telegramm": FeedConfig("arznei-telegramm", "https://www.arznei-telegramm.de", feed_type="scrape", source_category="fachpresse_aufbereitet", language="de"),
    # AWMF Leitlinien-Register
    "AWMF Leitlinien": FeedConfig("AWMF Leitlinien", "https://register.awmf.org/de/leitlinien/aktuelle-leitlinien", feed_type="scrape", source_category="leitlinie", language="de"),
}


def get_active_feeds(wave: Optional[int] = None) -> dict[str, FeedConfig]:
    """Return active feeds, optionally filtered by rollout wave."""
    return {
        name: cfg for name, cfg in FEED_REGISTRY.items()
        if cfg.active and (wave is None or cfg.wave <= wave)
    }

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
# Alert rules  (→ status = "ALERT")
#
# Two tiers:
#   UNCONDITIONAL: keyword alone triggers alert (high-specificity terms)
#   CONTEXTUAL:    keyword + at least one context word required
#   SUPPRESS:      title patterns that prevent alert (false-positive filter)
# ---------------------------------------------------------------------------
ALERT_RULES_UNCONDITIONAL: list = [
    "rückruf",
    "arzneimittelrückruf",
    "rote-hand-brief",
    "rote hand brief",
    "sicherheitswarnung",
    "black box warning",
    "urgent safety restriction",
    "urgent field safety notice",
    "chargenrückruf",
]

ALERT_RULES_CONTEXTUAL: list = [
    # ("trigger keyword", ["required context words"])
    ("bfarm", [
        "warnt", "warnung", "rückruf", "risikobewertung",
        "anordnung", "ordnet", "untersagt", "widerruf", "ruht", "ruhen",
        "chargenrückruf", "sicherheitsmaßnahme", "nebenwirkung",
        "defekt", "fälschung", "gefälscht", "mangelhaft", "entzieht",
        "recall", "withdrawal", "suspended",
    ]),
    ("contraindicated", [
        "new", "updated", "added", "now", "neu", "aktualisiert",
        "änderung", "ergänzt", "hinzugefügt",
    ]),
]

ALERT_SUPPRESS_TITLE_PATTERNS: list = [
    "interview",
    "daten zugänglich",
    "datenbank",
    "jahresbericht",
    "stellenangebot",
    "pressemitteilung",
    "konferenz",
    "symposium",
    "veranstaltung",
]

# Keep flat list for backward-compat (used by scorer.py SAFETY_KEYWORDS)
ALERT_KEYWORDS = ALERT_RULES_UNCONDITIONAL

# ---------------------------------------------------------------------------
# Score display thresholds  (used by app.py + digest.py)
# ---------------------------------------------------------------------------
SCORE_THRESHOLD_HIGH = 70   # grün — Top: Hohe Relevanz, starke Grundlage, Praxisbezug
SCORE_THRESHOLD_MID = 45    # gelb — Relevant: Solider Inhalt, selektiv aufgreifen
                             # darunter: grau — Monitor: Nachrichtenwert oder Nischenthema

# v1 thresholds (backward compatibility)
SCORE_THRESHOLD_HIGH_V1 = 65
SCORE_THRESHOLD_MID_V1 = 40

# ---------------------------------------------------------------------------
# Scoring v2 — 6 dimensions with variable maxima (sum = 100)
# ---------------------------------------------------------------------------
V2_DIMENSIONS = {
    "clinical_action_relevance": {"label": "Klinische Handlungsrelevanz", "max": 20},
    "evidence_depth":            {"label": "Evidenz- & Recherchetiefe",   "max": 20},
    "topic_appeal":              {"label": "Thematische Zugkraft",        "max": 20},
    "novelty":                   {"label": "Neuigkeitswert",              "max": 16},
    "source_authority":          {"label": "Quellenautorität",            "max": 12},
    "presentation_quality":      {"label": "Aufbereitungsqualität",       "max": 12},
}

V2_TIER_TOP = 70       # ≥70 → TOP
V2_TIER_RELEVANT = 45  # 45–69 → RELEVANT
                        # <45 → MONITOR

# ---------------------------------------------------------------------------
# LLM Configuration (Claude API for summaries)
# ---------------------------------------------------------------------------
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_MAX_ARTICLES_PER_RUN = 50  # limit Claude calls per pipeline run

# ---------- Quality Gate: Only keep articles above this score ----------
# Articles below this threshold are discarded after scoring (never stored).
# This saves LLM summary costs and keeps the DB lean.
# Score >= 55 yields ~80-100 articles/day from current feed volume.
SCORE_MIN_KEEP = 45         # absolute minimum to store in DB
SCORE_MIN_LLM_SUMMARY = 55  # below this: template summary only (saves LLM calls)
DAILY_MAX_ARTICLES = 120    # hard cap per day — keeps top N by score
LLM_TIMEOUT = 30  # seconds per API call
LLM_SUMMARY_SYSTEM_PROMPT = """\
Du bist ein erfahrener Medizinredakteur für ein tägliches Ärzte-Dashboard.
Fasse den folgenden Artikel kurz und präzise auf Deutsch zusammen.

Antworte EXAKT in diesem Format (3 Zeilen, getrennt durch ;;;):
KERN: [1 Satz: Das wichtigste Ergebnis oder die zentrale Aussage];;;PRAXIS: [1 Satz: Was bedeutet das konkret für den behandelnden Arzt?];;;EINORDNUNG: [1 Satz: Stärke der Evidenz, Limitationen, oder Kontext]

Regeln:
- Jeder Teil maximal 1 Satz
- Medizinisch präzise, aber verständlich
- KERN soll das Hauptergebnis enthalten, nicht den Studientitel wiederholen
- PRAXIS soll konkreten Handlungsbezug haben (z.B. "Therapieumstellung erwägen", "Bei Screening beachten")
- EINORDNUNG soll Evidenzlevel oder Limitationen nennen
- Bei Gesundheitspolitik-Artikeln: PRAXIS = Auswirkung auf Praxisalltag
- Keine Einleitung, keine Floskel, direkt zum Punkt"""

# ---------------------------------------------------------------------------
# Multi-Provider LLM Configuration (esanum 60-EUR architecture)
# ---------------------------------------------------------------------------


@dataclass
class LLMProvider:
    """Configuration for a single OpenAI-compatible LLM provider."""

    name: str           # e.g. "groq", "gemini_flash", "mistral"
    base_url: str       # OpenAI-compatible endpoint
    api_key_env: str    # Environment variable name for API key
    model: str          # Model identifier
    max_tokens: int = 1024
    timeout: float = 30.0


LLM_PROVIDERS = {
    "groq": LLMProvider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
    ),
    "gemini_flash": LLMProvider(
        name="gemini_flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        model="gemini-2.5-flash",  # 2.0 deprecated 2026-03 → upgraded to 2.5
        max_tokens=1024,
    ),
    "gemini_pro": LLMProvider(
        name="gemini_pro",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        model="gemini-2.5-pro",
        max_tokens=1024,
        timeout=60.0,
    ),
    "gemini_flash_lite": LLMProvider(
        name="gemini_flash_lite",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        model="gemini-2.5-flash-lite",
    ),
    "mistral": LLMProvider(
        name="mistral",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        model="mistral-small-latest",
    ),
    "cerebras": LLMProvider(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key_env="CEREBRAS_API_KEY",
        model="llama3.1-8b",
        max_tokens=1024,
    ),
    # Claude — only for high-quality editorial drafts (pay-per-use)
    "claude_sonnet": LLMProvider(
        name="claude_sonnet",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        model="claude-sonnet-4-5",
        max_tokens=1500,
        timeout=90.0,
    ),
}

# Task → ordered provider chain (primary first, then fallbacks).
# Keys reference LLM_PROVIDERS above.
#
# Provider-Rotation: Last auf mehrere Free-Tiers verteilen.
# Bei 429 (Rate Limit) rotiert die Pipeline automatisch zum nächsten.
#
# Kapazitäten (Free-Tier, je 1 Key):
#   Groq:             30 RPM, 14.400 RPD  → Arbeitstier für Massen-Tasks
#   Gemini Flash:     15 RPM,  1.500 RPD  → Qualitäts-Tasks
#   Gemini Flash-Lite:30 RPM,  3.000 RPD  → Prefilter (günstig)
#   Gemini Pro:        5 RPM,     25 RPD  → Nur Trend/Weekly (beste Qualität)
#   Mistral Small:    30 RPM,  ~5.000 RPD → Solider Fallback
#   Cerebras Llama70B:30 RPM,  ~1.000 RPD → Schneller Fallback
#
# Pipeline (~80 Artikel/Lauf, 2× täglich = ~160 Artikel/Tag):
#   prefilter (Batch 5): ~32 Calls → Gemini Flash-Lite → Mistral → Cerebras
#   scoring:            ~160 Calls → Gemini Flash-Lite → Mistral → Cerebras
#   summary:            ~160 Calls → Groq → Mistral → Cerebras
#   trends:               3 Calls → Gemini Pro → Gemini Flash → Groq
#   entwurf:           ~5-10 Calls → Gemini Flash → Groq → Mistral
#   frag_lumio:        ~5-20 Calls → Groq → Cerebras → Gemini Flash
#
LLM_TASK_PROVIDERS = {
    # High-volume pipeline tasks — Flash-Lite primary (günstigster Output: $0.40/1M)
    # Groq 70B als Fallback (gute Qualität, $0.79/1M Output)
    # Vorher: Gemini Flash primary ($2.50/1M Output) → 6× teurer
    "prefilter":        ["gemini_flash_lite", "cerebras", "groq"],
    "scoring":          ["gemini_flash_lite", "groq", "cerebras"],
    "summary":          ["gemini_flash_lite", "groq", "cerebras"],  # Test: Lite statt Flash (spart ~$8/Mo)
    # Low-volume quality tasks → Flash-Lite primary (wenige Calls, Qualität beobachten)
    "trend_summary":    ["gemini_flash_lite", "groq", "cerebras"],
    "weekly_overview":  ["gemini_flash_lite", "groq", "cerebras"],
    # Sammlungs-Entwürfe: Claude Sonnet (Bezahl-API, beste Qualität)
    "article_draft":    ["claude_sonnet", "gemini_flash", "groq"],
    "artikel_entwurf":  ["claude_sonnet", "gemini_flash", "groq"],
    # Kongress-Briefings: Gemini → Groq → Cerebras (kein Claude — Kosten sparen)
    "kongress_briefing":["gemini_flash", "groq", "cerebras"],
    # Suchbegriff-Expansion: schnell + günstig, kurze Antwort (~50 Tokens)
    "search_expansion": ["groq", "gemini_flash_lite", "cerebras"],
}


def get_provider_chain(task: str) -> List["LLMProvider"]:
    """Return ordered list of LLMProvider objects for a given task."""
    provider_keys = LLM_TASK_PROVIDERS.get(task, [])
    return [LLM_PROVIDERS[k] for k in provider_keys if k in LLM_PROVIDERS]

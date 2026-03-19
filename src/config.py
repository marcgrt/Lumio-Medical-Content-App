"""Lumio configuration — sources, scoring weights, specialties."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

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
    # International — Top Journals
    "NEJM": "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "The Lancet": "https://www.thelancet.com/rssfeed/lancet_current.xml",
    "BMJ": "https://www.bmj.com/rss/recent.xml",
    "JAMA": "https://jamanetwork.com/rss/site_3/67.xml",
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
SCORE_THRESHOLD_HIGH = 65   # grün — Top-Evidenz, starker Fachartikel
SCORE_THRESHOLD_MID = 40    # gelb — Solide Fachpresse / gute Studie
                             # darunter: grau/rot — News, Preprints

# ---------------------------------------------------------------------------
# LLM Configuration (Claude API for summaries)
# ---------------------------------------------------------------------------
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_MAX_ARTICLES_PER_RUN = 50  # limit Claude calls per pipeline run
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
    max_tokens: int = 300
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
        model="gemini-2.0-flash",  # 2.0: 1500 RPD free (vs 2.5: only 20 RPD!)
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
}

# Task → ordered provider chain (primary first, then fallbacks).
# Keys reference LLM_PROVIDERS above.
#
# Kapazitäts-Strategie (1 Gemini Key + 1 Groq Key):
#   Groq:   30 RPM, 14.400 RPD (free) → ideal für Massen-Tasks
#   Gemini: Flash 1500 RPD / Pro 25 RPD → ideal für Qualitäts-Tasks
#
#   Pipeline (~60 Artikel/Lauf, 2× täglich = ~120 Artikel):
#     prefilter:  120× → Gemini Flash Lite (günstig, schnell)
#     scoring:    120× → Groq (Hauptlast, 240/Tag << 14.400 Limit)
#     summary:    120× → Groq (240/Tag, passt locker)
#     trends:       3× → Gemini Pro (wenige Calls, beste Qualität)
#     entwurf:   ~5-10× → Gemini Flash (on-demand, gute Textqualität)
#     frag_lumio: ~5-20× → Groq (interaktiv, schnelle Antwort)
#
LLM_TASK_PROVIDERS = {
    # High-volume pipeline tasks → Groq (14.400 RPD Kapazität)
    "prefilter":        ["gemini_flash_lite", "gemini_flash", "groq"],
    "scoring":          ["groq", "gemini_flash"],
    "summary":          ["groq", "gemini_flash"],
    # Low-volume quality tasks → Gemini (beste Textqualität)
    "trend_summary":    ["gemini_pro", "gemini_flash", "groq"],
    "weekly_overview":  ["gemini_pro", "gemini_flash", "groq"],
    "article_draft":    ["gemini_flash", "groq"],
    # Interactive chat — Groq (schnellste Antwortzeit)
    "frag_lumio":       ["groq", "gemini_flash"],
}


def get_provider_chain(task: str) -> List["LLMProvider"]:
    """Return ordered list of LLMProvider objects for a given task."""
    provider_keys = LLM_TASK_PROVIDERS.get(task, [])
    return [LLM_PROVIDERS[k] for k in provider_keys if k in LLM_PROVIDERS]

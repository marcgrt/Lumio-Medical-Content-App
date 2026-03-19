# Lumio

**Medizinische Evidenz-Plattform** — Automatisierte Recherche, Scoring und redaktionelle Aufbereitung medizinischer Fachliteratur.

Lumio sammelt aus 11 Quellen, bewertet nach Evidenz-Hierarchie, fasst per KI zusammen und liefert ein redaktionelles Dashboard mit Trend-Radar, Konkurrenz-Analyse und Watchlists.

---

## Architektur

```
                    11 Quellen (PubMed, RSS, WHO, BfArM, ...)
                                    |
                              [Pipeline]
                    Ingest → Dedup → Prefilter (LLM)
                       → Score → Classify → Summarize (LLM)
                                    |
                              [SQLite + FTS5]
                                    |
              ┌─────────────┬───────┴───────┬──────────────┐
              |             |               |              |
         [Streamlit]    [FastAPI]     [Digest-Mail]   [Themen-Pakete]
          Port 8501     Port 8000     (Top-10 SMTP)   (Wochenberichte)
              |
    ┌─────┬──┴──┬────────┬─────────┐
   Feed  Suche Insights Redaktion Versand
```

### Datenfluss

```
Quellen ──► Ingestion (async, 11 parallel) ──► Dedup (Levenshtein + Embeddings)
    ──► LLM-Prefilter (Relevanz + Fachgebiet) ──► Scoring (regelbasiert, 5 Dimensionen)
    ──► Classifier (Fachgebiet + Alerts) ──► LLM-Summarizer (KERN/PRAXIS/EINORDNUNG)
    ──► SQLite (FTS5 Volltext-Index) ──► Watchlist-Matching ──► E-Mail-Benachrichtigung
```

### LLM-Provider-Kette

```
Aufgabe            Primaer              Fallback 1          Fallback 2
─────────────────────────────────────────────────────────────────────
Prefilter          Gemini Flash Lite    Gemini Flash        Groq
Scoring            Groq                 Gemini Flash        —
Zusammenfassung    Groq                 Gemini Flash        —
Trend-Summary      Gemini Pro           Gemini Flash        Groq
Artikel-Entwurf    Gemini Flash         Groq                —
Letzter Fallback   Anthropic Claude (wenn API-Key gesetzt)
```

---

## Schnellstart

### Voraussetzungen

- Python 3.9+
- pip

### Installation

```bash
git clone <repo-url> lumio
cd lumio
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Umgebungsvariablen

Kopiere `.env.example` nach `.env` und trage mindestens einen LLM-Key ein:

```bash
cp .env.example .env
```

```env
# Mindestens einer der beiden:
GROQ_API_KEY=gsk_...          # Haupt-Provider (14.400 Calls/Tag)
GEMINI_API_KEY=AIza...         # Zweit-Provider (1.500 Calls/Tag)

# Optional:
ANTHROPIC_API_KEY=sk-ant-...   # Fallback (kostenpflichtig)
MISTRAL_API_KEY=...            # Zusaetzlicher Fallback

# E-Mail (optional):
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=user@gmail.com
SMTP_PASS=app-passwort
DIGEST_EMAIL=redaktion@example.com
ALERT_EMAIL=alerts@example.com

# API-Schutz (fuer n8n/Cron):
API_TOKEN=mein-geheimes-token
```

### Starten

```bash
# Web-Dashboard
streamlit run app.py

# Pipeline einmalig ausfuehren (z.B. letzte 2 Tage)
python -m src 2

# Oder beides via Docker
docker-compose up
```

---

## Projektstruktur

```
lumio/
├── app.py                    # Streamlit-Haupteinstieg
├── start.sh                  # Docker-Startskript (API + Streamlit)
├── requirements.txt
├── .env.example
│
├── src/
│   ├── config.py             # Konfiguration, Scoring-Gewichte, LLM-Provider
│   ├── models.py             # Datenbank-Modelle (Article, Watchlist, ...)
│   ├── pipeline.py           # Pipeline-Orchestrierung
│   ├── api.py                # FastAPI-Endpunkte (/api/pipeline/run, /api/digest/send)
│   ├── llm_client.py         # Multi-Provider LLM-Client mit Fallback + Rate-Limiting
│   ├── digest.py             # Tages-Digest per E-Mail
│   ├── themen_paket.py       # Woechentliche Themen-Pakete pro Watchlist
│   │
│   ├── ingestion/            # 11 Datenquellen
│   │   ├── europe_pmc.py     # PubMed Central API
│   │   ├── rss_feeds.py      # NEJM, Lancet, BMJ, JAMA, Aerzteblatt, ...
│   │   ├── google_news.py    # Google News (3 deutsche Suchbegriffe)
│   │   ├── medrxiv.py        # medRxiv Preprints
│   │   ├── biorxiv.py        # bioRxiv Preprints
│   │   ├── who.py            # WHO Disease Outbreak News
│   │   ├── bfarm.py          # BfArM Sicherheitsmeldungen
│   │   ├── ema.py            # EMA Pharmakovigilanz
│   │   ├── cochrane.py       # Cochrane Reviews
│   │   ├── awmf.py           # AWMF Leitlinien
│   │   └── rki.py            # RKI Surveillance
│   │
│   └── processing/           # Verarbeitungs-Module
│       ├── prefilter.py      # LLM-basierte Relevanzfilterung (Batch)
│       ├── dedup.py          # Deduplizierung (Levenshtein + Cosine)
│       ├── scorer.py         # Relevanz-Scoring (5 Dimensionen)
│       ├── classifier.py     # Fachgebiet-Erkennung + Alert-Flagging
│       ├── summarizer.py     # LLM-Zusammenfassungen (KERN/PRAXIS/EINORDNUNG)
│       ├── trends.py         # Themen-Radar (Clustering + Momentum)
│       ├── watchlist.py      # Watchlist-Matching + Benachrichtigung
│       ├── luecken_detektor.py       # Redaktionelle Blindstellen
│       ├── redaktions_gedaechtnis.py # Was wurde schon berichtet?
│       ├── konkurrenz_radar.py       # Wettbewerbsanalyse
│       └── story_radar.py           # Story-Pitches fuer die Redaktion
│
├── views/                    # Streamlit-Tabs
│   ├── feed.py               # Dashboard + Artikel-Feed
│   ├── search.py             # Volltextsuche + Werkbank
│   ├── insights.py           # Analytics, Charts, Heatmap, Export
│   ├── redaktion.py          # Luecken, Gedaechtnis, Konkurrenz
│   └── versand.py            # Pipeline-Steuerung, Digest, Pakete
│
├── components/               # UI-Helfer
│   ├── sidebar.py            # Sidebar (Filter, KPIs, Watchlists)
│   ├── css.py                # Dark Theme (Apple/Asana-Stil)
│   └── helpers.py            # Query-Helfer, Rendering-Funktionen
│
├── tests/                    # 255 Tests
│   ├── conftest.py           # Fixtures (make_article, make_trend)
│   └── test_*.py             # Unit-Tests
│
├── static/                   # Logo, Favicon, Easter-Egg-Audio
└── db/                       # SQLite-Datenbank (auto-erstellt)
```

---

## Scoring-System

Jeder Artikel erhaelt einen **Relevanz-Score (0-100)** aus 5 gewichteten Dimensionen:

| Dimension | Gewicht | Beschreibung |
|-----------|---------|--------------|
| **Journal** | 30% | Prestige-Tier (NEJM=100, Preprints=30) |
| **Studiendesign** | 25% | Evidenz-Hierarchie (Meta-Analyse=100, News=35) |
| **Aktualitaet** | 20% | Exponentieller Zerfall (heute=100, 10 Tage=37) |
| **Keywords** | 15% | Sicherheit (+20), Leitlinien (+15), Landmark (+10) |
| **Arztrelevanz** | 10% | Therapie, Diagnostik, Gesundheitspolitik |

**Bonus-Modifikatoren:** Redaktions-Bonus (+3-8 fuer Aerzteblatt etc.), Interdisziplinaritaet (+5-10), Open Access (+5), Strukturiertes Abstract (+2-4), DOI (+2). **Malus:** Paywall ohne Abstract (-8 bis -15), Industrie-News (-10 bis -20), Kurz-Abstract (-5).

**Schwellenwerte:**

| Farbe | Score | Bedeutung |
|-------|-------|-----------|
| Gruen | >= 65 | Top-Evidenz |
| Gelb | 40-64 | Solide |
| Grau | < 40 | News / Preprints |

---

## Datenbank

**SQLite** mit WAL-Modus (Write-Ahead Logging) fuer parallele Lesezugriffe.

### Tabellen

| Tabelle | Beschreibung |
|---------|-------------|
| `article` | Artikel (Titel, Abstract, Score, Status, Fachgebiet, ...) |
| `source` | Datenquellen (Name, URL, Typ, letzte Abfrage) |
| `status_change` | Audit-Log (Wer hat wann welchen Status geaendert?) |
| `watchlist` | Benutzer-Watchlists (Keywords, Min-Score, Fachgebiet-Filter) |
| `watchlist_match` | Watchlist-Treffer + Benachrichtigungs-Status |
| `user_profile` | Benutzer-Lernprofil (JSON) |

### FTS5 Volltextsuche

Virtuelle Tabelle `article_fts` indexiert: Titel, Abstract, Zusammenfassung, Tags, Autoren, Journal, MeSH-Terms, Fachgebiet, Quelle. Automatisch synchronisiert via SQLite-Triggers.

---

## LLM-Konfiguration

### Provider

| Provider | Modell | Free-Tier | Einsatz |
|----------|--------|-----------|---------|
| **Groq** | llama-3.3-70b | 14.400 Calls/Tag | Scoring, Zusammenfassungen |
| **Gemini Flash** | gemini-2.0-flash | 1.500 Calls/Tag | Prefilter, Entwuerfe |
| **Gemini Pro** | gemini-2.5-pro | 25 Calls/Tag | Trend-Summaries |
| **Mistral** | mistral-small | 5.000 Calls/Tag | Fallback |
| **Anthropic** | Claude | Kostenpflichtig | Letzter Fallback |

### Key-Rotation

Mehrere Keys pro Provider moeglich:

```env
GROQ_API_KEY=gsk_key1
GROQ_API_KEY_2=gsk_key2
GROQ_API_KEY_3=gsk_key3
```

Lumio rotiert automatisch zwischen Keys und trackt taegliche Nutzung pro Key.

### Rate-Limiting

- Token-Bucket pro Provider (RPM)
- Taegliches Limit-Tracking (RPD)
- Warnung bei 80% Auslastung
- Automatischer Wechsel zum naechsten Provider bei Limit

---

## API-Endpunkte

FastAPI laeuft parallel zu Streamlit auf Port 8000.

```
GET  /api/health              # Statuscheck
POST /api/pipeline/run        # Pipeline starten (Bearer-Token erforderlich)
     ?days_back=2             # Zeitraum (1-30 Tage)
POST /api/digest/send         # Digest versenden (Bearer-Token erforderlich)
     ?email=user@example.com  # Optionaler Empfaenger
```

**Authentifizierung:** `Authorization: Bearer {API_TOKEN}`

---

## Docker-Deployment

```bash
# .env konfigurieren
cp .env.example .env
# Keys eintragen...

# Starten
docker-compose up -d

# Logs
docker-compose logs -f lumio
```

### Docker-Compose Services

| Service | Port | Beschreibung |
|---------|------|-------------|
| `lumio` | 8000, 8501 | API + Streamlit |
| `nginx` | 80, 443 | Reverse Proxy mit .htpasswd |
| `certbot` | — | Let's Encrypt Auto-Renewal (12h) |

### Volumes

- `./db/` — SQLite-Datenbank (persistent)
- Sentence-Transformer-Modell-Cache

---

## Tests

```bash
# Alle Tests (255 Tests)
pytest

# Einzelne Datei
pytest tests/test_scorer.py -v

# Nach Name filtern
pytest -k "dedup" -v

# Mit Coverage (wenn installiert)
pytest --cov=src --cov=components --cov=views
```

### Test-Abdeckung

| Modul | Tests | Beschreibung |
|-------|-------|-------------|
| `test_scorer.py` | Scoring | Alle 5 Dimensionen + Modifikatoren |
| `test_scorer_modifiers.py` | Modifikatoren | Paywall, OA, DOI, Industrie, Abstract |
| `test_classifier.py` | Klassifikation | 13 Fachgebiete + Alert-Erkennung |
| `test_dedup.py` | Deduplizierung | Levenshtein + DOI + Embedding-Fallback |
| `test_watchlist.py` | Watchlists | Keyword-Matching, Filter, Batch |
| `test_prefilter.py` | LLM-Prefilter | Batch-Modus, JSON-Parsing, Fallback |
| `test_summarizer.py` | Zusammenfassung | Template + LLM-Format, Tags |
| `test_helpers.py` | UI-Helfer | Badges, Pills, Summary-Parsing, HTML-Escape |
| `test_config.py` | Konfiguration | Gewichte, Schwellenwerte, Journal-Tiers |
| `test_konkurrenz_radar.py` | Konkurrenz | Topic-Extraktion, Overlap, Geschwindigkeit |
| `test_story_radar.py` | Story-Radar | Pitch-Scoring, Bonus-Logik |
| `test_redaktions_gedaechtnis.py` | Gedaechtnis | Topic-Extraktion, Vorschlaege |
| `test_luecken_detektor.py` | Luecken | Keyword-Extraktion, Vorschlaege |
| `test_digest.py` | Digest | Score-Farben, Diversifizierung |
| `test_llm_client.py` | LLM-Client | Rate-Limiting, Usage-Stats |
| `test_pipeline.py` | Pipeline | End-to-End mit Mocks |

---

## Entwicklung

### Neue Datenquelle hinzufuegen

1. Erstelle `src/ingestion/neue_quelle.py` mit `async def fetch(days_back: int) -> list[Article]`
2. Registriere in `src/pipeline.py` → `ingest_all()` (Name + Funktion)
3. Pipeline erkennt und integriert die Quelle automatisch

### Neues Fachgebiet hinzufuegen

1. Keywords in `src/config.py` → `SPECIALTY_MESH` eintragen
2. Farben in `components/helpers.py` → `SPECIALTY_COLORS` definieren
3. Fertig — Klassifikation, Heatmap und Filter arbeiten automatisch

### Scoring-Gewichte anpassen

In `src/config.py`:

```python
WEIGHT_JOURNAL = 0.30
WEIGHT_STUDY_DESIGN = 0.25
WEIGHT_RECENCY = 0.20
WEIGHT_KEYWORD_BOOST = 0.15
WEIGHT_ARZTRELEVANZ = 0.10
```

Summe muss 1.0 ergeben. Schwellenwerte:

```python
SCORE_THRESHOLD_HIGH = 65   # Ab hier "Top-Evidenz"
SCORE_THRESHOLD_MID = 40    # Ab hier "Solide"
```

---

## Lizenz

Proprietary — alle Rechte vorbehalten.

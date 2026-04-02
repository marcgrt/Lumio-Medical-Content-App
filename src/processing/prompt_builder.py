'''
Prompt Builder for Lumio Cowork — Fachartikel Generation.

Implements 5 prompting techniques (CoT, ToT, Persona, SC, FS) and 12 Pro-Modes
based on the FACHARTIKEL_TASK_BLUEPRINT architecture.

Usage:
    from src.processing.prompt_builder import build_article_prompt

    prompt = build_article_prompt(
        articles=articles_data,         # List of dicts with title, abstract, summary_de
        briefing=briefing_dict,         # From collection briefing fields
        technique='cot',                # cot|tot|persona|sc|fs
        pro_modes={'teachme', 'benchmark'},  # Max 3
        custom_experts=None,            # Optional ToT expert overrides
        fs_examples=None,               # Optional Few-Shot examples
    )
'''

from typing import Optional

# ---------------------------------------------------------------------------
# Output Format (appended to every prompt)
# ---------------------------------------------------------------------------

OUTPUT_FORMAT = '''### AUSGABEFORMAT

**TITEL:** [SEO-optimiert, max. 65 Zeichen, klarer Mehrwert]
**UNTERTITEL:** [Kontext oder Neugier-Trigger, max. 120 Zeichen]

**LEAD / EINLEITUNG (3-4 Sätze):**
[Warum ist das jetzt relevant? Was erfährt der Leser?]

**HAUPTTEIL:**
Strukturiere mit klaren Zwischenüberschriften (H2/H3):
- Jeder Abschnitt: Kernaussage -> Evidenz -> Praxis-Relevanz
- Fachbegriffe erklären, wenn nicht Grundwissen der Zielgruppe
- Studien-Daten mit Einordnung (Effektstärke, Limitationen)

**FAZIT / PRAXIS-TAKEAWAY (3-5 Bullet-Points):**
[Was bedeutet das konkret für den Arzt im Alltag?]

**QUELLEN:**
[Nummerierte Quellenangaben im Vancouver-Stil — basierend auf den gelieferten Artikeln]

---
**SEO-ELEMENTE:**
- Meta-Title: [max. 60 Zeichen]
- Meta-Description: [max. 155 Zeichen]
- Alt-Text für Titelbild: [Beschreibend + Keyword]'''


# ---------------------------------------------------------------------------
# 12 Pro-Mode Blocks
# ---------------------------------------------------------------------------

PRO_MODES = {
    'neuro': {
        'emoji': '🧠', 'name': 'Neuro-Trigger',
        'subtitle': 'Psychologie-Prinzipien für stärkere Wirkung',
        'tooltip': 'Integriert neuropsychologische Prinzipien wie Verlustaversion, Social Proof, Ankereffekt, Framing und kognitive Leichtigkeit in den Output. Jede Empfehlung wird mit dem zugrundeliegenden psychologischen Mechanismus annotiert.',
        'block': '''### PRO MODE: NEURO-TRIGGER
Wende bei jeder Empfehlung gezielt neuropsychologische Prinzipien an:
- Verlustaversion (Kahneman): Formuliere, was die Zielgruppe verpasst/verliert
- Social Proof: Integriere Validierung durch Peers, Zahlen oder Referenzen
- Ankereffekt: Setze einen hohen Referenzpunkt vor der eigentlichen Empfehlung
- Cognitive Ease: Bevorzuge einfache Formulierungen — sie wirken glaubwürdiger
- Peak-End-Rule: Gestalte Höhepunkt und Ende besonders stark
Kennzeichne bei jeder Maßnahme: [TRIGGER: Name].''',
    },
    'contrarian': {
        'emoji': '🎯', 'name': 'Contrarian View',
        'subtitle': 'Hinterfrage Annahmen, finde konträre Ideen',
        'tooltip': 'Zwingt das Modell, die naheliegendste Lösung bewusst zu verwerfen und das Gegenteil zu denken. Deckt blinde Flecken auf, durchbricht Groupthink und führt zu unerwarteten, differenzierenden Ansätzen.',
        'block': '''### PRO MODE: CONTRARIAN VIEW
1. Identifiziere die offensichtlichste Lösung — und verwirf sie.
2. Formuliere die Gegenthese: Was wäre, wenn das Gegenteil stimmt?
3. Entwickle mindestens einen Ansatz basierend auf der Gegenthese.
4. Bewerte: Ist der kontrare Ansatz stärker oder deckt er einen blinden Fleck auf?
5. Integriere die besten Contrarian-Erkenntnisse ins finale Ergebnis.
Markiere mit 🎯.''',
    },
    'crossindustry': {
        'emoji': '🌍', 'name': 'Cross-Industry',
        'subtitle': 'Inspiration aus branchenfremden Erfolgsmodellen',
        'tooltip': 'Sucht gezielt nach Strategien und Taktiken aus völlig anderen Branchen und überträgt sie auf die aktuelle Aufgabe. Innovation durch Analogie-Transfer.',
        'block': '''### PRO MODE: CROSS-INDUSTRY INSPIRATION
- Identifiziere eine Strategie aus einer völlig anderen Industrie
- Analysiere das Grundprinzip hinter dem Erfolg
- Übertrage: 'Aus [Branche]: [Prinzip] -> Für uns: [Anwendung]'
Ziel: Mindestens eine Empfehlung, auf die der Wettbewerb nicht kommt.''',
    },
    'datastory': {
        'emoji': '📊', 'name': 'Data Storytelling',
        'subtitle': 'Verwandle Zahlen in überzeugende Geschichten',
        'tooltip': 'Wandelt Daten und Statistiken in verständliche Geschichten um. Jede Zahl wird in einen menschlichen Kontext gesetzt, mit Vergleichen und narrativen Bögen.',
        'block': '''### PRO MODE: DATA STORYTELLING
Jede Zahl/KPI als Story:
- Kontext: Was bedeutet die Zahl konkret?
- Vergleich: In Relation zu etwas Greifbarem setzen
- Trend: Woher, wohin?
- Visualisierung: Chart-Typ oder Infografik-Idee vorschlagen
Keine nackte Zahl ohne menschlichen Kontext.''',
    },
    'perspektiv': {
        'emoji': '🎭', 'name': 'Perspektiv-Shift',
        'subtitle': 'Ergebnis aus verschiedenen Blickwinkeln prüfen',
        'tooltip': 'Generiert zusätzlich zum Ergebnis eine Bewertung aus 3 Perspektiven: Zielgruppe, Wettbewerber, skeptischer Reviewer. Deckt Schwächen auf und stärkt die Argumentation.',
        'block': '''### PRO MODE: PERSPEKTIV-SHIFT
Betrachte das Ergebnis aus 3 Perspektiven:
A — Zielgruppe: Was überzeugt? Was erzeugt Widerstand?
B — Wettbewerber: Was würdest du kopieren? Was ist angreifbar?
C — Skeptischer Reviewer: Wo sind Behauptungen schwach belegt?
Integriere Erkenntnisse als konkreten Verbesserungsvorschlag.''',
    },
    'benchmark': {
        'emoji': '🏆', 'name': 'Benchmark Mode',
        'subtitle': 'World-Class-Beispiel zeigen, dann adaptieren',
        'tooltip': 'Beginnt mit dem besten bekannten Beispiel, analysiert WARUM es funktioniert, und nutzt diese Prinzipien als Vorlage. Lernen von den Besten.',
        'block': '''### PRO MODE: BENCHMARK
1. Gold Standard identifizieren: Bestes Beispiel für diese Art von Fachartikel.
2. Erfolgsprinzipien extrahieren: 3-5 Punkte WARUM es so erfolgreich ist.
3. Adaption: Jedes Erfolgsprinzip konkret auf die aktuelle Aufgabe übertragen.
4. Delta-Check: Vergleiche dein Ergebnis mit dem Gold Standard. Nachschärfen.
Formatiere als '🏆 BENCHMARK: [Name]'.''',
    },
    'microdetail': {
        'emoji': '🔬', 'name': 'Micro-Detail',
        'subtitle': 'Obsessiver Fokus auf ein entscheidendes Element',
        'tooltip': 'Wählt automatisch das wirkungsvollste Element aus und liefert maximale Tiefe: 5 Varianten, Word-by-Word-Analyse, Begründung für jedes Wort. Qualität durch obsessive Tiefe.',
        'block': '''### PRO MODE: MICRO-DETAIL
Identifiziere das EINE Element mit größtem Impact.
- 5 Varianten (emotional, rational, provokant, minimal, maximal)
- Für jede: Warum + wann sie die beste Wahl ist
- Word-by-Word-Analyse der stärksten Variante
- Finale Empfehlung
Markiere mit '🔬 MICRO-DETAIL: [Element]'.''',
    },
    'remix': {
        'emoji': '🧩', 'name': 'Remix Mode',
        'subtitle': 'Vorhandene Assets zu etwas Neuem kombinieren',
        'tooltip': 'Statt alles von Null: Identifiziert bestehende Inhalte und Elemente, die rekombiniert werden können. Wie ein DJ — die besten Tracks entstehen durch intelligentes Sampling.',
        'block': '''### PRO MODE: REMIX
1. Bestandsaufnahme: Welche bestehenden Elemente sind relevant?
2. Rekombination: 3 kreative Kombinationen vorschlagen
3. Mashup: Die stärkste Kombination voll ausarbeiten
4. Effizienz-Check: Aufwand vs. Komplett-Neuentwicklung''',
    },
    'wildcard': {
        'emoji': '🎰', 'name': 'Wild Card',
        'subtitle': 'Eine bewusst verrückte Überraschungsidee',
        'tooltip': 'Fügt eine bewusst unerwartete, riskantere Idee hinzu, mit Risiko/Potenzial/Machbarkeits-Scoring und Testvorschlag. Kann die beste Idee sein — oder den Denkraum öffnen.',
        'block': '''### PRO MODE: WILD CARD
Füge EINE unkonventionelle Idee hinzu:
- Darf riskant/überraschend sein, muss aufs Ziel einzahlen
- Bewerte: Risiko (1-10) | Potenzial (1-10) | Machbarkeit (1-10)
- Wie man sie risikoarm testen kann
Markiere mit '🎰 WILD CARD'.''',
    },
    'baukasten': {
        'emoji': '🏗️', 'name': 'Baukasten Mode',
        'subtitle': 'Modulare Bausteine zum Frei-Kombinieren',
        'tooltip': 'Liefert das Ergebnis als modulare, nummerierte Bausteine mit Kompatibilitäts-Matrix und 3 fertigen Kombinationen (Sicher, Kreativ, Maximum Impact). Ideal für Teams.',
        'block': '''### PRO MODE: BAUKASTEN
Liefere als modulares System:
- Nummerierte Bausteine [H1][H2][B1][CTA1] etc.
- Kompatibilitäts-Matrix: Welche passen zusammen?
- 3 fertige Kombinationen: 'Sicher', 'Kreativ', 'Maximum Impact'
- Platzhalter: [HIER: eigenes Beispiel]''',
    },
    'teachme': {
        'emoji': '🎓', 'name': 'Teach Me',
        'subtitle': 'Erkläre bei jeder Empfehlung das Warum',
        'tooltip': 'Jede Empfehlung wird mit einer kurzen Erklärung versehen, WARUM sie funktioniert — mit Referenz auf Studien oder Prinzipien. Plus 3 Takeaways am Ende. Verwandelt den Output in ein Lern-Dokument.',
        'block': '''### PRO MODE: TEACH ME
Jede Empfehlung mit 'Warum es funktioniert':
- Format: Empfehlung -> 🎓 Warum: [1-2 Sätze Erklärung]
- Referenziere Studien, Frameworks, Prinzipien
- Am Ende: '3 Dinge, die du gelernt hast' als Takeaway-Box''',
    },
    'spicy': {
        'emoji': '🌶️', 'name': 'Spicy Take',
        'subtitle': 'Provokantes, meinungsstarkes Feedback inklusive',
        'tooltip': 'Fügt am Ende einen ehrlichen, meinungsstarken Feedback-Abschnitt hinzu — ohne Höflichkeitsfloskeln. Wie ein erfahrener Mentor, der kein Blatt vor den Mund nimmt.',
        'block': '''### PRO MODE: SPICY TAKE
Am Ende '🌶️ Spicy Take' mit brutally honest Feedback:
- Was am Briefing problematisch ist
- Welche Industrie-Wahrheit ignoriert wird
- Was ein Top-5%-Medical-Writer anders machen würde
Ton: Direkt, meinungsstark, respektvoll aber schonungslos.''',
    },
    'reversebrief': {
        'emoji': '🔄', 'name': 'Reverse Brief',
        'subtitle': '5 smarte Rückfragen vor dem Ergebnis',
        'tooltip': 'Statt sofort loszulegen: Das Modell stellt erst 5 gezielte Rückfragen (als Multiple-Choice), die das Briefing schärfen. Bessere Fragen = bessere Ergebnisse.',
        'block': '''### PRO MODE: REVERSE BRIEF
ZUERST 5 Rückfragen stellen:
- Als Multiple-Choice mit 2-3 Optionen
- Sortiert nach Impact
- Format: 'Frage 1: [Frage] -> A) ... | B) ... | C) ...'
Dann selbst beantworten + Ergebnis erstellen.
Im Ergebnis: [VARIABEL bei Frage X] markieren.''',
    },
}

# Recommended Pro-Modes for medical articles
RECOMMENDED_PRO_MODES = ['teachme', 'benchmark', 'microdetail', 'reversebrief']

# ---------------------------------------------------------------------------
# Default Experts for Tree of Thoughts
# ---------------------------------------------------------------------------

DEFAULT_EXPERTS = [
    ('Medical Writer', 'Medizinische Genauigkeit, Quellenarbeit & verständliche Fachsprache'),
    ('SEO Content Strategist', 'Suchintention, Keyword-Integration & Ranking-Potenzial'),
    ('Fachredakteur', 'Redaktionelle Qualität, Leserführung & journalistische Standards'),
]


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

def _build_article_context(articles: list[dict], max_chars_per_article: int = 500) -> str:
    '''Build article context string from collection articles.'''
    if not articles:
        return '(Keine Artikel in der Sammlung)'

    parts = []
    for i, a in enumerate(articles, 1):
        title = a.get('title', 'Ohne Titel')
        source = a.get('journal') or a.get('source', '')
        date = a.get('pub_date', '')
        abstract = a.get('abstract', '') or ''
        summary = a.get('summary_de', '') or ''

        # Prefer summary, fallback to abstract
        text = summary if len(summary) > 50 else abstract
        if len(text) > max_chars_per_article:
            text = text[:max_chars_per_article] + '...'

        url = a.get('url', '')
        doi = a.get('doi', '')

        entry = f'**Artikel {i}: {title}**'
        source_line = []
        if source:
            source_line.append(source)
        if date:
            source_line.append(date)
        if source_line:
            entry += f'\nQuelle: {" | ".join(source_line)}'
        if url:
            entry += f'\nURL: {url}'
        elif doi:
            entry += f'\nDOI: {doi}'
        if text:
            entry += f'\n{text}'
        parts.append(entry)

    return '\n\n'.join(parts)


def _build_briefing_context(briefing: dict) -> tuple[str, str]:
    '''Split briefing into core context (top) and detail context (bottom).

    Returns (core_ctx, detail_ctx).
    '''
    core_lines = []
    detail_lines = []

    # Core fields — placed at top of prompt
    theme = briefing.get('theme')
    if theme:
        core_lines.append(f'  - Thema: {theme}')

    audience = briefing.get('target_audience')
    if audience:
        core_lines.append(f'  - Zielgruppe: {audience}')

    goal = briefing.get('goal')
    if goal:
        core_lines.append(f'  - Ziel: {goal}')

    # Detail fields
    fmt = briefing.get('article_format')
    if fmt and fmt != '—':
        detail_lines.append(f'  - Artikelformat: {fmt}')

    tone = briefing.get('tonality')
    if tone and tone != '—':
        detail_lines.append(f'  - Tonalität: {tone}')

    length = briefing.get('target_length')
    if length and length != '—':
        detail_lines.append(f'  - Länge: {length}')

    key_msg = briefing.get('key_message')
    if key_msg:
        detail_lines.append(f'  - Kernaussage: {key_msg}')

    keywords = briefing.get('keywords')
    if keywords:
        detail_lines.append(f'  - SEO-Keywords: {keywords}')

    notes = briefing.get('internal_notes')
    if notes:
        detail_lines.append(f'  - Redaktionelle Hinweise: {notes}')

    return '\n'.join(core_lines), '\n'.join(detail_lines)


def _build_pro_mode_suffix(pro_modes: set[str]) -> str:
    '''Build pro-mode suffix (max 3).'''
    active = list(pro_modes)[:3]
    if not active:
        return ''
    blocks = [PRO_MODES[pid]['block'] for pid in active if pid in PRO_MODES]
    return '\n\n' + '\n\n'.join(blocks)


# ---------------------------------------------------------------------------
# 5 Technique Templates
# ---------------------------------------------------------------------------

def _prompt_cot(article_ctx: str, core_ctx: str, detail_ctx: str,
                pro_suffix: str, collection_name: str) -> str:
    return f'''### AUFGABE
Fachartikel — schrittweise und nachvollziehbar entwickeln.
Thema: {collection_name}

### KERNKONTEXT
{core_ctx if core_ctx else '  - Zielgruppe: Praktizierende Ärzte in Deutschland'}

### DENKPROZESS (jeden Schritt sichtbar machen)

**SCHRITT 1 — SITUATIONSANALYSE**
Analysiere den Ist-Zustand basierend auf den Quellen-Artikeln.
Identifiziere die kritischen Informationen und den aktuellen Wissensstand.

**SCHRITT 2 — OPTIONEN ENTWICKELN**
Erarbeite 3 verschiedene Ansätze für den Fachartikel mit je:
  - Kernidee (1-2 Sätze)
  - Stärke des Ansätzes
  - Schwäche / Risiko
  - Relevanz für die Zielgruppe

**SCHRITT 3 — ENTSCHEIDUNG & BEGRÜNDUNG**
Identifiziere den stärksten Ansatz und begründe die Wahl.

**SCHRITT 4 — VOLLSTÄNDIGE UMSETZUNG**
Entwickle den gewählten Ansatz als fertigen Fachartikel — direkt verwendbar.

**SCHRITT 5 — KRITISCHER REVIEW**
Überprüfe den Artikel auf medizinische Korrektheit, Inkonsistenzen und Schwachstellen.
Optimiere auf Basis dieses Reviews.

### QUELLEN-ARTIKEL
{article_ctx}

### REDAKTIONELLES BRIEFING
{detail_ctx if detail_ctx else '(Standard-Einstellungen — passe Zielgruppe, Tonalität und Format oben an für bessere Ergebnisse)'}

### FORMAT
Klar strukturiert mit Überschriften — professionell, direkt einsetzbar.
Sprache: Deutsch. Medizinisch korrekt aber verständlich.

Eine fehlerhafte Analyse hätte kostspielige Konsequenzen. Nimm dir Zeit für jeden Schritt.
{pro_suffix}

{OUTPUT_FORMAT}'''


def _prompt_tot(article_ctx: str, core_ctx: str, detail_ctx: str,
                pro_suffix: str, collection_name: str,
                experts: Optional[list[tuple[str, str]]] = None) -> str:
    exp = experts or DEFAULT_EXPERTS
    expert_block = '\n'.join(
        f'  -> Experte {i+1} — {name}\n    Perspektive: {pov}'
        for i, (name, pov) in enumerate(exp)
    )

    return f'''### AUFGABE
Entwickle einen fundierten Fachartikel: {collection_name}

### KERNKONTEXT
{core_ctx if core_ctx else '  - Zielgruppe: Praktizierende Ärzte in Deutschland'}

### EXPERTENRUNDE — 3 parallele Denkpfade

{expert_block}

### PROZESS (strikt einhalten)

**SCHRITT 1 — INDIVIDUELLE ANALYSE**
Jeder Experte entwickelt seinen Ansatz für den Artikel unabhängig (max. 200 Wörter).

**SCHRITT 2 — PEER-KRITIK**
Jeder Experte bewertet die Ansätze der anderen beiden:
  -> Stärkste Idee identifizieren.
  -> Kritischste Schwäche identifizieren.
  -> Backtracking-Regel: Erkennt ein Experte, dass sein Ansatz fundamental
     schwächer ist, verwirft er ihn vollständig und schließt sich dem stärksten
     Ansatz an — mit Begründung.

**SCHRITT 3 — SYNTHESE**
Gemeinsame Einigung auf den stärksten kombinierten Ansatz.

**SCHRITT 4 — VOLLSTÄNDIGER ARTIKEL**
Schreibe den fertigen Fachartikel basierend auf der Synthese.

**SCHRITT 5 — METAKOGNITIVER CHECK**
Lies den Artikel nochmals. Identifiziere den wahrscheinlichsten Grund,
warum er medizinisch oder redaktionell schwach sein könnte. Passe an.

### QUELLEN-ARTIKEL
{article_ctx}

### REDAKTIONELLES BRIEFING
{detail_ctx if detail_ctx else '(Standard-Einstellungen — passe Zielgruppe, Tonalität und Format oben an für bessere Ergebnisse)'}
{pro_suffix}

{OUTPUT_FORMAT}'''


def _prompt_persona(article_ctx: str, core_ctx: str, detail_ctx: str,
                    pro_suffix: str, collection_name: str) -> str:
    return f'''### ROLLE
Du bist ein erfahrener Medical Writer und Fachredakteur mit 15+ Jahren Expertise
in der medizinischen Fachjournalistik für esanum, das größte Ärztenetzwerk in Europa.
Du kombinierst tiefes medizinisches Fachverständnis mit exzellenter Leserführung
und SEO-Kompetenz.

### KERNKONTEXT
{core_ctx if core_ctx else '  - Zielgruppe: Praktizierende Ärzte in Deutschland'}

### AUFGABE
Fachartikel '{collection_name}' mit maximaler Qualität und Praxisrelevanz erstellen.

### DEIN VORGEHEN

**1. KURZE ANALYSE (max. 3 Sätze)**
Identifiziere den entscheidenden Hebel — was macht dieses Thema jetzt relevant?

**2. UMSETZUNG**
Liefere den fertigen Fachartikel — direkt kopierbar und publizierbar.

**3. OPTIMIERUNGSVORSCHLÄGE**
2 konkrete Variationen oder Verbesserungen.

**4. SELBSTPRÜFUNG**
Lies aus Sicht der Zielgruppe. Schwachstellen finden und nachbessern.

### QUELLEN-ARTIKEL
{article_ctx}

### REDAKTIONELLES BRIEFING
{detail_ctx if detail_ctx else '(Standard-Einstellungen — passe Zielgruppe, Tonalität und Format oben an für bessere Ergebnisse)'}

### QUALITATSSTANDARDS
  - Konkret statt abstrakt
  - Auf die Zielgruppe zugeschnitten
  - Evidenzbasiert mit klarer Praxis-Relevanz
  - Sprache: Deutsch, medizinisch korrekt, verständlich
{pro_suffix}

{OUTPUT_FORMAT}'''


def _prompt_sc(article_ctx: str, core_ctx: str, detail_ctx: str,
               pro_suffix: str, collection_name: str) -> str:
    return f'''### AUFGABE
Fachartikel '{collection_name}' aus 4 unabhängigen Perspektiven entwickeln.

### KERNKONTEXT
{core_ctx if core_ctx else '  - Zielgruppe: Praktizierende Ärzte in Deutschland'}

### PROZESS

**RUNDE 1 — 4 UNABHÄNGIGE VARIANTEN**
Entwickle 4 vollständig unterschiedliche Ansätze für den Artikel.
Wähle für jede eine andere Strategie, Tonalität oder Priorisierung.

  -> Variante 1: [Differenzierungsfokus benennen, dann ausarbeiten]
  -> Variante 2: [...]
  -> Variante 3: [...]
  -> Variante 4: [...]

**RUNDE 2 — SCORING & RANKING**
| Variante | Fokus | Med. Korrektheit (1-10) | Lesbarkeit (1-10) | SEO-Potenzial (1-10) | Praxis-Relevanz (1-10) | Gesamt |

**RUNDE 3 — FINALE EMPFEHLUNG**
Stärkste Variante oder Hybrid-Version — direkt einsetzbar als fertiger Artikel.

**RUNDE 4 — METAKOGNITIVER CHECK**
Wahrscheinlichster Grund fürs Scheitern -> anpassen.

### QUELLEN-ARTIKEL
{article_ctx}

### REDAKTIONELLES BRIEFING
{detail_ctx if detail_ctx else '(Standard-Einstellungen — passe Zielgruppe, Tonalität und Format oben an für bessere Ergebnisse)'}
{pro_suffix}

{OUTPUT_FORMAT}'''


def _prompt_fs(article_ctx: str, core_ctx: str, detail_ctx: str,
               pro_suffix: str, collection_name: str,
               examples: Optional[list[str]] = None) -> str:
    ex_block = ''
    if examples:
        for i, ex in enumerate(examples[:3], 1):
            if ex and ex.strip():
                ex_block += f'\n**Beispiel {i}:**\n{ex.strip()}\n'

    return f'''### AUFGABE
Fachartikel '{collection_name}' — mit Beispiel-basierter Stilkonsistenz erstellen.

### KERNKONTEXT
{core_ctx if core_ctx else '  - Zielgruppe: Praktizierende Ärzte in Deutschland'}

### FEW-SHOT-METHODIK
Du arbeitest nach dem Few-Shot-Prinzip: Die folgenden Beispiele definieren Ton,
Stil, Format und Qualitätsniveau.

### REFERENZ-BEISPIELE
Analysiere auf: Tonalität, Struktur, Stilmittel, Zielgruppen-Ansprache.
{ex_block if ex_block else '(Keine Beispiele angegeben — verwende esanum-typischen Stil: evidenzbasiert, praxisnah, verständlich)'}

### DEIN VORGEHEN

**1. STIL-ANALYSE (max. 5 Sätze)**
Beschreibe den erkannten Stil.

**2. UMSETZUNG**
Erstelle den Fachartikel im exakt gleichen Stil.

**3. STIL-ABGLEICH**
Vergleiche Punkt für Punkt. Korrigiere Abweichungen.

### QUELLEN-ARTIKEL
{article_ctx}

### REDAKTIONELLES BRIEFING
{detail_ctx if detail_ctx else '(Standard-Einstellungen — passe Zielgruppe, Tonalität und Format oben an für bessere Ergebnisse)'}
{pro_suffix}

{OUTPUT_FORMAT}'''


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

TECHNIQUES = {
    'cot': {
        'name': 'Chain of Thought', 'emoji': '🔗', 'badge': 'Strukturiert',
        'desc': 'Schrittweises Durchdenken — Analyse, Optionen, Entscheidung, Umsetzung, Prüfung',
        'rec': True,
        'help': 'Die KI arbeitet transparent in 5 Schritten: Situation analysieren, Optionen entwickeln, beste wählen, vollständig umsetzen, kritisch prüfen. Besonders geeignet für Studienzusammenfassungen, Hintergrundberichte und Leitlinien-Updates.',
    },
    'tot': {
        'name': 'Tree of Thoughts', 'emoji': '🌳', 'badge': 'Höchste Qualität',
        'desc': '3 Experten erarbeiten parallel Entwürfe, kritisieren sich gegenseitig, einigen sich auf das Beste',
        'rec': False,
        'help': 'Drei KI-Fachleute (z.B. Medical Writer, SEO-Stratege, Fachredakteur) entwickeln unabhängig voneinander Entwürfe, bewerten sich gegenseitig und fassen die stärksten Ideen zusammen. Erste Wahl bei Übersichtsartikeln und komplexen Themen.',
    },
    'persona': {
        'name': 'Experten-Persona', 'emoji': '🎭', 'badge': 'Schnell & stilsicher',
        'desc': 'Die KI schreibt als erfahrener Medical Writer mit 15+ Jahren Redaktionserfahrung',
        'rec': False,
        'help': 'Die KI übernimmt die Rolle eines erfahrenen esanum-Redakteurs und schreibt direkt im passenden Ton. Die schnellste Technik — besonders geeignet für Nachrichten, Meinungsbeiträge und Newsletter-Aufmacher.',
    },
    'sc': {
        'name': 'Multi-Perspektiven', 'emoji': '🔄', 'badge': 'Maximale Vielfalt',
        'desc': '4 unterschiedliche Artikelvarianten entstehen parallel — die beste wird per Bewertungsmatrix ausgewählt',
        'rec': False,
        'help': 'Die KI erstellt 4 komplett verschiedene Artikelversionen (z.B. sachlich, erzählerisch, datengetrieben, praxisnah), vergleicht sie anhand einer Bewertungstabelle und liefert die stärkste. Gut geeignet für Ankündigungen und Themen mit mehreren Blickwinkeln.',
    },
    'fs': {
        'name': 'Few-Shot', 'emoji': '📝', 'badge': 'Stilvorlage',
        'desc': '1–3 Beispieltexte vorgeben — die KI übernimmt Ton, Aufbau und Stil',
        'rec': False,
        'help': 'Du lieferst bestehende esanum-Artikel als Vorlage. Die KI analysiert Schreibstil, Struktur und Tonalität und schreibt den neuen Artikel im gleichen Format. Ideal, um einen einheitlichen Redaktionsstil beizubehalten.',
    },
}


def build_article_prompt(
    articles: list[dict],
    briefing: dict,
    collection_name: str,
    technique: str = 'cot',
    pro_modes: Optional[set[str]] = None,
    custom_experts: Optional[list[tuple[str, str]]] = None,
    fs_examples: Optional[list[str]] = None,
) -> str:
    '''Build a complete prompt for article generation.

    Args:
        articles: List of article dicts (title, abstract, summary_de, journal, pub_date)
        briefing: Briefing dict from collection (target_audience, article_format, tonality, etc.)
        collection_name: Name of the collection
        technique: Prompting technique (cot, tot, persona, sc, fs)
        pro_modes: Set of active pro-mode IDs (max 3)
        custom_experts: Override for ToT experts [(name, perspective), ...]
        fs_examples: Example texts for Few-Shot technique

    Returns:
        Complete prompt string ready for LLM API call.
    '''
    article_ctx = _build_article_context(articles)
    core_ctx, detail_ctx = _build_briefing_context(briefing or {})
    pro_suffix = _build_pro_mode_suffix(pro_modes or set())

    if technique == 'cot':
        return _prompt_cot(article_ctx, core_ctx, detail_ctx, pro_suffix, collection_name)
    elif technique == 'tot':
        return _prompt_tot(article_ctx, core_ctx, detail_ctx, pro_suffix,
                           collection_name, custom_experts)
    elif technique == 'persona':
        return _prompt_persona(article_ctx, core_ctx, detail_ctx, pro_suffix, collection_name)
    elif technique == 'sc':
        return _prompt_sc(article_ctx, core_ctx, detail_ctx, pro_suffix, collection_name)
    elif technique == 'fs':
        return _prompt_fs(article_ctx, core_ctx, detail_ctx, pro_suffix,
                          collection_name, fs_examples)
    else:
        return _prompt_cot(article_ctx, core_ctx, detail_ctx, pro_suffix, collection_name)

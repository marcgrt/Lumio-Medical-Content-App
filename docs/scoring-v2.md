# LUMIO Relevanz-Scoring v2 — Vollständiges Modell

## Designprinzip

Dieses Scoring bewertet: **Wie wahrscheinlich ist es, dass ein praktizierender Arzt diesen Inhalt lesen will, davon profitiert und ihn weiterempfiehlt?**

Wissenschaftliche Studien und journalistische Artikel werden auf derselben Skala bewertet. Ein brillant recherchierter Fachartikel kann denselben Score erreichen wie eine Meta-Analyse — wenn er für Ärzte genauso relevant, fundiert und ansprechend aufbereitet ist.

---

## Scoring-Architektur

Sechs Dimensionen, Summe = 0–100 Punkte.

| # | Dimension | Max | Anteil | Kernfrage |
|---|-----------|-----|--------|-----------|
| 1 | Klinische Handlungsrelevanz | 20 | 20 % | Kann der Arzt danach konkret etwas ändern? |
| 2 | Evidenz- & Recherchetiefe | 20 | 20 % | Wie methodisch solide ist die Grundlage? |
| 3 | Thematische Zugkraft | 20 | 20 % | Wollen Ärzte das lesen, teilen, diskutieren? |
| 4 | Neuigkeitswert | 16 | 16 % | Bringt das genuinely neue Information? |
| 5 | Quellenautorität | 12 | 12 % | Wie vertrauenswürdig ist die Quelle? |
| 6 | Aufbereitungsqualität | 12 | 12 % | Wie gut ist der Inhalt für Ärzte aufbereitet? |

**Warum diese Gewichtung:**
Die drei stärksten Dimensionen (je 20 %) messen Praxisnutzen, Fundierung und Engagement — die drei Faktoren, die redaktionelle Entscheidungen bei esanum treiben sollten. Neuigkeitswert (16 %) belohnt Aktualität, ohne Einordnungen bekannter Themen zu bestrafen. Quellenautorität und Aufbereitungsqualität (je 12 %) sind Korrektive: Sie verhindern, dass unseriöse Quellen hochscoren, und belohnen ärztegerechte Darstellung — ohne dass allein der Journalname den Score dominiert.

---

## Dimension 1: Klinische Handlungsrelevanz (0–20)

**Leitfrage:** Ändert dieser Inhalt, was ein Arzt morgen in der Praxis, Klinik oder im beruflichen Alltag tut?

### Scoring-Stufen

**18–20 — Sofortige Handlungsänderung**
Der Arzt muss nach dem Lesen aktiv werden. Beispiele:
- Rote-Hand-Brief / Rückruf eines häufig verordneten Medikaments
- Neue Dosierungsempfehlung für eine Standardtherapie
- Neuer diagnostischer Algorithmus, der bestehenden ersetzt
- Gesetzesänderung mit unmittelbarer Auswirkung auf Praxisabläufe (z.B. neue Abrechnungsziffer, Dokumentationspflicht)
- Zulassungsentzug oder neue Kontraindikation

**14–17 — Handlungsänderung wahrscheinlich, aber nicht sofort**
Der Arzt wird sein Vorgehen anpassen, aber nicht am nächsten Morgen. Beispiele:
- Neue Leitlinie, die in Wochen/Monaten in die Praxis diffundiert
- Zulassung einer neuen Therapieoption (verfügbar, aber Einarbeitung nötig)
- Relevante Änderung der Vergütungsstruktur (wirkt in nächster Abrechnungsperiode)
- Große RCT, die aktuelle Erstlinientherapie bestätigt oder in Frage stellt

**9–13 — Beeinflusst Entscheidungen indirekt**
Kein konkreter Handlungsschritt, aber verändert das ärztliche Denken. Beispiele:
- Registerdaten zu Langzeit-Outcomes einer gängigen Therapie
- Vergleichsstudien zwischen zwei etablierten Standardtherapien
- Epidemiologische Trends, die Screening-Praxis beeinflussen könnten
- Gesundheitspolitische Entwicklungen mit mittelbaren Auswirkungen auf Praxisorganisation

**4–8 — Hintergrundwissen ohne direkte Konsequenz**
Fachlich interessant, aber kein Arzt ändert deswegen seinen Alltag. Beispiele:
- Phase-I/II-Daten (zu früh für Praxis)
- Grundlagenforschung mit therapeutischem Potenzial in >5 Jahren
- Epidemiologische Daten ohne Handlungsimplikation
- Rein akademische Debatte ohne Praxisbezug

**0–3 — Keine erkennbare ärztliche Relevanz**
Industrienews ohne klinischen Bezug, reine Forschungspolitik, administrative Themen ohne Arztbezug.

### Bewertungshinweise für das LLM
- Gesundheitspolitik KANN 18–20 erreichen, wenn sie den Praxisalltag direkt betrifft (neue Pflichten, neue Abrechnungsregeln).
- Nicht verwechseln: „Betrifft das Gesundheitswesen" ≠ „Muss der Arzt etwas tun". Ein Artikel über steigende Klinikkosten = 6–9. Ein Artikel über eine neue Dokumentationspflicht ab nächstem Quartal = 16–18.
- Breite der Betroffenheit berücksichtigen: Betrifft der Inhalt 80 % aller Ärzte oder 2 %? Bei gleicher Handlungsrelevanz den breiteren Inhalt höher scoren.

---

## Dimension 2: Evidenz- & Recherchetiefe (0–20)

**Leitfrage:** Wie methodisch solide ist die Informationsgrundlage — egal ob Studie oder Journalismus?

Diese Dimension bewertet NICHT den Studientyp, sondern die Qualität der Beweisführung. Ein investigativer Journalismusbeitrag mit fünf unabhängigen Quellen, Datenanalyse und Gegenposition steht einer gut gemachten RCT in nichts nach.

### Scoring-Stufen

**18–20 — Exzellente Evidenz oder Recherchetiefe**

Für Studien:
- Meta-Analyse / Systematic Review mit transparenter Methodik, PRISMA-konform
- Große, multizentrische RCT mit harten klinischen Endpunkten und adäquater Power
- Cochrane Review

Für journalistische Artikel:
- Investigativ recherchiert mit ≥4 unabhängigen Quellen
- Eigene Datenanalyse oder exklusive Daten
- Gegenpositionen eingeholt und abgewogen
- Transparente Methodik (Quellen benannt, Limitationen adressiert)
- Experteneinschätzung plus Primärdaten

**14–17 — Starke Evidenz oder solide Recherche**

Für Studien:
- RCT mit relevantem Endpunkt, aber z.B. monozentrisch oder mit Surrogatendpunkt
- Große Kohortenstudie (>10.000 Teilnehmer) mit adäquater Adjustierung

Für journalistische Artikel:
- 2–3 unabhängige Quellen, darunter mindestens eine Primärquelle
- Strukturierte Argumentation mit Faktengrundlage
- Einordnung durch mindestens einen zitierten Experten
- Klare Trennung von Fakt und Meinung

**9–13 — Moderate Evidenz oder Standardrecherche**

Für Studien:
- Kleinere Kohorten-/Registerstudien
- Retrospektive Analysen mit methodischen Einschränkungen
- Post-hoc-Analysen großer Studien

Für journalistische Artikel:
- 1–2 Quellen, überwiegend Wiedergabe von Aussagen
- Korrekte Darstellung, aber keine eigene Analyse
- Übersichtsartikel, der bekannte Evidenz kompetent zusammenfasst

**4–8 — Schwache Evidenz oder dünne Recherche**

Für Studien:
- Fallberichte, Fallserien
- Pilotstudien mit <50 Teilnehmern
- In-vitro- / Tiermodelldaten als Hauptaussage

Für journalistische Artikel:
- Einzelquelle, keine Gegenposition
- Überwiegend Meinungsstück ohne Datengrundlage
- Wiedergabe einer Pressemitteilung ohne Einordnung

**0–3 — Keine belastbare Grundlage**
Unbelegte Behauptungen, Pressemitteilungen ohne Faktencheck, reine Spekulation, anekdotische Evidenz ohne Kontext.

### Bewertungshinweise für das LLM
- Bei Studien: Methodische Qualität zählt, nicht nur der Studientyp. Eine schlecht gemachte Meta-Analyse mit hohem Bias-Risiko bekommt 10–13, nicht automatisch 18+.
- Bei Journalismus: Nach Quellenvielfalt, Datengrundlage und Gegenposition schauen. Drei zitierte Experten sind wertvoller als ein einzelner Professor.
- Nicht jeden Fachartikel mit Expertenzitat automatisch bei 14+ einordnen. Die Einordnung muss substanziell sein, nicht nur ein Zwei-Satz-Statement.
- Transparenz der Methodik belohnen: Wer seine Quellen und Limitationen benennt, bekommt mehr Punkte.

---

## Dimension 3: Thematische Zugkraft (0–20)

**Leitfrage:** Wie stark wollen Ärzte diesen Inhalt lesen, teilen und diskutieren?

Diese Dimension misst das Engagement-Potenzial. Sie bewertet NICHT, ob ein Thema klinisch wichtig ist (das macht Dimension 1), sondern ob es Ärzte emotional oder beruflich packt.

### Scoring-Stufen

**18–20 — Maximale Zugkraft: Ärzte reden morgen darüber**
Themen, die in der Ärzteschaft starke Reaktionen auslösen:
- Existenzielle Berufsthemen: Ärztemangel, Klinikschließungen, Honorarreform, Arbeitszeitgesetz, Kassenzulassung, Regress
- Sicherheitsalarme bei häufig verordneten Medikamenten oder Impfstoffen
- Kontroverse, die die Ärzteschaft spaltet (z.B. Homöopathie-Debatte, Sterbehilfe)
- Medienwirksame Fälle mit berufsethischer Dimension

**14–17 — Starke Zugkraft: Wird im Kollegenkreis besprochen**
- Burnout, Work-Life-Balance, Vereinbarkeit im Arztberuf
- Digitalisierung mit direktem Praxisbezug (ePA, TI-Störungen, KI in der Diagnostik)
- Bürokratieabbau oder -aufbau
- Patientenkommunikation, schwierige Gesprächssituationen
- Neue, kontroverse Therapieansätze bei häufigen Erkrankungen (z.B. GLP-1-Agonisten bei Adipositas)
- Prominente Erkrankungen / Todesfälle mit medizinischer Lernkomponente

**9–13 — Moderate Zugkraft: Wird gelesen, aber selten geteilt**
- Leitlinien-Updates ohne dramatische Änderungen
- Kongressberichte und Studienzusammenfassungen
- Solide Fortbildungsinhalte zu Standardthemen
- Gesundheitspolitik ohne direkte Betroffenheit des einzelnen Arztes

**4–8 — Geringe Zugkraft: Nur für Spezialisten interessant**
- Seltene Erkrankungen ohne aktuellen Medienkontext
- Nischen-Fachthemen, die <5 % der Ärzteschaft betreffen
- Technische Methodendiskussionen (Studiendesign, Statistik)
- Forschungsergebnisse ohne erkennbare klinische Perspektive

**0–3 — Keine Zugkraft**
Industrienews ohne ärztlichen Bezug, administrative Mitteilungen, rein akademische Dispute.

### Bewertungshinweise für das LLM
- Zugkraft ≠ Wichtigkeit. Eine Leitlinienänderung kann klinisch wichtig sein (Dimension 1: hoch), aber wenig Zugkraft haben, wenn sie erwartbar war und ein Nischenfach betrifft.
- Umgekehrt: Ein Artikel über Ärztemangel ändert nicht das Verhalten am Patienten (Dimension 1: niedrig), hat aber enorme Zugkraft.
- Mediale Aktualität erhöht die Zugkraft. Eine seltene Erkrankung bekommt 14+ Zugkraft, wenn sie gerade durch einen prominenten Fall in der Öffentlichkeit steht.
- Kontroversität erhöht die Zugkraft. Wenn ein Thema die Ärzteschaft spaltet, steigt das Engagement.
- Breite der betroffenen Fachgruppen berücksichtigen: Ein Thema, das Hausärzte UND Internisten UND Chirurgen betrifft, hat mehr Zugkraft als eines, das nur Nephrologen interessiert.

---

## Dimension 4: Neuigkeitswert (0–16)

**Leitfrage:** Bringt dieser Inhalt genuinely neue Information in die ärztliche Wissenslandschaft?

### Scoring-Stufen

**14–16 — Erstmalig, überraschend oder paradigmenwechselnd**
- Erstpublikation einer großen Studie
- Unerwartetes Ergebnis, das bisheriges Wissen revidiert
- Erste Leitlinie zu einem bisher unleitlinierten Thema
- Neuartige Therapie/Diagnostik (First-in-Class)
- Exklusive Recherche mit neuen Fakten, die bisher unbekannt waren

**10–13 — Relevantes Update oder neue Perspektive**
- Phase-III-Ergebnisse nach bekannten Phase-II-Daten
- Zulassungsentscheidung nach erwarteten Studiendaten
- Wichtige Subgruppenanalyse mit klinischer Konsequenz
- Neue Leitlinienversion mit moderaten Änderungen
- Journalistischer Artikel, der bekanntes Thema mit neuen Daten oder neuem Blickwinkel aufarbeitet

**5–9 — Bestätigung, Einordnung oder Zusammenfassung**
- Studie bestätigt bekannte Praxis
- Systematic Review ohne überraschende Ergebnisse
- Kongressvortrag, der vorab publizierte Daten wiederholt
- Guter Übersichtsartikel, der Bekanntes kompetent zusammenfasst

**0–4 — Nichts Neues**
- Wiedergabe bereits berichteter Inhalte
- Redundante Berichterstattung über bekannte Fakten
- Thema wurde in den letzten 4 Wochen bereits in gleicher Tiefe behandelt

### Bewertungshinweise für das LLM
- Neuigkeitswert ist relativ zum Wissensstand der Zielgruppe. Eine Studie, die für Forscher banal ist, kann für Allgemeinmediziner neu sein, wenn sie bisher nur in Spezialistenjournalen publiziert wurde.
- „Überraschend" schlägt „erstmalig": Ein erwartetes Phase-III-Ergebnis (10–12) schlägt NICHT ein überraschendes Kohortenergebnis (14–16).
- Einordnungs-Journalismus kann 8–12 erreichen, wenn der Blickwinkel frisch ist. „Die 10. Zusammenfassung derselben Studie" dagegen liegt bei 0–4.
- Exklusive journalistische Recherche, die neue Fakten zutage fördert, bekommt 14–16, gleichwertig mit einer Erstpublikation.

---

## Dimension 5: Quellenautorität (0–12)

**Leitfrage:** Wie vertrauenswürdig ist die Quelle, aus der dieser Inhalt stammt?

### Scoring-Stufen

**11–12 — Höchste Autorität**
- NEJM, Lancet, JAMA, BMJ, Nature Medicine, Nature, Science
- Offizielle Behördenkommunikation: BfArM, EMA, FDA, RKI, AWMF, PEI, WHO
- Cochrane Library

**9–10 — Hohe Autorität**
- Führende Fachjournale: Circulation, JCO, European Heart Journal, Annals of Internal Medicine, Gut, Blood
- Deutsches Ärzteblatt (redaktionelle Beiträge, nicht Kleinanzeigen)
- Offizielle Mitteilungen großer Fachgesellschaften (DGK, DGIM, DGHO etc.)

**7–8 — Etablierte Autorität**
- Solide Fachjournale mit Impact Factor >5
- Ärzte Zeitung (eigene Recherchebeiträge)
- Pharmazeutische Zeitung
- Große internationale Fachmedien (Medscape, BMJ Best Practice)

**5–6 — Anerkannte Quellen**
- Peer-reviewed Journale mit Impact Factor 2–5
- Fachgesellschafts-Mitteilungen kleinerer Gesellschaften
- Spezialisierte medizinische Nachrichtenportale mit redaktioneller Kontrolle
- Kongressabstracts großer Kongresse (ASCO, ESC, AHA, EASD, DGP etc.)

**3–4 — Eingeschränkt vertrauenswürdig**
- Peer-reviewed Journale mit niedrigem IF (<2)
- Preprints auf medRxiv, bioRxiv (nicht peer-reviewed, aber wissenschaftliche Plattform)
- Regionale/lokale Medizinmedien

**0–2 — Geringe Autorität**
- Pressemitteilungen ohne Primärquelle
- Unternehmens-PR, Marketingmaterial
- Blogs, Social Media ohne redaktionelle Kontrolle
- Nicht-medizinische Medien ohne Fachexpertise

### Bewertungshinweise für das LLM
- Quellenautorität ist ein Vertrauenssignal, kein Qualitätsgarant. Ein schlechter Artikel im NEJM bleibt ein schlechter Artikel — aber die Quelle ist trotzdem vertrauenswürdig. Deshalb ist diese Dimension auf 12 Punkte begrenzt.
- Ärzteblatt-Originalbeiträge (redaktionell) bekommen 9–10. Ärzteblatt-Nachrichten (Agenturmeldungen) bekommen 7–8.
- Bei Mehrfachquellen: Die stärkste Primärquelle zählt. Ein Ärzte-Zeitung-Artikel, der eine Lancet-Studie einordnet, bekommt die Autorität der Ärzte Zeitung (7–8), NICHT der Lancet. Die Lancet-Qualität fließt in Dimension 2 ein.
- Preprints pauschal bei 3–4, unabhängig von der Autorenreputation. Keine Peer-Review = eingeschränktes Vertrauen.

---

## Dimension 6: Aufbereitungsqualität (0–12)

**Leitfrage:** Wie gut ist dieser Inhalt für praktizierende Ärzte aufbereitet?

Diese Dimension bewertet, ob der Inhalt so präsentiert wird, dass ein Arzt den Kern in angemessener Zeit erfassen und für seine Praxis nutzen kann.

### Scoring-Stufen

**11–12 — Exzellente Aufbereitung für die Zielgruppe**
- Klare Kernbotschaft in den ersten Absätzen erkennbar
- Klinische Implikationen explizit benannt und kontextualisiert
- Zahlen verständlich dargestellt: NNT, absolute Risikoreduktion, nicht nur p-Werte oder relative Risiken
- Strukturiert und scanbar (Zwischenüberschriften, Kernaussagen hervorgehoben)
- Visuelle Aufbereitung bei komplexen Daten (Tabellen, Infografiken)
- Bei Journalismus: Praxistipps, Take-Home-Messages, Checklisten

**8–10 — Gute Aufbereitung**
- Kernbotschaft erkennbar, aber nicht sofort
- Strukturiertes Abstract vorhanden (IMRAD oder vergleichbar)
- Wichtigste Endpunkte klar dargestellt
- Gut lesbar, aber ohne besondere didaktische Elemente
- Bei Journalismus: Verständliche Sprache, logischer Aufbau

**5–7 — Akzeptable Aufbereitung**
- Fachlich korrekt, aber sperrig oder akademisch überformuliert
- Abstract vorhanden, aber ohne klinische Einordnung
- Relevante Details müssen im Volltext gesucht werden
- Keine klinischen Implikationen formuliert — Leser muss selbst ableiten

**2–4 — Mangelhafte Aufbereitung**
- Schwer zugänglich, keine Zusammenfassung
- Wesentliche Informationen fehlen (z.B. Studiengröße, Endpunkte unklar)
- Paywall mit unzureichender Vorschau (<80 Wörter Abstract)
- Unstrukturiert, kein klarer roter Faden

**0–1 — Nicht verwertbar**
- Kein Abstract, kein Volltext zugänglich
- Reine Paywall ohne inhaltliche Vorschau
- Automatisch übersetzter Text ohne Qualitätskontrolle
- Technisch defekter oder unvollständiger Inhalt

### Bewertungshinweise für das LLM
- Diese Dimension gleicht den Nachteil akademischer Paper gegenüber journalistischen Beiträgen aus. Ein Nature-Paper mit 30-seitigem Supplement und kryptischem Abstract verliert hier Punkte gegenüber einem Ärzteblatt-Beitrag, der dieselbe Studie für Kliniker einordnet.
- Absolute Zahlen belohnen. Wenn ein Artikel nur relative Risikoreduktion nennt (z.B. „35 % weniger Herzinfarkte"), aber keine absoluten Zahlen (NNT, absolute Risikodifferenz): maximal 8 Punkte.
- Paywall ist KEIN automatischer Malus, wenn ein informatives Abstract vorhanden ist (>150 Wörter mit Kerndaten). Paywall OHNE brauchbares Abstract dagegen: maximal 3 Punkte.

---

## Kalibrierungsbeispiele

Diese Beispiele definieren Ankerpunkte für konsistentes Scoring. Das LLM soll sie als Referenz verwenden.

### Beispiel A: NEJM Meta-Analyse — Neue Erstlinientherapie bei Typ-2-Diabetes

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 19 | Direkte Therapieänderung für Millionen Patienten |
| Evidenz & Recherche | 19 | Meta-Analyse, PRISMA-konform, harte Endpunkte |
| Zugkraft | 15 | Diabetes ist häufig, aber Leitlinienänderung = erwartbar, kein emotionales Thema |
| Neuigkeitswert | 15 | Erstmalige Synthese, ändert Empfehlung |
| Quellenautorität | 12 | NEJM |
| Aufbereitung | 7 | Akademisch, dichte Statistik, keine klinische Einordnung für Generalisten |
| **Gesamt** | **87** | |

### Beispiel B: Ärzteblatt Investigativ — Folgen der Krankenhausreform für niedergelassene Ärzte

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 17 | Betrifft Praxisorganisation, Überweisungswege, Notaufnahme-Zugang |
| Evidenz & Recherche | 16 | Eigene Datenanalyse, 4 Experteninterviews, Gegenpositionen, Regionaldaten |
| Zugkraft | 19 | Existenzielles Berufsthema, betrifft fast alle Ärzte |
| Neuigkeitswert | 12 | Neue Analyse einer bekannten Entwicklung, frischer Blickwinkel |
| Quellenautorität | 9 | Ärzteblatt (Originalbeitrag) |
| Aufbereitung | 11 | Praxisnah, verständlich, Take-Home-Messages, Infografik |
| **Gesamt** | **84** | |

### Beispiel C: Ärzte Zeitung — Rote-Hand-Brief zu Ibuprofen-Retard (hypothetisch)

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 20 | Sofortige Handlungsänderung für jeden Verordner |
| Evidenz & Recherche | 11 | Behördenquelle zitiert, aber keine eigenständige Analyse |
| Zugkraft | 18 | Ibuprofen = eines der meistverordneten Medikamente, betrifft fast alle |
| Neuigkeitswert | 16 | Erstmalige Sicherheitswarnung |
| Quellenautorität | 7 | Ärzte Zeitung (die BfArM-Quelle stärkt Dim. 2, nicht Dim. 5) |
| Aufbereitung | 9 | Klar, direkt, Kerninfo sofort erfassbar |
| **Gesamt** | **81** | |

### Beispiel D: Case Report in mittelrangigem Journal — Seltene UAW eines Nischenmedikaments

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 4 | Einzelfall, Nischenmedikament, kaum Generalisierung |
| Evidenz & Recherche | 5 | Ein Fall, keine Kontrollgruppe |
| Zugkraft | 4 | Betrifft <1 % der Ärzte, kein aktueller Medienkontext |
| Neuigkeitswert | 8 | Erstbeschreibung dieser UAW, aber geringe Tragweite |
| Quellenautorität | 4 | IF 2.5 Journal |
| Aufbereitung | 6 | Standardformat, Abstract vorhanden |
| **Gesamt** | **31** | |

### Beispiel E: Pressemitteilung Pharma — Phase-II-Daten Onkologie

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 3 | Phase II, frühestens in 3–5 Jahren praxisrelevant |
| Evidenz & Recherche | 4 | Selektive Datenpräsentation, keine Peer-Review, keine Gegenposition |
| Zugkraft | 7 | Onkologie = hohes Grundinteresse, aber Phase-II = zu früh für Begeisterung |
| Neuigkeitswert | 11 | Neue Daten, aber erwartbares Studiendesign |
| Quellenautorität | 1 | Pressemitteilung |
| Aufbereitung | 4 | PR-Sprache, selektive Darstellung, keine klinische Einordnung |
| **Gesamt** | **30** | |

### Beispiel F: Nature Medicine — Grundlagenforschung Alzheimer (neuer Mechanismus)

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 5 | Kein therapeutischer Ansatz in Sichtweite |
| Evidenz & Recherche | 18 | Exzellente Methodik, reproduziert in 3 Modellen |
| Zugkraft | 14 | Alzheimer = hohes Patienteninteresse, Medienecho |
| Neuigkeitswert | 15 | Genuinely neuer Mechanismus |
| Quellenautorität | 12 | Nature Medicine |
| Aufbereitung | 5 | Hochspezialisiert, nur für Neurowissenschaftler voll verständlich |
| **Gesamt** | **69** | |

### Beispiel G: Ärzteblatt Fortbildung — CME-Artikel Herzinsuffizienz-Management

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 14 | Aktuelles Therapieschema systematisch aufbereitet |
| Evidenz & Recherche | 13 | Guter Review, fasst aktuelle Evidenz korrekt zusammen, keine eigene Forschung |
| Zugkraft | 11 | Herzinsuffizienz = häufig, aber CME-Routine-Update, keine Kontroverse |
| Neuigkeitswert | 6 | Zusammenfassung bekannter Evidenz, keine neuen Daten |
| Quellenautorität | 9 | Ärzteblatt |
| Aufbereitung | 12 | CME-optimiert: Lernziele, Kernaussagen, Praxistipps, Selbsttest |
| **Gesamt** | **65** | |

### Beispiel H: Medscape-Beitrag — Burnout unter Klinikärzten (aktuelle Umfrage)

| Dimension | Score | Begründung |
|-----------|-------|------------|
| Handlungsrelevanz | 8 | Kein direkter Handlungsschritt am Patienten, aber berufliche Selbstreflexion |
| Evidenz & Recherche | 12 | Eigene Umfrage mit 3.000 Teilnehmern, methodisch solide, Vergleichsdaten |
| Zugkraft | 18 | Emotionales Kernthema, hohe Identifikation, wird geteilt |
| Neuigkeitswert | 11 | Neue Umfragedaten, Trend bestätigt sich |
| Quellenautorität | 7 | Medscape |
| Aufbereitung | 10 | Gut visualisiert, Infografiken, klare Kernaussagen |
| **Gesamt** | **66** | |

---

## Score-Stufen (Anzeige in der App)

| Stufe | Bereich | Label | Bedeutung |
|-------|---------|-------|-----------|
| 🟢 Grün | ≥70 | TOP | Hohe Relevanz, starke Grundlage, Praxisbezug — Redaktions-Priorität |
| 🟡 Gelb | 45–69 | RELEVANT | Solider Inhalt, selektiv aufgreifen — abhängig von Kapazität und Aktualität |
| ⚪ Grau | <45 | MONITOR | Nachrichtenwert oder Nischenthema — nur bei besonderem Anlass aufgreifen |

**Warum die Schwellen angepasst wurden:**
Im v1-Modell lag Grün bei ≥65. Im neuen Modell sind die Dimensionen so kalibriert, dass Scores gleichmäßiger verteilt sind. Die Grün-Schwelle bei 70 verhindert, dass zu viele mittelmäßige Artikel als Top markiert werden. Gelb beginnt bei 45 statt 40, weil die Kalibrierungsbeispiele zeigen, dass Artikel unter 45 selten redaktionellen Mehrwert bieten.

---

## LLM-Prompt-Template

Der folgende Prompt wird an das Scoring-LLM übergeben. Variablen in `{{geschweiften Klammern}}` werden dynamisch befüllt.

```
Du bist ein medizinischer Relevanz-Scorer für eine Ärzteplattform mit 369.000 registrierten Ärzten in Deutschland.

Bewerte den folgenden Artikel in 6 Dimensionen. Vergib für jede Dimension einen Score UND eine Begründung in 1–2 Sätzen.

DIMENSIONEN:
1. Klinische Handlungsrelevanz (0–20): Kann ein Arzt nach dem Lesen konkret etwas anders machen?
2. Evidenz- & Recherchetiefe (0–20): Wie methodisch solide ist die Grundlage — egal ob Studie oder Journalismus?
3. Thematische Zugkraft (0–20): Wie stark wollen Ärzte das lesen, teilen und diskutieren?
4. Neuigkeitswert (0–16): Bringt das genuinely neue Information?
5. Quellenautorität (0–12): Wie vertrauenswürdig ist die Quelle?
6. Aufbereitungsqualität (0–12): Wie gut für Ärzte aufbereitet?

WICHTIGE REGELN:
- Wissenschaftliche Studien und journalistische Artikel werden auf DERSELBEN Skala bewertet.
- Ein investigativer Ärzteblatt-Beitrag KANN denselben Score erreichen wie eine NEJM-Studie.
- Bewerte die QUALITÄT der Beweisführung, nicht den Studientyp.
- Quellenautorität ist ein Vertrauenssignal (max 12 Punkte), kein dominanter Faktor.
- Zugkraft misst Engagement-Potenzial bei Ärzten, nicht klinische Wichtigkeit.

KALIBRIERUNGS-ANKER:
- NEJM Meta-Analyse, neue Erstlinientherapie Diabetes: ~87
- Ärzteblatt investigativ, Krankenhausreform-Folgen für Ärzte: ~84
- Rote-Hand-Brief häufiges Medikament (Ärzte Zeitung): ~81
- Nature Medicine Grundlagenforschung Alzheimer: ~69
- Ärzteblatt CME Herzinsuffizienz: ~65
- Medscape Burnout-Umfrage Klinikärzte: ~66
- Case Report seltene UAW, Nischenjornal: ~31
- Pharma-Pressemitteilung Phase II: ~30

{{FEEDBACK_EXAMPLES}}

ARTIKEL:
Quelle: {{source}}
Journal: {{journal}}
Titel: {{title}}
Abstract/Text: {{abstract}}
Datum: {{date}}
DOI: {{doi}}

Antworte AUSSCHLIESSLICH in diesem JSON-Format:
{
  "scores": {
    "clinical_action_relevance": {"score": 0, "reason": ""},
    "evidence_depth": {"score": 0, "reason": ""},
    "topic_appeal": {"score": 0, "reason": ""},
    "novelty": {"score": 0, "reason": ""},
    "source_authority": {"score": 0, "reason": ""},
    "presentation_quality": {"score": 0, "reason": ""}
  },
  "total_score": 0,
  "tier": "TOP|RELEVANT|MONITOR",
  "one_line_summary": "Kernaussage in einem Satz für die Redaktion"
}
```

---

## Feedback-Kalibrierung

Wenn genug Approve/Reject-Entscheidungen der Redaktion vorliegen, werden diese als Few-Shot-Beispiele in den `{{FEEDBACK_EXAMPLES}}`-Block injiziert:

```
REDAKTIONELLE REFERENZEN (lerne die redaktionelle Linie aus diesen Beispielen):

APPROVED (Score sollte ≥60 sein):
- "Neue S3-Leitlinie Asthma: Biologika-Einsatz ab Stufe 4" → Score: 78
- "Ärztemangel: Warum junge Mediziner die Klinik verlassen" → Score: 72

REJECTED (Score sollte <55 sein):
- "Pharmaunternehmen X meldet Umsatzwachstum" → Score: 22
- "Phase-I-Studie zeigt Verträglichkeit neuer Substanz" → Score: 34
```

Die Schwellenwerte (≥60 für Approved, <55 für Rejected) werden dynamisch angepasst, sobald >50 Entscheidungen vorliegen.

---

## Migration von v1 zu v2

### Was entfällt
- Gewichtete Formel des regelbasierten Scorings (Studiendesign-Score, Keyword-Boost, Arztrelevanz-Score)
- Separater Journal-Tier-Score als dominante Dimension (30 % → jetzt 12 % Quellenautorität)
- Exponentielle Aktualitäts-Abklingfunktion (jetzt in Neuigkeitswert integriert, bewertet inhaltliche Neuigkeit statt kalendarisches Alter)
- Boni/Mali-System (Interdisziplinär-Bonus, Open-Access-Bonus, Paywall-Malus etc.)

### Was erhalten bleibt
- KI-Scoring als primäre Methode
- Feedback-Kalibrierung über redaktionelle Entscheidungen
- Fachgebiets-Erkennung (Specialty Classification) — unverändert
- Score-Stufen-System (Grün/Gelb/Grau) mit angepassten Schwellen

### Was sich ändert
- 5 → 6 Dimensionen
- Studientyp ist keine eigene Dimension mehr, sondern fließt in Evidenz- & Recherchetiefe ein
- Thematische Zugkraft als neue Dimension (war vorher nur „Zielgruppen-Fit")
- Aufbereitungsqualität als neue Dimension (war vorher nur über IMRAD-Bonus adressiert)
- Kalibrierungsbeispiele fest im Prompt verankert
- Grün-Schwelle von 65 auf 70 angehoben
- Gelb-Schwelle von 40 auf 45 angehoben

---

## Regelbasierter Fallback (vereinfacht)

Für den Fall, dass das LLM nicht verfügbar ist, existiert ein vereinfachter regelbasierter Scorer. Dieser produziert Näherungswerte und wird in der App als "geschätzt" markiert.

| Dimension | Regelbasierte Annäherung |
|-----------|--------------------------|
| Handlungsrelevanz | Keyword-Matching: Therapie/Dosierung/Leitlinie → hoch; Grundlagenforschung → niedrig |
| Evidenz & Recherche | Studiendesign-Keywords + Quellenzählung im Abstract |
| Zugkraft | Themenliste mit festen Scores (aus Engagement-Daten) |
| Neuigkeitswert | Kombination aus Publikationsdatum + Neuigkeits-Keywords |
| Quellenautorität | Journal-Tier-Liste (vereinfacht auf 5 Stufen) |
| Aufbereitung | Abstract-Länge + IMRAD-Erkennung + Paywall-Check |

Der Fallback-Score wird parallel zum LLM-Score berechnet und im Breakdown als `rule_based_score_v2` gespeichert.

"""Template-based summarizer (Option A — no LLM required)."""

from src.models import Article


def generate_template_summary(article: Article) -> str:
    """Generate a structured German summary from title + abstract."""
    title = article.title or "Kein Titel"
    abstract = article.abstract or ""
    study = article.study_type or ""
    journal = article.journal or "Unbekannte Quelle"

    # Extract first meaningful sentence from abstract
    first_sentence = ""
    if abstract:
        # Split on period followed by space or end
        sentences = [s.strip() for s in abstract.split(". ") if len(s.strip()) > 20]
        if sentences:
            first_sentence = sentences[0].rstrip(".")

    # Build 3-line summary
    parts = []

    # Line 1: Core finding (title-based)
    parts.append(f"Kernbefund: {title.rstrip('.')}")

    # Line 2: Study design / source
    if study:
        parts.append(f"Studiendesign: {study} — publiziert in {journal}")
    else:
        parts.append(f"Quelle: {journal}")

    # Line 3: Key detail from abstract or generic note
    if first_sentence:
        # Truncate if too long
        if len(first_sentence) > 200:
            first_sentence = first_sentence[:197] + "..."
        parts.append(f"Details: {first_sentence}.")
    else:
        parts.append("Kein Abstract verfügbar — Originalartikel prüfen.")

    return " | ".join(parts)


def summarize_articles(articles: list[Article]) -> list[Article]:
    """Add template summaries to articles that don't have one yet."""
    for article in articles:
        if not article.summary_de:
            article.summary_de = generate_template_summary(article)
    return articles

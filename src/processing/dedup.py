"""Article deduplication — three-pass approach."""

import logging
import re
import unicodedata
from difflib import SequenceMatcher

from src.models import Article

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    """Lowercase, strip accents, remove non-alphanumeric."""
    title = title.lower().strip()
    # Remove accents
    title = unicodedata.normalize("NFKD", title)
    title = "".join(c for c in title if not unicodedata.combining(c))
    # Keep only alphanumeric and spaces
    title = re.sub(r"[^a-z0-9\s]", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _similarity_ratio(s1: str, s2: str) -> float:
    """Compute similarity ratio between two strings (0.0–1.0).

    Uses SequenceMatcher which is fast for short strings and gives a ratio
    that's easier to reason about than raw Levenshtein distance.
    Quick reject if lengths differ by more than 50%.
    """
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    # Quick reject: very different lengths can't be >85% similar
    if min(len1, len2) / max(len1, len2) < 0.5:
        return 0.0
    return SequenceMatcher(None, s1, s2).ratio()


def deduplicate(articles: list[Article], cosine_threshold: float = 0.92) -> list[Article]:
    """Remove duplicate articles using DOI match and title similarity.

    Pass 1: Exact DOI match (same DOI = duplicate, keep first)
    Pass 2: Normalized title similarity (>85% SequenceMatcher ratio)
    Pass 3: (Sentence-Transformers cosine similarity — optional)

    IMPORTANT: A primary study (NEJM) and a commentary/summary about it
    (Medscape, Ärzteblatt) are NOT duplicates — they have different titles,
    abstracts, and editorial value. The dedup only catches the same article
    arriving through multiple feeds.
    """
    if not articles:
        return articles

    unique: list[Article] = []
    seen_dois: set[str] = set()
    seen_titles: list[tuple[str, Article]] = []

    # Pass 1 + 2: DOI and title
    for article in articles:
        # Pass 1: DOI — exact match only
        doi = (article.doi or "").strip().lower()
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)

        # Pass 2: Normalized title similarity
        norm = _normalize_title(article.title)
        if not norm:
            unique.append(article)
            continue

        is_dup = False
        for seen_norm, seen_article in seen_titles:
            ratio = _similarity_ratio(norm, seen_norm)
            if ratio > 0.85:
                # Keep the article with the longer abstract
                if len(article.abstract or "") > len(seen_article.abstract or ""):
                    # Replace the existing one
                    idx = next(i for i, a in enumerate(unique) if a is seen_article)
                    unique[idx] = article
                    seen_titles = [(n, a) if a is not seen_article else (norm, article)
                                   for n, a in seen_titles]
                is_dup = True
                break
        if is_dup:
            continue

        seen_titles.append((norm, article))
        unique.append(article)

    removed = len(articles) - len(unique)
    if removed:
        logger.info("Dedup pass 1+2 (DOI + title >85%%): removed %d duplicates (%d → %d)",
                     removed, len(articles), len(unique))

    # Pass 3: Sentence-Transformers (optional)
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        titles = [a.title for a in unique]
        embeddings = model.encode(titles, convert_to_numpy=True, show_progress_bar=False)

        # Compute pairwise cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # avoid division by zero
        normalized = embeddings / norms

        to_remove: set[int] = set()
        for i in range(len(unique)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(unique)):
                if j in to_remove:
                    continue
                sim = float(np.dot(normalized[i], normalized[j]))
                if sim > cosine_threshold:
                    to_remove.add(j)

        if to_remove:
            unique = [a for idx, a in enumerate(unique) if idx not in to_remove]
            logger.info("Dedup pass 3 (embeddings): removed %d more duplicates",
                        len(to_remove))

    except ImportError:
        logger.debug("sentence-transformers not installed — skipping pass 3")

    return unique

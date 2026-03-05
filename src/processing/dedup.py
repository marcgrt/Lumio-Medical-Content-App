"""Article deduplication — three-pass approach."""

import logging
import re
import unicodedata

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


def _levenshtein(s1: str, s2: str) -> int:
    """Simple Levenshtein distance (optimised for short-circuit)."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) > 10:  # can't be < threshold anyway
        return abs(len1 - len2)

    # Two-row DP
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)
    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[len2]


def deduplicate(articles: list[Article], cosine_threshold: float = 0.92) -> list[Article]:
    """Remove duplicate articles using DOI match and title similarity.

    Pass 1: Exact DOI match
    Pass 2: Normalized title Levenshtein distance < 5
    Pass 3: (Sentence-Transformers cosine similarity — optional, only if installed)
    """
    if not articles:
        return articles

    unique: list[Article] = []
    seen_dois: set[str] = set()
    seen_titles: list[str] = []

    # Pass 1 + 2: DOI and title
    for article in articles:
        # Pass 1: DOI
        doi = (article.doi or "").strip().lower()
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)

        # Pass 2: Normalized title
        norm = _normalize_title(article.title)
        if not norm:
            unique.append(article)
            continue

        is_dup = False
        for seen in seen_titles:
            if _levenshtein(norm, seen) < 5:
                is_dup = True
                break
        if is_dup:
            continue

        seen_titles.append(norm)
        unique.append(article)

    removed = len(articles) - len(unique)
    if removed:
        logger.info("Dedup pass 1+2: removed %d duplicates (%d → %d)",
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

"""Shared text utility functions used across the workflow pipeline."""


def _trigrams(text: str) -> set[str]:
    """Extract character trigrams for Jaccard similarity computation."""
    t = text.replace(" ", "").replace("\n", "")
    if len(t) < 3:
        return {t}
    return {t[i : i + 3] for i in range(len(t) - 2)}


def trigram_jaccard(a: str, b: str) -> float:
    """Trigram Jaccard similarity 0~1."""
    ta = _trigrams(a)
    tb = _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

"""
Fuzzy Surname Matching for Russian Names
==========================================
Compares surname variants accounting for:
- Gender suffixes (-ов/-ова, -ин/-ина, -ский/-ская)
- Common typos and transliteration errors
- Levenshtein / SequenceMatcher similarity

Usage:
    from app.services.phase1.fuzzy_matching import surname_similarity

    score = surname_similarity("Портной", "Портнов")  # ~0.8
"""

from difflib import SequenceMatcher
from typing import List, Tuple

from app.services.phase1.transliteration import transliterate

# ── Gender suffix pairs ────────────────────────────────────────────

_GENDER_PAIRS = [
    ('ов', 'ова'),
    ('ев', 'ева'),
    ('ёв', 'ёва'),
    ('ин', 'ина'),
    ('ын', 'ына'),
    ('ский', 'ская'),
    ('ской', 'ская'),
    ('цкий', 'цкая'),
    ('ный', 'ная'),
    ('ной', 'ная'),
    ('ий', 'ая'),
    ('ый', 'ая'),
    ('ко', 'ко'),   # Ukrainian surnames (same for both)
    ('ук', 'ук'),   # Ukrainian
    ('юк', 'юк'),
    ('ич', 'ич'),   # Belarusian
]

# ── Common surname transformations ─────────────────────────────────

_SUFFIX_TRANSFORMS = {
    # From -> list of alternative endings
    'ов': ['ова', 'овский', 'овская', 'овских'],
    'ева': ['ев', 'евский', 'евская'],
    'ев': ['ева', 'евский', 'евская'],
    'ин': ['ина', 'инский', 'инская'],
    'ина': ['ин', 'инский', 'инская'],
    'ский': ['ская', 'ских'],
    'ская': ['ский', 'ских'],
    'ной': ['ная', 'нов', 'нова'],
    'ная': ['ной', 'нов', 'нова'],
    'ный': ['ная', 'нов', 'нова'],
    'ов': ['ова', 'овский'],
    'ова': ['ов', 'овская'],
}


def surname_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two surnames (0.0 to 1.0).
    Handles Cyrillic/Latin, case differences, and gender variants.

    Args:
        name1: First surname
        name2: Second surname

    Returns:
        Float from 0.0 to 1.0
    """
    if not name1 or not name2:
        return 0.0

    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    # Exact match
    if n1 == n2:
        return 1.0

    # Try cross-script comparison
    n1_lat = transliterate(n1)
    n2_lat = transliterate(n2)

    if n1_lat == n2_lat:
        return 1.0

    # Check if they're gender variants of the same base
    base1 = _get_surname_base(n1)
    base2 = _get_surname_base(n2)
    if base1 and base2 and base1 == base2:
        return 0.95

    # Also check Latin bases
    base1_lat = _get_surname_base(n1_lat)
    base2_lat = _get_surname_base(n2_lat)
    if base1_lat and base2_lat and base1_lat == base2_lat:
        return 0.9

    # SequenceMatcher on both Cyrillic and Latin forms
    score_cyr = SequenceMatcher(None, n1, n2).ratio()
    score_lat = SequenceMatcher(None, n1_lat, n2_lat).ratio()

    return max(score_cyr, score_lat)


def _get_surname_base(surname: str) -> str:
    """Extract the base of a surname by removing common suffixes."""
    s = surname.lower()

    # Try removing suffixes from longest to shortest
    suffixes = sorted(
        [s for pair in _GENDER_PAIRS for s in pair if s],
        key=len, reverse=True
    )

    for suffix in suffixes:
        if s.endswith(suffix) and len(s) > len(suffix) + 1:
            return s[:-len(suffix)]

    return s



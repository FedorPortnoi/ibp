"""
Fuzzy Surname Matching for Russian Names
==========================================
Compares and generates surname variants accounting for:
- Gender suffixes (-ов/-ова, -ин/-ина, -ский/-ская)
- Common typos and transliteration errors
- Levenshtein / SequenceMatcher similarity

Usage:
    from app.services.phase1.fuzzy_matching import surname_similarity, generate_similar_surnames

    score = surname_similarity("Портной", "Портнов")  # ~0.8
    variants = generate_similar_surnames("Портной")
    # Returns: ["Портнов", "Портнова", "Портновский", ...]
"""

import logging
from difflib import SequenceMatcher
from typing import List, Tuple

logger = logging.getLogger(__name__)

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
    n1_lat = _to_latin(n1)
    n2_lat = _to_latin(n2)

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


def generate_similar_surnames(surname: str) -> List[str]:
    """
    Generate likely surname variants from a base surname.
    Includes gender variants, common suffix transformations.

    Args:
        surname: Base surname (e.g. "Портной")

    Returns:
        List of variant surnames
    """
    if not surname:
        return []

    variants = []
    s_lower = surname.lower()

    # Generate gender variants
    for male_end, female_end in _GENDER_PAIRS:
        if s_lower.endswith(male_end):
            base = surname[:-len(male_end)]
            variants.append(base + female_end)
            # Also capitalize properly
            if surname[0].isupper():
                variants[-1] = variants[-1][0].upper() + variants[-1][1:]
        elif s_lower.endswith(female_end) and male_end != female_end:
            base = surname[:-len(female_end)]
            variants.append(base + male_end)
            if surname[0].isupper():
                variants[-1] = variants[-1][0].upper() + variants[-1][1:]

    # Suffix transformations
    for suffix, alternatives in _SUFFIX_TRANSFORMS.items():
        if s_lower.endswith(suffix):
            base = surname[:-len(suffix)]
            for alt in alternatives:
                new_name = base + alt
                if surname[0].isupper():
                    new_name = new_name[0].upper() + new_name[1:]
                if new_name.lower() != s_lower and new_name not in variants:
                    variants.append(new_name)

    # Deduplicate while preserving order, exclude original
    seen = {surname.lower()}
    result = []
    for v in variants:
        if v.lower() not in seen:
            seen.add(v.lower())
            result.append(v)

    return result


def find_best_surname_match(target: str, candidates: List[str], threshold: float = 0.6) -> List[Tuple[str, float]]:
    """
    Find the best matching surnames from a list of candidates.

    Args:
        target: Target surname to match against
        candidates: List of candidate surnames
        threshold: Minimum similarity score (0.0 to 1.0)

    Returns:
        List of (surname, score) tuples above threshold, sorted by score descending
    """
    matches = []
    for candidate in candidates:
        score = surname_similarity(target, candidate)
        if score >= threshold:
            matches.append((candidate, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


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


def _to_latin(text: str) -> str:
    """Basic Cyrillic to Latin transliteration for comparison."""
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    return ''.join(table.get(ch, ch) for ch in text.lower())

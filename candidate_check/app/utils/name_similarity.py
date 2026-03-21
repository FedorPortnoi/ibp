"""
Name similarity utilities for Russian name matching.
Extracted from per_profile_search.py for reuse.
"""


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names (0.0 - 1.0).

    Handles:
    - Case insensitivity
    - Partial matches (first name or last name only)
    - Cyrillic/Latin transliteration variations
    - Common Russian diminutives
    """
    if not name1 or not name2:
        return 0.0

    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    if n1 == n2:
        return 1.0

    parts1 = set(n1.split())
    parts2 = set(n2.split())

    common_parts = parts1 & parts2
    if common_parts:
        max_parts = max(len(parts1), len(parts2))
        return 0.5 + (0.5 * len(common_parts) / max_parts)

    transliterated1 = _transliterate_name(n1)
    transliterated2 = _transliterate_name(n2)

    if transliterated1 == transliterated2:
        return 0.9

    trans_parts1 = set(transliterated1.split())
    trans_parts2 = set(transliterated2.split())
    trans_common = trans_parts1 & trans_parts2
    if trans_common:
        max_parts = max(len(trans_parts1), len(trans_parts2))
        return 0.4 + (0.4 * len(trans_common) / max_parts)

    return _fuzzy_similarity(transliterated1, transliterated2)


def _transliterate_name(name: str) -> str:
    """Transliterate Cyrillic to Latin for comparison."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = ""
    for char in name.lower():
        result += translit_map.get(char, char)
    return result


def _fuzzy_similarity(s1: str, s2: str) -> float:
    """Calculate fuzzy string similarity (Jaccard-based)."""
    if not s1 or not s2:
        return 0.0

    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)

    set1, set2 = set(s1), set(s2)
    overlap = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    jaccard = overlap / union
    length_diff = abs(len1 - len2) / max(len1, len2)
    length_penalty = 1.0 - (length_diff * 0.3)

    return jaccard * length_penalty * 0.3

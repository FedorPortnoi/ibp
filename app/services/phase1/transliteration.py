"""
Multi-System Russian-Latin Transliteration
============================================
Generates multiple Latin transliteration variants for Russian names.

Covers: GOST, BGN/PCGN, Russian passport, and common informal spellings.
Handles key ambiguities like X->Kh/H/X, Й->Y/I/J, etc.

Usage:
    from app.services.phase1.transliteration import transliterate_russian

    variants = transliterate_russian("Тихон Портной")
    # Returns: ["Tikhon Portnoi", "Tikhon Portnoy", "Tihon Portnoi", ...]
"""

import logging
from itertools import product
from typing import List, Set

logger = logging.getLogger(__name__)

# ── Transliteration systems ────────────────────────────────────────
# Each maps a Cyrillic character to possible Latin representations.
# Multiple options per character enable generating all common variants.

# Core single-char mappings (no ambiguity)
_CORE = {
    'а': ['a'], 'б': ['b'], 'в': ['v'], 'г': ['g'], 'д': ['d'],
    'з': ['z'], 'и': ['i'], 'к': ['k'], 'л': ['l'], 'м': ['m'],
    'н': ['n'], 'о': ['o'], 'п': ['p'], 'р': ['r'], 'с': ['s'],
    'т': ['t'], 'у': ['u'], 'ф': ['f'],
}

# Ambiguous characters — multiple transliterations
_AMBIGUOUS = {
    'е': ['e', 'ye'],        # ye at start of word, e otherwise
    'ё': ['yo', 'e', 'jo'],
    'ж': ['zh', 'j'],
    'й': ['y', 'i', 'j'],
    'х': ['kh', 'h', 'x'],
    'ц': ['ts', 'c', 'tz'],
    'ч': ['ch', 'tch'],
    'ш': ['sh'],
    'щ': ['shch', 'sch'],
    'ъ': [''],               # hard sign — omitted
    'ы': ['y', 'i'],
    'ь': ['', "'"],          # soft sign — omitted or apostrophe
    'э': ['e'],
    'ю': ['yu', 'iu', 'ju'],
    'я': ['ya', 'ia', 'ja'],
}

# Combine into full map
_FULL_MAP = {}
_FULL_MAP.update(_CORE)
_FULL_MAP.update(_AMBIGUOUS)

# Special ending patterns (Russian surname endings)
_ENDING_VARIANTS = {
    'ой': ['oi', 'oy'],
    'ий': ['iy', 'y', 'ii'],
    'ый': ['yy', 'y', 'iy'],
    'ей': ['ei', 'ey'],
    'ёв': ['yov', 'ev', 'jov'],
    'ев': ['ev', 'yev'],
    'ов': ['ov'],
    'ин': ['in'],
}


def transliterate_russian(name: str, max_variants: int = 12) -> List[str]:
    """
    Generate multiple Latin transliteration variants for a Russian name.

    Args:
        name: Russian name (e.g. "Тихон Портной")
        max_variants: Maximum variants to return (default 12)

    Returns:
        List of unique Latin transliterations, most common first.
    """
    if not name or not name.strip():
        return []

    parts = name.strip().split()
    if not parts:
        return []

    # Transliterate each word independently, then combine
    word_variants = []
    for word in parts:
        variants = _transliterate_word(word)
        word_variants.append(variants)

    # Combine: product of all word variants
    results: Set[str] = set()
    for combo in product(*word_variants):
        result = ' '.join(combo)
        results.add(result)
        if len(results) >= max_variants * 3:
            break

    # Sort: prefer shorter, more common variants first
    sorted_results = sorted(results, key=lambda x: (len(x), x))

    return sorted_results[:max_variants]


def transliterate_name_part(word: str, max_variants: int = 6) -> List[str]:
    """
    Transliterate a single name part (first name or last name).

    Args:
        word: Single Russian word
        max_variants: Max variants to return

    Returns:
        List of Latin transliterations
    """
    return _transliterate_word(word)[:max_variants]


def _transliterate_word(word: str) -> List[str]:
    """Generate transliteration variants for a single word."""
    if not word:
        return ['']

    # Check if already Latin
    if all(c.isascii() or c in ' -' for c in word):
        return [word.lower()]

    word_lower = word.lower()

    # Check for special ending patterns first
    ending_subs = {}
    for ending, variants in _ENDING_VARIANTS.items():
        if word_lower.endswith(ending):
            ending_subs[ending] = variants
            break

    # Character-by-character transliteration
    char_options = []
    i = 0
    end_handled = False

    while i < len(word_lower):
        ch = word_lower[i]

        # Check if this starts a special ending
        if not end_handled and ending_subs:
            for ending, variants in ending_subs.items():
                if word_lower[i:] == ending:
                    char_options.append(variants)
                    i = len(word_lower)
                    end_handled = True
                    break
            if end_handled:
                break

        if ch in _FULL_MAP:
            char_options.append(_FULL_MAP[ch])
        elif ch.isalpha():
            # Pass through unknown characters
            char_options.append([ch])
        elif ch in ' -':
            char_options.append([ch])
        else:
            # Skip non-alpha, non-space
            pass
        i += 1

    if not char_options:
        return [word.lower()]

    # Generate combinations (limit to avoid explosion)
    variants: List[str] = []
    for combo in product(*char_options):
        variant = ''.join(combo)
        if variant and variant not in variants:
            variants.append(variant)
        if len(variants) >= 20:
            break

    # Capitalize first letter for proper nouns
    # Return lowercased for username generation
    return variants if variants else [word.lower()]


def generate_username_patterns(first_lat: str, last_lat: str) -> List[str]:
    """
    Generate common VK/social media username patterns from transliterated name parts.

    Args:
        first_lat: Latin first name (e.g. "tikhon")
        last_lat: Latin last name (e.g. "portnoi")

    Returns:
        List of candidate usernames
    """
    f = first_lat.lower().replace(' ', '').replace("'", '')
    l = last_lat.lower().replace(' ', '').replace("'", '')

    if not f or not l:
        return []

    fi = f[0]  # first initial

    patterns = [
        f'{f}.{l}',      # tikhon.portnoi
        f'{f}_{l}',      # tikhon_portnoi
        f'{l}.{f}',      # portnoi.tikhon
        f'{l}_{f}',      # portnoi_tikhon
        f'{fi}.{l}',     # t.portnoi
        f'{fi}_{l}',     # t_portnoi
        f'{fi}{l}',      # tportnoi
        f'{f}{l}',       # tikhonportnoi
        f'{l}{f}',       # portnoitikhon
        f'{l}',          # portnoi
        f'{l}{fi}',      # portnoит
    ]

    # Deduplicate
    return list(dict.fromkeys(patterns))

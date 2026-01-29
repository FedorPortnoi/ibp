"""
Email Generator Service
=======================
Generates likely email addresses from a Russian name.
Based on common Russian email patterns.
"""

from typing import List, Set
import re

# Russian email domains (ordered by popularity)
# Source: Research on Russian email usage patterns
RUSSIAN_EMAIL_DOMAINS = [
    # Mail.ru group (largest in Russia, ~50% of Russian email users)
    'mail.ru',
    'bk.ru',
    'list.ru',
    'inbox.ru',
    'internet.ru',

    # Yandex group (~30% of Russian email users)
    'yandex.ru',
    'ya.ru',
    'yandex.com',
    'yandex.by',
    'yandex.kz',
    'yandex.ua',

    # Rambler group (legacy but still used)
    'rambler.ru',
    'lenta.ru',
    'myrambler.ru',
    'autorambler.ru',
    'ro.ru',
    'r0.ru',

    # International (used by ~15% of Russians)
    'gmail.com',
    'outlook.com',
    'hotmail.com',
    'icloud.com',

    # Other Russian
    'mail.com',
    'pochta.ru',  # Russian Post email
]

# Transliteration map (Cyrillic to Latin)
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
    'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya'
}

# Alternative transliteration for common variations
TRANSLIT_ALT = {
    'ж': 'j',
    'х': 'h',
    'ц': 'c',
    'ч': 'tch',
    'ш': 'sch',
    'щ': 'sh',
    'ю': 'iu',
    'я': 'ia'
}


def transliterate(text: str, use_alt: bool = False) -> str:
    """
    Convert Cyrillic text to Latin.

    Args:
        text: Text to transliterate
        use_alt: Use alternative transliteration rules

    Returns:
        Transliterated text
    """
    translit_map = TRANSLIT_ALT if use_alt else TRANSLIT_MAP
    result = ''
    for char in text.lower():
        if char in translit_map:
            result += translit_map[char]
        elif char in TRANSLIT_MAP:
            result += TRANSLIT_MAP[char]
        else:
            result += char
    return result


def is_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    return bool(re.search(r'[\u0400-\u04FF]', text))


def generate_email_candidates(
    first_name: str,
    last_name: str,
    birth_year: str = None,
    username_hints: List[str] = None
) -> List[str]:
    """
    Generate likely email addresses from name.

    Args:
        first_name: First name (Russian or Latin)
        last_name: Last name (Russian or Latin)
        birth_year: Optional birth year (e.g., "1990")
        username_hints: Optional list of known usernames to base patterns on

    Returns:
        List of likely email addresses (50-100 candidates)
    """
    emails: Set[str] = set()

    # Clean names
    first_name = first_name.strip() if first_name else ''
    last_name = last_name.strip() if last_name else ''

    if not first_name and not last_name:
        return []

    # Transliterate if Cyrillic (both standard and alternative)
    names_to_try = []

    if is_cyrillic(first_name) or is_cyrillic(last_name):
        # Standard transliteration
        fname_std = transliterate(first_name)
        lname_std = transliterate(last_name)
        names_to_try.append((fname_std, lname_std))

        # Alternative transliteration
        fname_alt = transliterate(first_name, use_alt=True)
        lname_alt = transliterate(last_name, use_alt=True)
        if (fname_alt, lname_alt) != (fname_std, lname_std):
            names_to_try.append((fname_alt, lname_alt))
    else:
        names_to_try.append((first_name.lower(), last_name.lower()))

    # Year variations
    years = []
    if birth_year:
        years = [birth_year, birth_year[-2:]]

    # Common birth year suffixes
    common_years = ['90', '91', '92', '93', '94', '95', '96', '97', '98', '99', '00', '01', '02']

    for fname, lname in names_to_try:
        # Get initials
        f_init = fname[0] if fname else ''
        l_init = lname[0] if lname else ''

        # Base patterns
        patterns = [
            f"{fname}",                      # pavel
            f"{lname}",                      # durov
            f"{fname}{lname}",               # paveldurov
            f"{fname}.{lname}",              # pavel.durov
            f"{fname}_{lname}",              # pavel_durov
            f"{fname}-{lname}",              # pavel-durov
            f"{lname}{fname}",               # durovpavel
            f"{lname}.{fname}",              # durov.pavel
            f"{lname}_{fname}",              # durov_pavel
            f"{f_init}{lname}",              # pdurov
            f"{f_init}.{lname}",             # p.durov
            f"{f_init}_{lname}",             # p_durov
            f"{fname}{l_init}",              # paveld
            f"{fname}.{l_init}",             # pavel.d
            f"{lname}{f_init}",              # durovp
            f"{f_init}{l_init}",             # pd
        ]

        # Add year variations for top patterns
        year_patterns = []
        for p in patterns[:10]:  # Top patterns only
            for y in years:
                year_patterns.append(f"{p}{y}")
                year_patterns.append(f"{p}_{y}")
                year_patterns.append(f"{p}.{y}")
            # Also add common years if no birth year provided
            if not birth_year:
                for y in common_years[:5]:
                    year_patterns.append(f"{p}{y}")

        patterns.extend(year_patterns)

        # Generate emails for each domain
        # Use more domains for base patterns, fewer for year variants
        for i, pattern in enumerate(patterns):
            if pattern and len(pattern) >= 3:
                # Top 10 patterns get all domains, rest get top 10
                domains_to_use = RUSSIAN_EMAIL_DOMAINS if i < 10 else RUSSIAN_EMAIL_DOMAINS[:10]
                for domain in domains_to_use:
                    email = f"{pattern}@{domain}"
                    if is_valid_email(email):
                        emails.add(email.lower())

    # Add username-based patterns if hints provided
    if username_hints:
        for username in username_hints[:10]:  # Max 10 hints
            username = username.lower().strip()
            if username and len(username) >= 3:
                # Use all Russian domains for username hints
                for domain in RUSSIAN_EMAIL_DOMAINS[:15]:  # Top 15 Russian domains
                    email = f"{username}@{domain}"
                    if is_valid_email(email):
                        emails.add(email.lower())

    return sorted(list(emails))[:150]  # Cap at 150


def is_valid_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254


def generate_from_username(username: str) -> List[str]:
    """
    Generate email candidates based on a username.
    Uses all Russian domains since usernames often match email prefixes.

    Args:
        username: Known username from social media

    Returns:
        List of likely email addresses
    """
    emails = []
    username = username.lower().strip()

    if not username or len(username) < 3:
        return emails

    # Remove common prefixes/suffixes for variations
    clean_username = re.sub(r'^(id|user|profile)', '', username)
    clean_username = re.sub(r'[_\d]+$', '', clean_username)

    # Also try replacing underscores with dots
    dot_username = username.replace('_', '.')

    candidates = [username]
    if clean_username and clean_username != username and len(clean_username) >= 3:
        candidates.append(clean_username)
    if dot_username != username:
        candidates.append(dot_username)

    # Use all Russian domains for username-based emails
    for candidate in candidates:
        for domain in RUSSIAN_EMAIL_DOMAINS:  # All domains
            email = f"{candidate}@{domain}"
            if is_valid_email(email):
                emails.append(email.lower())

    return list(set(emails))[:50]  # Up to 50 candidates per username

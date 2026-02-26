"""
Email Generator Service
=======================
Generates likely email addresses from a Russian name.
Based on common Russian email patterns.

Enhanced with:
- Russian diminutives (Даниил → Даня, Дмитрий → Дима)
- Priority-based generation
- SMTP verification support
"""

from typing import List, Set, Dict, Optional, Any
import re
import logging
import time

from app.services.phase1.transliteration import transliterate

logger = logging.getLogger(__name__)

# Russian email domains (ordered by popularity)
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

# Top providers (most common for young Russians)
TOP_PROVIDERS = ['mail.ru', 'gmail.com', 'yandex.ru', 'bk.ru', 'ya.ru']

# Catch-all domains that always accept (can't verify)
CATCH_ALL_DOMAINS = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com']

# Russian diminutives map (first name → common nicknames)
RUSSIAN_DIMINUTIVES = {
    # Male names
    'aleksandr': ['sasha', 'shura', 'sanya', 'alex', 'san'],
    'aleksey': ['lyosha', 'alyosha', 'lesha', 'alex', 'alesha'],
    'andrey': ['andryusha', 'andryukha', 'dron'],
    'anton': ['tosha', 'tonya', 'antosha'],
    'artem': ['tyoma', 'tema', 'art'],
    'boris': ['borya', 'bob'],
    'daniil': ['danya', 'dan', 'dani', 'danila', 'danik'],
    'denis': ['den', 'denya', 'denchik'],
    'dmitriy': ['dima', 'mitya', 'dimka', 'dimok', 'dimon'],
    'evgeniy': ['zhenya', 'zheka', 'gene'],
    'fedor': ['fedya', 'fedka', 'fed'],
    'georgiy': ['zhora', 'gosha', 'george'],
    'grigoriy': ['grisha', 'grishenka'],
    'igor': ['igorek', 'gorik'],
    'ilya': ['ilyusha', 'ilyukha'],
    'ivan': ['vanya', 'vanechka', 'vanyusha'],
    'kirill': ['kirya', 'kiryusha', 'kir'],
    'konstantin': ['kostya', 'kos', 'kostik'],
    'maksim': ['max', 'maks', 'maksik', 'makson'],
    'mikhail': ['misha', 'mishka', 'mike', 'miha'],
    'nikita': ['nik', 'nikitos'],
    'nikolay': ['kolya', 'nik', 'nikolasha'],
    'oleg': ['olezhka', 'olik'],
    'pavel': ['pasha', 'pavlik', 'pashka'],
    'petr': ['petya', 'petrusha'],
    'roman': ['roma', 'romka', 'romchik'],
    'sergey': ['seryozha', 'serega', 'serge', 'serj'],
    'stanislav': ['stas', 'stasik'],
    'stepan': ['styopa', 'stepa'],
    'tikhon': ['tisha', 'tishka', 'tih'],
    'timofey': ['tima', 'timka', 'tim'],
    'valeriy': ['valera', 'val'],
    'vasiliy': ['vasya', 'vasyok'],
    'viktor': ['vitya', 'vityok', 'vic'],
    'vitaliy': ['vitalik', 'vital'],
    'vladimir': ['vova', 'volodya', 'vlad', 'vovka'],
    'vladislav': ['vlad', 'vladik'],
    'vyacheslav': ['slava', 'slavik'],
    'yaroslav': ['yarik', 'slava'],
    'yuriy': ['yura', 'yurik'],
    # Female names
    'aleksandra': ['sasha', 'shura', 'sanya', 'alex'],
    'alina': ['alya', 'alinochka'],
    'anastasiya': ['nastya', 'nastyusha', 'asya', 'stasya'],
    'angelina': ['gela', 'lina', 'angel', 'angie'],
    'anna': ['anya', 'anyuta', 'annushka', 'nyuta'],
    'daria': ['dasha', 'dashenka', 'dashka'],
    'diana': ['di', 'dianochka'],
    'ekaterina': ['katya', 'katyusha', 'kate', 'katerina'],
    'elena': ['lena', 'lenochka', 'alyona', 'helen'],
    'elizaveta': ['liza', 'lizochka', 'beth'],
    'evgeniya': ['zhenya', 'zheka'],
    'galina': ['galya', 'galechka'],
    'irina': ['ira', 'irochka', 'irisha'],
    'kristina': ['kris', 'kristya', 'tina'],
    'kseniya': ['ksyusha', 'ksyu', 'ksusha'],
    'larisa': ['lara', 'larochka'],
    'lyudmila': ['lyuda', 'mila', 'lyusya'],
    'margarita': ['rita', 'margo'],
    'mariya': ['masha', 'mashka', 'mary', 'marusya'],
    'nadezhda': ['nadya', 'nadyusha'],
    'natalya': ['natasha', 'nata', 'natashenka'],
    'nina': ['ninochka', 'ninusha'],
    'oksana': ['oksanochka', 'ksana'],
    'olga': ['olya', 'olechka', 'olenka'],
    'polina': ['polya', 'polinochka'],
    'sofiya': ['sonya', 'sofochka', 'sofa'],
    'svetlana': ['sveta', 'svetik', 'svetlanka'],
    'tatyana': ['tanya', 'tanechka', 'tanyusha'],
    'valentina': ['valya', 'valyusha'],
    'valeriya': ['lera', 'lerochka'],
    'vera': ['verochka', 'verusha'],
    'viktoriya': ['vika', 'vikochka', 'vic'],
    'yuliya': ['yulya', 'yulechka', 'julia'],
}

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


def get_diminutives(first_name: str) -> List[str]:
    """
    Get Russian diminutives for a first name.

    Args:
        first_name: First name (Latin or Cyrillic)

    Returns:
        List of diminutive forms
    """
    # Transliterate if Cyrillic
    name_latin = transliterate(first_name.lower().strip()) if is_cyrillic(first_name) else first_name.lower().strip()

    return RUSSIAN_DIMINUTIVES.get(name_latin, [])


def generate_smart_email_candidates(
    first_name: str,
    last_name: str,
    usernames: List[str] = None,
    birth_year: str = None,
    max_candidates: int = 60
) -> List[Dict[str, Any]]:
    """
    Generate email candidates with priority scoring using name patterns,
    diminutives, and ALL known usernames.

    Args:
        first_name: First name (Russian or Latin)
        last_name: Last name (Russian or Latin)
        usernames: ALL known usernames (VK, Instagram, Telegram, etc.)
        birth_year: Optional birth year
        max_candidates: Maximum candidates to generate

    Returns:
        List of dicts with 'email', 'source', 'priority', 'confidence'
    """
    candidates = []
    seen = set()

    # Clean names
    first_name = first_name.strip() if first_name else ''
    last_name = last_name.strip() if last_name else ''
    usernames = [u.lower().strip().lstrip('@') for u in (usernames or []) if u]

    if not first_name and not last_name and not usernames:
        return []

    # Transliterate names
    fn = transliterate(first_name) if is_cyrillic(first_name) else first_name.lower()
    ln = transliterate(last_name) if is_cyrillic(last_name) else last_name.lower()

    # Get diminutives
    diminutives = get_diminutives(first_name)

    def add_candidate(local_part: str, provider: str, source: str, priority: int):
        if not local_part or len(local_part) < 2:
            return
        email = f"{local_part}@{provider}".lower()
        if email not in seen and is_valid_email(email):
            seen.add(email)
            candidates.append({
                'email': email,
                'source': source,
                'priority': priority,
                'confidence': 'low',
                'verification': 'unverified'
            })

    # ===== PRIORITY 1: Best name patterns + top providers =====
    if fn and ln:
        f_init = fn[0] if fn else ''
        best_patterns = [
            f"{fn}.{ln}",      # daniil.glazkov
            f"{fn}{ln}",       # daniilglazkov
            f"{f_init}{ln}",   # dglazkov
            f"{f_init}.{ln}",  # d.glazkov
            f"{ln}.{fn}",      # glazkov.daniil
        ]
        for pattern in best_patterns:
            for provider in TOP_PROVIDERS:
                add_candidate(pattern, provider, 'Name pattern (best)', 1)

    # ===== PRIORITY 2: Username patterns + top providers =====
    for username in usernames[:5]:
        for provider in TOP_PROVIDERS:
            add_candidate(username, provider, f'Username ({username})', 2)

    # ===== PRIORITY 3: Diminutive patterns + top providers =====
    for dim in diminutives[:3]:
        if ln:
            for provider in TOP_PROVIDERS:
                add_candidate(f"{dim}.{ln}", provider, f'Diminutive ({dim})', 3)
                add_candidate(f"{dim}{ln}", provider, f'Diminutive ({dim})', 3)
        for provider in TOP_PROVIDERS[:3]:
            add_candidate(dim, provider, f'Diminutive only ({dim})', 3)

    # ===== PRIORITY 4: All name patterns + remaining providers =====
    if fn and ln:
        f_init = fn[0] if fn else ''
        l_init = ln[0] if ln else ''
        all_patterns = [
            f"{fn}_{ln}", f"{ln}{fn}", f"{ln}_{fn}",
            f"{f_init}_{ln}", f"{ln}{f_init}", f"{fn}{l_init}",
            fn, ln
        ]
        for pattern in all_patterns:
            for provider in RUSSIAN_EMAIL_DOMAINS[:10]:
                add_candidate(pattern, provider, 'Name pattern', 4)

    # ===== PRIORITY 5: Username patterns + all providers =====
    for username in usernames:
        for provider in RUSSIAN_EMAIL_DOMAINS[:10]:
            add_candidate(username, provider, f'Username ({username})', 5)
        # Also try username variations
        clean = re.sub(r'[_\d]+$', '', username)
        dot = username.replace('_', '.')
        if clean != username and len(clean) >= 3:
            for provider in TOP_PROVIDERS:
                add_candidate(clean, provider, f'Username variant ({clean})', 5)
        if dot != username:
            for provider in TOP_PROVIDERS:
                add_candidate(dot, provider, f'Username variant ({dot})', 5)

    # ===== PRIORITY 6: More diminutive combinations =====
    for dim in diminutives:
        for provider in RUSSIAN_EMAIL_DOMAINS[:8]:
            if ln:
                add_candidate(f"{dim}.{ln}", provider, f'Diminutive ({dim})', 6)
            add_candidate(dim, provider, f'Diminutive only ({dim})', 6)

    # Sort by priority and limit
    candidates.sort(key=lambda c: c['priority'])
    return candidates[:max_candidates]


def smtp_verify_email(email: str, timeout: int = 8) -> Optional[bool]:
    """
    Verify email exists via SMTP RCPT TO command.

    Note: Many mail servers block SMTP verification from residential IPs.
    This works best from servers with proper PTR records.

    Args:
        email: Email address to verify
        timeout: Connection timeout in seconds

    Returns:
        True: Email exists
        False: Email rejected (doesn't exist)
        None: Inconclusive (catch-all domain, connection error, blocked)
    """
    import smtplib
    try:
        import dns.resolver
    except ImportError:
        logger.debug("dnspython not installed, skipping SMTP verification")
        return None

    domain = email.split('@')[1]

    # Skip catch-all domains (always accept all addresses)
    if domain in CATCH_ALL_DOMAINS:
        return None

    # Domains known to block SMTP verification
    BLOCKED_DOMAINS = ['mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'yandex.ru', 'ya.ru']
    if domain in BLOCKED_DOMAINS:
        # These domains block SMTP verification - return None to mark as "likely"
        return None

    try:
        # Get MX record
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(mx_records[0].exchange).rstrip('.')

        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host)
        server.helo('verify.example.com')
        server.mail('verify@example.com')
        code, message = server.rcpt(email)
        server.quit()

        if code == 250:
            return True   # Email accepted = exists
        elif code in (550, 551, 552, 553, 554):
            return False  # Rejected = doesn't exist
        else:
            return None   # Unknown response

    except dns.resolver.NoAnswer:
        return None
    except dns.resolver.NXDOMAIN:
        return False  # Domain doesn't exist
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
            ConnectionRefusedError, TimeoutError, OSError):
        return None  # Can't connect (blocked or network issue)
    except Exception as e:
        logger.debug(f"SMTP verification error for {email}: {e}")
        return None


def generate_corporate_emails(
    first_name: str,
    last_name: str,
    employer: str,
) -> List[Dict[str, Any]]:
    """
    Generate corporate email patterns based on employer name from VK career field.

    Args:
        first_name: First name (Russian or Latin)
        last_name: Last name (Russian or Latin)
        employer: Company name from VK career field

    Returns:
        List of candidate dicts with email, source, priority, confidence
    """
    candidates = []
    if not employer or not (first_name or last_name):
        return candidates

    # Transliterate names
    fn = transliterate(first_name).lower() if is_cyrillic(first_name) else first_name.lower()
    ln = transliterate(last_name).lower() if is_cyrillic(last_name) else last_name.lower()
    f_init = fn[0] if fn else ''

    # Try to extract domain from employer name
    # Common Russian corporate domain patterns
    employer_clean = employer.strip().lower()
    employer_clean = re.sub(r'^(ооо|оао|зао|пао|ип)\s+', '', employer_clean)
    employer_clean = re.sub(r'[«»""\']+', '', employer_clean)
    employer_latin = transliterate(employer_clean) if is_cyrillic(employer_clean) else employer_clean
    employer_latin = re.sub(r'[^a-z0-9]', '', employer_latin)

    if not employer_latin or len(employer_latin) < 3:
        return candidates

    # Typical corporate domains
    corp_domains = [
        f'{employer_latin}.ru',
        f'{employer_latin}.com',
    ]

    patterns = []
    if fn and ln:
        patterns = [
            f'{fn}@',
            f'{fn}.{ln}@',
            f'{f_init}.{ln}@',
            f'{f_init}{ln}@',
            f'{ln}.{fn}@',
            f'{ln}@',
        ]
    elif ln:
        patterns = [f'{ln}@']
    elif fn:
        patterns = [f'{fn}@']

    for pattern in patterns:
        for domain in corp_domains:
            email = f'{pattern}{domain}'
            if is_valid_email(email):
                candidates.append({
                    'email': email.lower(),
                    'source': f'Corporate ({employer})',
                    'priority': 2,
                    'confidence': 'low',
                    'verification': 'unverified',
                })

    return candidates[:20]


def skype_to_email_candidates(skype_username: str) -> List[Dict[str, Any]]:
    """
    Generate email candidates from a Skype username.
    Microsoft accounts often use skype_username@outlook.com or @hotmail.com.
    Gravatar can also be checked with skype@live.com.

    Args:
        skype_username: Skype username from VK contacts

    Returns:
        List of candidate dicts
    """
    candidates = []
    if not skype_username or len(skype_username) < 3:
        return candidates

    username = skype_username.lower().strip()

    # Microsoft account domains
    ms_domains = ['outlook.com', 'hotmail.com', 'live.com', 'live.ru']
    # Also try popular Russian domains since people often use same username
    other_domains = ['gmail.com', 'mail.ru', 'yandex.ru']

    for domain in ms_domains:
        email = f'{username}@{domain}'
        if is_valid_email(email):
            candidates.append({
                'email': email,
                'source': f'Skype username ({username})',
                'priority': 2,
                'confidence': 'low',
                'verification': 'unverified',
            })

    for domain in other_domains:
        email = f'{username}@{domain}'
        if is_valid_email(email):
            candidates.append({
                'email': email,
                'source': f'Skype username ({username})',
                'priority': 4,
                'confidence': 'low',
                'verification': 'unverified',
            })

    return candidates


# Domains that block SMTP verification but are popular in Russia
BLOCKED_DOMAINS = {'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'yandex.ru', 'ya.ru'}


def verify_email_candidates(
    candidates: List[Dict[str, Any]],
    max_to_verify: int = 25,
    delay: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Verify top email candidates via SMTP.

    Args:
        candidates: List of email candidate dicts
        max_to_verify: Maximum emails to verify
        delay: Delay between SMTP checks (seconds)

    Returns:
        Filtered and updated candidates with verification results
    """
    # Sort by priority
    sorted_candidates = sorted(candidates, key=lambda c: c.get('priority', 99))

    verified = []
    checked = 0
    smtp_verified_count = 0

    for candidate in sorted_candidates:
        email = candidate['email']
        domain = email.split('@')[1] if '@' in email else ''

        if checked >= max_to_verify:
            # Keep remaining without checking
            candidate['verification'] = 'unchecked'
            verified.append(candidate)
            continue

        result = smtp_verify_email(email)
        checked += 1

        if result is True:
            candidate['confidence'] = 'high'
            candidate['verification'] = 'smtp_verified'
            smtp_verified_count += 1
            verified.append(candidate)
            logger.info(f"SMTP verified: {email}")
        elif result is False:
            # Email rejected - skip it entirely
            logger.debug(f"SMTP rejected: {email}")
            continue
        else:
            # Inconclusive - but differentiate popular domains
            if domain in CATCH_ALL_DOMAINS:
                candidate['confidence'] = 'medium'
                candidate['verification'] = 'catch_all_domain'
            elif domain in BLOCKED_DOMAINS:
                # Popular Russian domains that block SMTP - treat as likely
                candidate['confidence'] = 'medium'
                candidate['verification'] = 'likely'
            else:
                candidate['confidence'] = 'low'
                candidate['verification'] = 'inconclusive'
            verified.append(candidate)

        # Rate limit
        if checked < max_to_verify:
            time.sleep(delay)

    # Sort: verified first, then likely/catch-all, then by priority
    verified.sort(key=lambda c: (
        0 if c.get('verification') == 'smtp_verified' else
        1 if c.get('verification') in ('catch_all_domain', 'likely') else 2,
        c.get('priority', 99)
    ))

    logger.info(f"SMTP verification: {smtp_verified_count} verified, {checked} checked, {len(verified)} kept")

    return verified

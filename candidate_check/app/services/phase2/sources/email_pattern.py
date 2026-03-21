"""
Email Pattern Generation Source
================================
Wraps existing email generation logic as a BaseSource plugin.
Generates email candidates from name + usernames + Russian domains.

Improvements (Feb 2026):
- MX record validation: only emit patterns for domains that have a real
  MX record. Domains that don't resolve are silently dropped.
- Russian-domain priority: mail.ru group + Yandex are checked first
  and assigned higher confidence. International domains (gmail, outlook)
  are only included if the user has an international-looking username hint.
- Noise reduction: hard cap dropped from 50 to 20 results; year-suffix
  patterns are suppressed unless a birth_year hint is provided.

Tier: C (Pattern Generation)
"""

import logging
import threading
from typing import List, Optional, Dict, Set

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MX record cache — avoids re-resolving the same domain within a run.
# Thread-safe: guarded by _mx_lock.
# ---------------------------------------------------------------------------
_mx_cache: Dict[str, bool] = {}
_mx_lock = threading.Lock()

# Domains we KNOW have valid MX records — pre-seeded to skip DNS lookups for
# the most common Russian providers (cold-start speedup).
_KNOWN_GOOD_MX: Set[str] = {
    'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'internet.ru',
    'yandex.ru', 'ya.ru', 'yandex.com', 'yandex.by', 'yandex.kz',
    'rambler.ru', 'lenta.ru', 'myrambler.ru', 'ro.ru', 'r0.ru',
    'gmail.com', 'outlook.com', 'hotmail.com', 'icloud.com',
}

# Russian-provider domains in priority order.
# Rationale: ~80% of Russian users use one of these five.
RUSSIAN_PRIORITY_DOMAINS = [
    'mail.ru', 'yandex.ru', 'bk.ru', 'list.ru', 'inbox.ru',
    'ya.ru', 'rambler.ru',
]

# Additional Russian domains (lower priority).
RUSSIAN_EXTRA_DOMAINS = [
    'internet.ru', 'myrambler.ru', 'lenta.ru', 'ro.ru', 'r0.ru',
    'yandex.by', 'yandex.kz',
]

# International domains — only appended when an international username hint
# is present (e.g., the VK screen_name looks non-Cyrillic and non-translit).
INTERNATIONAL_DOMAINS = [
    'gmail.com', 'outlook.com', 'hotmail.com',
]


def _has_mx(domain: str) -> bool:
    """
    Return True if *domain* has at least one MX (or A/AAAA fallback) record.

    Results are cached globally for the process lifetime so that repeated
    calls within a single investigation run cost only one DNS round-trip
    per unique domain.

    If dnspython is not installed, always returns True (no filtering).
    """
    with _mx_lock:
        if domain in _mx_cache:
            return _mx_cache[domain]
        # Pre-seeded known-good list — skip DNS lookup entirely.
        if domain in _KNOWN_GOOD_MX:
            _mx_cache[domain] = True
            return True

    try:
        import dns.resolver
        try:
            dns.resolver.resolve(domain, 'MX')
            result = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            # No MX — try A record as fallback (some small providers omit MX)
            try:
                dns.resolver.resolve(domain, 'A')
                result = True
            except Exception as e:
                logger.debug(f"[EmailPattern] A record resolve failed for {domain}: {e}")
                result = False
        except Exception as e:
            # Network error, timeout, etc. — assume good to avoid false drops.
            logger.debug(f"[EmailPattern] MX check network error for {domain}: {e}")
            result = True
    except ImportError:
        # dnspython not installed — skip filtering.
        result = True

    with _mx_lock:
        _mx_cache[domain] = result
    return result


def _validate_domains(domains: List[str]) -> List[str]:
    """Filter *domains* to those that have a resolvable MX record."""
    return [d for d in domains if _has_mx(d)]


def _looks_international(usernames: List[str]) -> bool:
    """
    Heuristic: return True if any username hint looks like it belongs to
    a person who might use an international email provider.

    Criteria: username contains non-translit characters, or explicitly
    matches common English patterns (first.last, etc.).
    """
    import re
    for u in usernames:
        # If it's all-ASCII and looks like a Western first.last pattern,
        # the person might have a gmail/outlook account.
        if re.match(r'^[a-z]+\.[a-z]+\d*$', u.lower()):
            return True
    return False


class EmailPatternSource(BaseSource):
    """
    Generate email candidates from name patterns and known usernames.

    Noise-reduction strategy:
    1. Only emit addresses for domains that have a real MX record (DNS check).
    2. Prioritise Russian mail providers (mail.ru, yandex.ru, bk.ru …)
       because the tool targets Russian-speaking subjects.
    3. Skip year-suffix permutations unless a birth_year hint is passed.
    4. Hard-cap output at 20 results (down from 50).
    5. International domains (gmail, outlook) are only included when the
       username hints look internationally-oriented.
    """

    name = "Email Pattern Generator"
    source_type = SourceType.EMAIL
    source_tier = SourceTier.C
    requires_api_key = False
    rate_limit_per_minute = 999  # No external calls

    # Maximum results to emit. Keeping this low forces downstream holehe/SMTP
    # checkers to work on only the most plausible candidates.
    MAX_RESULTS = 20

    def is_available(self) -> bool:
        return True

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        results: List[SourceResult] = []

        if not name and not username:
            return results

        # Parse name into first/last
        first_name = ""
        last_name = ""
        if name:
            parts = name.strip().split()
            first_name = parts[0] if parts else ""
            last_name = parts[-1] if len(parts) > 1 else ""

        usernames: List[str] = []
        if username:
            usernames = [username] if isinstance(username, str) else list(username)

        # Optional birth year — passed by callers that have profile data.
        birth_year: Optional[str] = kwargs.get('birth_year')

        try:
            candidates = self._generate_candidates(
                first_name=first_name,
                last_name=last_name,
                usernames=usernames,
                birth_year=birth_year,
            )

            seen: Set[str] = set()
            for email_addr, confidence, method in candidates:
                email_lower = email_addr.lower()
                if email_lower in seen:
                    continue
                seen.add(email_lower)

                results.append(SourceResult(
                    data_type='email',
                    value=email_lower,
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=confidence,
                    metadata={'generation_method': method},
                ))

                if len(results) >= self.MAX_RESULTS:
                    break

        except Exception as e:
            self.logger.warning(f"Email pattern generation error: {e}")

        self.logger.info(
            f"Generated {len(results)} email candidates "
            f"(cap={self.MAX_RESULTS}, MX-validated)"
        )
        return results

    # ------------------------------------------------------------------
    # Internal generation logic
    # ------------------------------------------------------------------

    def _generate_candidates(
        self,
        first_name: str,
        last_name: str,
        usernames: List[str],
        birth_year: Optional[str],
    ) -> List[tuple]:
        """
        Return a list of (email, confidence, method) tuples, ordered from
        most-likely to least-likely.

        Domain selection logic:
        - Always try RUSSIAN_PRIORITY_DOMAINS (pre-seeded, no DNS cost).
        - Also try RUSSIAN_EXTRA_DOMAINS after MX validation.
        - Add INTERNATIONAL_DOMAINS only if usernames look international.
        - Skip domains that fail MX check.
        """
        from ..email_generator import (
            transliterate, is_cyrillic, is_valid_email, RUSSIAN_EMAIL_DOMAINS
        )

        candidates: List[tuple] = []
        seen_emails: Set[str] = set()

        # Build domain lists
        russian_primary = _validate_domains(RUSSIAN_PRIORITY_DOMAINS)
        russian_extra = _validate_domains(RUSSIAN_EXTRA_DOMAINS)
        intl = (
            _validate_domains(INTERNATIONAL_DOMAINS)
            if _looks_international(usernames)
            else []
        )
        ordered_domains = russian_primary + russian_extra + intl

        if not ordered_domains:
            # Fallback: use the pre-defined list without MX checks
            ordered_domains = RUSSIAN_PRIORITY_DOMAINS

        def add(local: str, domain: str, confidence: float, method: str):
            if not local or len(local) < 2:
                return
            addr = f"{local}@{domain}".lower()
            if addr in seen_emails or not is_valid_email(addr):
                return
            if domain not in ordered_domains:
                return
            seen_emails.add(addr)
            candidates.append((addr, confidence, method))

        # Transliterate names
        fn = transliterate(first_name) if is_cyrillic(first_name) else first_name.lower()
        ln = transliterate(last_name) if is_cyrillic(last_name) else last_name.lower()
        f_init = fn[0] if fn else ''
        l_init = ln[0] if ln else ''

        # ---- Tier 1: username@domain — highest confidence ----
        # A known username is the best signal we have.
        for uname in usernames[:3]:
            uname = uname.lower().strip().lstrip('@')
            if not uname or len(uname) < 2:
                continue
            # Primary Russian domains get 0.45; international get 0.35
            for dom in russian_primary:
                add(uname, dom, 0.45, f'username:{uname}')
            for dom in russian_extra:
                add(uname, dom, 0.38, f'username:{uname}')
            for dom in intl:
                add(uname, dom, 0.35, f'username:{uname}')

        # ---- Tier 2: best name patterns on Russian primary domains ----
        if fn and ln:
            best_patterns = [
                (f"{fn}.{ln}", 0.40),   # pavel.durov
                (f"{fn}{ln}", 0.38),    # paveldurov
                (f"{f_init}{ln}", 0.37),  # pdurov
                (f"{f_init}.{ln}", 0.36),  # p.durov
                (f"{ln}.{fn}", 0.35),   # durov.pavel
                (f"{ln}{fn}", 0.34),    # durovpavel
            ]
            for pat, conf in best_patterns:
                for dom in russian_primary:
                    add(pat, dom, conf, 'name_pattern:best')

        # ---- Tier 3: birth_year combinations on top patterns ----
        if birth_year and fn and ln:
            year2 = birth_year[-2:]  # e.g. "90" from "1990"
            year_patterns = [
                f"{fn}.{ln}",
                f"{fn}{ln}",
                f"{f_init}{ln}",
            ]
            for pat in year_patterns:
                for yr in [year2, birth_year]:
                    for dom in russian_primary[:3]:  # mail.ru, yandex.ru, bk.ru only
                        add(f"{pat}{yr}", dom, 0.33, f'name_year:{yr}')
                        add(f"{pat}_{yr}", dom, 0.32, f'name_year:{yr}')

        # ---- Tier 4: wider name patterns on extra Russian domains ----
        if fn and ln:
            extra_patterns = [
                (f"{fn}_{ln}", 0.30),
                (f"{ln}_{fn}", 0.29),
                (f"{ln}{f_init}", 0.28),
                (fn, 0.27),
                (ln, 0.26),
            ]
            for pat, conf in extra_patterns:
                for dom in russian_primary + russian_extra:
                    add(pat, dom, conf, 'name_pattern:extra')

        # ---- Tier 5: username variants (cleaned / dot-form) ----
        for uname in usernames[:3]:
            import re
            uname = uname.lower().strip().lstrip('@')
            clean = re.sub(r'[_\d]+$', '', uname)
            dot = uname.replace('_', '.')
            for variant in {clean, dot} - {uname}:
                if len(variant) >= 2:
                    for dom in russian_primary:
                        add(variant, dom, 0.30, f'username_variant:{variant}')

        return candidates

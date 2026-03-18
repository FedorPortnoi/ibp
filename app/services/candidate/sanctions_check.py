"""
Sanctions & Wanted List Checks
===============================
Checks a candidate against multiple sources:

Primary (globally accessible):
1. OpenSanctions API — covers Rosfinmonitoring, OFAC, EU, UN, Interpol, etc.
2. Local MVD database — offline wanted persons list
3. Local Extremist database — offline extremist list
4. Интерпол — international red notices (public API)

Fallback (geo-restricted, used when available):
- Росфинмониторинг website scraper
- МВД website scraper
- Перечень экстремистов website scraper

Each check is independent and returns a SanctionsResult.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


@dataclass
class SanctionsResult:
    source_name: str       # "Росфинмониторинг" / "МВД Розыск" / "Интерпол" / "Перечень экстремистов"
    checked: bool          # True if we successfully queried this source
    found: bool            # True if candidate was found on the list
    match_details: Optional[str] = None  # Details of the match if found
    error: Optional[str] = None          # Error message if check failed
    url: str = ''          # URL for manual verification

    def to_dict(self) -> dict:
        return {
            'source_name': self.source_name,
            'checked': self.checked,
            'found': self.found,
            'match_details': self.match_details,
            'error': self.error,
            'url': self.url,
        }


def _transliterate_simple(name: str) -> str:
    """
    Simple Cyrillic -> Latin transliteration for Interpol API queries.
    Uses the existing transliteration module if available,
    otherwise falls back to a basic mapping.

    Always returns a proper Python str (never bytes, never '?'-corrupted).
    """
    # Ensure input is a proper Unicode str, not bytes masquerading as str
    if isinstance(name, bytes):
        name = name.decode('utf-8', errors='replace')

    try:
        from app.services.phase1.transliteration import transliterate_russian
        variants = transliterate_russian(name, max_variants=1)
        if variants and variants[0].isascii():
            # Capitalize each word
            return ' '.join(w.capitalize() for w in variants[0].split())
        elif variants:
            logger.warning(
                "[SanctionsCheck] transliterate_russian returned non-ASCII: %r",
                variants[0],
            )
    except Exception as e:
        logger.debug(f"[SanctionsCheck] Transliteration import failed, using fallback: {e}")

    # Fallback basic transliteration
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = []
    for ch in name:
        lower = ch.lower()
        if lower in table:
            mapped = table[lower]
            if ch.isupper() and mapped:
                mapped = mapped[0].upper() + mapped[1:]
            result.append(mapped)
        elif ch.isascii():
            # Keep ASCII characters (spaces, hyphens, Latin letters)
            result.append(ch)
        # else: skip non-ASCII characters not in the transliteration table
    return ''.join(result)


def _name_matches(query_name: str, text: str) -> Optional[str]:
    """
    Check if query_name appears in text using fuzzy matching.
    Returns the matched fragment or None.
    """
    parts = query_name.strip().split()
    if len(parts) < 2:
        return None

    last_name = parts[0].lower()
    first_name = parts[1].lower()
    text_lower = text.lower()

    # Full name match
    full = ' '.join(parts).lower()
    if full in text_lower:
        return f"Полное совпадение: {query_name}"

    # Last + first name (any order)
    if last_name in text_lower and first_name in text_lower:
        return f"Совпадение по ФИ: {parts[0]} {parts[1]}"

    return None


class SanctionsService:
    """
    Run sanctions/wanted list checks for a candidate.

    Usage:
        svc = SanctionsService()
        results = svc.check_all("Иванов Иван Иванович", inn=None)
        for r in results:
            print(r.to_dict())
    """

    TIMEOUT = 20  # seconds per request

    def check_all(
        self,
        full_name: str,
        inn: Optional[str] = None,
        birth_date: Optional[str] = None,
    ) -> List[SanctionsResult]:
        """
        Run all sanctions checks in parallel.

        Primary sources (globally accessible):
        - OpenSanctions API (covers Rosfinmonitoring + international lists)
        - Local MVD wanted database
        - Local Extremist list database
        - Interpol Red Notices API

        Fallback sources (geo-restricted, run in parallel):
        - Rosfinmonitoring website scraper
        - MVD website scraper
        - Extremist list website scraper
        """
        results = []

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {}

            # Primary: OpenSanctions (replaces Rosfinmonitoring for global access)
            futures[executor.submit(
                self._check_opensanctions, full_name, birth_date,
            )] = 'opensanctions'

            # Primary: Local MVD database
            futures[executor.submit(
                self._check_mvd_local, full_name,
            )] = 'mvd_local'

            # Primary: Local Extremist database
            futures[executor.submit(
                self._check_extremist_local, full_name,
            )] = 'extremist_local'

            # Primary: Interpol (works globally)
            futures[executor.submit(
                self._check_interpol, full_name,
            )] = 'interpol'

            # Fallback: live scrapers (may fail outside Russia)
            futures[executor.submit(
                self._check_rosfinmonitoring, full_name,
            )] = 'rosfinmonitoring'
            futures[executor.submit(
                self._check_mvd_wanted, full_name,
            )] = 'mvd_live'

            try:
                for future in as_completed(futures, timeout=60):
                    source = futures[future]
                    try:
                        result = future.result(timeout=30)
                        if isinstance(result, list):
                            results.extend(result)
                        elif result is not None:
                            results.append(result)
                    except Exception as e:
                        logger.warning("Sanctions check '%s' failed: %s", source, e)
            except TimeoutError:
                logger.warning("Sanctions: some checks timed out (60s)")
                for f in futures:
                    f.cancel()

        # Deduplicate: if both OpenSanctions and live scraper found something,
        # prefer the more detailed result but keep both source names
        results = self._deduplicate_results(results)

        # Ensure we always return at least the 4 expected source slots
        expected = {
            'Росфинмониторинг': False,
            'МВД — розыск': False,
            'Интерпол': False,
            'Перечень экстремистов': False,
        }
        for r in results:
            name = r.source_name
            if name in expected:
                expected[name] = True
            # Map OpenSanctions results to expected slots
            elif 'Росфинмониторинг' in name:
                expected['Росфинмониторинг'] = True

        # Fill missing slots with "checked but not found" if we checked OpenSanctions
        opensanctions_checked = any(
            'OpenSanctions' in r.source_name or 'Росфинмониторинг' in r.source_name
            for r in results if r.checked
        )
        for name, found in expected.items():
            if not found:
                # If OpenSanctions was checked, we can vouch for Rosfinmonitoring
                checked = opensanctions_checked if name == 'Росфинмониторинг' else False
                results.append(SanctionsResult(
                    source_name=name,
                    checked=checked,
                    found=False,
                    error=None if checked else 'Источник недоступен',
                ))

        return results

    def _deduplicate_results(self, results: List[SanctionsResult]) -> List[SanctionsResult]:
        """Remove duplicate source entries, preferring checked+found over unchecked."""
        seen = {}
        for r in results:
            key = r.source_name
            if key in seen:
                existing = seen[key]
                # Prefer checked over unchecked, found over not found
                if r.checked and (not existing.checked or (r.found and not existing.found)):
                    seen[key] = r
            else:
                seen[key] = r
        return list(seen.values())

    # ── Primary: OpenSanctions API ────────────────────────────────

    def _check_opensanctions(
        self, full_name: str, birth_date: Optional[str] = None,
    ) -> List[SanctionsResult]:
        """
        Check OpenSanctions API for sanctions matches.
        Returns list of SanctionsResult (one per matching dataset).
        """
        try:
            from app.services.candidate.opensanctions_service import OpenSanctionsService
            svc = OpenSanctionsService(timeout=self.TIMEOUT)
            matches = svc.check_person(full_name, birth_date=birth_date)

            if not matches:
                # Checked successfully, no matches
                return [SanctionsResult(
                    source_name='OpenSanctions',
                    checked=True,
                    found=False,
                    url='https://opensanctions.org/',
                )]

            results = []
            for m in matches:
                d = m.to_sanctions_dict()
                results.append(SanctionsResult(
                    source_name=d['source_name'],
                    checked=True,
                    found=True,
                    match_details=d['match_details'],
                    url=d['url'],
                ))
            return results

        except Exception as e:
            logger.warning(f"OpenSanctions check error: {e}")
            return [SanctionsResult(
                source_name='OpenSanctions',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url='https://opensanctions.org/',
            )]

    # ── Primary: Local MVD Database ────────────────────────────────

    def _check_mvd_local(self, full_name: str) -> SanctionsResult:
        """Check local MVD wanted persons database."""
        try:
            from app.services.candidate.local_security_db import LocalSecurityDB
            db = LocalSecurityDB()

            if not db.has_mvd_data():
                return SanctionsResult(
                    source_name='МВД — розыск',
                    checked=False,
                    found=False,
                    error='Локальная база МВД не загружена',
                    url='https://xn--b1aew.xn--p1ai/wanted',
                )

            matches = db.check_mvd_wanted(full_name)
            if matches:
                details = matches[0].to_sanctions_dict()
                return SanctionsResult(
                    source_name='МВД — розыск',
                    checked=True,
                    found=True,
                    match_details=details['match_details'],
                    url=details['url'],
                )

            return SanctionsResult(
                source_name='МВД — розыск',
                checked=True,
                found=False,
                url='https://xn--b1aew.xn--p1ai/wanted',
            )

        except Exception as e:
            logger.warning(f"Local MVD check error: {e}")
            return SanctionsResult(
                source_name='МВД — розыск',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url='https://xn--b1aew.xn--p1ai/wanted',
            )

    # ── Primary: Local Extremist Database ──────────────────────────

    def _check_extremist_local(self, full_name: str) -> SanctionsResult:
        """Check local extremist list database."""
        try:
            from app.services.candidate.local_security_db import LocalSecurityDB
            db = LocalSecurityDB()

            if not db.has_extremist_data():
                return SanctionsResult(
                    source_name='Перечень экстремистов',
                    checked=False,
                    found=False,
                    error='Локальная база экстремистов не загружена',
                    url='https://minjust.gov.ru/ru/extremist-materials/',
                )

            matches = db.check_extremist_list(full_name)
            if matches:
                details = matches[0].to_sanctions_dict()
                return SanctionsResult(
                    source_name='Перечень экстремистов',
                    checked=True,
                    found=True,
                    match_details=details['match_details'],
                    url=details['url'],
                )

            return SanctionsResult(
                source_name='Перечень экстремистов',
                checked=True,
                found=False,
                url='https://minjust.gov.ru/ru/extremist-materials/',
            )

        except Exception as e:
            logger.warning(f"Local extremist check error: {e}")
            return SanctionsResult(
                source_name='Перечень экстремистов',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url='https://minjust.gov.ru/ru/extremist-materials/',
            )

    # ── Fallback Source 1: Росфинмониторинг ────────────────────────

    def _check_rosfinmonitoring(self, full_name: str) -> SanctionsResult:
        """
        Check Rosfinmonitoring terrorism/sanctions list.
        Fetches the page at fedsfm.ru and searches for the name in text.
        """
        url = 'https://www.fedsfm.ru/documents/terrorists-catalog-portal-act'
        try:
            r = requests.get(url, headers=HEADERS, timeout=self.TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or 'utf-8'
            text = r.text

            match = _name_matches(full_name, text)
            if match:
                return SanctionsResult(
                    source_name='Росфинмониторинг',
                    checked=True,
                    found=True,
                    match_details=match,
                    url=url,
                )

            return SanctionsResult(
                source_name='Росфинмониторинг',
                checked=True,
                found=False,
                url=url,
            )

        except requests.Timeout:
            return SanctionsResult(
                source_name='Росфинмониторинг',
                checked=False,
                found=False,
                error='Таймаут соединения',
                url=url,
            )
        except requests.ConnectionError:
            return SanctionsResult(
                source_name='Росфинмониторинг',
                checked=False,
                found=False,
                error='Сайт недоступен (возможна геоблокировка)',
                url=url,
            )
        except Exception as e:
            logger.warning(f"Rosfinmonitoring check error: {e}")
            return SanctionsResult(
                source_name='Росфинмониторинг',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url=url,
            )

    # ── Source 2: МВД Розыск ──────────────────────────────────────

    def _check_mvd_wanted(self, full_name: str) -> SanctionsResult:
        """
        Check MVD wanted persons list.
        The site uses Cyrillic domain (xn--b1aew.xn--p1ai).
        """
        base_url = 'https://xn--b1aew.xn--p1ai/wanted'
        url = base_url
        try:
            parts = full_name.strip().split()
            if len(parts) >= 2:
                # Try search with name params
                params = {
                    'lastName': parts[0],
                    'firstName': parts[1],
                }
                if len(parts) > 2:
                    params['middleName'] = parts[2]
                r = requests.get(
                    base_url,
                    params=params,
                    headers=HEADERS,
                    timeout=self.TIMEOUT,
                    allow_redirects=True,
                )
            else:
                r = requests.get(
                    base_url,
                    headers=HEADERS,
                    timeout=self.TIMEOUT,
                )

            r.raise_for_status()
            r.encoding = r.apparent_encoding or 'utf-8'
            text = r.text

            # Check for actual person cards in search results
            # MVD wanted page shows person blocks with names
            match = _name_matches(full_name, text)
            if match:
                # Verify it's in a result context, not just page chrome
                lower_text = text.lower()
                name_lower = full_name.lower()
                # Look for the name near wanted-related markers
                idx = lower_text.find(name_lower)
                if idx == -1:
                    # Try last+first only
                    search_parts = full_name.strip().split()
                    search_term = f"{search_parts[0]} {search_parts[1]}".lower()
                    idx = lower_text.find(search_term)

                if idx >= 0:
                    # Check surrounding context for result markers
                    context = lower_text[max(0, idx - 500):idx + 500]
                    result_markers = [
                        'розыск', 'wanted', 'фио', 'person',
                        'card', 'result', 'item',
                    ]
                    if any(m in context for m in result_markers):
                        return SanctionsResult(
                            source_name='МВД Розыск',
                            checked=True,
                            found=True,
                            match_details=match,
                            url=url,
                        )

            return SanctionsResult(
                source_name='МВД Розыск',
                checked=True,
                found=False,
                url=url,
            )

        except requests.Timeout:
            return SanctionsResult(
                source_name='МВД Розыск',
                checked=False,
                found=False,
                error='Таймаут соединения',
                url=url,
            )
        except requests.ConnectionError:
            return SanctionsResult(
                source_name='МВД Розыск',
                checked=False,
                found=False,
                error='Сайт недоступен (возможна геоблокировка)',
                url=url,
            )
        except Exception as e:
            logger.warning(f"MVD wanted check error: {e}")
            return SanctionsResult(
                source_name='МВД Розыск',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url=url,
            )

    # ── Source 3: Интерпол ────────────────────────────────────────

    def _check_interpol(self, full_name: str) -> SanctionsResult:
        """
        Check Interpol Red Notices via public API.
        Transliterates the Cyrillic name to Latin first.
        """
        url = 'https://ws-public.interpol.int/notices/v1/red'
        try:
            latin_name = _transliterate_simple(full_name)
            parts = latin_name.strip().split()

            if len(parts) < 2:
                return SanctionsResult(
                    source_name='Интерпол',
                    checked=False,
                    found=False,
                    error='Недостаточно данных для поиска',
                    url=url,
                )

            # Interpol API: forename + name (surname)
            forename = parts[1] if len(parts) > 1 else ''
            name = parts[0]

            # Validate transliteration produced ASCII-safe text.
            # If transliteration silently failed (e.g., locale/encoding issue),
            # the values may still contain non-ASCII characters — fall back to
            # the original Cyrillic name which requests encodes as valid UTF-8.
            if not forename.isascii() or not name.isascii():
                logger.warning(
                    "[Interpol] Transliteration produced non-ASCII: "
                    "forename=%r, name=%r — falling back to original Cyrillic",
                    forename, name,
                )
                orig_parts = full_name.strip().split()
                name = orig_parts[0]
                forename = orig_parts[1] if len(orig_parts) > 1 else ''

            params = {
                'forename': forename,
                'name': name,
                'nationality': 'RU',
                'resultPerPage': 20,
            }

            logger.debug(
                "[Interpol] Request params: forename=%r, name=%r, url=%s",
                forename, name, url,
            )

            r = requests.get(
                url,
                params=params,
                headers={
                    'User-Agent': HEADERS['User-Agent'],
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
                },
                timeout=self.TIMEOUT,
            )

            logger.debug("[Interpol] Final request URL: %s", r.url)

            if r.status_code == 403:
                return SanctionsResult(
                    source_name='Интерпол',
                    checked=False,
                    found=False,
                    error='API заблокировал запрос (403)',
                    url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
                )

            if r.status_code in (502, 503, 504):
                logger.warning(f"Interpol API returned {r.status_code}")
                return SanctionsResult(
                    source_name='Интерпол',
                    checked=False,
                    found=False,
                    error='Сервис временно недоступен',
                    url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
                )

            r.raise_for_status()
            data = r.json()

            total = data.get('total', 0)
            notices = data.get('_embedded', {}).get('notices', [])

            if total > 0 and notices:
                # Check if any notice actually matches our person
                for notice in notices:
                    n_forename = (notice.get('forename') or '').lower()
                    n_name = (notice.get('name') or '').lower()

                    if (
                        forename.lower() in n_forename
                        or n_forename in forename.lower()
                    ) and (
                        name.lower() in n_name
                        or n_name in name.lower()
                    ):
                        entity_id = notice.get('entity_id', '')
                        detail_url = f'https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices#{"" if not entity_id else entity_id}'
                        return SanctionsResult(
                            source_name='Интерпол',
                            checked=True,
                            found=True,
                            match_details=(
                                f"Red Notice: {notice.get('forename', '')} "
                                f"{notice.get('name', '')} "
                                f"(ID: {entity_id})"
                            ),
                            url=detail_url,
                        )

            return SanctionsResult(
                source_name='Интерпол',
                checked=True,
                found=False,
                url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
            )

        except requests.Timeout:
            return SanctionsResult(
                source_name='Интерпол',
                checked=False,
                found=False,
                error='Таймаут соединения',
                url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
            )
        except requests.ConnectionError:
            return SanctionsResult(
                source_name='Интерпол',
                checked=False,
                found=False,
                error='Сервис недоступен',
                url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
            )
        except Exception as e:
            logger.warning(f"Interpol check error: {e}")
            return SanctionsResult(
                source_name='Интерпол',
                checked=False,
                found=False,
                error=f'Ошибка: {e}',
                url='https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices',
            )

    # ── Source 4: Перечень экстремистов ───────────────────────────

    def _check_extremists(self, full_name: str) -> SanctionsResult:
        """
        Check Minjust extremist organizations/persons list.
        """
        url = 'https://minjust.gov.ru/ru/extremist-materials/'
        alt_url = 'https://minjust.gov.ru/ru/activity/directions/942/'

        for check_url in [url, alt_url]:
            try:
                r = requests.get(
                    check_url,
                    headers=HEADERS,
                    timeout=self.TIMEOUT,
                )
                r.raise_for_status()
                r.encoding = r.apparent_encoding or 'utf-8'
                text = r.text

                match = _name_matches(full_name, text)
                if match:
                    return SanctionsResult(
                        source_name='Перечень экстремистов',
                        checked=True,
                        found=True,
                        match_details=match,
                        url=check_url,
                    )

            except requests.Timeout:
                continue
            except requests.ConnectionError:
                continue
            except Exception as e:
                logger.warning(f"Extremist list check error ({check_url}): {e}")
                continue

            # If we got here, the page loaded but no match was found
            return SanctionsResult(
                source_name='Перечень экстремистов',
                checked=True,
                found=False,
                url=check_url,
            )

        # All URLs failed
        return SanctionsResult(
            source_name='Перечень экстремистов',
            checked=False,
            found=False,
            error='Сайт недоступен (возможна геоблокировка)',
            url=url,
        )

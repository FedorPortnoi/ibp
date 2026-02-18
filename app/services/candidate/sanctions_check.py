"""
Sanctions & Wanted List Checks
===============================
Checks a candidate against 4 sources:
1. Росфинмониторинг — terrorism financing sanctions
2. МВД Розыск — federal wanted persons
3. Интерпол — international red notices
4. Перечень экстремистов — extremist list (Минюст)

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
    Simple Cyrillic → Latin transliteration for Interpol API queries.
    Uses the existing transliteration module if available,
    otherwise falls back to a basic mapping.
    """
    try:
        from app.services.phase1.transliteration import transliterate_russian
        variants = transliterate_russian(name, max_variants=1)
        if variants:
            # Capitalize each word
            return ' '.join(w.capitalize() for w in variants[0].split())
    except Exception:
        pass

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
        else:
            result.append(ch)
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
    ) -> List[SanctionsResult]:
        """
        Run all 4 checks in parallel.
        Returns list of 4 SanctionsResult objects.
        """
        results = [None, None, None, None]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._check_rosfinmonitoring, full_name): 0,
                executor.submit(self._check_mvd_wanted, full_name): 1,
                executor.submit(self._check_interpol, full_name): 2,
                executor.submit(self._check_extremists, full_name): 3,
            }

            for future in as_completed(futures, timeout=60):
                idx = futures[future]
                try:
                    results[idx] = future.result(timeout=30)
                except Exception as e:
                    logger.warning(f"Sanctions check #{idx} failed: {e}")
                    labels = [
                        'Росфинмониторинг', 'МВД Розыск',
                        'Интерпол', 'Перечень экстремистов',
                    ]
                    results[idx] = SanctionsResult(
                        source_name=labels[idx],
                        checked=False,
                        found=False,
                        error=str(e),
                    )

        # Fill any None slots (shouldn't happen, but be safe)
        labels = [
            'Росфинмониторинг', 'МВД Розыск',
            'Интерпол', 'Перечень экстремистов',
        ]
        for i in range(4):
            if results[i] is None:
                results[i] = SanctionsResult(
                    source_name=labels[i],
                    checked=False,
                    found=False,
                    error='Проверка не завершена',
                )

        return results

    # ── Source 1: Росфинмониторинг ────────────────────────────────

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

            params = {
                'forename': forename,
                'name': name,
                'nationality': 'RU',
                'resultPerPage': 20,
            }

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

            if r.status_code == 403:
                return SanctionsResult(
                    source_name='Интерпол',
                    checked=False,
                    found=False,
                    error='API заблокировал запрос (403)',
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

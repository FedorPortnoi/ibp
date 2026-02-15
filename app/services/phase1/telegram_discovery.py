"""
Telegram Discovery Service — Phase 1
=====================================
Finds Telegram accounts for a target using three sequential methods:

  A) VK Cross-Reference — check t.me/{vk_screen_name} for each screen_name
     passed from the frontend (extracted from VK search results).
  B) Username Guessing — generate candidate usernames from name, check t.me.
  C) Telethon Directory Search — search Telegram's user directory by name.

Frontend sends VK screen_names AFTER VK search completes, so Method A uses
real VK results instead of running a duplicate VK search.
"""

import logging
import os
import re
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TelegramDiscoveryService:
    """
    Discovers Telegram accounts for a target person.

    Usage:
        svc = TelegramDiscoveryService()
        try:
            results = svc.discover('Артём', 'Козлов', vk_screen_names=['artem_kozlov', 'kozlov99'])
        finally:
            svc.close()
    """

    MAX_VK_CROSSREF = 50       # Max screen_names to check in Method A
    MAX_USERNAME_CANDIDATES = 25  # Max generated candidates in Method B
    MAX_TELETHON_RESULTS = 100   # Max results from Telethon Method C
    MAX_TOTAL_RESULTS = 100      # Hard cap on total results
    CHECK_DELAY = 0.35           # Seconds between t.me requests

    def __init__(self):
        from app.services.phase2.telegram_crossref import TelegramCrossRef
        self._checker = TelegramCrossRef(request_delay=self.CHECK_DELAY)

    def discover(
        self,
        first_name: str,
        last_name: str,
        vk_screen_names: List[str] = None,
        city: str = '',
        age_from: int = None,
        age_to: int = None,
    ) -> List[Dict]:
        """
        Run all three Telegram discovery methods sequentially.

        Args:
            first_name: Target's first name (Cyrillic or Latin).
            last_name: Target's last name.
            vk_screen_names: Screen names from VK search results (for Method A).
            city: Optional city filter.
            age_from: Optional minimum age.
            age_to: Optional maximum age.

        Returns:
            List of profile dicts in the standard search response format.
        """
        all_profiles = {}  # Deduplicate by username (lowercase)
        count_a = count_b = count_c = 0

        # ── Method A: VK Cross-Reference ──
        try:
            profiles_a = self._method_a_vk_crossref(
                vk_screen_names or [], first_name, last_name
            )
            for p in profiles_a:
                key = p.get('username', '').lower()
                if key and key not in all_profiles:
                    all_profiles[key] = p
                    count_a += 1
        except Exception as e:
            logger.warning(f"TG Method A (VK cross-ref) error: {e}")

        # ── Method B: Username Guessing ──
        try:
            profiles_b = self._method_b_username_guessing(
                first_name, last_name, set(all_profiles.keys())
            )
            for p in profiles_b:
                key = p.get('username', '').lower()
                if key and key not in all_profiles:
                    all_profiles[key] = p
                    count_b += 1
        except Exception as e:
            logger.warning(f"TG Method B (username guessing) error: {e}")

        # ── Method C: Telethon Directory Search ──
        try:
            profiles_c = self._method_c_telethon_search(
                first_name, last_name, set(all_profiles.keys())
            )
            for p in profiles_c:
                key = p.get('username', '').lower()
                if key and key not in all_profiles:
                    all_profiles[key] = p
                    count_c += 1
        except Exception as e:
            logger.warning(f"TG Method C (Telethon) error: {e}")

        results = list(all_profiles.values())[:self.MAX_TOTAL_RESULTS]
        deduped = (count_a + count_b + count_c) - len(results)

        logger.info(
            f"Telegram search complete: {len(results)} unique profiles "
            f"({count_a} cross-ref + {count_b} guessing + {count_c} Telethon"
            f"{f', {deduped} deduped' if deduped > 0 else ''})"
        )
        return results

    # ─────────────────────────────────────────────────────────────
    # Method A: VK Cross-Reference
    # ─────────────────────────────────────────────────────────────

    def _method_a_vk_crossref(
        self,
        vk_screen_names: List[str],
        first_name: str,
        last_name: str,
    ) -> List[Dict]:
        """
        For each VK screen_name, check if the same username exists on Telegram.
        Many Russians use the same username across VK and Telegram.
        """
        if not vk_screen_names:
            logger.info("TG Method A (VK cross-ref): no VK screen_names provided, skipping")
            return []

        # Filter out empty and numeric VK IDs (id123456)
        candidates = []
        for sn in vk_screen_names:
            sn = (sn or '').strip()
            if not sn:
                continue
            if sn.startswith('id') and sn[2:].isdigit():
                continue
            if sn.lower() not in {c.lower() for c in candidates}:
                candidates.append(sn)

        candidates = candidates[:self.MAX_VK_CROSSREF]
        logger.info(f"TG Method A (VK cross-ref): checking {len(candidates)} screen_names from VK...")

        found = []
        for screen_name in candidates:
            tg_profile = self._checker.check_username_web(screen_name)

            if tg_profile.exists and tg_profile.is_personal:
                # Method A doesn't require strict name verification
                # (VK profile was already verified by VK search), but check anyway
                match = self._checker._verify_names(
                    first_name, last_name, tg_profile.display_name
                )
                if match['match']:
                    confidence = 'high' if match['score'] > 0.7 else 'medium'
                else:
                    confidence = 'low'

                profile_dict = self._to_dict(
                    tg_profile,
                    confidence=confidence,
                    source='Совпадение с VK username',
                )
                found.append(profile_dict)
                logger.info(f"TG Method A: found @{screen_name} (VK cross-ref)")

        logger.info(f"TG Method A (VK cross-ref): checked {len(candidates)}, found {len(found)}")
        return found

    # ─────────────────────────────────────────────────────────────
    # Method B: Username Guessing
    # ─────────────────────────────────────────────────────────────

    def _method_b_username_guessing(
        self,
        first_name: str,
        last_name: str,
        already_checked: set,
    ) -> List[Dict]:
        """
        Generate plausible Telegram usernames from the name,
        check each on t.me, verify display name matches.
        """
        candidates = self._generate_telegram_candidates(first_name, last_name)
        # Remove already checked usernames
        candidates = [c for c in candidates if c.lower() not in already_checked]

        logger.info(f"TG Method B (guessing): checking {len(candidates)} candidates...")

        found = []
        for candidate in candidates:
            already_checked.add(candidate.lower())
            tg_profile = self._checker.check_username_web(candidate)

            if tg_profile.exists and tg_profile.is_personal:
                match = self._checker._verify_names(
                    first_name, last_name, tg_profile.display_name
                )
                if match['match']:
                    confidence = 'medium' if match['score'] > 0.7 else 'low'
                    source = 'Совпадение username'
                else:
                    # Username matches pattern but display name doesn't match
                    continue

                profile_dict = self._to_dict(
                    tg_profile,
                    confidence=confidence,
                    source=source,
                )
                found.append(profile_dict)
                logger.info(f"TG Method B: found @{candidate} (guessing)")

        logger.info(f"TG Method B (guessing): checked {len(candidates)}, found {len(found)}")
        return found

    # ─────────────────────────────────────────────────────────────
    # Method C: Telethon Directory Search
    # ─────────────────────────────────────────────────────────────

    def _method_c_telethon_search(
        self,
        first_name: str,
        last_name: str,
        already_checked: set,
    ) -> List[Dict]:
        """
        Use Telethon's contacts.SearchRequest to find Telegram users by name.
        Searches both Cyrillic and Latin transliteration of the name.
        """
        api_id = os.environ.get('TELEGRAM_API_ID', '')
        api_hash = os.environ.get('TELEGRAM_API_HASH', '')
        phone = os.environ.get('TELEGRAM_PHONE', '')

        if not all([api_id, api_hash, phone]):
            logger.info("TG Method C: Telethon credentials not configured, skipping")
            return []

        try:
            import asyncio
            from telethon import TelegramClient
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.errors import FloodWaitError

            session_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', '..', 'tg_session'
            )
            os.makedirs(session_dir, exist_ok=True)
            session_path = os.path.join(session_dir, 'ibp_session')

            # Build search queries (Cyrillic + Latin)
            search_queries = []
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                search_queries.append(full_name)

            latin_name = self._transliterate_full_name(first_name, last_name)
            if latin_name and latin_name.lower() != full_name.lower():
                search_queries.append(latin_name)

            async def _search():
                client = TelegramClient(session_path, int(api_id), api_hash)
                await client.connect()

                if not await client.is_user_authorized():
                    logger.warning(
                        "TG Method C: Telethon session not authorized. "
                        "Run 'python scripts/telethon_auth.py' first."
                    )
                    await client.disconnect()
                    return []

                profiles = []
                try:
                    for query in search_queries:
                        logger.info(f'TG Method C (Telethon): searching directory for "{query}"...')
                        try:
                            result = await client(SearchRequest(
                                q=query,
                                limit=self.MAX_TELETHON_RESULTS,
                            ))

                            for user in result.users:
                                if getattr(user, 'bot', False):
                                    continue

                                username = getattr(user, 'username', '') or ''
                                if username.lower() in already_checked:
                                    continue

                                display = f"{user.first_name or ''} {user.last_name or ''}".strip()
                                if not username and not display:
                                    continue

                                already_checked.add(username.lower())

                                # Verify name match
                                match = self._checker._verify_names(
                                    first_name, last_name, display
                                )
                                if match['match']:
                                    confidence = 'high' if match['score'] > 0.7 else 'medium'
                                else:
                                    confidence = 'low'

                                profiles.append({
                                    'platform': 'telegram',
                                    'id': str(user.id),
                                    'url': f'https://t.me/{username}' if username else '',
                                    'first_name': user.first_name or '',
                                    'last_name': user.last_name or '',
                                    'photo_url': None,
                                    'city': '',
                                    'age': None,
                                    'username': username,
                                    'bio': '',
                                    'confidence': confidence,
                                    'source': 'Поиск Telegram',
                                    'source_method': 'Telethon directory search',
                                })

                        except FloodWaitError as e:
                            logger.warning(f"TG Method C: Telethon flood wait: {e.seconds}s")
                            break
                        except Exception as e:
                            logger.warning(f"TG Method C: Telethon search error for '{query}': {e}")

                finally:
                    await client.disconnect()

                return profiles

            loop = asyncio.new_event_loop()
            try:
                found = loop.run_until_complete(_search())
            finally:
                loop.close()

            logger.info(f"TG Method C (Telethon): found {len(found)} users")
            return found

        except ImportError:
            logger.info("TG Method C: Telethon not installed, skipping directory search")
            return []
        except Exception as e:
            logger.warning(f"TG Method C: Telethon error: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # Username Generation
    # ─────────────────────────────────────────────────────────────

    def _generate_telegram_candidates(self, first_name: str, last_name: str) -> List[str]:
        """
        Generate plausible Telegram usernames from a Russian name.
        Uses multi-system transliteration + diminutive variants.
        """
        try:
            from app.services.phase1.transliteration import transliterate_name_part
            first_variants = transliterate_name_part(first_name.lower(), max_variants=2)
            last_variants = transliterate_name_part(last_name.lower(), max_variants=2)
        except (ImportError, Exception):
            first_variants = [self._basic_translit(first_name)]
            last_variants = [self._basic_translit(last_name)]

        candidates = []
        for first in first_variants:
            for last in last_variants:
                first = first.replace("'", '').replace(' ', '')
                last = last.replace("'", '').replace(' ', '')
                if not first or not last:
                    continue

                candidates.extend([
                    f"{first}_{last}",       # artem_kozlov
                    f"{last}_{first}",       # kozlov_artem
                    f"{first}{last}",        # artemkozlov
                    f"{last}{first}",        # kozlovartem
                    f"{first[0]}{last}",     # akozlov
                    f"{first[0]}_{last}",    # a_kozlov
                    f"{first}.{last}",       # artem.kozlov
                    f"{last}.{first}",       # kozlov.artem
                    f"{first[0]}.{last}",    # a.kozlov
                    f"{last}_{first[0]}",    # kozlov_a
                    f"{first}_{last[0]}",    # artem_k
                    f"{last}.{first[0]}",    # kozlov.a
                ])

        # Add diminutive variants (e.g., sasha_kozlov for Александр Козлов)
        try:
            from app.services.phase1.russian_diminutives import get_all_name_variants
            diminutives = get_all_name_variants(first_name)
            for dim in list(diminutives)[:3]:
                dim_latin = self._basic_translit(dim)
                if dim_latin and last_variants:
                    last = last_variants[0].replace("'", '').replace(' ', '')
                    if last:
                        candidates.extend([
                            f"{dim_latin}_{last}",
                            f"{dim_latin}.{last}",
                            f"{dim_latin}{last}",
                        ])
        except (ImportError, Exception):
            pass

        # Deduplicate, filter valid Telegram usernames (5+ chars, starts with letter)
        seen = set()
        valid = []
        for c in candidates:
            cl = c.lower()
            if cl in seen:
                continue
            seen.add(cl)
            if len(c) >= 5 and re.match(r'^[a-zA-Z][a-zA-Z0-9_.]+$', c):
                valid.append(c)

        return valid[:self.MAX_USERNAME_CANDIDATES]

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _transliterate_full_name(self, first_name: str, last_name: str) -> str:
        """Transliterate a full name to Latin for Telethon search."""
        try:
            from app.services.phase1.transliteration import transliterate_name_part
            first_variants = transliterate_name_part(first_name.lower(), max_variants=1)
            last_variants = transliterate_name_part(last_name.lower(), max_variants=1)
            first_latin = first_variants[0].title() if first_variants else ''
            last_latin = last_variants[0].title() if last_variants else ''
            return f"{first_latin} {last_latin}".strip()
        except (ImportError, Exception):
            first_latin = self._basic_translit(first_name).title()
            last_latin = self._basic_translit(last_name).title()
            return f"{first_latin} {last_latin}".strip()

    @staticmethod
    def _basic_translit(text: str) -> str:
        """Basic Cyrillic to Latin transliteration fallback."""
        table = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        return ''.join(table.get(ch, ch) for ch in text.lower())

    @staticmethod
    def _to_dict(tg_profile, confidence: str, source: str) -> Dict:
        """Convert a TelegramProfile dataclass to the standard search response dict."""
        return {
            'platform': 'telegram',
            'id': '',
            'url': f'https://t.me/{tg_profile.username}',
            'first_name': tg_profile.display_name.split()[0] if tg_profile.display_name else '',
            'last_name': ' '.join(tg_profile.display_name.split()[1:]) if tg_profile.display_name else '',
            'photo_url': tg_profile.photo_url,
            'city': '',
            'age': None,
            'username': tg_profile.username,
            'bio': tg_profile.bio[:200] if tg_profile.bio else '',
            'confidence': confidence,
            'source': source,
        }

    def close(self):
        """Clean up resources."""
        if self._checker:
            self._checker.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

    from dotenv import load_dotenv
    load_dotenv()

    # Test search
    from flask import Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ibp.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    svc = TelegramDiscoveryService()
    query_parts = sys.argv[1:] if len(sys.argv) > 1 else ['Артём', 'Козлов']
    first = query_parts[0] if query_parts else 'Артём'
    last = query_parts[1] if len(query_parts) > 1 else 'Козлов'

    results = svc.discover(first, last, vk_screen_names=['artem_kozlov', 'kozlov99'])
    print(f"\nFound {len(results)} Telegram profiles for {first} {last}")
    for r in results:
        print(f"  @{r['username']} - {r['first_name']} {r['last_name']} ({r['confidence']}) [{r['source']}]")

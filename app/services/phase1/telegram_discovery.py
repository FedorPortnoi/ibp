"""
Telegram Discovery Service — Phase 1
=====================================
Finds Telegram accounts for a target using three methods:
1. VK screen_name cross-reference (reuses Phase 2 telegram_crossref module)
2. Username guessing from name (transliterate + common patterns)
3. Telethon directory search (optional, requires API credentials)

Each method produces TelegramProfile results with confidence ratings.
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
        results = svc.discover('Артём', 'Козлов')
    """

    MAX_VK_CROSSREF = 10
    MAX_USERNAME_CANDIDATES = 12
    USERNAME_CHECK_DELAY = 1.5  # seconds between t.me checks
    VK_CROSSREF_DELAY = 1.0

    def __init__(self):
        from app.services.phase2.telegram_crossref import TelegramCrossRef
        self._checker = TelegramCrossRef(request_delay=self.USERNAME_CHECK_DELAY)

    def discover(
        self,
        first_name: str,
        last_name: str,
        city: str = '',
        age_from: int = None,
        age_to: int = None,
    ) -> List[Dict]:
        """
        Run all three Telegram discovery methods and return unified results.

        Returns list of profile dicts in the standard search response format.
        """
        results = []
        seen_usernames = set()

        # Method 1: VK cross-reference (screen_names + connections.telegram)
        try:
            method1 = self._vk_crossref(first_name, last_name, city, age_from, age_to)
            for profile in method1:
                username = profile.get('username', '').lower()
                if username and username not in seen_usernames:
                    seen_usernames.add(username)
                    results.append(profile)
        except Exception as e:
            logger.warning(f"Telegram Method 1 (VK cross-ref) error: {e}")

        # Method 2: Username guessing
        try:
            method2 = self._username_guessing(first_name, last_name, seen_usernames)
            for profile in method2:
                username = profile.get('username', '').lower()
                if username and username not in seen_usernames:
                    seen_usernames.add(username)
                    results.append(profile)
        except Exception as e:
            logger.warning(f"Telegram Method 2 (username guessing) error: {e}")

        # Method 3: Telethon directory search
        try:
            method3 = self._telethon_search(first_name, last_name, seen_usernames)
            for profile in method3:
                username = profile.get('username', '').lower()
                if username and username not in seen_usernames:
                    seen_usernames.add(username)
                    results.append(profile)
        except Exception as e:
            logger.warning(f"Telegram Method 3 (Telethon) error: {e}")

        logger.info(f"Telegram discovery: found {len(results)} profiles for {first_name} {last_name}")
        return results

    def _vk_crossref(
        self,
        first_name: str,
        last_name: str,
        city: str = '',
        age_from: int = None,
        age_to: int = None,
    ) -> List[Dict]:
        """
        Method 1: Run a lightweight VK API search, then cross-reference
        screen_names and connections.telegram against Telegram.
        """
        results = []
        query = f"{first_name} {last_name}"

        # Get VK profiles via the existing search
        vk_profiles = self._quick_vk_search(query, city, age_from, age_to)
        if not vk_profiles:
            return results

        checked_usernames = set()

        # Step 1: Check VK connections.telegram field (highest priority)
        for vk_profile in vk_profiles[:self.MAX_VK_CROSSREF]:
            tg_username = self._get_vk_connections_telegram(vk_profile)
            if tg_username and tg_username.lower() not in checked_usernames:
                checked_usernames.add(tg_username.lower())
                tg_profile = self._checker.check_username_web(tg_username)
                if tg_profile.exists and tg_profile.is_personal:
                    results.append(self._to_dict(
                        tg_profile,
                        confidence='high',
                        source='VK связь (подтверждено)',
                    ))

        # Step 2: Check VK screen_names on Telegram
        for vk_profile in vk_profiles[:self.MAX_VK_CROSSREF]:
            screen_name = (
                vk_profile.get('screen_name')
                or vk_profile.get('domain')
                or ''
            )
            if not screen_name or screen_name.lower() in checked_usernames:
                continue
            # Skip numeric VK IDs
            if screen_name.startswith('id') and screen_name[2:].isdigit():
                continue

            checked_usernames.add(screen_name.lower())
            tg_profile = self._checker.check_username_web(screen_name)

            if tg_profile.exists and tg_profile.is_personal:
                # Verify name match
                match = self._checker._verify_names(
                    first_name, last_name, tg_profile.display_name
                )
                if match['match']:
                    confidence = 'high' if match['score'] > 0.7 else 'medium'
                else:
                    confidence = 'low'

                results.append(self._to_dict(
                    tg_profile,
                    confidence=confidence,
                    source='Совпадение с VK username',
                ))

            if len(results) >= 5:
                break

        return results

    def _username_guessing(
        self,
        first_name: str,
        last_name: str,
        already_checked: set,
    ) -> List[Dict]:
        """
        Method 2: Generate plausible Telegram usernames from the name,
        check each on t.me, verify name matches.
        """
        results = []
        candidates = self._generate_telegram_candidates(first_name, last_name)

        for candidate in candidates:
            if candidate.lower() in already_checked:
                continue

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
                    confidence = 'low'
                    source = 'Совпадение username, имя отличается'

                results.append(self._to_dict(
                    tg_profile,
                    confidence=confidence,
                    source=source,
                ))

            if len(results) >= 3:
                break

        return results

    def _telethon_search(
        self,
        first_name: str,
        last_name: str,
        already_checked: set,
    ) -> List[Dict]:
        """
        Method 3: Use Telethon's contacts.search to find Telegram users by name.
        Only runs if TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE are set.
        """
        api_id = os.environ.get('TELEGRAM_API_ID', '')
        api_hash = os.environ.get('TELEGRAM_API_HASH', '')
        phone = os.environ.get('TELEGRAM_PHONE', '')

        if not all([api_id, api_hash, phone]):
            logger.info("Telethon not configured, skipping Telegram directory search")
            return []

        try:
            import asyncio
            from telethon import TelegramClient
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.errors import FloodWaitError

            session_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', '..', 'telegram_session'
            )
            os.makedirs(session_dir, exist_ok=True)
            session_path = os.path.join(session_dir, 'ibp_session')

            async def _search():
                client = TelegramClient(session_path, int(api_id), api_hash)
                await client.connect()

                if not await client.is_user_authorized():
                    logger.info("Telethon session not authorized, skipping")
                    await client.disconnect()
                    return []

                try:
                    query = f"{first_name} {last_name}"
                    result = await client(SearchRequest(q=query, limit=20))

                    profiles = []
                    for user in result.users:
                        username = getattr(user, 'username', '') or ''
                        if username.lower() in already_checked:
                            continue
                        if getattr(user, 'bot', False):
                            continue

                        already_checked.add(username.lower())
                        display = f"{user.first_name or ''} {user.last_name or ''}".strip()

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
                            'photo_url': None,  # Telethon photos need separate download
                            'city': '',
                            'age': None,
                            'username': username,
                            'bio': '',
                            'confidence': confidence,
                            'source': 'Поиск Telegram',
                        })

                    return profiles

                except FloodWaitError as e:
                    logger.warning(f"Telethon flood wait: {e.seconds}s")
                    return []
                finally:
                    await client.disconnect()

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_search())
            finally:
                loop.close()

        except ImportError:
            logger.info("Telethon not installed, skipping directory search")
            return []
        except Exception as e:
            logger.warning(f"Telethon search error: {e}")
            return []

    def _quick_vk_search(
        self,
        query: str,
        city: str = '',
        age_from: int = None,
        age_to: int = None,
    ) -> List[Dict]:
        """
        Run a lightweight VK search to get screen_names for cross-reference.
        Uses the existing BuratinoVKSearch.
        """
        try:
            from app.services.phase1.buratino_vk_search import buratino_vk_search
            profiles, _ = buratino_vk_search.search(
                query=query,
                city=city or None,
                age_from=age_from,
                age_to=age_to,
                count=self.MAX_VK_CROSSREF,
                target_name=query,
            )
            # Convert VKProfileResult to dicts
            return [p.to_dict() for p in profiles]
        except Exception as e:
            logger.warning(f"Quick VK search for TG cross-ref failed: {e}")
            return []

    def _get_vk_connections_telegram(self, vk_profile: Dict) -> Optional[str]:
        """
        Check VK API for connections.telegram field.
        Requires a service token and the user's VK ID.
        """
        vk_id = vk_profile.get('vk_id') or vk_profile.get('id')
        if not vk_id:
            return None

        try:
            import requests as req
            token = os.environ.get('VK_SERVICE_TOKEN', '')
            if not token:
                return None

            resp = req.get('https://api.vk.com/method/users.get', params={
                'user_ids': str(vk_id),
                'fields': 'connections',
                'access_token': token,
                'v': '5.199',
            }, timeout=5)

            data = resp.json()
            users = data.get('response', [])
            if users:
                return users[0].get('telegram')
        except Exception as e:
            logger.debug(f"VK connections check failed for {vk_id}: {e}")

        return None

    def _generate_telegram_candidates(self, first_name: str, last_name: str) -> List[str]:
        """
        Generate plausible Telegram usernames from a Russian name.
        Uses the existing transliteration module.
        """
        try:
            from app.services.phase1.transliteration import transliterate_name_part
            first_variants = transliterate_name_part(first_name.lower(), max_variants=2)
            last_variants = transliterate_name_part(last_name.lower(), max_variants=2)
        except ImportError:
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
                    f"{first}_{last[0]}",    # artem_k
                ])

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

    @staticmethod
    def _basic_translit(text: str) -> str:
        """Basic Cyrillic→Latin transliteration fallback."""
        table = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
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

    if '--setup' in sys.argv:
        # Interactive Telethon session setup
        api_id = os.environ.get('TELEGRAM_API_ID')
        api_hash = os.environ.get('TELEGRAM_API_HASH')
        phone = os.environ.get('TELEGRAM_PHONE')

        if not all([api_id, api_hash, phone]):
            print("ERROR: Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env")
            sys.exit(1)

        import asyncio
        from telethon import TelegramClient

        session_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'telegram_session'
        )
        os.makedirs(session_dir, exist_ok=True)
        session_path = os.path.join(session_dir, 'ibp_session')

        async def setup():
            client = TelegramClient(session_path, int(api_id), api_hash)
            await client.start(phone)
            print("Telethon session created successfully!")
            await client.disconnect()

        asyncio.run(setup())
    else:
        # Test search
        from flask import Flask
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ibp.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        svc = TelegramDiscoveryService()
        query_parts = sys.argv[1:] if len(sys.argv) > 1 else ['Артём', 'Козлов']
        first = query_parts[0] if query_parts else 'Артём'
        last = query_parts[1] if len(query_parts) > 1 else 'Козлов'

        results = svc.discover(first, last)
        print(f"\nFound {len(results)} Telegram profiles for {first} {last}")
        for r in results:
            print(f"  @{r['username']} - {r['first_name']} {r['last_name']} ({r['confidence']}) [{r['source']}]")

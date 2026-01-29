"""
Entity Resolver - Merge multiple profiles into unified identity.
Agent 5 - Entity Resolution & Analysis

INTERFACE: Used by Agents 2,3,4 (search) and Agent 1 (orchestrator)
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class EntityResolver:
    """
    Merges profiles from multiple platforms into unified identity.

    Matching weights:
    - Same phone: +30 points
    - Same email: +30 points
    - Same photo (face match): +40 points
    - Similar username: +15 points
    - Same city: +10 points
    - Same name (including diminutives): +10 points
    - Same workplace: +20 points
    """

    WEIGHTS = {
        'face_match': 40,
        'phone_match': 30,
        'email_match': 30,
        'workplace_match': 20,
        'username_similar': 15,
        'city_match': 10,
        'name_match': 10,
    }

    # Russian name diminutives mapping
    RUSSIAN_DIMINUTIVES = {
        'александр': ['саша', 'шура', 'саня', 'алекс', 'san', 'sasha', 'alex'],
        'алексей': ['леша', 'лёша', 'алёша', 'лёха', 'lesha', 'lyosha'],
        'андрей': ['андрюша', 'андрюха', 'дрон', 'andrey', 'andrew'],
        'анна': ['аня', 'анюта', 'нюра', 'нюша', 'anya', 'ann'],
        'владимир': ['вова', 'володя', 'вовчик', 'vova', 'vlad'],
        'дмитрий': ['дима', 'димон', 'митя', 'dima', 'dmitry'],
        'евгений': ['женя', 'жека', 'zhenya', 'eugene'],
        'екатерина': ['катя', 'катюша', 'катерина', 'kate', 'katya'],
        'иван': ['ваня', 'ванюша', 'ванёк', 'vanya', 'ivan'],
        'максим': ['макс', 'максик', 'max', 'maxim'],
        'мария': ['маша', 'машенька', 'маруся', 'masha', 'maria'],
        'михаил': ['миша', 'мишка', 'михон', 'misha', 'mike'],
        'наталья': ['наташа', 'ната', 'натали', 'natasha'],
        'николай': ['коля', 'николаша', 'ник', 'kolya', 'nick'],
        'ольга': ['оля', 'оленька', 'олюшка', 'olya', 'olga'],
        'павел': ['паша', 'пашка', 'павлик', 'пашок', 'pasha', 'pavel', 'paul'],
        'петр': ['петя', 'петька', 'петруха', 'petya', 'peter'],
        'сергей': ['серёжа', 'серега', 'серж', 'serega', 'sergey'],
        'татьяна': ['таня', 'танюша', 'тата', 'tanya', 'tatiana'],
        'даниил': ['даня', 'данила', 'дэн', 'danya', 'dan', 'daniel'],
        'тихон': ['тиша', 'тихоня', 'tikhon', 'tisha'],
        'юрий': ['юра', 'юрок', 'юрец', 'yura', 'yuri'],
        'федор': ['федя', 'федька', 'федюня', 'fedor', 'fedya', 'theodore'],
        'артем': ['тёма', 'артёмка', 'artem', 'artyom'],
        'кирилл': ['кирюша', 'кирюха', 'kirill', 'cyril'],
        'виктор': ['витя', 'витёк', 'viktor', 'victor'],
        'роман': ['рома', 'ромка', 'roman', 'roma'],
        'игорь': ['игорёк', 'гоша', 'igor'],
        'олег': ['олежка', 'олежик', 'oleg'],
        'денис': ['дениска', 'ден', 'denis'],
        'антон': ['антоха', 'тоха', 'anton'],
        'валерий': ['валера', 'валерка', 'valera', 'valery'],
        'константин': ['костя', 'костик', 'kostya', 'konstantin'],
        'вячеслав': ['слава', 'славик', 'slava', 'vyacheslav'],
        'станислав': ['стас', 'стасик', 'stas', 'stanislav'],
        'борис': ['боря', 'борька', 'boris', 'borya'],
        'георгий': ['гоша', 'жора', 'georgy', 'george'],
        'григорий': ['гриша', 'гришка', 'grisha', 'grigory'],
        'елена': ['лена', 'леночка', 'lena', 'elena', 'helen'],
        'ирина': ['ира', 'иришка', 'ira', 'irina'],
        'светлана': ['света', 'светик', 'sveta', 'svetlana'],
        'юлия': ['юля', 'юлька', 'yulya', 'julia'],
        'ксения': ['ксюша', 'ксюха', 'ksyusha', 'ksenia'],
        'дарья': ['даша', 'дашутка', 'dasha', 'darya'],
        'полина': ['поля', 'полинка', 'polya', 'polina'],
        'анастасия': ['настя', 'настюша', 'nastya', 'anastasia'],
        'виктория': ['вика', 'викуся', 'vika', 'victoria'],
        'александра': ['саша', 'шура', 'саня', 'sasha', 'alexandra'],
    }

    def __init__(self):
        self._build_reverse_diminutive_map()

    def _build_reverse_diminutive_map(self):
        """Build reverse mapping: diminutive -> formal name"""
        self._reverse_map = {}
        for formal, diminutives in self.RUSSIAN_DIMINUTIVES.items():
            self._reverse_map[formal] = formal
            for dim in diminutives:
                self._reverse_map[dim.lower()] = formal

    def calculate_match_score(self, profile_a: Dict, profile_b: Dict) -> Tuple[float, List[str]]:
        """
        Calculate probability two profiles are same person.

        Returns:
            Tuple of (score 0.0-1.0, list of matching evidence)
        """
        score = 0
        evidence = []
        max_possible = sum(self.WEIGHTS.values())

        # Phone match
        phones_a = set(self._normalize_phones(profile_a.get('phones', [])))
        phones_b = set(self._normalize_phones(profile_b.get('phones', [])))
        if phones_a and phones_b and (phones_a & phones_b):
            score += self.WEIGHTS['phone_match']
            evidence.append(f"Same phone: {list(phones_a & phones_b)[0]}")

        # Email match
        emails_a = set(e.lower().strip() for e in profile_a.get('emails', []) if e)
        emails_b = set(e.lower().strip() for e in profile_b.get('emails', []) if e)
        if emails_a and emails_b and (emails_a & emails_b):
            score += self.WEIGHTS['email_match']
            evidence.append(f"Same email: {list(emails_a & emails_b)[0]}")

        # Name match (including diminutives)
        if self._names_match(profile_a.get('display_name', ''), profile_b.get('display_name', '')):
            score += self.WEIGHTS['name_match']
            evidence.append("Names match (including diminutives)")

        # Username similarity
        username_sim = self._username_similarity(
            profile_a.get('username', ''),
            profile_b.get('username', '')
        )
        if username_sim > 0.7:
            score += self.WEIGHTS['username_similar']
            evidence.append(f"Similar usernames ({username_sim:.0%})")

        # City match
        city_a = (profile_a.get('city') or '').lower().strip()
        city_b = (profile_b.get('city') or '').lower().strip()
        if city_a and city_b and (city_a in city_b or city_b in city_a):
            score += self.WEIGHTS['city_match']
            evidence.append(f"Same city: {city_a or city_b}")

        # Workplace match
        work_a = (profile_a.get('workplace') or '').lower().strip()
        work_b = (profile_b.get('workplace') or '').lower().strip()
        if work_a and work_b and len(work_a) > 3 and len(work_b) > 3:
            if work_a in work_b or work_b in work_a:
                score += self.WEIGHTS['workplace_match']
                evidence.append("Same workplace")

        confidence = score / max_possible if max_possible > 0 else 0
        return confidence, evidence

    def _normalize_phones(self, phones: List) -> List[str]:
        """Normalize phone numbers to +7XXXXXXXXXX format."""
        if not phones:
            return []
        normalized = []
        for phone in phones:
            if not phone:
                continue
            digits = re.sub(r'\D', '', str(phone))
            if len(digits) == 11 and digits.startswith('8'):
                digits = '7' + digits[1:]
            if len(digits) == 10:
                digits = '7' + digits
            if len(digits) == 11 and digits.startswith('7'):
                normalized.append('+' + digits)
        return normalized

    def _names_match(self, name_a: str, name_b: str) -> bool:
        """Check if names match, including diminutives."""
        if not name_a or not name_b:
            return False

        name_a_lower = name_a.lower().strip()
        name_b_lower = name_b.lower().strip()

        # Direct match
        if name_a_lower == name_b_lower:
            return True

        # Extract first names
        first_a = name_a_lower.split()[0] if name_a_lower else ''
        first_b = name_b_lower.split()[0] if name_b_lower else ''

        if not first_a or not first_b:
            return False

        # Check if both map to same formal name
        formal_a = self._reverse_map.get(first_a)
        formal_b = self._reverse_map.get(first_b)

        if formal_a and formal_b and formal_a == formal_b:
            return True

        # Check surname match (last word)
        parts_a = name_a_lower.split()
        parts_b = name_b_lower.split()
        if len(parts_a) > 1 and len(parts_b) > 1:
            if parts_a[-1] == parts_b[-1]:  # Same surname
                return True

        return False

    def _username_similarity(self, username_a: str, username_b: str) -> float:
        """Calculate username similarity score."""
        if not username_a or not username_b:
            return 0.0

        def normalize(u):
            u = u.lower()
            u = re.sub(r'[_\-\.]', '', u)
            u = re.sub(r'\d{2,4}$', '', u)  # Remove trailing years
            return u

        norm_a = normalize(username_a)
        norm_b = normalize(username_b)

        if not norm_a or not norm_b:
            return 0.0

        return SequenceMatcher(None, norm_a, norm_b).ratio()

    def merge_profiles(self, profiles: List[Dict]) -> Dict:
        """Merge multiple profiles into unified identity."""
        if not profiles:
            return {}
        if len(profiles) == 1:
            return profiles[0].copy()

        merged = {
            'names': [],
            'usernames': [],
            'platforms': [],
            'urls': [],
            'phones': [],
            'emails': [],
            'cities': [],
            'workplaces': [],
            'photos': [],
            'bios': [],
            'source_profiles': profiles,
            'merge_confidence': 0.0,
            'primary_name': '',
        }

        for p in profiles:
            if p.get('display_name'):
                merged['names'].append(p['display_name'])
            if p.get('username'):
                merged['usernames'].append(p['username'])
            if p.get('platform'):
                merged['platforms'].append(p['platform'])
            if p.get('url'):
                merged['urls'].append(p['url'])
            if p.get('phones'):
                merged['phones'].extend(p['phones'])
            if p.get('emails'):
                merged['emails'].extend(p['emails'])
            if p.get('city'):
                merged['cities'].append(p['city'])
            if p.get('workplace'):
                merged['workplaces'].append(p['workplace'])
            if p.get('photo_url'):
                merged['photos'].append(p['photo_url'])
            if p.get('bio'):
                merged['bios'].append(p['bio'])

        # Deduplicate
        merged['phones'] = list(set(self._normalize_phones(merged['phones'])))
        merged['emails'] = list(set(e.lower().strip() for e in merged['emails'] if e))
        merged['cities'] = list(set(c for c in merged['cities'] if c))
        merged['platforms'] = list(set(merged['platforms']))

        # Calculate overall confidence
        if len(profiles) >= 2:
            scores = []
            for i, p1 in enumerate(profiles):
                for p2 in profiles[i+1:]:
                    score, _ = self.calculate_match_score(p1, p2)
                    scores.append(score)
            merged['merge_confidence'] = sum(scores) / len(scores) if scores else 0

        # Pick best primary name (longest/most complete)
        merged['primary_name'] = max(merged['names'], key=lambda n: len(n.split()), default='Unknown')

        return merged

    def find_name_variants(self, name: str) -> List[str]:
        """Find all variants of a Russian name (formal + diminutives)."""
        first_name = name.lower().split()[0] if name else ''

        # Find formal name
        formal = self._reverse_map.get(first_name, first_name)

        # Get all diminutives for this formal name
        variants = [formal]
        if formal in self.RUSSIAN_DIMINUTIVES:
            variants.extend(self.RUSSIAN_DIMINUTIVES[formal])

        return list(set(variants))

    def cluster_profiles(self, profiles: List[Dict], threshold: float = 0.3) -> List[List[Dict]]:
        """
        Cluster profiles that likely belong to same person.

        Args:
            profiles: List of profile dictionaries
            threshold: Minimum match score to consider same person

        Returns:
            List of clusters, where each cluster is a list of related profiles
        """
        if not profiles:
            return []

        clusters = []
        used = set()

        for i, profile in enumerate(profiles):
            if i in used:
                continue

            cluster = [profile]
            used.add(i)

            for j, other in enumerate(profiles):
                if j in used:
                    continue

                score, _ = self.calculate_match_score(profile, other)
                if score >= threshold:
                    cluster.append(other)
                    used.add(j)

            clusters.append(cluster)

        return clusters


# Singleton instance
entity_resolver = EntityResolver()

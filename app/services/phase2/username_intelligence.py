"""
Username Intelligence Service
=============================
Analyzes username patterns to discover related accounts and generate
likely email addresses based on Russian naming conventions.

Features:
- Username pattern analysis (separators, years, variations)
- Related username generation
- Pattern-based email candidate creation
- Cross-platform username correlation
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Russian email domains for generation
RUSSIAN_DOMAINS = [
    'mail.ru', 'yandex.ru', 'gmail.com', 'bk.ru', 'list.ru',
    'inbox.ru', 'rambler.ru', 'ya.ru', 'yandex.com'
]

# Common year patterns (birth years, graduation years)
COMMON_YEARS = [
    '85', '86', '87', '88', '89', '90', '91', '92', '93', '94', '95',
    '96', '97', '98', '99', '00', '01', '02', '03', '04', '05',
    '1985', '1986', '1987', '1988', '1989', '1990', '1991', '1992',
    '1993', '1994', '1995', '1996', '1997', '1998', '1999', '2000',
    '2001', '2002', '2003', '2004', '2005'
]

# Russian city abbreviations commonly used in usernames
CITY_ABBREVIATIONS = {
    'msk': 'Moscow', 'spb': 'Saint Petersburg', 'nsk': 'Novosibirsk',
    'ekb': 'Yekaterinburg', 'kzn': 'Kazan', 'nnov': 'Nizhny Novgorod',
    'sam': 'Samara', 'omsk': 'Omsk', 'krd': 'Krasnodar', 'rst': 'Rostov',
    'perm': 'Perm', 'vlg': 'Volgograd', 'vrn': 'Voronezh',
}


@dataclass
class UsernameAnalysis:
    """Analysis results for a username."""
    original: str
    base_name: str  # Username without numbers/decorations
    separators: List[str]  # Detected separators (_, ., -)
    year_suffix: Optional[str] = None
    city_suffix: Optional[str] = None
    numeric_suffix: Optional[str] = None
    has_cyrillic: bool = False
    possible_first_name: Optional[str] = None
    possible_last_name: Optional[str] = None
    variations: List[str] = field(default_factory=list)
    email_candidates: List[str] = field(default_factory=list)


class UsernameIntelligence:
    """
    Analyze usernames and generate related accounts/emails.

    Patterns commonly found in Russian usernames:
    - firstname_lastname (ivan_petrov)
    - firstnamelastname (ivanpetrov)
    - nickname + year (ivan1990)
    - nickname + city (ivan_msk)
    - diminutive (vanya, fedya, petya)
    """

    # Patterns for name extraction
    NAME_PATTERNS = [
        # firstname_lastname or firstname.lastname
        r'^([a-z]+)[_\.]([a-z]+)$',
        # firstnamelastname (need to guess split point)
        r'^([a-z]{2,6})([a-z]{3,12})$',
    ]

    # Common Russian name diminutives
    DIMINUTIVES = {
        'sasha': ['alexander', 'alexandra', 'alex', 'aleksander'],
        'vanya': ['ivan', 'vanja'],
        'fedya': ['fedor', 'fyodor'],
        'petya': ['petr', 'peter', 'pyotr'],
        'kolya': ['nikolay', 'nikolai', 'nikita'],
        'dima': ['dmitry', 'dmitriy', 'dmitri'],
        'misha': ['mikhail', 'michael', 'mihayl'],
        'pasha': ['pavel', 'paul'],
        'serega': ['sergey', 'sergei', 'serge'],
        'leha': ['aleksey', 'alexey', 'alex'],
        'tolik': ['anatoly', 'anatoliy'],
        'zhenya': ['evgeny', 'evgeniy', 'eugene'],
        'valya': ['valentin', 'valentina', 'valery'],
        'vasya': ['vasily', 'vasiliy'],
        'slava': ['vyacheslav', 'vladislav'],
        'andryuha': ['andrey', 'andrei', 'andrew'],
        'kostya': ['konstantin', 'konstantine'],
        'vitya': ['viktor', 'victor'],
        'yura': ['yuri', 'yury', 'yuriy'],
    }

    def __init__(self):
        """Initialize username intelligence service."""
        # Build reverse diminutive lookup
        self.full_to_diminutive = {}
        for dim, fulls in self.DIMINUTIVES.items():
            for full in fulls:
                self.full_to_diminutive[full] = dim

    def analyze(self, username: str) -> UsernameAnalysis:
        """
        Analyze a username for patterns.

        Args:
            username: Username to analyze

        Returns:
            UsernameAnalysis with detected patterns
        """
        result = UsernameAnalysis(
            original=username,
            base_name=username,
            separators=[]
        )

        # Lowercase for analysis
        username_lower = username.lower().strip()

        # Check for Cyrillic
        result.has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', username))

        # Detect separators
        if '_' in username_lower:
            result.separators.append('_')
        if '.' in username_lower:
            result.separators.append('.')
        if '-' in username_lower:
            result.separators.append('-')

        # Extract year suffix
        year_match = re.search(r'(\d{2,4})$', username_lower)
        if year_match:
            potential_year = year_match.group(1)
            if potential_year in COMMON_YEARS:
                result.year_suffix = potential_year
                result.base_name = username_lower[:year_match.start()].rstrip('_.-')

        # Extract city suffix
        for abbrev, city in CITY_ABBREVIATIONS.items():
            if username_lower.endswith('_' + abbrev) or username_lower.endswith(abbrev):
                result.city_suffix = city
                if username_lower.endswith('_' + abbrev):
                    result.base_name = username_lower[:-len(abbrev)-1]
                break

        # Extract numeric suffix (non-year)
        if not result.year_suffix:
            num_match = re.search(r'(\d+)$', username_lower)
            if num_match:
                result.numeric_suffix = num_match.group(1)
                result.base_name = username_lower[:num_match.start()].rstrip('_.-')

        # Try to extract first/last name
        base_clean = result.base_name.rstrip('_.-0123456789')

        # Pattern: firstname_lastname
        if '_' in base_clean or '.' in base_clean:
            parts = re.split(r'[_.]', base_clean)
            if len(parts) >= 2:
                result.possible_first_name = parts[0]
                result.possible_last_name = parts[-1]
        else:
            # Single word - might be first name or nickname
            result.possible_first_name = base_clean

        # Generate variations
        result.variations = self._generate_variations(result)

        # Generate email candidates
        result.email_candidates = self._generate_email_candidates(result)

        return result

    def _generate_variations(self, analysis: UsernameAnalysis) -> List[str]:
        """Generate username variations based on analysis."""
        variations = set()
        base = analysis.base_name

        # Original
        variations.add(analysis.original.lower())
        variations.add(base)

        # Without numbers
        base_no_nums = re.sub(r'\d+', '', base)
        if base_no_nums and base_no_nums != base:
            variations.add(base_no_nums)

        # Separator swaps
        for sep in ['_', '.', '', '-']:
            if analysis.possible_first_name and analysis.possible_last_name:
                variations.add(f"{analysis.possible_first_name}{sep}{analysis.possible_last_name}")
                variations.add(f"{analysis.possible_last_name}{sep}{analysis.possible_first_name}")

        # Diminutive expansions
        if analysis.possible_first_name:
            fname = analysis.possible_first_name.lower()

            # If it's a diminutive, add full names
            if fname in self.DIMINUTIVES:
                for full in self.DIMINUTIVES[fname]:
                    variations.add(full)
                    if analysis.possible_last_name:
                        variations.add(f"{full}_{analysis.possible_last_name}")
                        variations.add(f"{full}.{analysis.possible_last_name}")

            # If it's a full name, add diminutive
            if fname in self.full_to_diminutive:
                dim = self.full_to_diminutive[fname]
                variations.add(dim)
                if analysis.possible_last_name:
                    variations.add(f"{dim}_{analysis.possible_last_name}")

        # Year variations
        if analysis.year_suffix:
            for var in list(variations):
                if not any(c.isdigit() for c in var):
                    variations.add(f"{var}{analysis.year_suffix}")
                    variations.add(f"{var}_{analysis.year_suffix}")

        # Filter valid usernames
        valid_variations = [
            v for v in variations
            if v and len(v) >= 3 and re.match(r'^[a-z0-9._-]+$', v)
        ]

        return sorted(set(valid_variations))

    def _generate_email_candidates(self, analysis: UsernameAnalysis) -> List[str]:
        """Generate likely email addresses from username analysis."""
        candidates = set()

        # All variations become email prefixes
        for var in analysis.variations:
            if len(var) >= 3:
                for domain in RUSSIAN_DOMAINS[:6]:  # Top 6 domains
                    email = f"{var}@{domain}"
                    if self._is_valid_email(email):
                        candidates.add(email)

        # First initial + last name patterns
        if analysis.possible_first_name and analysis.possible_last_name:
            initial = analysis.possible_first_name[0]
            lname = analysis.possible_last_name

            patterns = [
                f"{initial}{lname}",
                f"{initial}.{lname}",
                f"{initial}_{lname}",
            ]

            for pattern in patterns:
                for domain in RUSSIAN_DOMAINS[:4]:
                    candidates.add(f"{pattern}@{domain}")

        return sorted(candidates)

    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation."""
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email)) and len(email) <= 254

    def correlate_usernames(self, usernames: List[str]) -> Dict[str, List[str]]:
        """
        Find correlations between multiple usernames.

        Args:
            usernames: List of usernames from different platforms

        Returns:
            Dict with correlation findings
        """
        results = {
            'common_bases': [],
            'likely_names': [],
            'suggested_emails': [],
            'patterns': []
        }

        analyses = [self.analyze(u) for u in usernames]

        # Find common base names
        base_names = [a.base_name for a in analyses]
        if len(set(base_names)) == 1:
            results['common_bases'] = [base_names[0]]
            results['patterns'].append('All usernames share same base')

        # Find common first/last names
        first_names = set(a.possible_first_name for a in analyses if a.possible_first_name)
        last_names = set(a.possible_last_name for a in analyses if a.possible_last_name)

        if len(first_names) == 1:
            results['likely_names'].append(('first', list(first_names)[0]))
        if len(last_names) == 1:
            results['likely_names'].append(('last', list(last_names)[0]))

        # Collect all email candidates
        all_emails = set()
        for analysis in analyses:
            all_emails.update(analysis.email_candidates)

        results['suggested_emails'] = sorted(all_emails)[:30]

        return results

    def get_email_candidates_for_username(self, username: str) -> List[str]:
        """
        Get email candidates for a single username.

        Args:
            username: Username to analyze

        Returns:
            List of likely email addresses
        """
        analysis = self.analyze(username)
        return analysis.email_candidates


def analyze_username(username: str) -> UsernameAnalysis:
    """Convenience function for single username analysis."""
    intel = UsernameIntelligence()
    return intel.analyze(username)


def get_emails_from_username(username: str) -> List[str]:
    """Convenience function to get emails from username."""
    intel = UsernameIntelligence()
    return intel.get_email_candidates_for_username(username)


def correlate_usernames(usernames: List[str]) -> Dict:
    """Convenience function for username correlation."""
    intel = UsernameIntelligence()
    return intel.correlate_usernames(usernames)

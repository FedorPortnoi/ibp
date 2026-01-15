"""
Smart Username Generator for Russian Names
===========================================
Generates realistic username variations from Russian names.

Features:
- Multi-variant transliteration (Ё→e/yo/jo, Ж→zh/j, etc.)
- 50+ Russian diminutives database
- Smart name combination patterns
- Birth year only when provided
- Validation and deduplication

Author: IBP Project
Version: 1.0
"""

import re
from typing import List, Dict, Set, Optional
from itertools import product


# =============================================================================
# TRANSLITERATION ENGINE
# =============================================================================

# Multi-variant transliteration map (Russian → [Latin variants])
TRANSLIT_VARIANTS = {
    'а': ['a'],
    'б': ['b'],
    'в': ['v'],
    'г': ['g'],
    'д': ['d'],
    'е': ['e'],
    'ё': ['e', 'yo', 'jo', 'io'],
    'ж': ['zh', 'j', 'g'],
    'з': ['z'],
    'и': ['i'],
    'й': ['y', 'i', 'j', 'ii'],
    'к': ['k'],
    'л': ['l'],
    'м': ['m'],
    'н': ['n'],
    'о': ['o'],
    'п': ['p'],
    'р': ['r'],
    'с': ['s'],
    'т': ['t'],
    'у': ['u'],
    'ф': ['f'],
    'х': ['kh', 'h', 'x'],
    'ц': ['ts', 'c', 'tz'],
    'ч': ['ch', 'tch'],
    'ш': ['sh'],
    'щ': ['shch', 'sch', 'sh'],
    'ъ': [''],
    'ы': ['y', 'i'],
    'ь': ['', 'i'],
    'э': ['e'],
    'ю': ['yu', 'iu', 'ju', 'u'],
    'я': ['ya', 'ia', 'ja', 'a'],
}

# Simple transliteration (one variant per letter, most common)
TRANSLIT_SIMPLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate_simple(text: str) -> str:
    """Simple transliteration - one output per input."""
    result = []
    for char in text.lower():
        if char in TRANSLIT_SIMPLE:
            result.append(TRANSLIT_SIMPLE[char])
        elif char.isalnum() or char in '._-':
            result.append(char)
    return ''.join(result)


def transliterate_variants(text: str, max_variants: int = 8) -> List[str]:
    """
    Generate multiple transliteration variants.

    Example: "Фёдор" → ["fedor", "fyodor", "feodor", "fiodor"]
    """
    text = text.lower().strip()
    if not text:
        return []

    # Build list of possible transliterations for each character
    char_options = []
    for char in text:
        if char in TRANSLIT_VARIANTS:
            char_options.append(TRANSLIT_VARIANTS[char])
        elif char.isalnum():
            char_options.append([char])
        # Skip other characters (spaces, punctuation)

    if not char_options:
        return []

    # Generate combinations (limit to avoid explosion)
    variants = set()

    # Always include the simple transliteration first
    simple = transliterate_simple(text)
    if simple:
        variants.add(simple)

    # Generate combinations
    try:
        for combo in product(*char_options):
            variant = ''.join(combo)
            if variant and len(variant) >= 2:
                variants.add(variant)
            if len(variants) >= max_variants:
                break
    except MemoryError:
        pass

    return list(variants)[:max_variants]


# =============================================================================
# RUSSIAN DIMINUTIVES DATABASE
# =============================================================================

# Format: 'canonical_name': ['diminutive1', 'diminutive2', ...]
RUSSIAN_DIMINUTIVES = {
    # Male names
    'александр': ['sasha', 'sanya', 'shura', 'alex', 'san', 'sashka', 'alik'],
    'алексей': ['lyosha', 'alyosha', 'lesha', 'alex', 'lyokha', 'aleksei'],
    'анатолий': ['tolya', 'tolik', 'tolyan'],
    'андрей': ['andrey', 'andrew', 'andryusha', 'andryukha', 'dron'],
    'антон': ['anton', 'tosha', 'toha'],
    'артём': ['artyom', 'tema', 'tyoma', 'artem'],
    'артур': ['artur', 'art'],
    'борис': ['borya', 'bob', 'boris'],
    'вадим': ['vadik', 'vadya', 'vadim'],
    'валентин': ['valya', 'valik', 'valentin'],
    'валерий': ['valera', 'valerka', 'valery'],
    'василий': ['vasya', 'vasek', 'vasily', 'vaska'],
    'виктор': ['vitya', 'viktor', 'victor', 'vitka'],
    'виталий': ['vitalik', 'vitaly', 'vita'],
    'владимир': ['vova', 'volodya', 'vladimir', 'vovka', 'vlad'],
    'владислав': ['vlad', 'vladik', 'slava'],
    'вячеслав': ['slava', 'slavik', 'vyacheslav'],
    'геннадий': ['gena', 'genya', 'gennady'],
    'георгий': ['zhora', 'gosha', 'georgy', 'george'],
    'глеб': ['gleb'],
    'григорий': ['grisha', 'grigory', 'greg'],
    'даниил': ['danya', 'danil', 'dan', 'daniel'],
    'денис': ['denis', 'den', 'denya'],
    'дмитрий': ['dima', 'dimon', 'mitya', 'dimka', 'dmitry', 'dmitri'],
    'евгений': ['zhenya', 'evgeny', 'eugene', 'zheka'],
    'егор': ['egor', 'yegor', 'gosha'],
    'иван': ['vanya', 'ivan', 'vanyusha', 'vanko'],
    'игорь': ['igor', 'gosha', 'igorek'],
    'илья': ['ilya', 'ilyusha', 'ilyukha'],
    'кирилл': ['kirill', 'kirya', 'cyril'],
    'константин': ['kostya', 'konstantin', 'kostik', 'kos'],
    'леонид': ['lyonya', 'leonid', 'leo'],
    'максим': ['max', 'maksim', 'maxim', 'maks'],
    'михаил': ['misha', 'mikhail', 'michael', 'mishka', 'miha'],
    'никита': ['nikita', 'nik', 'nikitos'],
    'николай': ['kolya', 'nikolay', 'nick', 'kolyan'],
    'олег': ['oleg'],
    'павел': ['pasha', 'pavel', 'pashka', 'paul'],
    'пётр': ['petya', 'petr', 'peter', 'petka', 'pyotr'],
    'роман': ['roma', 'roman', 'romka', 'romych'],
    'руслан': ['ruslan', 'rus'],
    'сергей': ['serega', 'sergey', 'sergei', 'seryoga', 'serge'],
    'станислав': ['stas', 'stanislav', 'stasik'],
    'степан': ['styopa', 'stepan', 'stepa'],
    'тимофей': ['tima', 'timofey', 'tim'],
    'фёдор': ['fedya', 'fedor', 'fyodor', 'fedka', 'theodore'],
    'юрий': ['yura', 'yury', 'yuri', 'yurik'],
    'ярослав': ['yarik', 'yaroslav', 'slava'],

    # Female names
    'александра': ['sasha', 'alexandra', 'shura', 'sashenka'],
    'алина': ['alina', 'alinochka', 'ali'],
    'алиса': ['alisa', 'alice', 'ali'],
    'анастасия': ['nastya', 'asya', 'stasya', 'anastasia', 'nastenka'],
    'анна': ['anya', 'anna', 'anyuta', 'ann', 'annushka'],
    'валентина': ['valya', 'valentina'],
    'валерия': ['lera', 'valeriya', 'valeria'],
    'вера': ['vera', 'verochka'],
    'виктория': ['vika', 'victoria', 'viktoriya', 'vikusya'],
    'галина': ['galya', 'galina', 'gala'],
    'дарья': ['dasha', 'darya', 'daria', 'dashenka', 'dashka'],
    'диана': ['diana', 'di'],
    'евгения': ['zhenya', 'evgeniya', 'eugenia', 'zheka'],
    'екатерина': ['katya', 'kate', 'katyusha', 'ekaterina', 'catherine', 'katka'],
    'елена': ['lena', 'elena', 'lenochka', 'helen', 'alyona'],
    'елизавета': ['liza', 'elizaveta', 'elizabeth', 'lizka'],
    'ирина': ['ira', 'irina', 'irochka', 'irka'],
    'ксения': ['ksusha', 'ksenia', 'kseniya', 'ksyusha'],
    'лариса': ['lara', 'larisa', 'larochka'],
    'любовь': ['lyuba', 'lubov', 'love'],
    'людмила': ['lyuda', 'lyudmila', 'mila'],
    'маргарита': ['rita', 'margarita', 'margo'],
    'марина': ['marina', 'marinochka'],
    'мария': ['masha', 'maria', 'mary', 'mashenka', 'mashka'],
    'надежда': ['nadya', 'nadezhda', 'nadyusha'],
    'наталья': ['natasha', 'natalya', 'natalia', 'nata'],
    'нина': ['nina', 'ninochka'],
    'оксана': ['oksana', 'ksana', 'ksyusha'],
    'ольга': ['olya', 'olga', 'olenka'],
    'полина': ['polina', 'polya', 'pauline'],
    'светлана': ['sveta', 'svetlana', 'svetik'],
    'софья': ['sonya', 'sofia', 'sophia', 'sofya'],
    'татьяна': ['tanya', 'tatyana', 'tatiana', 'tanechka', 'tanka'],
    'юлия': ['yulya', 'julia', 'juliya', 'yulia'],
    'яна': ['yana', 'yanochka'],
}


def get_diminutives(name: str) -> List[str]:
    """Get diminutives for a Russian name."""
    name_lower = name.lower().strip()

    # Direct lookup
    if name_lower in RUSSIAN_DIMINUTIVES:
        return RUSSIAN_DIMINUTIVES[name_lower]

    # Latin name aliases (common English/Latin spellings)
    LATIN_ALIASES = {
        'dmitry': 'дмитрий', 'dmitri': 'дмитрий', 'dimitri': 'дмитрий',
        'alexander': 'александр', 'alex': 'александр', 'sasha': 'александр',
        'alexei': 'алексей', 'alexey': 'алексей',
        'andrey': 'андрей', 'andrew': 'андрей', 'andrei': 'андрей',
        'anton': 'антон',
        'artem': 'артём', 'artyom': 'артём',
        'boris': 'борис',
        'eugene': 'евгений', 'evgeny': 'евгений', 'evgeni': 'евгений',
        'fedor': 'фёдор', 'fyodor': 'фёдор', 'theodore': 'фёдор',
        'georgy': 'георгий', 'george': 'георгий',
        'igor': 'игорь',
        'ilya': 'илья',
        'ivan': 'иван', 'john': 'иван',
        'kirill': 'кирилл', 'cyril': 'кирилл',
        'konstantin': 'константин', 'constantine': 'константин',
        'maxim': 'максим', 'max': 'максим', 'maksim': 'максим',
        'mikhail': 'михаил', 'michael': 'михаил', 'misha': 'михаил',
        'nikita': 'никита',
        'nikolay': 'николай', 'nikolai': 'николай', 'nicholas': 'николай',
        'oleg': 'олег',
        'pavel': 'павел', 'paul': 'павел',
        'peter': 'пётр', 'petr': 'пётр', 'pyotr': 'пётр',
        'roman': 'роман',
        'sergey': 'сергей', 'sergei': 'сергей', 'serge': 'сергей',
        'stanislav': 'станислав',
        'vladimir': 'владимир',
        'yuri': 'юрий', 'yury': 'юрий',
        # Female
        'anastasia': 'анастасия', 'nastya': 'анастасия',
        'anna': 'анна', 'ann': 'анна',
        'catherine': 'екатерина', 'kate': 'екатерина', 'katya': 'екатерина',
        'elena': 'елена', 'helen': 'елена', 'lena': 'елена',
        'elizabeth': 'елизавета', 'liza': 'елизавета',
        'irina': 'ирина',
        'maria': 'мария', 'mary': 'мария', 'masha': 'мария',
        'natalia': 'наталья', 'natasha': 'наталья',
        'olga': 'ольга',
        'sofia': 'софья', 'sophia': 'софья',
        'tatiana': 'татьяна', 'tanya': 'татьяна',
        'victoria': 'виктория', 'vika': 'виктория',
        'yulia': 'юлия', 'julia': 'юлия',
    }

    # Check Latin alias
    if name_lower in LATIN_ALIASES:
        rus_name = LATIN_ALIASES[name_lower]
        if rus_name in RUSSIAN_DIMINUTIVES:
            return RUSSIAN_DIMINUTIVES[rus_name]

    # Try transliterated version
    name_translit = transliterate_simple(name_lower)
    for rus_name, dims in RUSSIAN_DIMINUTIVES.items():
        rus_translit = transliterate_simple(rus_name)
        if rus_translit == name_translit:
            return dims
        # Also check if input matches any diminutive
        if name_translit in dims:
            return dims

    return []


# =============================================================================
# USERNAME GENERATOR
# =============================================================================

class SmartUsernameGenerator:
    """
    Generates realistic usernames from Russian names.

    Priority order:
    1. Diminutive alone (sasha, dima, katya)
    2. Diminutive + lastname (sashaivanov)
    3. Full firstname + lastname variations
    4. Transliteration variants
    5. Birth year variants (only if provided)
    """

    def __init__(self, max_results: int = 50):
        self.max_results = max_results

    def generate(self,
                 full_name: str,
                 birth_year: Optional[int] = None,
                 max_results: Optional[int] = None) -> List[str]:
        """
        Generate username variations from a Russian name.

        Args:
            full_name: Full name in Russian or Latin (e.g., "Дмитрий Медведев")
            birth_year: Optional birth year (e.g., 1965)
            max_results: Max usernames to return

        Returns:
            List of username variations, most likely first
        """
        max_results = max_results or self.max_results

        # Parse name - handle CamelCase (DmitryMedvedev -> Dmitry Medvedev)
        full_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', full_name)
        full_name = re.sub(r'([а-яё])([А-ЯЁ])', r'\1 \2', full_name)

        parts = full_name.strip().split()
        if not parts:
            return []

        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ''

        # Get transliterations
        firstname_variants = transliterate_variants(firstname, max_variants=4)
        lastname_variants = transliterate_variants(lastname, max_variants=4) if lastname else []

        # Get primary transliterations
        fn = transliterate_simple(firstname)
        ln = transliterate_simple(lastname) if lastname else ''

        # Get diminutives
        diminutives = get_diminutives(firstname)

        # Collect usernames in priority order
        usernames = []

        # === PRIORITY 1: Diminutive alone ===
        for dim in diminutives[:5]:
            usernames.append(dim)

        # === PRIORITY 2: Diminutive + lastname ===
        if ln:
            for dim in diminutives[:3]:
                usernames.append(f"{dim}{ln}")
                usernames.append(f"{dim}.{ln}")
                usernames.append(f"{dim}_{ln}")

        # === PRIORITY 3: Full firstname + lastname variations ===
        if fn:
            usernames.append(fn)

        if fn and ln:
            # Standard patterns
            usernames.append(f"{fn}{ln}")
            usernames.append(f"{fn}.{ln}")
            usernames.append(f"{fn}_{ln}")
            usernames.append(f"{fn}-{ln}")

            # Reversed
            usernames.append(f"{ln}{fn}")
            usernames.append(f"{ln}.{fn}")
            usernames.append(f"{ln}_{fn}")

            # Initial patterns
            if fn:
                initial = fn[0]
                usernames.append(f"{initial}{ln}")
                usernames.append(f"{initial}.{ln}")
                usernames.append(f"{initial}_{ln}")
                usernames.append(f"{ln}{initial}")

        # === PRIORITY 4: Transliteration variants ===
        for fn_var in firstname_variants[1:]:  # Skip first (already added)
            usernames.append(fn_var)
            if ln:
                usernames.append(f"{fn_var}{ln}")
                usernames.append(f"{fn_var}.{ln}")

        for ln_var in lastname_variants[1:]:
            if fn:
                usernames.append(f"{fn}{ln_var}")
                usernames.append(f"{fn}.{ln_var}")

        # === PRIORITY 5: Birth year variants (ONLY IF PROVIDED) ===
        if birth_year:
            year_short = str(birth_year)[-2:]  # e.g., 1990 → 90
            year_full = str(birth_year)  # e.g., 1990

            base_names = [fn] + diminutives[:2]
            if ln:
                base_names.append(f"{fn}{ln}")

            for base in base_names:
                if base:
                    usernames.append(f"{base}{year_short}")
                    usernames.append(f"{base}{year_full}")
                    usernames.append(f"{base}_{year_short}")

        # Validate and deduplicate
        valid_usernames = []
        seen = set()

        for username in usernames:
            username = self._clean_username(username)
            if username and username not in seen and self._is_valid(username):
                seen.add(username)
                valid_usernames.append(username)
                if len(valid_usernames) >= max_results:
                    break

        return valid_usernames

    def _clean_username(self, username: str) -> str:
        """Clean and normalize username."""
        # Remove invalid characters
        username = re.sub(r'[^a-zA-Z0-9._-]', '', username.lower())
        # Remove leading/trailing separators
        username = username.strip('._-')
        # Collapse multiple separators
        username = re.sub(r'[._-]{2,}', '.', username)
        return username

    def _is_valid(self, username: str) -> bool:
        """Validate username."""
        if not username:
            return False

        # Length check
        if len(username) < 3 or len(username) > 30:
            return False

        # Must start with letter
        if not username[0].isalpha():
            return False

        # No 3+ repeated characters
        if re.search(r'(.)\1{2,}', username):
            return False

        # Only allowed characters
        if not re.match(r'^[a-z0-9._-]+$', username):
            return False

        return True

    # Alias for backward compatibility
    def generate_usernames(self, name: str, max_results: int = None, birth_year: int = None) -> List[str]:
        return self.generate(name, birth_year=birth_year, max_results=max_results)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_usernames(full_name: str,
                       birth_year: Optional[int] = None,
                       max_results: int = 50) -> List[str]:
    """
    Generate username variations from a name.

    Args:
        full_name: Name in Russian or Latin
        birth_year: Optional birth year
        max_results: Maximum usernames to generate

    Returns:
        List of username variations
    """
    generator = SmartUsernameGenerator(max_results=max_results)
    return generator.generate(full_name, birth_year=birth_year)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Smart Username Generator Test")
    print("=" * 60)

    # Test 1: Dmitry Medvedev (no birth year)
    print("\nTest 1: Дмитрий Медведев (no birth year)")
    print("-" * 40)
    usernames = generate_usernames("Дмитрий Медведев", max_results=30)
    for i, u in enumerate(usernames, 1):
        print(f"  {i:2}. {u}")

    # Test 2: With birth year
    print("\nTest 2: Фёдор Портной (birth year 1990)")
    print("-" * 40)
    usernames = generate_usernames("Фёдор Портной", birth_year=1990, max_results=30)
    for i, u in enumerate(usernames, 1):
        print(f"  {i:2}. {u}")

    # Test 3: Female name
    print("\nTest 3: Екатерина Иванова")
    print("-" * 40)
    usernames = generate_usernames("Екатерина Иванова", max_results=20)
    for i, u in enumerate(usernames, 1):
        print(f"  {i:2}. {u}")

    # Test 4: Transliteration variants
    print("\nTest 4: Transliteration of 'Фёдор'")
    print("-" * 40)
    variants = transliterate_variants("Фёдор")
    print(f"  Variants: {variants}")

    # Test 5: Diminutives lookup
    print("\nTest 5: Diminutives for 'Дмитрий'")
    print("-" * 40)
    dims = get_diminutives("Дмитрий")
    print(f"  Diminutives: {dims}")

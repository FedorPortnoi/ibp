"""
Enhanced Username Generator v2
==============================
Generates 100+ realistic username variations based on Russian naming conventions.

Features:
- Russian diminutives (Fedor → Fedya, Fedka, Fedyusha)
- Common Russian username patterns
- Transliteration (Cyrillic → Latin)
- Year-based variations (birth years 1980-2010)
- Common number suffixes Russians actually use (228, 777, 666, 1337, etc.)
- Combined name patterns (first_last, last_first, f.last, etc.)

Author: IBP Project
"""

import re
from typing import List, Set, Tuple
from itertools import product


class EnhancedUsernameGenerator:
    """
    Generates realistic username variations based on Russian naming patterns.
    
    Russians typically use:
    - Diminutives of their first name
    - Combinations of first + last name
    - Birth year or significant years
    - Popular number suffixes (228, 777, 666, etc.)
    """
    
    # Russian diminutives mapping
    RUSSIAN_DIMINUTIVES = {
        # Male names
        'fedor': ['fedya', 'fedka', 'fedyusha', 'fedyunya', 'fedenka'],
        'федор': ['федя', 'федька', 'федюша', 'федюня', 'феденька'],
        'alexander': ['sasha', 'shura', 'sanya', 'alex', 'alik'],
        'александр': ['саша', 'шура', 'саня', 'алекс', 'алик'],
        'alexey': ['lyosha', 'alyosha', 'lesha', 'alex'],
        'алексей': ['лёша', 'алёша', 'леша', 'алекс'],
        'dmitry': ['dima', 'mitya', 'dimka', 'dimochka'],
        'дмитрий': ['дима', 'митя', 'димка', 'димочка'],
        'ivan': ['vanya', 'vanechka', 'vanyusha'],
        'иван': ['ваня', 'ванечка', 'ванюша'],
        'mikhail': ['misha', 'mishka', 'miша', 'mike'],
        'михаил': ['миша', 'мишка', 'михан'],
        'nikolay': ['kolya', 'nikolasha', 'nik', 'nick'],
        'николай': ['коля', 'николаша', 'ник'],
        'sergey': ['seryozha', 'serega', 'sergei'],
        'сергей': ['серёжа', 'серёга', 'серый'],
        'vladimir': ['vova', 'volodya', 'vlad', 'vovka'],
        'владимир': ['вова', 'володя', 'влад', 'вовка'],
        'andrey': ['andryusha', 'andryukha', 'dron'],
        'андрей': ['андрюша', 'андрюха', 'дрон'],
        'pavel': ['pasha', 'pavlik', 'pashka'],
        'павел': ['паша', 'павлик', 'пашка'],
        'maksim': ['max', 'maksik', 'maks'],
        'максим': ['макс', 'максик'],
        'evgeny': ['zhenya', 'zheka', 'evgen'],
        'евгений': ['женя', 'жека', 'евген'],
        'denis': ['den', 'deniska', 'denchik'],
        'денис': ['ден', 'дениска', 'денчик'],
        'roman': ['roma', 'romka', 'romashka'],
        'роман': ['рома', 'ромка', 'ромашка'],
        'artem': ['tyoma', 'tema', 'art'],
        'артем': ['тёма', 'тема', 'арт'],
        'kirill': ['kirya', 'kiryusha', 'kir'],
        'кирилл': ['киря', 'кирюша', 'кир'],
        'nikita': ['nik', 'nikitos', 'nikitka'],
        'никита': ['ник', 'никитос', 'никитка'],
        'ilya': ['ilyusha', 'ilyukha'],
        'илья': ['илюша', 'илюха'],
        'egor': ['gosha', 'zhora', 'egorka'],
        'егор': ['гоша', 'жора', 'егорка'],
        'oleg': ['olik', 'olezhka'],
        'олег': ['олик', 'олежка'],
        'stanislav': ['stas', 'stasik', 'slavik'],
        'станислав': ['стас', 'стасик', 'славик'],
        'viktor': ['vitya', 'vityok', 'vik'],
        'виктор': ['витя', 'витёк', 'вик'],
        'konstantin': ['kostya', 'kostik', 'kos'],
        'константин': ['костя', 'костик', 'кос'],
        'anton': ['tosha', 'toha', 'antoshka'],
        'антон': ['тоша', 'тоха', 'антошка'],
        'vladislav': ['vlad', 'vladik', 'slava'],
        'владислав': ['влад', 'владик', 'слава'],
        'timofey': ['tima', 'timoha', 'tim'],
        'тимофей': ['тима', 'тимоха', 'тим'],
        'yaroslav': ['yarik', 'slava', 'yar'],
        'ярослав': ['ярик', 'слава', 'яр'],
        'georgiy': ['zhora', 'gosha', 'gera'],
        'георгий': ['жора', 'гоша', 'гера'],
        'danil': ['danya', 'danila', 'dan'],
        'данил': ['даня', 'данила', 'дан'],
        'boris': ['borya', 'borik'],
        'борис': ['боря', 'борик'],
        'gleb': ['glebka', 'glebushka'],
        'глеб': ['глебка', 'глебушка'],
        'arseniy': ['senya', 'arsik'],
        'арсений': ['сеня', 'арсик'],
        'matvey': ['motya', 'matveyка'],
        'матвей': ['мотя', 'матвейка'],
        
        # Female names
        'maria': ['masha', 'mashka', 'marusya', 'mary'],
        'мария': ['маша', 'машка', 'маруся'],
        'anna': ['anya', 'anyuta', 'annushka', 'ann'],
        'анна': ['аня', 'анюта', 'аннушка'],
        'elena': ['lena', 'lenochka', 'alyona'],
        'елена': ['лена', 'леночка', 'алёна'],
        'olga': ['olya', 'olenka', 'olechka'],
        'ольга': ['оля', 'оленька', 'олечка'],
        'natalia': ['natasha', 'nata', 'natusya'],
        'наталья': ['наташа', 'ната', 'натуся'],
        'ekaterina': ['katya', 'katyusha', 'kate'],
        'екатерина': ['катя', 'катюша', 'кейт'],
        'tatiana': ['tanya', 'tanechka', 'tata'],
        'татьяна': ['таня', 'танечка', 'тата'],
        'irina': ['ira', 'irochka', 'irisha'],
        'ирина': ['ира', 'ирочка', 'ириша'],
        'svetlana': ['sveta', 'svetik', 'svetochka'],
        'светлана': ['света', 'светик', 'светочка'],
        'yulia': ['yulya', 'yulechka', 'julia'],
        'юлия': ['юля', 'юлечка'],
        'victoria': ['vika', 'vikochka', 'vikusya'],
        'виктория': ['вика', 'викочка', 'викуся'],
        'daria': ['dasha', 'dashka', 'dashenka'],
        'дарья': ['даша', 'дашка', 'дашенька'],
        'anastasia': ['nastya', 'nastenka', 'nastyusha'],
        'анастасия': ['настя', 'настенька', 'настюша'],
        'polina': ['polya', 'polechka', 'polinka'],
        'полина': ['поля', 'полечка', 'полинка'],
        'alexandra': ['sasha', 'shura', 'alex'],
        'александра': ['саша', 'шура', 'алекс'],
        'sofia': ['sonya', 'sofochka', 'sofi'],
        'софия': ['соня', 'софочка', 'софи'],
        'kristina': ['kris', 'kristya', 'kristinka'],
        'кристина': ['крис', 'кристя', 'кристинка'],
        'alina': ['alya', 'alinochka', 'ali'],
        'алина': ['аля', 'алиночка', 'али'],
        'ksenia': ['ksusha', 'ksyusha', 'ksyu'],
        'ксения': ['ксюша', 'ксюха', 'ксю'],
        'marina': ['marin', 'marinochka', 'marisha'],
        'марина': ['марин', 'мариночка', 'мариша'],
        'vera': ['verochka', 'verusha'],
        'вера': ['верочка', 'веруша'],
        'evgenia': ['zhenya', 'zheka', 'zhenechka'],
        'евгения': ['женя', 'жека', 'женечка'],
        'valentina': ['valya', 'valechka', 'tina'],
        'валентина': ['валя', 'валечка', 'тина'],
        'galina': ['galya', 'galechka', 'galochka'],
        'галина': ['галя', 'галечка', 'галочка'],
    }
    
    # Popular Russian number suffixes
    POPULAR_SUFFIXES = [
        '',           # No suffix
        '1', '2', '3',
        '01', '02', '03',
        '11', '12', '13',
        '21', '22', '23',
        '69', '77', '88', '99',
        '007', '100', '101', '111', '123',
        '228',        # Very popular in Russia (criminal slang reference)
        '239',        # Krasnodar region code
        '777',        # Lucky number
        '666',        # Edge lord
        '1337',       # Leet speak
        '2000', '2001', '2002', '2003', '2004', '2005',  # Birth years
        '2006', '2007', '2008', '2009', '2010',
        '1990', '1991', '1992', '1993', '1994', '1995',
        '1996', '1997', '1998', '1999',
        '1985', '1986', '1987', '1988', '1989',
        '1980', '1981', '1982', '1983', '1984',
        'official', 'real', 'true', 'original',  # Common appendages
        'vk', 'tg', 'insta',
        'pro', 'top', 'best', 'super',
        'ru', 'rus', 'russia', 'msk', 'spb',  # Location based
    ]
    
    # Separators commonly used
    SEPARATORS = ['', '_', '.', '-', '__']
    
    # Cyrillic to Latin transliteration
    TRANSLIT_MAP = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    
    def __init__(self, max_results: int = 150):
        """
        Initialize generator.
        
        Args:
            max_results: Maximum usernames to generate (default 150)
        """
        self.max_results = max_results
    
    def transliterate(self, text: str) -> str:
        """Convert Cyrillic text to Latin characters."""
        result = []
        for char in text:
            result.append(self.TRANSLIT_MAP.get(char, char))
        return ''.join(result)
    
    def get_diminutives(self, name: str) -> List[str]:
        """Get diminutive forms of a name."""
        name_lower = name.lower()
        
        # Check both original and transliterated
        diminutives = set()
        
        # Direct lookup
        if name_lower in self.RUSSIAN_DIMINUTIVES:
            diminutives.update(self.RUSSIAN_DIMINUTIVES[name_lower])
        
        # Try transliterated version
        translit = self.transliterate(name_lower)
        if translit in self.RUSSIAN_DIMINUTIVES:
            for dim in self.RUSSIAN_DIMINUTIVES[translit]:
                diminutives.add(dim)
                diminutives.add(self.transliterate(dim))
        
        # Also transliterate any Cyrillic diminutives found
        final_diminutives = set()
        for dim in diminutives:
            final_diminutives.add(dim)
            final_diminutives.add(self.transliterate(dim))
        
        return list(final_diminutives)
    
    def generate_usernames(self, full_name: str, max_results: int = None) -> List[str]:
        """
        Generate username variations from a full name.
        
        Args:
            full_name: Person's full name (e.g., "Fedor Portnoi" or "Фёдор Портной")
            max_results: Override default max results
            
        Returns:
            List of username variations, prioritized by likelihood
        """
        if max_results is None:
            max_results = self.max_results
        
        # Parse name
        parts = full_name.strip().split()
        if not parts:
            return []
        
        # Assume first part is first name, rest is last name
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        # Transliterate to Latin
        first_latin = self.transliterate(first_name).lower()
        last_latin = self.transliterate(last_name).lower() if last_name else ''
        
        # Get first initial
        first_initial = first_latin[0] if first_latin else ''
        last_initial = last_latin[0] if last_latin else ''
        
        # Get diminutives
        diminutives = self.get_diminutives(first_name)
        
        # Build username set (ordered by priority)
        usernames = []
        seen = set()
        
        def add_username(username: str, priority: int = 50):
            """Add username if valid and not seen."""
            # Clean username
            username = re.sub(r'[^a-zA-Z0-9_.-]', '', username.lower())
            username = re.sub(r'[-_.]{2,}', '_', username)  # Remove double separators
            username = username.strip('_.-')
            
            if len(username) >= 3 and username not in seen:
                seen.add(username)
                usernames.append((priority, username))
        
        # PRIORITY 1: Full name combinations (most likely to be the real account)
        if last_latin:
            add_username(f"{first_latin}_{last_latin}", 100)
            add_username(f"{first_latin}.{last_latin}", 99)
            add_username(f"{first_latin}{last_latin}", 98)
            add_username(f"{last_latin}_{first_latin}", 97)
            add_username(f"{last_latin}.{first_latin}", 96)
            add_username(f"{last_latin}{first_latin}", 95)
            add_username(f"{first_initial}{last_latin}", 94)
            add_username(f"{first_latin}{last_initial}", 93)
            add_username(f"{first_initial}.{last_latin}", 92)
            add_username(f"{first_initial}_{last_latin}", 91)
            add_username(f"{last_latin}{first_initial}", 90)
            add_username(f"{last_latin}_{first_initial}", 89)
            add_username(f"{first_initial}{last_initial}", 88)
        
        # PRIORITY 2: First name only + suffixes
        add_username(first_latin, 85)
        for suffix in ['', '_', '1', '2', '01', '02']:
            add_username(f"{first_latin}{suffix}", 84)
        
        # PRIORITY 3: Last name only + suffixes
        if last_latin:
            add_username(last_latin, 80)
            for suffix in ['', '_', '1', '2']:
                add_username(f"{last_latin}{suffix}", 79)
        
        # PRIORITY 4: Diminutives (high priority for Russian targets)
        for dim in diminutives[:5]:  # Top 5 diminutives
            dim_latin = self.transliterate(dim).lower()
            add_username(dim_latin, 75)
            if last_latin:
                add_username(f"{dim_latin}_{last_latin}", 74)
                add_username(f"{dim_latin}.{last_latin}", 73)
                add_username(f"{dim_latin}{last_latin}", 72)
        
        # PRIORITY 5: With birth years (common pattern)
        birth_years = ['1990', '1991', '1992', '1993', '1994', '1995', 
                       '1996', '1997', '1998', '1999', '2000', '2001',
                       '2002', '2003', '2004', '2005', '1985', '1986',
                       '1987', '1988', '1989']
        
        for year in birth_years:
            add_username(f"{first_latin}{year}", 60)
            add_username(f"{first_latin}_{year}", 59)
            if last_latin:
                add_username(f"{first_latin}{last_latin}{year}", 58)
        
        # PRIORITY 6: Popular Russian suffixes
        popular = ['228', '777', '666', '1337', '007']
        for suffix in popular:
            add_username(f"{first_latin}{suffix}", 55)
            add_username(f"{first_latin}_{suffix}", 54)
            if last_latin:
                add_username(f"{first_latin}{last_latin}{suffix}", 53)
        
        # PRIORITY 7: With "official", "real" etc (common for popular people)
        for suffix in ['official', 'real', 'true', 'original', 'vk', 'tg']:
            add_username(f"{first_latin}_{suffix}", 50)
            if last_latin:
                add_username(f"{first_latin}{last_latin}_{suffix}", 49)
        
        # PRIORITY 8: Location-based
        for loc in ['ru', 'rus', 'russia', 'msk', 'spb', 'moscow', 'piter']:
            add_username(f"{first_latin}_{loc}", 45)
            if last_latin:
                add_username(f"{first_latin}{last_latin}_{loc}", 44)
        
        # PRIORITY 9: Remaining diminutives with suffixes
        for dim in diminutives:
            dim_latin = self.transliterate(dim).lower()
            for suffix in self.POPULAR_SUFFIXES[:20]:
                add_username(f"{dim_latin}{suffix}", 40)
        
        # PRIORITY 10: Short year suffixes (80, 81, 82, etc.)
        for year in range(80, 100):
            add_username(f"{first_latin}{year}", 35)
            if last_latin:
                add_username(f"{first_latin[0]}{last_latin}{year}", 34)
        
        for year in range(0, 10):
            add_username(f"{first_latin}0{year}", 33)
        
        # PRIORITY 11: Double first initial patterns
        add_username(f"{first_latin}{first_latin}", 30)
        if last_latin:
            add_username(f"{first_initial}{first_initial}{last_latin}", 29)
        
        # PRIORITY 12: "Pro", "top", etc. suffixes
        for suffix in ['pro', 'top', 'best', 'super', 'mega', 'ultra']:
            add_username(f"{first_latin}_{suffix}", 25)
            add_username(f"{suffix}_{first_latin}", 24)
        
        # Sort by priority (descending) and return
        usernames.sort(key=lambda x: -x[0])
        return [u[1] for u in usernames[:max_results]]
    
    def generate_search_queries(self, full_name: str) -> List[str]:
        """
        Generate search queries for finding the person.
        
        Returns queries formatted for search engines and social media search.
        """
        parts = full_name.strip().split()
        if not parts:
            return []
        
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        # Transliterate
        first_latin = self.transliterate(first_name)
        last_latin = self.transliterate(last_name) if last_name else ''
        
        queries = []
        
        # Exact name queries
        if last_name:
            queries.append(f'"{first_name} {last_name}"')
            queries.append(f'"{first_latin} {last_latin}"')
            queries.append(f'"{last_name} {first_name}"')
            queries.append(f'"{last_latin} {first_latin}"')
        else:
            queries.append(f'"{first_name}"')
            queries.append(f'"{first_latin}"')
        
        # Site-specific
        if last_latin:
            queries.append(f'site:vk.com "{first_latin} {last_latin}"')
            queries.append(f'site:ok.ru "{first_latin} {last_latin}"')
            queries.append(f'site:t.me "{first_latin} {last_latin}"')
        
        return queries


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    generator = EnhancedUsernameGenerator(max_results=100)
    
    # Test with Russian name
    test_names = [
        "Fedor Portnoi",
        "Александр Иванов",
        "Dmitry Petrov",
        "Anastasia Volkova"
    ]
    
    for name in test_names:
        print(f"\n{'='*60}")
        print(f"Name: {name}")
        print('='*60)
        
        usernames = generator.generate_usernames(name)
        print(f"\nGenerated {len(usernames)} usernames:")
        
        # Show top 30
        for i, username in enumerate(usernames[:30], 1):
            print(f"  {i:2d}. {username}")
        
        if len(usernames) > 30:
            print(f"  ... and {len(usernames) - 30} more")

"""
Russian Username Generator with Diminutives
============================================
Generates realistic username variations for Russian names including:
- Formal name patterns
- Diminutives (уменьшительные имена) 
- Affectionate forms (ласкательные)
- Colloquial/informal forms
- Common social media patterns
- Year suffixes
- Cyrillic variations (for VK, OK, etc.)

Russian naming is complex - people use many variations:
- Александр → Саша, Шура, Саня, Санёк, Алекс
- Екатерина → Катя, Катюша, Катенька, Кэт
- Дмитрий → Дима, Димон, Митя, Димка
"""

from typing import List, Set, Optional, Tuple
from transliterate import translit
import re


# =============================================================================
# RUSSIAN DIMINUTIVE DICTIONARY
# =============================================================================

# Format: "Formal Name": ["diminutive1", "diminutive2", ...]
# Ordered by popularity/commonness

MALE_DIMINUTIVES = {
    # А
    "Александр": ["Саша", "Шура", "Саня", "Санёк", "Алекс", "Санька", "Шурик", "Сашка", "Сашуля", "Сашок"],
    "Алексей": ["Лёша", "Лёха", "Алёша", "Лёшка", "Лёшик", "Алёшка", "Лёня"],
    "Анатолий": ["Толя", "Толик", "Толян", "Толька"],
    "Андрей": ["Андрюша", "Андрюха", "Дрон", "Дюша", "Андрюшка", "Андрейка"],
    "Антон": ["Тоша", "Тоха", "Антоха", "Антошка", "Тошка"],
    "Аркадий": ["Аркаша", "Аркан", "Аркашка"],
    "Артём": ["Тёма", "Артёмка", "Тёмка", "Артёмчик", "Тёмыч"],
    "Артур": ["Артурка", "Артурчик", "Арт"],
    
    # Б
    "Богдан": ["Богдаша", "Бодя", "Богданчик", "Даня", "Дан"],
    "Борис": ["Боря", "Борька", "Борян", "Боб"],
    
    # В
    "Вадим": ["Вадик", "Вадя", "Вадимка", "Вадюша"],
    "Валентин": ["Валя", "Валик", "Валентинка"],
    "Валерий": ["Валера", "Валерка", "Лера", "Валерон"],
    "Василий": ["Вася", "Васька", "Василёк", "Васёк", "Васян"],
    "Виктор": ["Витя", "Витёк", "Витька", "Виктор"],
    "Виталий": ["Виталик", "Виталя", "Витас", "Талик"],
    "Владимир": ["Вова", "Володя", "Вовка", "Вовчик", "Володька", "Влад", "Вован"],
    "Владислав": ["Влад", "Владик", "Слава", "Славик"],
    "Вячеслав": ["Слава", "Славик", "Славка", "Славян"],
    
    # Г
    "Геннадий": ["Гена", "Генка", "Геша", "Генаша"],
    "Георгий": ["Гоша", "Жора", "Гошка", "Жорик", "Георгий"],
    "Глеб": ["Глебушка", "Глебка", "Глебчик"],
    "Григорий": ["Гриша", "Гриня", "Гришка", "Гринька"],
    
    # Д
    "Даниил": ["Даня", "Данила", "Данька", "Данечка", "Дан", "Данил"],
    "Денис": ["Дэн", "Дениска", "Денчик", "Ден"],
    "Дмитрий": ["Дима", "Димон", "Митя", "Димка", "Димыч", "Димочка", "Митяй", "Димас"],
    
    # Е
    "Евгений": ["Женя", "Женёк", "Жека", "Женька", "Евген"],
    "Егор": ["Егорка", "Егорушка", "Гора", "Егорыч"],
    
    # И
    "Иван": ["Ваня", "Ванёк", "Ванька", "Ванюша", "Иванушка", "Ванёс"],
    "Игорь": ["Игорёк", "Игорёха", "Гоша", "Игорюша", "Гарик"],
    "Илья": ["Илюша", "Илюха", "Илюшка", "Ильюха"],
    
    # К
    "Кирилл": ["Кирюша", "Кирюха", "Киря", "Кир", "Кирюшка"],
    "Константин": ["Костя", "Костик", "Костян", "Кося", "Костюша"],
    
    # Л
    "Леонид": ["Лёня", "Лёнька", "Лёнчик", "Леонидка"],
    
    # М
    "Максим": ["Макс", "Максик", "Максимка", "Макся", "Максон"],
    "Марк": ["Маркуша", "Маркуха", "Марик"],
    "Матвей": ["Мотя", "Матвейка", "Матюша", "Мотька"],
    "Михаил": ["Миша", "Мишка", "Мишаня", "Мишуня", "Михан", "Мишутка"],
    
    # Н
    "Никита": ["Никитка", "Никитос", "Ник", "Никиточка", "Кит"],
    "Николай": ["Коля", "Колян", "Николаша", "Колька", "Коляныч", "Ник"],
    
    # О
    "Олег": ["Олежка", "Олежек", "Лёжик", "Олегыч"],
    
    # П
    "Павел": ["Паша", "Пашка", "Павлик", "Пашок", "Павлуша", "Паха"],
    "Пётр": ["Петя", "Петька", "Петруша", "Петро", "Петруха"],
    
    # Р
    "Роман": ["Рома", "Ромка", "Ромчик", "Ромыч", "Ромео", "Ромаха"],
    "Руслан": ["Русик", "Руся", "Русланчик", "Рус"],
    
    # С
    "Сергей": ["Серёжа", "Серёга", "Серж", "Серый", "Серёженька", "Серёжка", "Серго"],
    "Станислав": ["Стас", "Стасик", "Славик", "Стасян"],
    "Степан": ["Стёпа", "Стёпка", "Степашка", "Стёпушка"],
    
    # Т
    "Тимофей": ["Тима", "Тимоха", "Тимоша", "Тимка"],
    "Тимур": ["Тима", "Тимурка", "Тим"],
    
    # Ф
    "Фёдор": ["Федя", "Федька", "Федюня", "Федюша", "Феденька", "Федос"],
    "Филипп": ["Филя", "Фил", "Филиппок", "Филька"],
    
    # Э
    "Эдуард": ["Эдик", "Эд", "Эдя", "Эдуардик"],
    
    # Ю
    "Юрий": ["Юра", "Юрка", "Юрок", "Юрочка", "Юрец"],
    
    # Я
    "Ярослав": ["Ярик", "Слава", "Славик", "Яр", "Ярославка"],
}

FEMALE_DIMINUTIVES = {
    # А
    "Александра": ["Саша", "Сашка", "Шура", "Саня", "Санька", "Сашуля", "Шурочка", "Алекса"],
    "Алина": ["Аля", "Алинка", "Алиночка", "Лина"],
    "Алиса": ["Алиска", "Аля", "Лиса", "Алисочка"],
    "Анастасия": ["Настя", "Настёна", "Ася", "Настюша", "Стася", "Настасья", "Настюха", "Настёнка"],
    "Ангелина": ["Геля", "Лина", "Ангелинка", "Энжи"],
    "Анна": ["Аня", "Анюта", "Нюра", "Аннушка", "Нюта", "Анька", "Анечка", "Нюша"],
    "Арина": ["Аринка", "Ариша", "Рина", "Ариночка"],
    
    # В
    "Валентина": ["Валя", "Валюша", "Валечка", "Валентинка"],
    "Валерия": ["Лера", "Лерка", "Валерка", "Лерочка", "Валери"],
    "Варвара": ["Варя", "Варька", "Варенька", "Варварка", "Вава"],
    "Вера": ["Верочка", "Верунчик", "Верка", "Веруня"],
    "Вероника": ["Ника", "Вера", "Вероничка", "Рони"],
    "Виктория": ["Вика", "Викуся", "Викуля", "Вики", "Викусик", "Тори", "Викторка"],
    
    # Г
    "Галина": ["Галя", "Галка", "Галочка", "Галюня"],
    
    # Д
    "Дарья": ["Даша", "Дашка", "Дашуля", "Дашенька", "Дарьюшка", "Дашуня"],
    "Диана": ["Диана", "Ди", "Дианка", "Дианочка"],
    
    # Е
    "Ева": ["Евочка", "Евуся", "Евушка"],
    "Евгения": ["Женя", "Женечка", "Женька", "Евгеша", "Геня"],
    "Екатерина": ["Катя", "Катюша", "Катенька", "Катька", "Кэт", "Катерина", "Катюня", "Катюха"],
    "Елена": ["Лена", "Леночка", "Ленка", "Алёна", "Леся", "Еленка", "Ленуся"],
    "Елизавета": ["Лиза", "Лизка", "Лизонька", "Лизавета", "Лизочка", "Элиза", "Бетти"],
    
    # И
    "Инна": ["Инночка", "Инка", "Ина", "Инуся"],
    "Ирина": ["Ира", "Иришка", "Ирочка", "Ируся", "Ирка", "Иринка", "Ируня"],
    
    # К
    "Карина": ["Каринка", "Кара", "Каря", "Кариночка"],
    "Кристина": ["Кристя", "Кристинка", "Крис", "Тина", "Кристюша"],
    "Ксения": ["Ксюша", "Ксюха", "Ксеня", "Ксюшка", "Ксю", "Ксюня", "Ксенька"],
    
    # Л
    "Лариса": ["Лара", "Лариска", "Ларочка", "Ларуся"],
    "Любовь": ["Люба", "Любаша", "Любочка", "Любка", "Люся"],
    "Людмила": ["Люда", "Людочка", "Мила", "Людка", "Люся", "Милочка"],
    
    # М
    "Маргарита": ["Рита", "Марго", "Ритка", "Риточка", "Маргоша", "Маргаритка"],
    "Марина": ["Маринка", "Мариша", "Маришка", "Мара", "Маруся"],
    "Мария": ["Маша", "Машка", "Маруся", "Машуня", "Маня", "Машенька", "Манюня", "Мари"],
    "Милана": ["Мила", "Миланка", "Милаша", "Лана"],
    
    # Н
    "Надежда": ["Надя", "Надюша", "Наденька", "Надюха", "Надька"],
    "Наталья": ["Наташа", "Ната", "Наталка", "Наташка", "Натуля", "Натали", "Натуся"],
    "Нина": ["Ниночка", "Нинуля", "Нинка", "Ниня"],
    
    # О
    "Оксана": ["Ксана", "Оксанка", "Ксюша", "Ксанка"],
    "Ольга": ["Оля", "Олечка", "Олька", "Оленька", "Олюня", "Лёля"],
    
    # П
    "Полина": ["Поля", "Полинка", "Полюшка", "Поляша", "Полечка", "Полли"],
    
    # С
    "Светлана": ["Света", "Светик", "Светочка", "Светка", "Светуля", "Лана"],
    "София": ["Соня", "Софа", "Софочка", "Сонечка", "Софи", "Софьюшка", "Сонька"],
    
    # Т
    "Тамара": ["Тома", "Томочка", "Тамарка", "Томка"],
    "Татьяна": ["Таня", "Танюша", "Танечка", "Татьянка", "Танюшка", "Танька", "Тата"],
    
    # Ю
    "Юлия": ["Юля", "Юлька", "Юленька", "Юляша", "Юлечка", "Джули"],
    
    # Я
    "Яна": ["Янка", "Яночка", "Януся", "Янчик"],
}


# =============================================================================
# TRANSLITERATION MAPPINGS
# =============================================================================

# Standard transliteration (most common)
STANDARD_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
    'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya'
}

# Alternative transliterations people commonly use
ALTERNATIVE_TRANSLIT = {
    'ж': ['zh', 'j', 'g'],
    'х': ['kh', 'h', 'x'],
    'ц': ['ts', 'c', 'tz'],
    'ч': ['ch', 'tch'],
    'ш': ['sh'],
    'щ': ['shch', 'sch', 'sh'],
    'ы': ['y', 'i'],
    'э': ['e', 'eh'],
    'ю': ['yu', 'u', 'ju', 'iu'],
    'я': ['ya', 'ia', 'ja'],
    'ё': ['e', 'yo', 'io'],
    'й': ['y', 'i', 'j'],
}


# =============================================================================
# COMMON USERNAME PATTERNS
# =============================================================================

# Suffixes Russians commonly add
COMMON_SUFFIXES = [
    '', '_official', '_real', 'official', 'real',
    '_vk', '_ok', '_tg', '_insta',
    'ka', 'chik', 'ik', 'ok', 'ek',  # Diminutive endings
]

# Prefixes Russians commonly add  
COMMON_PREFIXES = [
    '', 'the', 'its', 'im', 'i_am', 'ya_',
    'real', 'official', 'true',
]

# Common year ranges for Russian social media users
BIRTH_YEAR_RANGES = {
    'millennials': range(1985, 1996),
    'gen_z': range(1997, 2005),
    'common': [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, '00', '01', '02', '03', '04', '05'],
}


# =============================================================================
# MAIN GENERATOR CLASS
# =============================================================================

class RussianUsernameGenerator:
    """
    Generates realistic Russian username variations.
    
    Usage:
        generator = RussianUsernameGenerator()
        usernames = generator.generate("Фёдор Портной", birth_year=1995)
    """
    
    def __init__(self):
        self.male_diminutives = MALE_DIMINUTIVES
        self.female_diminutives = FEMALE_DIMINUTIVES
        
    def transliterate(self, text: str, variant: str = 'standard') -> str:
        """
        Transliterate Cyrillic to Latin.
        
        Args:
            text: Text to transliterate
            variant: 'standard' or 'simple'
        """
        text = text.lower().strip()
        result = []
        
        for char in text:
            if char in STANDARD_TRANSLIT:
                result.append(STANDARD_TRANSLIT[char])
            elif char.isalnum() or char in '._-':
                result.append(char)
            elif char == ' ':
                result.append('_')
                
        return ''.join(result)
    
    def get_transliteration_variants(self, text: str) -> List[str]:
        """Get multiple transliteration variants for a text."""
        variants = set()
        
        # Standard transliteration
        standard = self.transliterate(text)
        variants.add(standard)
        
        # Try library transliteration
        try:
            lib_translit = translit(text.lower(), 'ru', reversed=True)
            variants.add(lib_translit.lower())
        except:
            pass
        
        # Alternative for specific characters
        text_lower = text.lower()
        if any(char in text_lower for char in ['ж', 'х', 'ц', 'ч', 'ш', 'щ', 'ю', 'я', 'ё']):
            # Generate variants with alternative transliterations
            for char, alternatives in ALTERNATIVE_TRANSLIT.items():
                if char in text_lower:
                    for alt in alternatives[1:]:  # Skip first (standard)
                        variant = standard.replace(STANDARD_TRANSLIT.get(char, ''), alt)
                        if variant != standard:
                            variants.add(variant)
        
        return list(variants)
    
    def get_diminutives(self, first_name: str) -> List[str]:
        """
        Get all diminutives for a first name.
        
        Args:
            first_name: First name in Russian (Cyrillic)
            
        Returns:
            List of diminutives in Cyrillic
        """
        # Normalize the name
        first_name = first_name.strip().title()
        
        # Check male names
        if first_name in self.male_diminutives:
            return self.male_diminutives[first_name]
        
        # Check female names
        if first_name in self.female_diminutives:
            return self.female_diminutives[first_name]
        
        # Try to find partial match
        for name, dims in {**self.male_diminutives, **self.female_diminutives}.items():
            if name.startswith(first_name) or first_name.startswith(name):
                return dims
        
        return []
    
    def generate_name_patterns(self, first: str, last: str) -> List[str]:
        """Generate common username patterns from first and last name."""
        patterns = []
        
        # Basic combinations
        patterns.extend([
            f"{first}{last}",           # ivanivanov
            f"{first}.{last}",          # ivan.ivanov
            f"{first}_{last}",          # ivan_ivanov
            f"{first}-{last}",          # ivan-ivanov
            f"{last}{first}",           # ivanovivan
            f"{last}.{first}",          # ivanov.ivan
            f"{last}_{first}",          # ivanov_ivan
            f"{first[0]}{last}",        # iivanov
            f"{first}{last[0]}",        # ivani
            f"{first[0]}.{last}",       # i.ivanov
            f"{first[0]}_{last}",       # i_ivanov
            f"{first[0]}-{last}",       # i-ivanov
            f"{last}{first[0]}",        # ivannovi
            first,                       # ivan
            last,                        # ivanov
        ])
        
        # Double letter patterns (common in Russian usernames)
        if len(first) >= 2:
            patterns.append(f"{first[0]*2}{last}")  # iiivanov
            patterns.append(f"{first}{first[-1]}")   # ivann
            
        # With underscores
        patterns.extend([
            f"_{first}{last}_",
            f"__{first}__",
            f"{first}__",
        ])
        
        return [p for p in patterns if p and len(p) >= 3]
    
    def add_year_suffixes(self, base_usernames: List[str], birth_year: Optional[int] = None) -> List[str]:
        """Add year suffixes to usernames."""
        result = list(base_usernames)
        
        years_to_add = []
        if birth_year:
            years_to_add = [
                str(birth_year),           # 1995
                str(birth_year)[-2:],      # 95
                str(birth_year)[-3:],      # 995
            ]
        else:
            # Common birth years for social media users
            years_to_add = ['95', '96', '97', '98', '99', '00', '01', '02', '03']
        
        for username in base_usernames[:10]:  # Limit to avoid explosion
            for year in years_to_add[:3]:
                result.append(f"{username}{year}")
                result.append(f"{username}_{year}")
                
        return result
    
    def generate(
        self, 
        full_name: str, 
        birth_year: Optional[int] = None,
        include_cyrillic: bool = True,
        max_variations: int = 50
    ) -> List[str]:
        """
        Generate comprehensive username variations.
        
        Args:
            full_name: Full name in Russian or English
            birth_year: Optional birth year for variations
            include_cyrillic: Include Cyrillic usernames (for VK, OK)
            max_variations: Maximum number of variations to return
            
        Returns:
            List of username variations, sorted by likelihood
        """
        usernames: Set[str] = set()
        priority_usernames: List[str] = []  # High-priority variations
        
        # Parse name
        parts = full_name.strip().split()
        if len(parts) < 1:
            return []
        
        # Determine if input is Cyrillic
        is_cyrillic = any('\u0400' <= char <= '\u04FF' for char in full_name)
        
        if is_cyrillic:
            cyrillic_name = full_name
            latin_name = self.transliterate(full_name)
        else:
            cyrillic_name = None
            latin_name = full_name.lower()
        
        # Extract first and last name
        latin_parts = latin_name.replace('.', ' ').replace('_', ' ').split()
        first_latin = latin_parts[0] if latin_parts else ''
        last_latin = latin_parts[-1] if len(latin_parts) > 1 else ''
        
        # Get Cyrillic parts for diminutive lookup
        if is_cyrillic:
            cyrillic_parts = cyrillic_name.split()
            first_cyrillic = cyrillic_parts[0] if cyrillic_parts else ''
        else:
            first_cyrillic = ''
        
        # ===================
        # HIGH PRIORITY: Diminutives (most likely to be used)
        # ===================
        if first_cyrillic:
            diminutives = self.get_diminutives(first_cyrillic)
            for dim in diminutives[:5]:  # Top 5 diminutives
                dim_latin = self.transliterate(dim)
                priority_usernames.append(dim_latin)
                
                if last_latin:
                    priority_usernames.append(f"{dim_latin}{last_latin}")
                    priority_usernames.append(f"{dim_latin}_{last_latin}")
                    priority_usernames.append(f"{dim_latin}.{last_latin}")
                    
                # Add year to diminutives
                if birth_year:
                    priority_usernames.append(f"{dim_latin}{str(birth_year)[-2:]}")
                    priority_usernames.append(f"{dim_latin}{last_latin}{str(birth_year)[-2:]}")
                    
                # Cyrillic versions for VK/OK
                if include_cyrillic:
                    usernames.add(dim.lower())
                    if len(cyrillic_parts) > 1:
                        usernames.add(f"{dim.lower()}{cyrillic_parts[-1].lower()}")
        
        # ===================
        # STANDARD: Full name patterns
        # ===================
        if first_latin and last_latin:
            patterns = self.generate_name_patterns(first_latin, last_latin)
            for pattern in patterns:
                usernames.add(pattern)
        elif first_latin:
            usernames.add(first_latin)
            usernames.add(f"{first_latin}{first_latin[-1]}")  # Double last letter
        
        # ===================
        # TRANSLITERATION VARIANTS
        # ===================
        if is_cyrillic:
            for variant in self.get_transliteration_variants(cyrillic_name):
                usernames.add(variant.replace(' ', ''))
                usernames.add(variant.replace(' ', '_'))
                usernames.add(variant.replace(' ', '.'))
        
        # ===================
        # YEAR SUFFIXES
        # ===================
        base_for_years = list(priority_usernames[:5]) + list(usernames)[:10]
        year_variations = self.add_year_suffixes(base_for_years, birth_year)
        usernames.update(year_variations)
        
        # ===================
        # CYRILLIC VARIATIONS (for VK, OK)
        # ===================
        if include_cyrillic and is_cyrillic:
            cyrillic_lower = cyrillic_name.lower()
            usernames.add(cyrillic_lower.replace(' ', ''))
            usernames.add(cyrillic_lower.replace(' ', '_'))
            usernames.add(cyrillic_lower.replace(' ', '.'))
            
            # Cyrillic with year
            if birth_year:
                usernames.add(f"{cyrillic_lower.replace(' ', '')}{str(birth_year)[-2:]}")
        
        # ===================
        # CLEAN AND PRIORITIZE
        # ===================
        # Remove invalid usernames
        valid_usernames = []
        for u in usernames:
            u = u.strip().lower()
            # Must be 3-30 chars, alphanumeric with . _ -
            if u and 3 <= len(u) <= 30 and re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9._-]+$', u):
                valid_usernames.append(u)
        
        # Combine priority + rest, deduplicate
        final = []
        seen = set()
        
        # Add priority usernames first
        for u in priority_usernames:
            u_clean = u.strip().lower()
            if u_clean and u_clean not in seen and 3 <= len(u_clean) <= 30:
                final.append(u_clean)
                seen.add(u_clean)
        
        # Add rest
        for u in valid_usernames:
            if u not in seen:
                final.append(u)
                seen.add(u)
        
        return final[:max_variations]


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_russian_usernames(
    full_name: str, 
    birth_year: Optional[int] = None,
    max_variations: int = 50
) -> List[str]:
    """
    Generate realistic Russian username variations.
    
    Args:
        full_name: Full name in Russian (Cyrillic) or English
        birth_year: Optional birth year
        max_variations: Maximum variations to return
        
    Returns:
        List of username variations
        
    Example:
        >>> generate_russian_usernames("Фёдор Портной", birth_year=1995)
        ['fedya', 'fedya_portnoi', 'fedyaportnoi', 'fedya95', 'fedya_portnoi95',
         'fedyunya', 'fedor', 'fedor_portnoi', 'fedorportnoi', 'portnoi_fedor', ...]
    """
    generator = RussianUsernameGenerator()
    return generator.generate(full_name, birth_year, max_variations=max_variations)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Russian Username Generator - Test")
    print("=" * 60)
    
    test_names = [
        ("Фёдор Портной", 1995),
        ("Александр Иванов", 1998),
        ("Екатерина Смирнова", 2001),
        ("Дмитрий Козлов", None),
        ("Анастасия Попова", 1997),
    ]
    
    for name, year in test_names:
        print(f"\n{'='*60}")
        print(f"Name: {name}")
        print(f"Birth Year: {year}")
        print("-" * 60)
        
        usernames = generate_russian_usernames(name, birth_year=year, max_variations=30)
        
        print(f"Generated {len(usernames)} variations:")
        print()
        
        # Show in columns
        for i, u in enumerate(usernames):
            print(f"  {i+1:2}. {u}")
        
    print("\n" + "=" * 60)
    print("Diminutive Examples:")
    print("-" * 60)
    
    generator = RussianUsernameGenerator()
    example_names = ["Александр", "Екатерина", "Дмитрий", "Анастасия", "Фёдор"]
    
    for name in example_names:
        dims = generator.get_diminutives(name)
        print(f"  {name}: {', '.join(dims[:6])}")

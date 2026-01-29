"""
Ultimate Russian Username Generator v3.0
=========================================
17-category comprehensive system covering all known patterns Russians use online.

Categories:
1. Basic Forms - diminutives, formal names
2. Name+Surname Combos - various combinations
3. Initial Patterns - initials with names
4. Year/Number Patterns - birth years, common numbers
5. Russian Prefixes - ya_, eto_, etc.
6. English Prefixes - the_, real_, just_, etc.
7. Suffix Patterns - _official, _real, etc.
8. City/Region - msk, spb, etc.
9. Gaming Patterns - ninja, pro, killer, etc.
10. Doubled Patterns - repeated names/chars
11. Leetspeak Patterns - number substitutions
12. Keyboard Layout - Cyrillic on English keyboard
13. Reversed Patterns - reversed names
14. Animal/Object Combos - nature words
15. Patronymic Patterns - father's name variants
16. Profession Patterns - professional prefixes
17. Special Char Patterns - dots, underscores

Author: IBP Project
Version: 3.0
"""

import re
from typing import List, Dict, Set, Optional, Tuple
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

# Keyboard layout map (Cyrillic keys → English keyboard positions)
KEYBOARD_CYRILLIC_TO_LATIN = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u',
    'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j',
    'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
    'б': ',', 'ю': '.', 'ё': '`',
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
    """Generate multiple transliteration variants."""
    text = text.lower().strip()
    if not text:
        return []

    char_options = []
    for char in text:
        if char in TRANSLIT_VARIANTS:
            char_options.append(TRANSLIT_VARIANTS[char])
        elif char.isalnum():
            char_options.append([char])

    if not char_options:
        return []

    variants = set()
    simple = transliterate_simple(text)
    if simple:
        variants.add(simple)

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


def keyboard_layout_convert(cyrillic_text: str) -> str:
    """Convert Cyrillic text as if typed on English keyboard layout."""
    result = []
    for char in cyrillic_text.lower():
        if char in KEYBOARD_CYRILLIC_TO_LATIN:
            mapped = KEYBOARD_CYRILLIC_TO_LATIN[char]
            if mapped.isalnum():
                result.append(mapped)
        elif char.isalnum():
            result.append(char)
    return ''.join(result)


# =============================================================================
# COMPREHENSIVE RUSSIAN DIMINUTIVES DATABASE
# =============================================================================

# Male diminutives (Cyrillic)
MALE_DIMINUTIVES_CYR = {
    "Александр": ["Саша", "Шура", "Саня", "Санёк", "Алекс", "Санька", "Шурик", "Сашка", "Санечка", "Алексашка", "Сашок"],
    "Алексей": ["Лёша", "Лёха", "Алёша", "Лёшка", "Лёшик"],
    "Анатолий": ["Толя", "Толик", "Толян", "Толька"],
    "Андрей": ["Андрюша", "Андрюха", "Дрон", "Дюша", "Андрюшка", "Андрейка", "Дрюня"],
    "Антон": ["Тоша", "Тоха", "Антоха", "Антошка"],
    "Артём": ["Тёма", "Артёмка", "Тёмка", "Артёмчик", "Тёмыч"],
    "Богдан": ["Богдаша", "Бодя", "Даня", "Дан"],
    "Борис": ["Боря", "Борька", "Борян", "Борюсик", "Боб"],
    "Вадим": ["Вадик", "Вадя", "Вадимка", "Вадос"],
    "Валерий": ["Валера", "Валерка", "Лера", "Валерон"],
    "Василий": ["Вася", "Васька", "Василёк", "Васёк", "Васян"],
    "Виктор": ["Витя", "Витёк", "Витька", "Вик"],
    "Виталий": ["Виталик", "Виталя", "Витас"],
    "Владимир": ["Вова", "Володя", "Вовка", "Вовчик", "Влад", "Вован", "Вовик"],
    "Владислав": ["Влад", "Владик", "Слава", "Славик", "Славян"],
    "Вячеслав": ["Слава", "Славик", "Славка", "Славян"],
    "Геннадий": ["Гена", "Генка", "Геша", "Генаша"],
    "Георгий": ["Гоша", "Жора", "Гошка", "Жорик", "Гога", "Гошан"],
    "Глеб": ["Глебушка", "Глебка", "Глебчик"],
    "Григорий": ["Гриша", "Гриня", "Гришка", "Гришаня"],
    "Даниил": ["Даня", "Данила", "Данька", "Дан", "Данил", "Данёк", "Дэн"],
    "Денис": ["Дэн", "Дениска", "Денчик", "Ден"],
    "Дмитрий": ["Дима", "Димон", "Митя", "Димка", "Димыч", "Митяй", "Димас", "Димасик"],
    "Евгений": ["Женя", "Женёк", "Жека", "Женька", "Евген"],
    "Егор": ["Егорка", "Егорушка", "Гора", "Егорыч"],
    "Иван": ["Ваня", "Ванёк", "Ванька", "Ванюша", "Ванёс"],
    "Игорь": ["Игорёк", "Игорёха", "Гоша", "Гарик", "Игорёша"],
    "Илья": ["Илюша", "Илюха", "Илюшка"],
    "Кирилл": ["Кирюша", "Кирюха", "Киря", "Кир", "Кирилка"],
    "Константин": ["Костя", "Костик", "Костян", "Костюша", "Кос"],
    "Леонид": ["Лёня", "Лёнька", "Лёнчик"],
    "Максим": ["Макс", "Максик", "Максимка", "Максон"],
    "Марк": ["Маркуша", "Марик"],
    "Матвей": ["Мотя", "Матвейка", "Матюша"],
    "Михаил": ["Миша", "Мишка", "Мишаня", "Михан", "Мишутка", "Михась"],
    "Никита": ["Никитка", "Никитос", "Ник", "Кит"],
    "Николай": ["Коля", "Колян", "Николаша", "Колька", "Ник"],
    "Олег": ["Олежка", "Олежек", "Лёжик", "Лёга"],
    "Павел": ["Паша", "Пашка", "Павлик", "Пашок", "Паха", "Пашуля", "Павлуша"],
    "Пётр": ["Петя", "Петька", "Петруша", "Петруха"],
    "Роман": ["Рома", "Ромка", "Ромчик", "Ромыч", "Ромаха", "Ромашка"],
    "Руслан": ["Русик", "Руся", "Рус", "Руслик"],
    "Сергей": ["Серёжа", "Серёга", "Серж", "Серый", "Серёжка", "Серго", "Серёня", "Сергуня"],
    "Станислав": ["Стас", "Стасик", "Славик", "Стасян"],
    "Степан": ["Стёпа", "Стёпка", "Степашка"],
    "Тимофей": ["Тима", "Тимоха", "Тимоша", "Тимка"],
    "Тимур": ["Тима", "Тимурка", "Тим"],
    "Фёдор": ["Федя", "Федька", "Федюня", "Федюша", "Феденька", "Федос"],
    "Филипп": ["Филя", "Фил", "Филиппок"],
    "Эдуард": ["Эдик", "Эд", "Эдя"],
    "Юрий": ["Юра", "Юрка", "Юрок", "Юрец"],
    "Ярослав": ["Ярик", "Слава", "Славик", "Яр"],
}

# Female diminutives (Cyrillic)
FEMALE_DIMINUTIVES_CYR = {
    "Александра": ["Саша", "Сашка", "Шура", "Саня", "Сашуля", "Алекса", "Сашенька"],
    "Алина": ["Аля", "Алинка", "Лина", "Алиночка"],
    "Алиса": ["Алиска", "Аля", "Лиса"],
    "Анастасия": ["Настя", "Настёна", "Ася", "Настюша", "Стася", "Настюха", "Настасья"],
    "Ангелина": ["Геля", "Лина", "Энжи"],
    "Анна": ["Аня", "Анюта", "Нюра", "Аннушка", "Анька", "Нюша", "Анечка"],
    "Арина": ["Аринка", "Ариша", "Рина"],
    "Валентина": ["Валя", "Валюша", "Валечка", "Валентинка"],
    "Валерия": ["Лера", "Лерка", "Валерка", "Валери"],
    "Варвара": ["Варя", "Варька", "Вава"],
    "Вера": ["Верочка", "Верка", "Веруня"],
    "Вероника": ["Ника", "Вера", "Рони", "Вероничка"],
    "Виктория": ["Вика", "Викуся", "Викуля", "Вики", "Тори"],
    "Галина": ["Галя", "Галка", "Галочка"],
    "Дарья": ["Даша", "Дашка", "Дашуля", "Дашенька", "Дашуня"],
    "Диана": ["Ди", "Дианка"],
    "Ева": ["Евочка", "Евуся"],
    "Евгения": ["Женя", "Женечка", "Женька", "Геня"],
    "Екатерина": ["Катя", "Катюша", "Катенька", "Катька", "Кэт", "Катюня", "Катюха"],
    "Елена": ["Лена", "Леночка", "Ленка", "Алёна", "Леся", "Ленуся"],
    "Елизавета": ["Лиза", "Лизка", "Лизонька", "Лизочка", "Элиза", "Лизавета", "Эля"],
    "Инна": ["Инночка", "Инка", "Ина"],
    "Ирина": ["Ира", "Иришка", "Ирочка", "Ируся", "Ирка", "Ируня", "Тина"],
    "Карина": ["Каринка", "Кара", "Каря"],
    "Кристина": ["Кристя", "Кристинка", "Крис", "Тина"],
    "Ксения": ["Ксюша", "Ксюха", "Ксеня", "Ксю", "Ксюня"],
    "Лариса": ["Лара", "Лариска", "Ларочка"],
    "Любовь": ["Люба", "Любаша", "Любочка", "Люся"],
    "Людмила": ["Люда", "Людочка", "Мила", "Люся"],
    "Маргарита": ["Рита", "Марго", "Ритка", "Маргоша"],
    "Марина": ["Маринка", "Мариша", "Мара", "Маруся"],
    "Мария": ["Маша", "Машка", "Маруся", "Машуня", "Маня", "Мари", "Машенька"],
    "Милана": ["Мила", "Миланка", "Милаша", "Лана"],
    "Надежда": ["Надя", "Надюша", "Наденька", "Надюха"],
    "Наталья": ["Наташа", "Ната", "Наталка", "Наташка", "Натали", "Натуся"],
    "Нина": ["Ниночка", "Нинуля", "Нинка"],
    "Оксана": ["Ксана", "Оксанка", "Ксюша"],
    "Ольга": ["Оля", "Олечка", "Олька", "Оленька", "Лёля"],
    "Полина": ["Поля", "Полинка", "Полюшка", "Полечка", "Полли"],
    "Светлана": ["Света", "Светик", "Светочка", "Светка", "Лана", "Светланка"],
    "София": ["Соня", "Софа", "Софочка", "Софи", "Сонька"],
    "Тамара": ["Тома", "Томочка", "Тамарка"],
    "Татьяна": ["Таня", "Танюша", "Танечка", "Танюшка", "Танька", "Тата"],
    "Юлия": ["Юля", "Юлька", "Юленька", "Юляша", "Джули"],
    "Яна": ["Янка", "Яночка", "Януся"],
}

# Combined dictionary with pre-transliterated values
RUSSIAN_DIMINUTIVES = {
    # Male names (transliterated)
    'александр': ['sasha', 'shura', 'sanya', 'sanek', 'alex', 'sanka', 'shurik', 'sashka', 'sanechka', 'aleksashka', 'sashok'],
    'алексей': ['lyosha', 'lyokha', 'alyosha', 'lyoshka', 'lyoshik', 'lesha', 'lekha'],
    'анатолий': ['tolya', 'tolik', 'tolyan', 'tolka'],
    'андрей': ['andryusha', 'andryukha', 'dron', 'dyusha', 'andryushka', 'andrey', 'andreyka', 'dryunya'],
    'антон': ['tosha', 'tokha', 'antokha', 'antoshka', 'anton'],
    'артём': ['tyoma', 'artyomka', 'tyomka', 'artyomchik', 'tyomych', 'tema', 'artem'],
    'богдан': ['bogdasha', 'bodya', 'danya', 'dan'],
    'борис': ['borya', 'borka', 'boryan', 'boris', 'boryusik', 'bob'],
    'вадим': ['vadik', 'vadya', 'vadimka', 'vadim', 'vados'],
    'валерий': ['valera', 'valerka', 'lera', 'valeron', 'valery'],
    'василий': ['vasya', 'vaska', 'vasilyok', 'vasyok', 'vasyan', 'vasily'],
    'виктор': ['vitya', 'vityok', 'vitka', 'viktor', 'victor', 'vik'],
    'виталий': ['vitalik', 'vitalya', 'vitas', 'vitaly'],
    'владимир': ['vova', 'volodya', 'vovka', 'vovchik', 'vlad', 'vovan', 'vladimir', 'vovik'],
    'владислав': ['vlad', 'vladik', 'slava', 'slavik', 'vladislav', 'slavyan'],
    'вячеслав': ['slava', 'slavik', 'slavka', 'slavyan', 'vyacheslav'],
    'геннадий': ['gena', 'genka', 'gesha', 'gennady', 'genasha'],
    'георгий': ['gosha', 'zhora', 'goshka', 'zhorik', 'georgy', 'george', 'goga', 'goshan'],
    'глеб': ['glebushka', 'glebka', 'glebchik', 'gleb'],
    'григорий': ['grisha', 'grinya', 'grishka', 'grigory', 'greg', 'grishanya'],
    'даниил': ['danya', 'danila', 'danka', 'dan', 'danil', 'daniel', 'danek', 'den'],
    'денис': ['den', 'deniska', 'denchik', 'denis'],
    'дмитрий': ['dima', 'dimon', 'mitya', 'dimka', 'dimych', 'mityay', 'dimas', 'dmitry', 'dmitri', 'dimasik'],
    'евгений': ['zhenya', 'zhenyok', 'zheka', 'zhenka', 'evgen', 'evgeny', 'eugene'],
    'егор': ['egorka', 'egorushka', 'gora', 'egorych', 'egor', 'yegor'],
    'иван': ['vanya', 'vanyok', 'vanka', 'vanyusha', 'vanyos', 'ivan'],
    'игорь': ['igoryok', 'igoryokha', 'gosha', 'garik', 'igor', 'igoryosha'],
    'илья': ['ilyusha', 'ilyukha', 'ilyushka', 'ilya'],
    'кирилл': ['kiryusha', 'kiryukha', 'kirya', 'kir', 'kirill', 'cyril', 'kirilka'],
    'константин': ['kostya', 'kostik', 'kostyan', 'kostyusha', 'konstantin', 'kos'],
    'леонид': ['lyonya', 'lyonka', 'lyonchik', 'leonid', 'leo'],
    'максим': ['maks', 'maksik', 'maksimka', 'makson', 'max', 'maxim'],
    'марк': ['markusha', 'marik', 'mark'],
    'матвей': ['motya', 'matveyka', 'matyusha', 'matvey'],
    'михаил': ['misha', 'mishka', 'mishanya', 'mikhan', 'mishutka', 'mikhail', 'michael', 'miha', 'mikhas'],
    'никита': ['nikitka', 'nikitos', 'nik', 'kit', 'nikita'],
    'николай': ['kolya', 'kolyan', 'nikolasha', 'kolka', 'nik', 'nikolay', 'nick'],
    'олег': ['olezhka', 'olezhek', 'lyozhik', 'oleg', 'lyoga'],
    'павел': ['pasha', 'pashka', 'pavlik', 'pashok', 'pakha', 'pavel', 'paul', 'pashulya', 'pavlusha'],
    'пётр': ['petya', 'petka', 'petrusha', 'petrukha', 'petr', 'peter', 'pyotr'],
    'роман': ['roma', 'romka', 'romchik', 'romych', 'romakha', 'roman', 'romashka'],
    'руслан': ['rusik', 'rusya', 'rus', 'ruslan', 'ruslik'],
    'сергей': ['seryozha', 'seryoga', 'serzh', 'seryy', 'seryozhka', 'sergo', 'sergey', 'sergei', 'serge', 'seryonya', 'sergunya'],
    'станислав': ['stas', 'stasik', 'slavik', 'stasyan', 'stanislav'],
    'степан': ['styopa', 'styopka', 'stepashka', 'stepan', 'stepa'],
    'тимофей': ['tima', 'timokha', 'timosha', 'timka', 'timofey', 'tim'],
    'тимур': ['tima', 'timurka', 'tim', 'timur'],
    'фёдор': ['fedya', 'fedka', 'fedyunya', 'fedyusha', 'fedenka', 'fedos', 'fedor', 'fyodor', 'theodore'],
    'филипп': ['filya', 'fil', 'filippok', 'filipp', 'philip'],
    'эдуард': ['edik', 'ed', 'edya', 'eduard', 'edward'],
    'юрий': ['yura', 'yurka', 'yurok', 'yurets', 'yury', 'yuri'],
    'ярослав': ['yarik', 'slava', 'slavik', 'yar', 'yaroslav'],

    # Female names (transliterated)
    'александра': ['sasha', 'sashka', 'shura', 'sanya', 'sashulya', 'aleksa', 'alexandra', 'sashenka'],
    'алина': ['alya', 'alinka', 'lina', 'alina', 'alinochka'],
    'алиса': ['aliska', 'alya', 'lisa', 'alisa', 'alice'],
    'анастасия': ['nastya', 'nastyona', 'asya', 'nastyusha', 'stasya', 'nastyukha', 'anastasia', 'nastasya'],
    'ангелина': ['gelya', 'lina', 'anzhi', 'angelina'],
    'анна': ['anya', 'anyuta', 'nyura', 'annushka', 'anka', 'nyusha', 'anna', 'ann', 'anechka'],
    'арина': ['arinka', 'arisha', 'rina', 'arina'],
    'валентина': ['valya', 'valyusha', 'valechka', 'valentina', 'valentinka'],
    'валерия': ['lera', 'lerka', 'valerka', 'valeri', 'valeriya', 'valeria'],
    'варвара': ['varya', 'varka', 'vava', 'varvara', 'barbara'],
    'вера': ['verochka', 'verka', 'verunya', 'vera'],
    'вероника': ['nika', 'vera', 'roni', 'veronika', 'veronica', 'veronichka'],
    'виктория': ['vika', 'vikusya', 'vikulya', 'viki', 'tori', 'viktoriya', 'victoria'],
    'галина': ['galya', 'galka', 'galochka', 'galina'],
    'дарья': ['dasha', 'dashka', 'dashulya', 'dashenka', 'dashunya', 'darya', 'daria'],
    'диана': ['di', 'dianka', 'diana'],
    'ева': ['evochka', 'evusya', 'eva', 'eve'],
    'евгения': ['zhenya', 'zhenechka', 'zhenka', 'genya', 'evgeniya', 'eugenia'],
    'екатерина': ['katya', 'katyusha', 'katenka', 'katka', 'ket', 'katyunya', 'katyukha', 'ekaterina', 'kate', 'catherine'],
    'елена': ['lena', 'lenochka', 'lenka', 'alyona', 'lesya', 'lenusya', 'elena', 'helen'],
    'елизавета': ['liza', 'lizka', 'lizonka', 'lizochka', 'eliza', 'elizaveta', 'elizabeth', 'lizaveta', 'elya'],
    'инна': ['innochka', 'inka', 'ina', 'inna'],
    'ирина': ['ira', 'irishka', 'irochka', 'irusya', 'irka', 'irunya', 'irina', 'tina'],
    'карина': ['karinka', 'kara', 'karya', 'karina'],
    'кристина': ['kristya', 'kristinka', 'kris', 'tina', 'kristina', 'christina'],
    'ксения': ['ksyusha', 'ksyukha', 'ksenya', 'ksyu', 'ksyunya', 'ksenia', 'kseniya'],
    'лариса': ['lara', 'lariska', 'larochka', 'larisa'],
    'любовь': ['lyuba', 'lyubasha', 'lyubochka', 'lyusya', 'lubov'],
    'людмила': ['lyuda', 'lyudochka', 'mila', 'lyusya', 'lyudmila'],
    'маргарита': ['rita', 'margo', 'ritka', 'margosha', 'margarita'],
    'марина': ['marinka', 'marisha', 'mara', 'marusya', 'marina'],
    'мария': ['masha', 'mashka', 'marusya', 'mashunya', 'manya', 'mari', 'maria', 'mary', 'mashenka'],
    'милана': ['mila', 'milanka', 'milasha', 'lana', 'milana'],
    'надежда': ['nadya', 'nadyusha', 'nadenka', 'nadyukha', 'nadezhda'],
    'наталья': ['natasha', 'nata', 'natalka', 'natashka', 'natali', 'natusya', 'natalya', 'natalia'],
    'нина': ['ninochka', 'ninulya', 'ninka', 'nina'],
    'оксана': ['ksana', 'oksanka', 'ksyusha', 'oksana'],
    'ольга': ['olya', 'olechka', 'olka', 'olenka', 'lyolya', 'olga'],
    'полина': ['polya', 'polinka', 'polyushka', 'polechka', 'polli', 'polina'],
    'светлана': ['sveta', 'svetik', 'svetochka', 'svetka', 'lana', 'svetlana', 'svetlanka'],
    'софия': ['sonya', 'sofa', 'sofochka', 'sofi', 'sonka', 'sofya', 'sofia', 'sophia'],
    'тамара': ['toma', 'tomochka', 'tamarka', 'tamara'],
    'татьяна': ['tanya', 'tanyusha', 'tanechka', 'tanyushka', 'tanka', 'tata', 'tatyana', 'tatiana'],
    'юлия': ['yulya', 'yulka', 'yulenka', 'yulyasha', 'dzhuli', 'julia', 'yulia'],
    'яна': ['yanka', 'yanochka', 'yanusya', 'yana'],
}

# Latin aliases for quick lookup
LATIN_ALIASES = {
    # Male - formal names
    'dmitry': 'дмитрий', 'dmitri': 'дмитрий', 'dimitri': 'дмитрий', 'dmitriy': 'дмитрий',
    'alexander': 'александр', 'alex': 'александр', 'aleksandr': 'александр',
    'alexei': 'алексей', 'alexey': 'алексей', 'aleksei': 'алексей',
    'andrey': 'андрей', 'andrew': 'андрей', 'andrei': 'андрей', 'andry': 'андрей',
    'anton': 'антон',
    'artem': 'артём', 'artyom': 'артём', 'artjom': 'артём',
    'bogdan': 'богдан',
    'boris': 'борис',
    'vadim': 'вадим',
    'valery': 'валерий', 'valeri': 'валерий', 'valeriy': 'валерий',
    'vasily': 'василий', 'vasiliy': 'василий',
    'viktor': 'виктор', 'victor': 'виктор',
    'vitaly': 'виталий', 'vitaliy': 'виталий',
    'vladimir': 'владимир',
    'vladislav': 'владислав',
    'vyacheslav': 'вячеслав',
    'gennady': 'геннадий', 'gennadiy': 'геннадий',
    'georgy': 'георгий', 'george': 'георгий', 'georgiy': 'георгий',
    'gleb': 'глеб',
    'grigory': 'григорий', 'gregory': 'григорий', 'grigoriy': 'григорий',
    'daniil': 'даниил', 'daniel': 'даниил', 'danil': 'даниил',
    'denis': 'денис',
    'eugene': 'евгений', 'evgeny': 'евгений', 'evgeni': 'евгений', 'evgeniy': 'евгений',
    'egor': 'егор', 'yegor': 'егор',
    'ivan': 'иван', 'john': 'иван',
    'igor': 'игорь',
    'ilya': 'илья', 'ilia': 'илья',
    'kirill': 'кирилл', 'cyril': 'кирилл',
    'konstantin': 'константин', 'constantine': 'константин',
    'leonid': 'леонид',
    'maxim': 'максим', 'maksim': 'максим',
    'mark': 'марк',
    'matvey': 'матвей', 'matthew': 'матвей',
    'mikhail': 'михаил', 'michael': 'михаил', 'mihail': 'михаил',
    'nikita': 'никита',
    'nikolay': 'николай', 'nikolai': 'николай', 'nicholas': 'николай',
    'oleg': 'олег',
    'pavel': 'павел', 'paul': 'павел',
    'petr': 'пётр', 'peter': 'пётр', 'pyotr': 'пётр',
    'roman': 'роман',
    'ruslan': 'руслан',
    'sergey': 'сергей', 'sergei': 'сергей', 'serge': 'сергей', 'sergiy': 'сергей',
    'stanislav': 'станислав',
    'stepan': 'степан', 'stefan': 'степан',
    'timofey': 'тимофей', 'timothy': 'тимофей',
    'timur': 'тимур',
    'fedor': 'фёдор', 'fyodor': 'фёдор', 'theodore': 'фёдор', 'feodor': 'фёдор',
    'filipp': 'филипп', 'philip': 'филипп', 'phillip': 'филипп',
    'eduard': 'эдуард', 'edward': 'эдуард',
    'yuri': 'юрий', 'yury': 'юрий', 'yuriy': 'юрий',
    'yaroslav': 'ярослав',
    # Male - common diminutives as input
    'sasha': 'александр', 'shura': 'александр', 'sanya': 'александр',
    'lyosha': 'алексей', 'lesha': 'алексей', 'alyosha': 'алексей',
    'tolya': 'анатолий', 'tolik': 'анатолий',
    'andryusha': 'андрей', 'dron': 'андрей',
    'tosha': 'антон', 'antokha': 'антон',
    'tema': 'артём', 'tyoma': 'артём',
    'borya': 'борис',
    'vadik': 'вадим',
    'valera': 'валерий',
    'vasya': 'василий', 'vaska': 'василий',
    'vitya': 'виктор',
    'vitalik': 'виталий',
    'vova': 'владимир', 'volodya': 'владимир', 'vlad': 'владимир', 'vovan': 'владимир',
    'vladik': 'владислав',
    'slava': 'вячеслав', 'slavik': 'вячеслав',
    'gena': 'геннадий', 'gesha': 'геннадий',
    'gosha': 'георгий', 'zhora': 'георгий',
    'grisha': 'григорий',
    'danya': 'даниил', 'dan': 'даниил', 'danila': 'даниил',
    'den': 'денис', 'deniska': 'денис',
    'dima': 'дмитрий', 'dimon': 'дмитрий', 'mitya': 'дмитрий', 'dimka': 'дмитрий', 'dimas': 'дмитрий',
    'zhenya': 'евгений', 'zheka': 'евгений', 'evgen': 'евгений',
    'egorka': 'егор',
    'vanya': 'иван', 'vanyok': 'иван',
    'garik': 'игорь',
    'ilyusha': 'илья', 'ilyukha': 'илья',
    'kirya': 'кирилл', 'kir': 'кирилл',
    'kostya': 'константин', 'kostik': 'константин', 'kostyan': 'константин',
    'lyonya': 'леонид',
    'max': 'максим', 'maks': 'максим', 'maksik': 'максим',
    'misha': 'михаил', 'mishka': 'михаил', 'miha': 'михаил',
    'nik': 'никита', 'nikitos': 'никита',
    'kolya': 'николай', 'kolyan': 'николай',
    'olezhka': 'олег',
    'pasha': 'павел', 'pashka': 'павел', 'pakha': 'павел',
    'petya': 'пётр', 'petka': 'пётр',
    'roma': 'роман', 'romka': 'роман', 'romych': 'роман',
    'rusik': 'руслан', 'rus': 'руслан',
    'seryozha': 'сергей', 'seryoga': 'сергей', 'serzh': 'сергей', 'sergo': 'сергей',
    'stas': 'станислав', 'stasik': 'станислав',
    'styopa': 'степан', 'stepa': 'степан',
    'tima': 'тимофей', 'timka': 'тимофей',
    'fedya': 'фёдор', 'fedka': 'фёдор', 'fedos': 'фёдор',
    'filya': 'филипп', 'fil': 'филипп',
    'edik': 'эдуард', 'ed': 'эдуард',
    'yura': 'юрий', 'yurka': 'юрий',
    'yarik': 'ярослав', 'yar': 'ярослав',
    # Female - formal names
    'alexandra': 'александра',
    'alina': 'алина',
    'alisa': 'алиса', 'alice': 'алиса',
    'anastasia': 'анастасия',
    'angelina': 'ангелина',
    'anna': 'анна', 'ann': 'анна',
    'arina': 'арина',
    'valentina': 'валентина',
    'valeriya': 'валерия', 'valeria': 'валерия',
    'varvara': 'варвара', 'barbara': 'варвара',
    'vera': 'вера',
    'veronika': 'вероника', 'veronica': 'вероника',
    'viktoriya': 'виктория', 'victoria': 'виктория',
    'galina': 'галина',
    'darya': 'дарья', 'daria': 'дарья',
    'diana': 'диана',
    'eva': 'ева', 'eve': 'ева',
    'evgeniya': 'евгения', 'eugenia': 'евгения',
    'ekaterina': 'екатерина', 'catherine': 'екатерина',
    'elena': 'елена', 'helen': 'елена',
    'elizaveta': 'елизавета', 'elizabeth': 'елизавета',
    'inna': 'инна',
    'irina': 'ирина',
    'karina': 'карина',
    'kristina': 'кристина', 'christina': 'кристина',
    'ksenia': 'ксения', 'kseniya': 'ксения',
    'larisa': 'лариса',
    'lubov': 'любовь',
    'lyudmila': 'людмила',
    'margarita': 'маргарита',
    'marina': 'марина',
    'maria': 'мария', 'mary': 'мария',
    'milana': 'милана',
    'nadezhda': 'надежда',
    'natalya': 'наталья', 'natalia': 'наталья',
    'nina': 'нина',
    'oksana': 'оксана',
    'olga': 'ольга',
    'polina': 'полина',
    'svetlana': 'светлана',
    'sofya': 'софия', 'sofia': 'софия', 'sophia': 'софия',
    'tamara': 'тамара',
    'tatyana': 'татьяна', 'tatiana': 'татьяна',
    'yulia': 'юлия', 'julia': 'юлия',
    'yana': 'яна',
    # Female - common diminutives as input
    'nastya': 'анастасия', 'asya': 'анастасия', 'stasya': 'анастасия',
    'anya': 'анна', 'anyuta': 'анна', 'nyura': 'анна', 'nyusha': 'анна',
    'arisha': 'арина',
    'valya': 'валентина',
    'lera': 'валерия', 'lerka': 'валерия',
    'varya': 'варвара',
    'vika': 'виктория', 'vikusya': 'виктория',
    'galya': 'галина',
    'dasha': 'дарья', 'dashka': 'дарья',
    'katya': 'екатерина', 'kate': 'екатерина', 'katyusha': 'екатерина',
    'lena': 'елена', 'lenochka': 'елена', 'alyona': 'елена',
    'liza': 'елизавета', 'lizka': 'елизавета',
    'ira': 'ирина', 'irishka': 'ирина',
    'ksyusha': 'ксения', 'ksyu': 'ксения',
    'lara': 'лариса',
    'lyuba': 'любовь', 'lyusya': 'любовь',
    'lyuda': 'людмила', 'mila': 'людмила',
    'rita': 'маргарита', 'margo': 'маргарита',
    'masha': 'мария', 'mashka': 'мария', 'marusya': 'мария',
    'nadya': 'надежда',
    'natasha': 'наталья', 'nata': 'наталья',
    'olya': 'ольга', 'olenka': 'ольга',
    'polya': 'полина',
    'sveta': 'светлана', 'svetik': 'светлана',
    'sonya': 'софия', 'sofa': 'софия',
    'toma': 'тамара',
    'tanya': 'татьяна', 'tanechka': 'татьяна', 'tata': 'татьяна',
    'yulya': 'юлия', 'yulenka': 'юлия',
    'yanka': 'яна',
}


def get_diminutives(name: str) -> List[str]:
    """Get diminutives for a Russian name."""
    name_lower = name.lower().strip()
    name_variants = [name_lower, name_lower.replace('ё', 'е'), name_lower.replace('е', 'ё')]

    for variant in name_variants:
        if variant in RUSSIAN_DIMINUTIVES:
            return RUSSIAN_DIMINUTIVES[variant]

    name_title = name.strip().title()
    name_title_variants = [name_title, name_title.replace('ё', 'е'), name_title.replace('е', 'ё'),
                          name_title.replace('Ё', 'Е'), name_title.replace('Е', 'Ё')]

    for variant in name_title_variants:
        if variant in MALE_DIMINUTIVES_CYR:
            return [transliterate_simple(d) for d in MALE_DIMINUTIVES_CYR[variant]]
        if variant in FEMALE_DIMINUTIVES_CYR:
            return [transliterate_simple(d) for d in FEMALE_DIMINUTIVES_CYR[variant]]

    if name_lower in LATIN_ALIASES:
        rus_name = LATIN_ALIASES[name_lower]
        if rus_name in RUSSIAN_DIMINUTIVES:
            return RUSSIAN_DIMINUTIVES[rus_name]

    name_translit = transliterate_simple(name_lower)
    for rus_name, dims in RUSSIAN_DIMINUTIVES.items():
        rus_translit = transliterate_simple(rus_name)
        if rus_translit == name_translit:
            return dims
        if name_translit in dims:
            return dims

    return []


# =============================================================================
# ULTIMATE USERNAME GENERATOR - 17 CATEGORIES
# =============================================================================

class UltimateUsernameGenerator:
    """
    17-category Russian username pattern system.

    Categories implemented:
    1. Basic Forms - diminutives and formal names
    2. Name+Surname Combos - various combinations
    3. Initial Patterns - initials with names
    4. Year/Number Patterns - birth years and common numbers
    5. Russian Prefixes - ya_, eto_, etc.
    6. English Prefixes - the_, real_, just_, etc.
    7. Suffix Patterns - _official, _real, etc.
    8. City/Region - msk, spb, etc.
    9. Gaming Patterns - ninja, pro, killer, etc.
    10. Doubled Patterns - repeated names/chars
    11. Leetspeak Patterns - number substitutions
    12. Keyboard Layout - Cyrillic on English keyboard
    13. Reversed Patterns - reversed names
    14. Animal/Object Combos - nature words
    15. Patronymic Patterns - father's name
    16. Profession Patterns - professional prefixes
    17. Special Char Patterns - dots, underscores
    """

    # === DATA STRUCTURES ===

    CITY_CODES = {
        'moscow': ['msk', 'msc', 'mos', '495', '499', '77'],
        'saint_petersburg': ['spb', 'piter', 'peter', '812', '78'],
        'novosibirsk': ['nsk', 'nvsb', '383', '54'],
        'yekaterinburg': ['ekb', 'ekburg', 'eburg', '343', '66'],
        'kazan': ['kzn', 'kazan', '843', '16'],
        'nizhny_novgorod': ['nn', 'nnov', 'nino', '831', '52'],
        'chelyabinsk': ['chel', 'che', '351', '74'],
        'samara': ['samara', 'sam', '846', '63'],
        'omsk': ['omsk', '381', '55'],
        'rostov': ['rostov', 'rnd', 'rost', '863', '61'],
        'ufa': ['ufa', '347', '02'],
        'krasnoyarsk': ['krsk', 'kras', '391', '24'],
        'perm': ['perm', '342', '59'],
        'voronezh': ['vrn', 'voronezh', '473', '36'],
        'volgograd': ['vlg', 'volga', '844', '34'],
    }

    GAMING_PREFIXES = [
        'ninja', 'pro', 'killer', 'dark', 'shadow', 'ghost', 'sniper', 'cyber',
        'neo', 'ace', 'boss', 'master', 'mega', 'super', 'ultra', 'hyper',
        'elite', 'epic', 'legend', 'crazy', 'mad', 'wild', 'fire', 'ice',
        'storm', 'thunder', 'wolf', 'bear', 'lion', 'tiger', 'dragon', 'phoenix',
        'demon', 'angel', 'god', 'king', 'lord', 'duke', 'prince', 'knight',
    ]

    GAMING_SUFFIXES = [
        'gamer', 'player', 'gaming', 'game', 'play', 'stream', 'streamer',
        'yt', 'youtube', 'twitch', 'ttv', 'tv', 'live', 'esport', 'esports',
    ]

    LEET_MAP = {
        'a': ['4', '@'],
        'e': ['3'],
        'i': ['1', '!'],
        'o': ['0'],
        's': ['5', '$'],
        't': ['7'],
        'b': ['8'],
        'g': ['9'],
        'l': ['1'],
    }

    RUSSIAN_PREFIXES = [
        'ya', 'ya_', 'ia', 'ia_',        # я (I)
        'eto', 'eto_', 'eta', 'eta_',    # это (this is)
        'im', 'im_',                      # I'm
        'ne', 'ne_',                      # не (not)
        'prosto', 'prosto_',              # просто (just)
        'realno', 'realno_',              # реально (really)
        'ochen', 'ochen_',                # очень (very)
        'tvoy', 'tvoya', 'tvoi',          # твой/твоя (your)
        'moy', 'moya', 'moi',             # мой/моя (my)
        'lubimiy', 'lubimaya',            # любимый (favorite)
        'miliy', 'milaya',                # милый (cute)
        'krasiviy', 'krasivaya',          # красивый (beautiful)
    ]

    ENGLISH_PREFIXES = [
        'the', 'the_', 'the.',
        'real', 'real_', 'real.',
        'just', 'just_',
        'only', 'only_',
        'its', 'its_', 'it_', 'its.',
        'im', 'i_am', 'iam', 'i_am_',
        'hey', 'hey_',
        'hi', 'hi_',
        'mr', 'mr_', 'mr.',
        'miss', 'miss_', 'ms_',
        'dr', 'dr_', 'dr.',
        'sir', 'sir_',
        'not', 'not_',
        'x', 'xx', 'xxx',
        'true', 'true_',
        'best', 'best_',
        'top', 'top_',
        'one', 'one_',
        'my', 'my_',
        'your', 'your_',
    ]

    SUFFIXES = [
        # Official/identity
        'official', '_official', '.official',
        'real', '_real', '.real',
        'original', '_original',
        'true', '_true',
        'vip', '_vip',
        # Platform hints
        'vk', '_vk', '.vk',
        'tg', '_tg', '.tg',
        'ok', '_ok',
        'insta', '_insta',
        # Status
        'online', '_online',
        'live', '_live',
        'here', '_here',
        # Common
        'man', '_man',
        'boy', '_boy',
        'girl', '_girl',
        'guy', '_guy',
        'dude', '_dude',
        'bro', '_bro',
        'sis', '_sis',
    ]

    NUMBER_SUFFIXES = [
        '1', '01', '001',
        '2', '02',
        '7', '07', '77', '777',
        '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23',
        '69', '96',
        '100', '101', '123', '228', '322', '420', '666',
        '007', '911',
    ]

    ANIMAL_WORDS = [
        'wolf', 'bear', 'lion', 'tiger', 'fox', 'cat', 'dog', 'eagle', 'hawk',
        'shark', 'snake', 'dragon', 'phoenix', 'raven', 'crow', 'owl', 'panther',
        'volk', 'medved', 'lis', 'lisa', 'kot', 'koshka', 'sobaka', 'orel',
        'sokol', 'akula', 'zmey', 'drakon', 'voron', 'sova', 'pantera',
    ]

    PROFESSION_PREFIXES = [
        'dev', 'developer', 'coder', 'hacker', 'programmer', 'engineer',
        'designer', 'artist', 'music', 'musician', 'dj', 'producer',
        'photo', 'photographer', 'video', 'editor', 'writer', 'blogger',
        'trader', 'crypto', 'business', 'entrepreneur', 'freelance', 'freelancer',
        'student', 'stud', 'teacher', 'coach', 'trainer', 'doctor', 'lawyer',
    ]

    def __init__(self, max_results: int = 200):
        self.max_results = max_results

    def generate_all_usernames(
        self,
        first_name: str,
        last_name: str = '',
        birth_year: Optional[int] = None,
        father_name: Optional[str] = None,
        gender: str = 'male',
        city: Optional[str] = None,
        max_usernames: int = 200
    ) -> List[str]:
        """
        Master generator applying all 17 categories.

        Args:
            first_name: First name (Cyrillic or Latin)
            last_name: Last name (Cyrillic or Latin)
            birth_year: Optional birth year (e.g., 1990)
            father_name: Optional patronymic/father's name
            gender: 'male' or 'female'
            city: Optional city name
            max_usernames: Maximum usernames to return

        Returns:
            List of username variations, most likely first
        """
        all_usernames: Set[str] = set()

        # Transliterate names
        fn = transliterate_simple(first_name)
        ln = transliterate_simple(last_name) if last_name else ''

        # Get diminutives
        diminutives = get_diminutives(first_name)
        if not diminutives:
            diminutives = [fn]

        # Get transliteration variants
        fn_variants = transliterate_variants(first_name, max_variants=4)
        ln_variants = transliterate_variants(last_name, max_variants=4) if last_name else []

        # Surname shortened forms
        sur_short = self._extract_surname_base(ln) if ln else ''

        # Name initial and surname initial
        name_init = fn[0] if fn else ''
        sur_init = ln[0] if ln else ''

        # Keyboard layout conversion
        keyboard_fn = keyboard_layout_convert(first_name)
        keyboard_ln = keyboard_layout_convert(last_name) if last_name else ''

        # === CATEGORY 1: Basic Forms (HIGH PRIORITY) ===
        basic = self._basic_forms(diminutives, fn, fn_variants)
        all_usernames.update(basic)

        # === CATEGORY 2: Name+Surname Combos (HIGH PRIORITY) ===
        if ln:
            combos = self._name_surname_combos(diminutives, ln, sur_short, fn)
            all_usernames.update(combos)

        # === CATEGORY 3: Initial Patterns (HIGH PRIORITY) ===
        if name_init:
            initials = self._initial_patterns(fn, ln, name_init, sur_init, diminutives)
            all_usernames.update(initials)

        # === CATEGORY 4: Year/Number Patterns (MEDIUM PRIORITY) ===
        year_patterns = self._year_patterns(diminutives, fn, ln, sur_short, birth_year)
        all_usernames.update(year_patterns)

        # === CATEGORY 5: Russian Prefixes (MEDIUM PRIORITY) ===
        ru_prefixes = self._russian_prefixes(diminutives[:5], fn)
        all_usernames.update(ru_prefixes)

        # === CATEGORY 6: English Prefixes (MEDIUM PRIORITY) ===
        en_prefixes = self._english_prefixes(diminutives[:5], fn, sur_short)
        all_usernames.update(en_prefixes)

        # === CATEGORY 7: Suffix Patterns (MEDIUM PRIORITY) ===
        suffixes = self._suffix_patterns(diminutives[:5], fn, sur_short)
        all_usernames.update(suffixes)

        # === CATEGORY 8: City/Region (LOW PRIORITY) ===
        if city:
            city_patterns = self._city_patterns(diminutives[:3], fn, city)
            all_usernames.update(city_patterns)
        # Also add default Moscow/SPB patterns
        default_city = self._city_patterns(diminutives[:2], fn, 'moscow')
        all_usernames.update(default_city)
        default_city2 = self._city_patterns(diminutives[:2], fn, 'saint_petersburg')
        all_usernames.update(default_city2)

        # === CATEGORY 9: Gaming Patterns (LOW PRIORITY) ===
        gaming = self._gaming_patterns(diminutives[:3], fn)
        all_usernames.update(gaming)

        # === CATEGORY 10: Doubled Patterns (LOW PRIORITY) ===
        doubled = self._doubled_patterns(diminutives[:4], fn)
        all_usernames.update(doubled)

        # === CATEGORY 11: Leetspeak Patterns (LOW PRIORITY) ===
        leet = self._leetspeak_patterns(diminutives[:3], fn)
        all_usernames.update(leet)

        # === CATEGORY 12: Keyboard Layout (MEDIUM PRIORITY) ===
        if keyboard_fn and keyboard_fn != fn:
            all_usernames.add(keyboard_fn)
            if keyboard_ln:
                all_usernames.add(f"{keyboard_fn}{keyboard_ln}")
                all_usernames.add(f"{keyboard_fn}_{keyboard_ln}")

        # === CATEGORY 13: Reversed Patterns (LOW PRIORITY) ===
        reversed_p = self._reversed_patterns(diminutives[:3], fn, ln)
        all_usernames.update(reversed_p)

        # === CATEGORY 14: Animal/Object Combos (LOW PRIORITY) ===
        animals = self._animal_patterns(diminutives[:2], fn)
        all_usernames.update(animals)

        # === CATEGORY 15: Patronymic Patterns (LOW PRIORITY) ===
        if father_name:
            patron = self._patronymic_patterns(fn, diminutives[:3], father_name, gender)
            all_usernames.update(patron)

        # === CATEGORY 16: Profession Patterns (LOW PRIORITY) ===
        profs = self._profession_patterns(diminutives[:2], fn)
        all_usernames.update(profs)

        # === CATEGORY 17: Special Char Patterns (LOW PRIORITY) ===
        special = self._special_char_patterns(diminutives[:3], fn, ln)
        all_usernames.update(special)

        # Validate, clean, and sort
        valid = []
        for username in all_usernames:
            clean = self._clean_username(username)
            if clean and self._is_valid_username(clean):
                valid.append(clean)

        # Deduplicate preserving order
        seen = set()
        unique = []
        for u in valid:
            if u not in seen:
                seen.add(u)
                unique.append(u)

        # Sort by likelihood
        sorted_usernames = self._sort_by_likelihood(unique, diminutives, fn, ln)

        return sorted_usernames[:max_usernames]

    # === CATEGORY IMPLEMENTATIONS ===

    def _basic_forms(self, diminutives: List[str], fn: str, fn_variants: List[str]) -> Set[str]:
        """Category 1: Basic name forms."""
        result = set()
        # Add all diminutives
        for dim in diminutives:
            result.add(dim)
        # Add formal name
        result.add(fn)
        # Add transliteration variants
        for var in fn_variants:
            result.add(var)
        return result

    def _name_surname_combos(self, diminutives: List[str], surname: str,
                             sur_short: str, fn: str) -> Set[str]:
        """Category 2: Name + Surname combinations."""
        result = set()
        for dim in diminutives[:8]:
            # dim + full surname
            result.add(f"{dim}{surname}")
            result.add(f"{dim}.{surname}")
            result.add(f"{dim}_{surname}")
            # dim + short surname
            if sur_short:
                result.add(f"{dim}{sur_short}")
                result.add(f"{dim}_{sur_short}")
            # surname + dim
            result.add(f"{surname}{dim}")
            result.add(f"{surname}_{dim}")

        # Full firstname + surname
        result.add(f"{fn}{surname}")
        result.add(f"{fn}.{surname}")
        result.add(f"{fn}_{surname}")
        result.add(f"{fn}-{surname}")
        result.add(f"{surname}{fn}")
        result.add(f"{surname}_{fn}")

        # Surname alone
        result.add(surname)
        if sur_short:
            result.add(sur_short)

        return result

    def _initial_patterns(self, fn: str, ln: str, name_init: str,
                          sur_init: str, diminutives: List[str]) -> Set[str]:
        """Category 3: Initial-based patterns."""
        result = set()

        if ln:
            # Initial + surname
            result.add(f"{name_init}{ln}")
            result.add(f"{name_init}.{ln}")
            result.add(f"{name_init}_{ln}")
            result.add(f"{ln}{name_init}")
            result.add(f"{ln}_{name_init}")

            # Both initials
            if sur_init:
                result.add(f"{name_init}{sur_init}")
                result.add(f"{name_init}.{sur_init}")
                result.add(f"{sur_init}{name_init}")

        # Initial + diminutive
        for dim in diminutives[:3]:
            if dim and dim[0] != name_init:
                result.add(f"{name_init}{dim}")
                result.add(f"{name_init}_{dim}")

        return result

    def _year_patterns(self, diminutives: List[str], fn: str, ln: str,
                       sur_short: str, birth_year: Optional[int]) -> Set[str]:
        """Category 4: Year and number patterns."""
        result = set()

        # Determine years to use
        if birth_year:
            year_short = str(birth_year)[-2:]
            year_full = str(birth_year)
            years = [year_short, year_full]
        else:
            # Common birth years (85-10)
            years = ['85', '86', '87', '88', '89', '90', '91', '92', '93', '94',
                     '95', '96', '97', '98', '99', '00', '01', '02', '03', '04',
                     '05', '06', '07', '08', '09', '10']

        bases = diminutives[:5] + [fn]
        if ln:
            bases.append(ln)
        if sur_short:
            bases.append(sur_short)

        for base in bases:
            # Year patterns
            for year in years[:10]:  # Limit years if no birth_year
                result.add(f"{base}{year}")
                result.add(f"{base}_{year}")

            # Number suffixes
            for num in self.NUMBER_SUFFIXES[:15]:
                result.add(f"{base}{num}")

        return result

    def _russian_prefixes(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 5: Russian prefixes."""
        result = set()
        bases = list(diminutives) + [fn]

        for prefix in self.RUSSIAN_PREFIXES:
            for base in bases:
                result.add(f"{prefix}{base}")

        return result

    def _english_prefixes(self, diminutives: List[str], fn: str, sur_short: str) -> Set[str]:
        """Category 6: English prefixes."""
        result = set()
        bases = list(diminutives) + [fn]
        if sur_short:
            bases.append(sur_short)

        for prefix in self.ENGLISH_PREFIXES:
            for base in bases:
                result.add(f"{prefix}{base}")

        return result

    def _suffix_patterns(self, diminutives: List[str], fn: str, sur_short: str) -> Set[str]:
        """Category 7: Suffix patterns."""
        result = set()
        bases = list(diminutives) + [fn]
        if sur_short:
            bases.append(sur_short)

        for base in bases:
            for suffix in self.SUFFIXES:
                result.add(f"{base}{suffix}")

        return result

    def _city_patterns(self, diminutives: List[str], fn: str, city: str) -> Set[str]:
        """Category 8: City/region patterns."""
        result = set()
        city_lower = city.lower().replace(' ', '_').replace('-', '_')

        # Find city codes
        codes = []
        for city_key, city_codes in self.CITY_CODES.items():
            if city_lower in city_key or city_key in city_lower:
                codes.extend(city_codes)
                break

        if not codes:
            codes = [city_lower[:3]]  # Use first 3 chars

        bases = list(diminutives) + [fn]
        for base in bases:
            for code in codes[:4]:  # Limit codes
                result.add(f"{code}_{base}")
                result.add(f"{code}{base}")
                result.add(f"{base}_{code}")
                result.add(f"{base}{code}")

        return result

    def _gaming_patterns(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 9: Gaming culture patterns."""
        result = set()
        bases = list(diminutives) + [fn]

        for base in bases:
            # Gaming prefixes
            for prefix in self.GAMING_PREFIXES[:15]:
                result.add(f"{prefix}{base}")
                result.add(f"{prefix}_{base}")
                result.add(f"{base}{prefix}")

            # Gaming suffixes
            for suffix in self.GAMING_SUFFIXES:
                result.add(f"{base}{suffix}")
                result.add(f"{base}_{suffix}")

        return result

    def _doubled_patterns(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 10: Doubled/repeated patterns."""
        result = set()
        bases = list(diminutives) + [fn]

        for base in bases:
            if len(base) >= 3:
                # Double the name
                result.add(f"{base}{base}")
                result.add(f"{base}_{base}")
                result.add(f"{base}.{base}")
                # Double last letter
                result.add(f"{base}{base[-1]}")
                result.add(f"{base}{base[-1]}{base[-1]}")
                # Triple pattern
                if len(base) <= 5:
                    result.add(f"{base}{base}{base}")

        return result

    def _leetspeak_patterns(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 11: Leetspeak substitutions."""
        result = set()
        bases = list(diminutives)[:3] + [fn]

        for base in bases:
            # Apply leet substitutions
            for char, replacements in self.LEET_MAP.items():
                if char in base:
                    for repl in replacements[:1]:  # Just first replacement
                        leet_name = base.replace(char, repl)
                        if leet_name != base:
                            result.add(leet_name)

        return result

    def _reversed_patterns(self, diminutives: List[str], fn: str, ln: str) -> Set[str]:
        """Category 13: Reversed name patterns."""
        result = set()
        bases = list(diminutives) + [fn]
        if ln:
            bases.append(ln)

        for base in bases:
            if len(base) >= 4:
                reversed_name = base[::-1]
                result.add(reversed_name)
                result.add(f"{reversed_name}_{base}")

        return result

    def _animal_patterns(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 14: Animal/nature word patterns."""
        result = set()
        bases = list(diminutives) + [fn]

        for base in bases:
            for animal in self.ANIMAL_WORDS[:10]:
                result.add(f"{base}_{animal}")
                result.add(f"{animal}_{base}")
                result.add(f"{base}{animal}")

        return result

    def _patronymic_patterns(self, fn: str, diminutives: List[str],
                             father_name: str, gender: str) -> Set[str]:
        """Category 15: Patronymic patterns."""
        result = set()

        father_translit = transliterate_simple(father_name)
        # Create patronymic suffix
        if gender == 'male':
            patronymic = f"{father_translit}ovich"
        else:
            patronymic = f"{father_translit}ovna"

        bases = list(diminutives)[:3] + [fn]
        for base in bases:
            result.add(f"{base}{patronymic}")
            result.add(f"{base}_{patronymic}")

        return result

    def _profession_patterns(self, diminutives: List[str], fn: str) -> Set[str]:
        """Category 16: Profession-related patterns."""
        result = set()
        bases = list(diminutives) + [fn]

        for base in bases:
            for prof in self.PROFESSION_PREFIXES[:10]:
                result.add(f"{prof}_{base}")
                result.add(f"{base}_{prof}")
                result.add(f"{prof}{base}")

        return result

    def _special_char_patterns(self, diminutives: List[str], fn: str, ln: str) -> Set[str]:
        """Category 17: Special character placement patterns."""
        result = set()
        bases = list(diminutives) + [fn]

        for base in bases:
            # Leading/trailing underscores (some platforms allow)
            result.add(f"_{base}")
            result.add(f"{base}_")
            result.add(f"__{base}")
            result.add(f"{base}__")

            # Dot patterns
            result.add(f".{base}")
            result.add(f"{base}.")

            if ln:
                # Various separators
                result.add(f"{base}..{ln}")
                result.add(f"{base}___{ln}")

        return result

    # === UTILITY METHODS ===

    def _extract_surname_base(self, surname: str) -> str:
        """Extract base from Russian surname by removing common suffixes."""
        if not surname or len(surname) < 4:
            return surname

        surname_lower = surname.lower()
        suffixes = [
            'nikov', 'ovsky', 'evsky', 'insky', 'evich', 'ovich',
            'enko', 'chuk', 'yuk', 'iuk',
            'kov', 'kow', 'skiy', 'sky', 'ski', 'skii',
            'yev', 'iev', 'aev', 'oev',
            'ev', 'ov', 'in', 'yn', 'uk'
        ]

        for suffix in suffixes:
            if surname_lower.endswith(suffix) and len(surname_lower) > len(suffix) + 2:
                return surname_lower[:-len(suffix)]

        return surname_lower

    def _clean_username(self, username: str) -> str:
        """Clean and normalize username."""
        if not username:
            return ''
        # Remove invalid characters, keep only alphanumeric and . _ -
        username = re.sub(r'[^a-zA-Z0-9._-]', '', username.lower())
        # Remove leading/trailing separators
        username = username.strip('._-')
        # Collapse multiple separators to single
        username = re.sub(r'[._-]{2,}', '_', username)
        return username

    def _is_valid_username(self, username: str) -> bool:
        """Validate username for VK/OK/Telegram compatibility."""
        if not username:
            return False

        # Length check (3-32 chars)
        if len(username) < 3 or len(username) > 32:
            return False

        # Must start with letter
        if not username[0].isalpha():
            return False

        # No 3+ consecutive identical letters (allow digits like 777)
        if re.search(r'([a-z])\1{2,}', username):
            return False

        # Only allowed characters
        if not re.match(r'^[a-z0-9._-]+$', username):
            return False

        return True

    def _sort_by_likelihood(self, usernames: List[str], diminutives: List[str],
                            fn: str, ln: str) -> List[str]:
        """Sort usernames by likelihood of being real."""
        def score(username: str) -> int:
            s = 0

            # High priority: plain diminutive
            if username in diminutives:
                s += 100

            # High priority: first 3 diminutives
            if username in diminutives[:3]:
                s += 50

            # Medium priority: contains diminutive
            for dim in diminutives[:5]:
                if dim in username:
                    s += 20
                    break

            # Medium priority: short names (4-10 chars optimal)
            if 4 <= len(username) <= 10:
                s += 15
            elif len(username) <= 15:
                s += 5

            # Medium priority: name+year pattern
            if re.search(r'\d{2}$', username):
                s += 10

            # Low priority: gaming patterns
            for gaming in self.GAMING_PREFIXES[:10]:
                if gaming in username:
                    s -= 10
                    break

            # Penalty: excessive underscores
            if username.count('_') > 2:
                s -= 15

            # Penalty: very long
            if len(username) > 20:
                s -= 10

            return s

        return sorted(usernames, key=score, reverse=True)

    # === BACKWARD COMPATIBILITY ===

    def generate_usernames(self, name: str, max_results: int = 100,
                           birth_year: Optional[int] = None) -> List[str]:
        """
        Alias for combined_search.py compatibility.

        Parses full name and calls generate_all_usernames.
        """
        # Parse name - handle CamelCase
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        name = re.sub(r'([а-яё])([А-ЯЁ])', r'\1 \2', name)

        parts = name.strip().split()
        if not parts:
            return []

        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''

        return self.generate_all_usernames(
            first_name=first_name,
            last_name=last_name,
            birth_year=birth_year,
            max_usernames=max_results
        )

    def generate(self, full_name: str, birth_year: Optional[int] = None,
                 max_results: Optional[int] = None) -> List[str]:
        """Another alias for compatibility."""
        return self.generate_usernames(
            full_name,
            max_results=max_results or self.max_results,
            birth_year=birth_year
        )


# =============================================================================
# LEGACY COMPATIBILITY - SmartUsernameGenerator alias
# =============================================================================

# Alias for backward compatibility
SmartUsernameGenerator = UltimateUsernameGenerator


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_usernames(full_name: str,
                       birth_year: Optional[int] = None,
                       max_results: int = 100) -> List[str]:
    """
    Generate username variations from a name.

    Args:
        full_name: Name in Russian or Latin
        birth_year: Optional birth year
        max_results: Maximum usernames to generate

    Returns:
        List of username variations
    """
    generator = UltimateUsernameGenerator(max_results=max_results)
    return generator.generate_usernames(full_name, max_results=max_results, birth_year=birth_year)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Ultimate Username Generator v3.0 Test")
    print("=" * 60)

    # Test 1: Pavel Durov (no birth year)
    print("\nTest 1: Павел Дуров (no birth year)")
    print("-" * 40)
    usernames = generate_usernames("Павел Дуров", max_results=50)
    print(f"Generated {len(usernames)} usernames")
    for i, u in enumerate(usernames[:20], 1):
        print(f"  {i:2}. {u}")

    # Test 2: With birth year
    print("\nTest 2: Дмитрий Медведев (birth year 1965)")
    print("-" * 40)
    usernames = generate_usernames("Дмитрий Медведев", birth_year=1965, max_results=50)
    print(f"Generated {len(usernames)} usernames")
    for i, u in enumerate(usernames[:20], 1):
        print(f"  {i:2}. {u}")

    # Test 3: Female name
    print("\nTest 3: Екатерина Иванова")
    print("-" * 40)
    usernames = generate_usernames("Екатерина Иванова", max_results=30)
    print(f"Generated {len(usernames)} usernames")
    for i, u in enumerate(usernames[:15], 1):
        print(f"  {i:2}. {u}")

    # Test 4: Verify specific patterns exist
    print("\nTest 4: Pattern verification for 'Павел Дуров'")
    print("-" * 40)
    usernames = generate_usernames("Павел Дуров", max_results=200)
    checks = [
        ('durov', 'durov' in usernames),
        ('pasha', 'pasha' in usernames),
        ('ya_pasha', 'ya_pasha' in usernames),
        ('any year pattern', any('90' in u or '95' in u for u in usernames)),
        ('eto prefix', any(u.startswith('eto') for u in usernames)),
    ]
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")

    print(f"\nTotal unique usernames: {len(usernames)}")

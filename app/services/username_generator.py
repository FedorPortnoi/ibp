"""
Russian Username Generator with Comprehensive Diminutives
==========================================================
Generates realistic username variations for Russian names.

CRITICAL: Russians RARELY use formal names online. They use diminutives!
- Александр → Саша, Шура, Саня, Санёк
- Екатерина → Катя, Катюша, Катенька
- Дмитрий → Дима, Димон, Митя, Димка

This generator PRIORITIZES DIMINUTIVES because that's what Russians actually use.

Features:
- 100+ Russian diminutives (8+ variants per name)
- Multi-variant transliteration (Ё→e/yo/jo, Ж→zh/j, etc.)
- Smart name combination patterns
- Birth year only when provided
- Cyrillic storage for VK/OK compatibility

Author: IBP Project
Version: 2.0
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
# COMPREHENSIVE RUSSIAN DIMINUTIVES DATABASE
# =============================================================================
# CRITICAL: Russians RARELY use formal names online. They use diminutives!
# This database contains 8+ variations per name - the forms people ACTUALLY use.

# Male diminutives (Cyrillic) - will be transliterated automatically
MALE_DIMINUTIVES_CYR = {
    "Александр": ["Саша", "Шура", "Саня", "Санёк", "Алекс", "Санька", "Шурик", "Сашка"],
    "Алексей": ["Лёша", "Лёха", "Алёша", "Лёшка", "Лёшик"],
    "Анатолий": ["Толя", "Толик", "Толян", "Толька"],
    "Андрей": ["Андрюша", "Андрюха", "Дрон", "Дюша", "Андрюшка"],
    "Антон": ["Тоша", "Тоха", "Антоха", "Антошка"],
    "Артём": ["Тёма", "Артёмка", "Тёмка", "Артёмчик", "Тёмыч"],
    "Богдан": ["Богдаша", "Бодя", "Даня", "Дан"],
    "Борис": ["Боря", "Борька", "Борян"],
    "Вадим": ["Вадик", "Вадя", "Вадимка"],
    "Валерий": ["Валера", "Валерка", "Лера", "Валерон"],
    "Василий": ["Вася", "Васька", "Василёк", "Васёк", "Васян"],
    "Виктор": ["Витя", "Витёк", "Витька"],
    "Виталий": ["Виталик", "Виталя", "Витас"],
    "Владимир": ["Вова", "Володя", "Вовка", "Вовчик", "Влад", "Вован"],
    "Владислав": ["Влад", "Владик", "Слава", "Славик"],
    "Вячеслав": ["Слава", "Славик", "Славка", "Славян"],
    "Геннадий": ["Гена", "Генка", "Геша"],
    "Георгий": ["Гоша", "Жора", "Гошка", "Жорик"],
    "Глеб": ["Глебушка", "Глебка", "Глебчик"],
    "Григорий": ["Гриша", "Гриня", "Гришка"],
    "Даниил": ["Даня", "Данила", "Данька", "Дан", "Данил"],
    "Денис": ["Дэн", "Дениска", "Денчик", "Ден"],
    "Дмитрий": ["Дима", "Димон", "Митя", "Димка", "Димыч", "Митяй", "Димас"],
    "Евгений": ["Женя", "Женёк", "Жека", "Женька", "Евген"],
    "Егор": ["Егорка", "Егорушка", "Гора", "Егорыч"],
    "Иван": ["Ваня", "Ванёк", "Ванька", "Ванюша", "Ванёс"],
    "Игорь": ["Игорёк", "Игорёха", "Гоша", "Гарик"],
    "Илья": ["Илюша", "Илюха", "Илюшка"],
    "Кирилл": ["Кирюша", "Кирюха", "Киря", "Кир"],
    "Константин": ["Костя", "Костик", "Костян", "Костюша"],
    "Леонид": ["Лёня", "Лёнька", "Лёнчик"],
    "Максим": ["Макс", "Максик", "Максимка", "Максон"],
    "Марк": ["Маркуша", "Марик"],
    "Матвей": ["Мотя", "Матвейка", "Матюша"],
    "Михаил": ["Миша", "Мишка", "Мишаня", "Михан", "Мишутка"],
    "Никита": ["Никитка", "Никитос", "Ник", "Кит"],
    "Николай": ["Коля", "Колян", "Николаша", "Колька", "Ник"],
    "Олег": ["Олежка", "Олежек", "Лёжик"],
    "Павел": ["Паша", "Пашка", "Павлик", "Пашок", "Паха"],
    "Пётр": ["Петя", "Петька", "Петруша", "Петруха"],
    "Роман": ["Рома", "Ромка", "Ромчик", "Ромыч", "Ромаха"],
    "Руслан": ["Русик", "Руся", "Рус"],
    "Сергей": ["Серёжа", "Серёга", "Серж", "Серый", "Серёжка", "Серго"],
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
    "Александра": ["Саша", "Сашка", "Шура", "Саня", "Сашуля", "Алекса"],
    "Алина": ["Аля", "Алинка", "Лина"],
    "Алиса": ["Алиска", "Аля", "Лиса"],
    "Анастасия": ["Настя", "Настёна", "Ася", "Настюша", "Стася", "Настюха"],
    "Ангелина": ["Геля", "Лина", "Энжи"],
    "Анна": ["Аня", "Анюта", "Нюра", "Аннушка", "Анька", "Нюша"],
    "Арина": ["Аринка", "Ариша", "Рина"],
    "Валентина": ["Валя", "Валюша", "Валечка"],
    "Валерия": ["Лера", "Лерка", "Валерка", "Валери"],
    "Варвара": ["Варя", "Варька", "Вава"],
    "Вера": ["Верочка", "Верка", "Веруня"],
    "Вероника": ["Ника", "Вера", "Рони"],
    "Виктория": ["Вика", "Викуся", "Викуля", "Вики", "Тори"],
    "Галина": ["Галя", "Галка", "Галочка"],
    "Дарья": ["Даша", "Дашка", "Дашуля", "Дашенька", "Дашуня"],
    "Диана": ["Ди", "Дианка"],
    "Ева": ["Евочка", "Евуся"],
    "Евгения": ["Женя", "Женечка", "Женька", "Геня"],
    "Екатерина": ["Катя", "Катюша", "Катенька", "Катька", "Кэт", "Катюня", "Катюха"],
    "Елена": ["Лена", "Леночка", "Ленка", "Алёна", "Леся", "Ленуся"],
    "Елизавета": ["Лиза", "Лизка", "Лизонька", "Лизочка", "Элиза"],
    "Инна": ["Инночка", "Инка", "Ина"],
    "Ирина": ["Ира", "Иришка", "Ирочка", "Ируся", "Ирка", "Ируня"],
    "Карина": ["Каринка", "Кара", "Каря"],
    "Кристина": ["Кристя", "Кристинка", "Крис", "Тина"],
    "Ксения": ["Ксюша", "Ксюха", "Ксеня", "Ксю", "Ксюня"],
    "Лариса": ["Лара", "Лариска", "Ларочка"],
    "Любовь": ["Люба", "Любаша", "Любочка", "Люся"],
    "Людмила": ["Люда", "Людочка", "Мила", "Люся"],
    "Маргарита": ["Рита", "Марго", "Ритка", "Маргоша"],
    "Марина": ["Маринка", "Мариша", "Мара", "Маруся"],
    "Мария": ["Маша", "Машка", "Маруся", "Машуня", "Маня", "Мари"],
    "Милана": ["Мила", "Миланка", "Милаша", "Лана"],
    "Надежда": ["Надя", "Надюша", "Наденька", "Надюха"],
    "Наталья": ["Наташа", "Ната", "Наталка", "Наташка", "Натали", "Натуся"],
    "Нина": ["Ниночка", "Нинуля", "Нинка"],
    "Оксана": ["Ксана", "Оксанка", "Ксюша"],
    "Ольга": ["Оля", "Олечка", "Олька", "Оленька", "Лёля"],
    "Полина": ["Поля", "Полинка", "Полюшка", "Полечка", "Полли"],
    "Светлана": ["Света", "Светик", "Светочка", "Светка", "Лана"],
    "София": ["Соня", "Софа", "Софочка", "Софи", "Сонька"],
    "Тамара": ["Тома", "Томочка", "Тамарка"],
    "Татьяна": ["Таня", "Танюша", "Танечка", "Танюшка", "Танька", "Тата"],
    "Юлия": ["Юля", "Юлька", "Юленька", "Юляша", "Джули"],
    "Яна": ["Янка", "Яночка", "Януся"],
}

# Combined dictionary with pre-transliterated values for fast lookup
# Format: 'canonical_name': ['diminutive1', 'diminutive2', ...]
RUSSIAN_DIMINUTIVES = {
    # Male names (transliterated)
    'александр': ['sasha', 'shura', 'sanya', 'sanek', 'alex', 'sanka', 'shurik', 'sashka'],
    'алексей': ['lyosha', 'lyokha', 'alyosha', 'lyoshka', 'lyoshik', 'lesha', 'lekha'],
    'анатолий': ['tolya', 'tolik', 'tolyan', 'tolka'],
    'андрей': ['andryusha', 'andryukha', 'dron', 'dyusha', 'andryushka', 'andrey'],
    'антон': ['tosha', 'tokha', 'antokha', 'antoshka', 'anton'],
    'артём': ['tyoma', 'artyomka', 'tyomka', 'artyomchik', 'tyomych', 'tema', 'artem'],
    'богдан': ['bogdasha', 'bodya', 'danya', 'dan'],
    'борис': ['borya', 'borka', 'boryan', 'boris'],
    'вадим': ['vadik', 'vadya', 'vadimka', 'vadim'],
    'валерий': ['valera', 'valerka', 'lera', 'valeron', 'valery'],
    'василий': ['vasya', 'vaska', 'vasilyok', 'vasyok', 'vasyan', 'vasily'],
    'виктор': ['vitya', 'vityok', 'vitka', 'viktor', 'victor'],
    'виталий': ['vitalik', 'vitalya', 'vitas', 'vitaly'],
    'владимир': ['vova', 'volodya', 'vovka', 'vovchik', 'vlad', 'vovan', 'vladimir'],
    'владислав': ['vlad', 'vladik', 'slava', 'slavik', 'vladislav'],
    'вячеслав': ['slava', 'slavik', 'slavka', 'slavyan', 'vyacheslav'],
    'геннадий': ['gena', 'genka', 'gesha', 'gennady'],
    'георгий': ['gosha', 'zhora', 'goshka', 'zhorik', 'georgy', 'george'],
    'глеб': ['glebushka', 'glebka', 'glebchik', 'gleb'],
    'григорий': ['grisha', 'grinya', 'grishka', 'grigory', 'greg'],
    'даниил': ['danya', 'danila', 'danka', 'dan', 'danil', 'daniel'],
    'денис': ['den', 'deniska', 'denchik', 'denis'],
    'дмитрий': ['dima', 'dimon', 'mitya', 'dimka', 'dimych', 'mityay', 'dimas', 'dmitry', 'dmitri'],
    'евгений': ['zhenya', 'zhenyok', 'zheka', 'zhenka', 'evgen', 'evgeny', 'eugene'],
    'егор': ['egorka', 'egorushka', 'gora', 'egorych', 'egor', 'yegor'],
    'иван': ['vanya', 'vanyok', 'vanka', 'vanyusha', 'vanyos', 'ivan'],
    'игорь': ['igoryok', 'igoryokha', 'gosha', 'garik', 'igor'],
    'илья': ['ilyusha', 'ilyukha', 'ilyushka', 'ilya'],
    'кирилл': ['kiryusha', 'kiryukha', 'kirya', 'kir', 'kirill', 'cyril'],
    'константин': ['kostya', 'kostik', 'kostyan', 'kostyusha', 'konstantin', 'kos'],
    'леонид': ['lyonya', 'lyonka', 'lyonchik', 'leonid', 'leo'],
    'максим': ['maks', 'maksik', 'maksimka', 'makson', 'max', 'maxim'],
    'марк': ['markusha', 'marik', 'mark'],
    'матвей': ['motya', 'matveyka', 'matyusha', 'matvey'],
    'михаил': ['misha', 'mishka', 'mishanya', 'mikhan', 'mishutka', 'mikhail', 'michael', 'miha'],
    'никита': ['nikitka', 'nikitos', 'nik', 'kit', 'nikita'],
    'николай': ['kolya', 'kolyan', 'nikolasha', 'kolka', 'nik', 'nikolay', 'nick'],
    'олег': ['olezhka', 'olezhek', 'lyozhik', 'oleg'],
    'павел': ['pasha', 'pashka', 'pavlik', 'pashok', 'pakha', 'pavel', 'paul'],
    'пётр': ['petya', 'petka', 'petrusha', 'petrukha', 'petr', 'peter', 'pyotr'],
    'роман': ['roma', 'romka', 'romchik', 'romych', 'romakha', 'roman'],
    'руслан': ['rusik', 'rusya', 'rus', 'ruslan'],
    'сергей': ['seryozha', 'seryoga', 'serzh', 'seryy', 'seryozhka', 'sergo', 'sergey', 'sergei', 'serge'],
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
    'александра': ['sasha', 'sashka', 'shura', 'sanya', 'sashulya', 'aleksa', 'alexandra'],
    'алина': ['alya', 'alinka', 'lina', 'alina'],
    'алиса': ['aliska', 'alya', 'lisa', 'alisa', 'alice'],
    'анастасия': ['nastya', 'nastyona', 'asya', 'nastyusha', 'stasya', 'nastyukha', 'anastasia'],
    'ангелина': ['gelya', 'lina', 'anzhi', 'angelina'],
    'анна': ['anya', 'anyuta', 'nyura', 'annushka', 'anka', 'nyusha', 'anna', 'ann'],
    'арина': ['arinka', 'arisha', 'rina', 'arina'],
    'валентина': ['valya', 'valyusha', 'valechka', 'valentina'],
    'валерия': ['lera', 'lerka', 'valerka', 'valeri', 'valeriya', 'valeria'],
    'варвара': ['varya', 'varka', 'vava', 'varvara', 'barbara'],
    'вера': ['verochka', 'verka', 'verunya', 'vera'],
    'вероника': ['nika', 'vera', 'roni', 'veronika', 'veronica'],
    'виктория': ['vika', 'vikusya', 'vikulya', 'viki', 'tori', 'viktoriya', 'victoria'],
    'галина': ['galya', 'galka', 'galochka', 'galina'],
    'дарья': ['dasha', 'dashka', 'dashulya', 'dashenka', 'dashunya', 'darya', 'daria'],
    'диана': ['di', 'dianka', 'diana'],
    'ева': ['evochka', 'evusya', 'eva', 'eve'],
    'евгения': ['zhenya', 'zhenechka', 'zhenka', 'genya', 'evgeniya', 'eugenia'],
    'екатерина': ['katya', 'katyusha', 'katenka', 'katka', 'ket', 'katyunya', 'katyukha', 'ekaterina', 'kate', 'catherine'],
    'елена': ['lena', 'lenochka', 'lenka', 'alyona', 'lesya', 'lenusya', 'elena', 'helen'],
    'елизавета': ['liza', 'lizka', 'lizonka', 'lizochka', 'eliza', 'elizaveta', 'elizabeth'],
    'инна': ['innochka', 'inka', 'ina', 'inna'],
    'ирина': ['ira', 'irishka', 'irochka', 'irusya', 'irka', 'irunya', 'irina'],
    'карина': ['karinka', 'kara', 'karya', 'karina'],
    'кристина': ['kristya', 'kristinka', 'kris', 'tina', 'kristina', 'christina'],
    'ксения': ['ksyusha', 'ksyukha', 'ksenya', 'ksyu', 'ksyunya', 'ksenia', 'kseniya'],
    'лариса': ['lara', 'lariska', 'larochka', 'larisa'],
    'любовь': ['lyuba', 'lyubasha', 'lyubochka', 'lyusya', 'lubov'],
    'людмила': ['lyuda', 'lyudochka', 'mila', 'lyusya', 'lyudmila'],
    'маргарита': ['rita', 'margo', 'ritka', 'margosha', 'margarita'],
    'марина': ['marinka', 'marisha', 'mara', 'marusya', 'marina'],
    'мария': ['masha', 'mashka', 'marusya', 'mashunya', 'manya', 'mari', 'maria', 'mary'],
    'милана': ['mila', 'milanka', 'milasha', 'lana', 'milana'],
    'надежда': ['nadya', 'nadyusha', 'nadenka', 'nadyukha', 'nadezhda'],
    'наталья': ['natasha', 'nata', 'natalka', 'natashka', 'natali', 'natusya', 'natalya', 'natalia'],
    'нина': ['ninochka', 'ninulya', 'ninka', 'nina'],
    'оксана': ['ksana', 'oksanka', 'ksyusha', 'oksana'],
    'ольга': ['olya', 'olechka', 'olka', 'olenka', 'lyolya', 'olga'],
    'полина': ['polya', 'polinka', 'polyushka', 'polechka', 'polli', 'polina'],
    'светлана': ['sveta', 'svetik', 'svetochka', 'svetka', 'lana', 'svetlana'],
    'софия': ['sonya', 'sofa', 'sofochka', 'sofi', 'sonka', 'sofya', 'sofia', 'sophia'],
    'тамара': ['toma', 'tomochka', 'tamarka', 'tamara'],
    'татьяна': ['tanya', 'tanyusha', 'tanechka', 'tanyushka', 'tanka', 'tata', 'tatyana', 'tatiana'],
    'юлия': ['yulya', 'yulka', 'yulenka', 'yulyasha', 'dzhuli', 'julia', 'yulia'],
    'яна': ['yanka', 'yanochka', 'yanusya', 'yana'],
}


def get_diminutives(name: str) -> List[str]:
    """
    Get diminutives for a Russian name.

    Handles:
    - Cyrillic input (Дмитрий)
    - Latin input (Dmitry, Dmitri, Dima)
    - Common aliases and diminutives as input
    """
    name_lower = name.lower().strip()

    # Handle ё/е variations
    name_variants = [name_lower, name_lower.replace('ё', 'е'), name_lower.replace('е', 'ё')]

    # Direct lookup in main dictionary
    for variant in name_variants:
        if variant in RUSSIAN_DIMINUTIVES:
            return RUSSIAN_DIMINUTIVES[variant]

    # Check Cyrillic dictionaries (for Title case input like "Дмитрий")
    name_title = name.strip().title()
    name_title_variants = [name_title, name_title.replace('ё', 'е'), name_title.replace('е', 'ё'),
                          name_title.replace('Ё', 'Е'), name_title.replace('Е', 'Ё')]

    for variant in name_title_variants:
        if variant in MALE_DIMINUTIVES_CYR:
            # Return transliterated versions
            return [transliterate_simple(d) for d in MALE_DIMINUTIVES_CYR[variant]]
        if variant in FEMALE_DIMINUTIVES_CYR:
            return [transliterate_simple(d) for d in FEMALE_DIMINUTIVES_CYR[variant]]

    # Extended Latin name aliases (common English/Latin spellings)
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

        # Male - common diminutives as input (find the formal name)
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
# SURNAME NICKNAME EXTRACTION
# =============================================================================

def extract_surname_nicknames(surname: str) -> List[str]:
    """
    Extract nickname from Russian surname by removing common suffixes.

    CRITICAL for finding usernames like @etoglaz from "Glazkov"

    Examples:
        Glazkov → Glaz (remove -kov)
        Ivanov → Ivan (remove -ov)
        Smirnov → Smirn (remove -ov)
        Kozlov → Kozl/Kozlik (remove -ov, add diminutive)

    Then adds common Russian username prefixes:
        Glaz → etoglaz, yaglaz, theglaz, etc.
    """
    nicknames = []

    # Transliterate if Cyrillic
    is_cyrillic = any('\u0400' <= c <= '\u04FF' for c in surname)
    surname_lower = transliterate_simple(surname).lower() if is_cyrillic else surname.lower()

    # Full surname alone is also a username pattern
    nicknames.append(surname_lower)

    # Russian surname suffixes in order of length (longer first!)
    suffixes = [
        'nikov', 'ovsky', 'evsky', 'insky', 'evich', 'ovich',
        'enko', 'chuk', 'yuk', 'iuk',
        'kov', 'kow', 'skiy', 'sky', 'ski', 'skii',
        'yev', 'iev', 'aev', 'oev',
        'ev', 'ov', 'in', 'yn', 'uk'
    ]

    base = None
    for suffix in suffixes:
        if surname_lower.endswith(suffix) and len(surname_lower) > len(suffix) + 2:
            base = surname_lower[:-len(suffix)]
            break

    if not base or len(base) < 3:
        # Try just the surname with prefixes
        base = surname_lower

    # Core nickname (the base extracted from surname)
    if base != surname_lower:
        nicknames.append(base)

    # Common Russian username prefixes (это, я, i'm, the, etc.)
    prefixes = [
        'eto', 'eto_', 'eto.',      # это (this is)
        'ya', 'ya_', 'ia', 'ia_',   # я (I am)
        'im', 'im_', 'i_am_',       # I'm
        'the', 'the_',              # the
        'its', 'its_', 'it_',       # it's
        'just', 'just_',            # just
        'real', 'real_',            # real
        'only', 'only_',            # only
        'x', 'xx', 'xxx',           # x prefix
        'mr', 'mr_', 'mr.',         # mr
        'not', 'not_',              # not
    ]

    for prefix in prefixes:
        nicknames.append(f"{prefix}{base}")

    # Diminutive/augmentative suffixes
    diminutive_suffixes = [
        'ok', 'ik', 'chik', 'ek', 'ka', 'ko',
        'yan', 'an', 'us', 'os', 'as',
        '_official', '_real', '_original',
        '228', '666', '777', '13',  # Common number suffixes
    ]

    for suf in diminutive_suffixes:
        nicknames.append(f"{base}{suf}")

    # Double last letter (common pattern: glaz -> glazz)
    if base and len(base) >= 3:
        nicknames.append(f"{base}{base[-1]}")
        nicknames.append(f"{base}{base[-1]}{base[-1]}")

    # With birth years (young person likely born 2000-2010)
    for year in ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                 '2000', '2001', '2002', '2003', '2004', '2005', '2006']:
        nicknames.append(f"{base}{year}")
        nicknames.append(f"eto{base}{year}")

    # Prefixed base with years
    for prefix in ['eto', 'ya', 'the', 'im']:
        for year in ['05', '06', '07']:
            nicknames.append(f"{prefix}{base}{year}")

    return nicknames


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

        # === PRIORITY 0: Surname nicknames (CRITICAL for finding @etoglaz style usernames) ===
        if ln:
            surname_nicks = extract_surname_nicknames(ln)
            for nick in surname_nicks:
                usernames.append(nick)

        # === PRIORITY 1: Diminutive alone (HIGHEST PRIORITY - what Russians actually use!) ===
        for dim in diminutives[:8]:  # Top 8 diminutives
            usernames.append(dim)

        # === PRIORITY 2: Diminutive + lastname ===
        if ln:
            for dim in diminutives[:6]:  # More diminutive+lastname combos
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

            # Prioritize diminutives with years (most realistic!)
            base_names = diminutives[:5] + [fn]
            if ln:
                base_names.extend([f"{dim}{ln}" for dim in diminutives[:3]])
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

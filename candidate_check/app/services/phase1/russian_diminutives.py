"""
Russian Diminutive Name Dictionary
===================================
Maps formal Russian first names to common diminutives used on social media.
Supports forward lookup (formal -> diminutives) and reverse lookup (diminutive -> formal).

Usage:
    from app.services.phase1.russian_diminutives import get_all_name_variants, get_formal_name

    variants = get_all_name_variants("Тихон")
    # Returns: ["Тихон", "Тиша", "Тишка", "Тишок", "Тиханя"]

    formal = get_formal_name("Саша")
    # Returns: ["Александр", "Александра"]
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Diminutive Dictionary ──────────────────────────────────────────

DIMINUTIVES = {
    # Male names
    "Тихон": ["Тиша", "Тишка", "Тишок", "Тиханя"],
    "Александр": ["Саша", "Сашка", "Шура", "Шурик", "Алекс", "Санёк", "Сашуля"],
    "Алексей": ["Лёша", "Лёшка", "Алёша", "Лёха", "Лёшенька"],
    "Андрей": ["Андрюша", "Андрюха", "Дрон"],
    "Артём": ["Тёма", "Тёмка", "Артёмка"],
    "Борис": ["Боря", "Борька"],
    "Вадим": ["Вадик", "Вадимка", "Вадя"],
    "Валерий": ["Валера", "Валерка"],
    "Василий": ["Вася", "Васька", "Василёк"],
    "Виктор": ["Витя", "Витёк", "Витька"],
    "Виталий": ["Виталик", "Витя"],
    "Владимир": ["Вова", "Вовка", "Володя", "Влад", "Вовочка"],
    "Владислав": ["Влад", "Владик", "Слава"],
    "Вячеслав": ["Слава", "Славик", "Славка"],
    "Георгий": ["Жора", "Гоша", "Гога", "Гера"],
    "Григорий": ["Гриша", "Гришка", "Гриня"],
    "Даниил": ["Даня", "Данила", "Данька", "Данёк", "Дэн"],
    "Денис": ["Дэн", "Денисёк", "Дениска"],
    "Дмитрий": ["Дима", "Димка", "Митя", "Митёк", "Димон"],
    "Евгений": ["Женя", "Женёк", "Жека"],
    "Егор": ["Егорка", "Гоша"],
    "Иван": ["Ваня", "Ванька", "Ванёк", "Ванюша"],
    "Игорь": ["Игорёк", "Игорёха", "Гоша"],
    "Илья": ["Илюша", "Илюха", "Илюшка"],
    "Кирилл": ["Кирюша", "Кирюха", "Кир"],
    "Константин": ["Костя", "Костик", "Костян"],
    "Лев": ["Лёва", "Лёвка"],
    "Максим": ["Макс", "Максик", "Максимка"],
    "Матвей": ["Мотя"],
    "Михаил": ["Миша", "Мишка", "Михась", "Мишаня"],
    "Никита": ["Никитка", "Ник", "Никитос"],
    "Николай": ["Коля", "Колян", "Колька", "Николаша"],
    "Олег": ["Олежка", "Олежек"],
    "Павел": ["Паша", "Пашка", "Павлик", "Пашок"],
    "Пётр": ["Петя", "Петька", "Петруха"],
    "Роман": ["Рома", "Ромка", "Ромыч", "Ромчик"],
    "Руслан": ["Русик", "Рус"],
    "Сергей": ["Серёжа", "Серёга", "Серж", "Серёжка"],
    "Степан": ["Стёпа", "Стёпка"],
    "Тимофей": ["Тима", "Тимоха", "Тимоша"],
    "Фёдор": ["Федя", "Федька", "Федюня"],
    "Филипп": ["Филя", "Филипок"],
    "Юрий": ["Юра", "Юрка", "Юрик"],
    "Ярослав": ["Ярик", "Славик", "Слава"],

    # Female names
    "Александра": ["Саша", "Сашка", "Шура", "Шурочка", "Сашуля"],
    "Алина": ["Аля", "Алинка"],
    "Анастасия": ["Настя", "Настенька", "Настюша", "Ася"],
    "Анна": ["Аня", "Анечка", "Анюта", "Нюра", "Нюша"],
    "Ангелина": ["Геля", "Лина", "Ангел"],
    "Валентина": ["Валя", "Валечка", "Валюша"],
    "Валерия": ["Лера", "Лерка", "Валерка"],
    "Вера": ["Верочка", "Верунчик"],
    "Виктория": ["Вика", "Викуся", "Викуля"],
    "Галина": ["Галя", "Галка", "Галочка"],
    "Дарья": ["Даша", "Дашка", "Дашуля"],
    "Диана": ["Ди"],
    "Евгения": ["Женя", "Женечка"],
    "Екатерина": ["Катя", "Катюша", "Катенька", "Кэт"],
    "Елена": ["Лена", "Леночка", "Ленка", "Алёна"],
    "Елизавета": ["Лиза", "Лизка", "Лизонька"],
    "Ирина": ["Ира", "Иринка", "Ирочка"],
    "Ксения": ["Ксюша", "Ксюшка", "Ксю"],
    "Любовь": ["Люба", "Любаша"],
    "Людмила": ["Люда", "Людочка", "Мила"],
    "Маргарита": ["Рита", "Ритка", "Марго"],
    "Мария": ["Маша", "Машка", "Машенька", "Маруся"],
    "Надежда": ["Надя", "Наденька", "Надюша"],
    "Наталья": ["Наташа", "Наталка", "Наташка"],
    "Оксана": ["Оксанка", "Ксана"],
    "Ольга": ["Оля", "Олька", "Оленька"],
    "Полина": ["Полинка", "Поля"],
    "Светлана": ["Света", "Светочка", "Светик"],
    "Софья": ["Соня", "Софа", "Сонечка"],
    "Татьяна": ["Таня", "Танюша", "Танечка"],
    "Юлия": ["Юля", "Юлька", "Юленька"],
}

# ── Reverse lookup cache (built on import) ──

_REVERSE_LOOKUP = {}  # diminutive -> list of formal names

def _build_reverse_lookup():
    """Build the reverse lookup dictionary."""
    for formal_name, diminutives in DIMINUTIVES.items():
        for dim in diminutives:
            dim_lower = dim.lower()
            if dim_lower not in _REVERSE_LOOKUP:
                _REVERSE_LOOKUP[dim_lower] = []
            if formal_name not in _REVERSE_LOOKUP[dim_lower]:
                _REVERSE_LOOKUP[dim_lower].append(formal_name)

_build_reverse_lookup()


# ── Public API ─────────────────────────────────────────────────────

def get_diminutives(formal_name: str) -> List[str]:
    """
    Get diminutive forms for a formal Russian name.

    Args:
        formal_name: Formal name like "Тихон"

    Returns:
        List of diminutives, e.g. ["Тиша", "Тишка", "Тишок", "Тиханя"]
        Empty list if name not found.
    """
    # Try exact match first
    if formal_name in DIMINUTIVES:
        return list(DIMINUTIVES[formal_name])

    # Try case-insensitive match
    name_lower = formal_name.lower()
    for key, values in DIMINUTIVES.items():
        if key.lower() == name_lower:
            return list(values)

    return []


def get_formal_name(diminutive: str) -> List[str]:
    """
    Reverse lookup: given a diminutive, find the formal name(s).

    Args:
        diminutive: A diminutive like "Саша"

    Returns:
        List of formal names, e.g. ["Александр", "Александра"]
        Empty list if not found.
    """
    return list(_REVERSE_LOOKUP.get(diminutive.lower(), []))


def get_all_name_variants(first_name: str) -> List[str]:
    """
    Get all name variants for a given first name (formal + all diminutives).
    Works for both formal names and diminutives.

    Args:
        first_name: Any form of a Russian first name

    Returns:
        List starting with the original name, followed by all variants.
        Deduplication is applied.
    """
    variants = [first_name]

    # Check if it's a formal name -> get diminutives
    diminutives = get_diminutives(first_name)
    if diminutives:
        variants.extend(diminutives)
    else:
        # Check if it's a diminutive -> get formal name(s) + their diminutives
        formal_names = get_formal_name(first_name)
        for formal in formal_names:
            if formal not in variants:
                variants.append(formal)
            for dim in get_diminutives(formal):
                if dim not in variants:
                    variants.append(dim)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen:
            seen.add(v_lower)
            result.append(v)

    return result


def is_known_name(name: str) -> bool:
    """Check if a name exists in our dictionary (formal or diminutive)."""
    name_lower = name.lower()
    for key in DIMINUTIVES:
        if key.lower() == name_lower:
            return True
    return name_lower in _REVERSE_LOOKUP

"""
INN Validator — Russian Tax Identification Number checksum validation.

10-digit INN (legal entity): 1 checkdigit
12-digit INN (individual): 2 checkdigits
"""


def validate_inn(inn: str) -> tuple:
    """
    Validate a Russian INN (tax identification number).

    Args:
        inn: String of 10 or 12 digits.

    Returns:
        (True, '') if valid, (False, 'error message') if invalid.
    """
    if not inn:
        return False, 'ИНН не указан'

    if not inn.isdigit():
        return False, 'ИНН должен содержать только цифры'

    if len(inn) == 10:
        return _validate_inn_10(inn)
    elif len(inn) == 12:
        return _validate_inn_12(inn)
    else:
        return False, 'ИНН должен содержать 10 или 12 цифр'


def _validate_inn_10(inn: str) -> tuple:
    """Validate 10-digit INN (legal entity)."""
    weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    checksum = sum(int(inn[i]) * weights[i] for i in range(9)) % 11 % 10
    if checksum != int(inn[9]):
        return False, 'Контрольная сумма ИНН некорректна'
    return True, ''


def _validate_inn_12(inn: str) -> tuple:
    """Validate 12-digit INN (individual)."""
    weights_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    weights_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

    check_11 = sum(int(inn[i]) * weights_11[i] for i in range(10)) % 11 % 10
    if check_11 != int(inn[10]):
        return False, 'Контрольная сумма ИНН некорректна'

    check_12 = sum(int(inn[i]) * weights_12[i] for i in range(11)) % 11 % 10
    if check_12 != int(inn[11]):
        return False, 'Контрольная сумма ИНН некорректна'

    return True, ''

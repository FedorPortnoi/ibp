"""
Mock Data Generators for Paid External APIs
=============================================
Provides realistic Russian mock data for all paid services so the full
pipeline can be tested end-to-end without real API keys.

Activated by setting USE_MOCK_APIS=true in .env or environment.

Each generator is deterministic per input (seeded by hashing the query)
so the same query always returns the same mock results.
"""

import hashlib
import os
import random
from typing import List, Dict, Optional


def _use_mock_apis() -> bool:
    """Check if mock API mode is enabled."""
    val = os.environ.get('USE_MOCK_APIS', '').lower()
    return val in ('true', '1', 'yes')


def _seed_rng(query: str) -> random.Random:
    """Create a seeded RNG so same query always produces same results."""
    h = int(hashlib.md5(query.encode('utf-8')).hexdigest()[:8], 16)
    return random.Random(h)


# ---------------------------------------------------------------------------
# Shared Russian name/data pools
# ---------------------------------------------------------------------------

RUSSIAN_FIRST_NAMES_M = [
    'Александр', 'Дмитрий', 'Сергей', 'Андрей', 'Алексей', 'Максим',
    'Евгений', 'Иван', 'Николай', 'Михаил', 'Владимир', 'Артём',
    'Денис', 'Роман', 'Павел', 'Олег', 'Виктор', 'Константин',
    'Кирилл', 'Игорь', 'Антон', 'Юрий', 'Василий', 'Тимур',
    'Борис', 'Григорий', 'Владислав', 'Вячеслав', 'Руслан', 'Георгий',
]

RUSSIAN_FIRST_NAMES_F = [
    'Анна', 'Мария', 'Елена', 'Ольга', 'Наталья', 'Ирина', 'Екатерина',
    'Светлана', 'Татьяна', 'Юлия', 'Дарья', 'Анастасия', 'Алина',
    'Виктория', 'Полина', 'Ксения', 'Людмила', 'Валентина', 'Надежда',
    'Галина', 'Марина', 'Вера', 'Лариса', 'Оксана', 'Тамара',
]

RUSSIAN_LAST_NAMES_M = [
    'Иванов', 'Петров', 'Сидоров', 'Кузнецов', 'Попов', 'Васильев',
    'Соколов', 'Михайлов', 'Новиков', 'Фёдоров', 'Морозов', 'Волков',
    'Алексеев', 'Лебедев', 'Семёнов', 'Егоров', 'Павлов', 'Козлов',
    'Степанов', 'Николаев', 'Орлов', 'Андреев', 'Макаров', 'Никитин',
    'Захаров', 'Зайцев', 'Соловьёв', 'Борисов', 'Яковлев', 'Григорьев',
]

RUSSIAN_LAST_NAMES_F = [
    'Иванова', 'Петрова', 'Сидорова', 'Кузнецова', 'Попова', 'Васильева',
    'Соколова', 'Михайлова', 'Новикова', 'Фёдорова', 'Морозова', 'Волкова',
    'Алексеева', 'Лебедева', 'Семёнова', 'Егорова', 'Павлова', 'Козлова',
    'Степанова', 'Николаева', 'Орлова', 'Андреева', 'Макарова', 'Никитина',
    'Захарова', 'Зайцева', 'Соловьёва', 'Борисова', 'Яковлева', 'Григорьева',
]

RUSSIAN_PATRONYMICS_M = [
    'Александрович', 'Дмитриевич', 'Сергеевич', 'Андреевич', 'Алексеевич',
    'Евгеньевич', 'Иванович', 'Николаевич', 'Михайлович', 'Владимирович',
    'Петрович', 'Олегович', 'Викторович', 'Павлович', 'Юрьевич',
]

RUSSIAN_PATRONYMICS_F = [
    'Александровна', 'Дмитриевна', 'Сергеевна', 'Андреевна', 'Алексеевна',
    'Евгеньевна', 'Ивановна', 'Николаевна', 'Михайловна', 'Владимировна',
    'Петровна', 'Олеговна', 'Викторовна', 'Павловна', 'Юрьевна',
]

RUSSIAN_CITIES = [
    'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
    'Казань', 'Нижний Новгород', 'Челябинск', 'Самара', 'Омск',
    'Ростов-на-Дону', 'Уфа', 'Красноярск', 'Воронеж', 'Пермь',
    'Волгоград', 'Краснодар', 'Саратов', 'Тюмень', 'Тольятти',
    'Ижевск', 'Барнаул', 'Ульяновск', 'Иркутск', 'Хабаровск',
    'Ярославль', 'Владивосток', 'Махачкала', 'Томск', 'Оренбург',
    'Кемерово', 'Рязань', 'Астрахань', 'Пенза', 'Липецк', 'Тула',
    'Калининград', 'Курск', 'Сочи', 'Ставрополь', 'Белгород',
]

RUSSIAN_STREETS = [
    'ул. Ленина', 'ул. Мира', 'ул. Пушкина', 'ул. Гагарина',
    'ул. Советская', 'ул. Кирова', 'ул. Горького', 'пр. Победы',
    'ул. Комсомольская', 'ул. Строителей', 'пр. Ленина', 'ул. Садовая',
    'ул. Молодёжная', 'ул. Новая', 'ул. Школьная', 'ул. Лесная',
    'ул. Набережная', 'ул. Центральная', 'пр. Космонавтов',
    'ул. Октябрьская', 'ул. Первомайская', 'ул. Заводская',
]

EMAIL_DOMAINS = [
    'mail.ru', 'yandex.ru', 'gmail.com', 'inbox.ru', 'bk.ru',
    'list.ru', 'rambler.ru', 'ya.ru',
]

BREACH_NAMES = [
    'VK_2012', 'Mail.ru_2014', 'Yandex_2014', 'Rambler_2012',
    'Adobe_2013', 'LinkedIn_2016', 'Badoo_2013', 'MySpace_2016',
    'DropBox_2012', 'Exploit.in_2016', 'AntiPublic_2017',
    'Collection1_2019', 'Wattpad_2020', 'Telegram_2020',
    'Facebook_2019', 'Pikabu_2018', 'LoveRu_2019',
    'Avito_2020', 'SberLeaks_2021', 'Wildberries_2022',
    'Delivery_Club_2022', 'CDEK_2022', 'Yandex_Food_2022',
    'DNS_Shop_2022', 'SDEK_2023', 'MGTSLeaks_2020',
]

# Transliteration map for generating mock emails from Cyrillic names
_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _transliterate(text: str) -> str:
    """Transliterate Cyrillic to Latin."""
    result = []
    for ch in text.lower():
        result.append(_TRANSLIT.get(ch, ch))
    return ''.join(result)


def _random_phone(rng: random.Random) -> str:
    """Generate a realistic Russian mobile phone number."""
    prefixes = ['916', '926', '903', '905', '915', '917', '919', '925',
                '906', '909', '951', '952', '953', '964', '965', '966',
                '967', '968', '977', '985', '999']
    prefix = rng.choice(prefixes)
    suffix = ''.join(str(rng.randint(0, 9)) for _ in range(7))
    return f'+7{prefix}{suffix}'


def _random_email(first: str, last: str, rng: random.Random) -> str:
    """Generate a realistic email from Russian name."""
    f_lat = _transliterate(first)
    l_lat = _transliterate(last)
    domain = rng.choice(EMAIL_DOMAINS)
    patterns = [
        f'{f_lat}.{l_lat}@{domain}',
        f'{f_lat}_{l_lat}@{domain}',
        f'{l_lat}.{f_lat}@{domain}',
        f'{f_lat}{l_lat[0]}@{domain}',
        f'{f_lat[0]}{l_lat}@{domain}',
        f'{l_lat}{rng.randint(1, 99)}@{domain}',
    ]
    return rng.choice(patterns)


def _random_md5(rng: random.Random) -> str:
    """Generate a realistic-looking MD5 hash."""
    return ''.join(rng.choice('0123456789abcdef') for _ in range(32))


def _random_password(rng: random.Random) -> str:
    """Generate a realistic-looking Russian password."""
    passwords = [
        'qwerty123', 'password1', '123456789', 'zxcvbn', 'iloveyou',
        'p@ssw0rd', 'moscow2020', 'qwe123', 'admin123', 'russia2022',
        'natasha1985', 'sergey_01', 'dima1990', 'katya2000', '1q2w3e4r',
        'spartak', 'zenit2021', 'cska1911', 'dynamo77', 'torpedo',
        'masha123', 'vanya1988', 'kolya_777', 'marina_love',
    ]
    return rng.choice(passwords)


def _random_person(rng: random.Random) -> Dict:
    """Generate a random Russian person identity."""
    is_male = rng.random() > 0.45
    if is_male:
        first = rng.choice(RUSSIAN_FIRST_NAMES_M)
        last = rng.choice(RUSSIAN_LAST_NAMES_M)
        patronymic = rng.choice(RUSSIAN_PATRONYMICS_M)
    else:
        first = rng.choice(RUSSIAN_FIRST_NAMES_F)
        last = rng.choice(RUSSIAN_LAST_NAMES_F)
        patronymic = rng.choice(RUSSIAN_PATRONYMICS_F)

    return {
        'first_name': first,
        'last_name': last,
        'patronymic': patronymic,
        'full_name': f'{last} {first} {patronymic}',
        'short_name': f'{last} {first}',
        'is_male': is_male,
    }


# ---------------------------------------------------------------------------
# GetContact Mock
# ---------------------------------------------------------------------------

GETCONTACT_TAG_TEMPLATES = [
    '{diminutive} работа', '{diminutive} офис', '{first} {last}',
    '{diminutive} сосед', '{diminutive} друг', '{first} ИП',
    '{last} {first} {patr}', '{diminutive} фитнес',
    '{diminutive} такси', '{first} доставка', '{diminutive} ремонт',
    '{last} адвокат', '{first} врач', '{diminutive} стройка',
    '{diminutive} школа', '{first} банк', '{diminutive} клиент',
    '{last} директор', '{first} бухгалтер', '{diminutive} магазин',
]

DIMINUTIVES_M = {
    'Александр': ['Саша', 'Шура'], 'Дмитрий': ['Дима', 'Митя'],
    'Сергей': ['Серёжа', 'Серж'], 'Андрей': ['Андрюша', 'Дрон'],
    'Алексей': ['Лёша', 'Лёха'], 'Максим': ['Макс'],
    'Евгений': ['Женя', 'Жека'], 'Иван': ['Ваня', 'Ванёк'],
    'Николай': ['Коля'], 'Михаил': ['Миша', 'Мишаня'],
    'Владимир': ['Вова', 'Володя'], 'Артём': ['Тёма'],
    'Денис': ['Дэн'], 'Роман': ['Рома'], 'Павел': ['Паша'],
    'Олег': ['Олежек'], 'Виктор': ['Витя'], 'Антон': ['Тоха'],
    'Кирилл': ['Кир'], 'Игорь': ['Гарик'],
}

DIMINUTIVES_F = {
    'Анна': ['Аня', 'Анюта'], 'Мария': ['Маша', 'Машенька'],
    'Елена': ['Лена', 'Алёна'], 'Ольга': ['Оля', 'Олюшка'],
    'Наталья': ['Наташа'], 'Ирина': ['Ира', 'Иришка'],
    'Екатерина': ['Катя', 'Катюша'], 'Светлана': ['Света', 'Светик'],
    'Татьяна': ['Таня'], 'Юлия': ['Юля', 'Юлечка'],
    'Дарья': ['Даша'], 'Анастасия': ['Настя', 'Настёна'],
    'Алина': ['Алинка'], 'Виктория': ['Вика'],
    'Полина': ['Полинка'], 'Ксения': ['Ксюша', 'Ксю'],
}


def _get_diminutive(first_name: str, is_male: bool, rng: random.Random) -> str:
    """Get a diminutive form of a Russian first name."""
    pool = DIMINUTIVES_M if is_male else DIMINUTIVES_F
    dims = pool.get(first_name, [first_name])
    return rng.choice(dims) if dims else first_name


def mock_getcontact(phone: str) -> List[Dict]:
    """
    Mock GetContact API response.
    Returns realistic Russian name tags for a phone number.
    """
    rng = _seed_rng(f'getcontact:{phone}')

    person = _random_person(rng)
    diminutive = _get_diminutive(
        person['first_name'], person['is_male'], rng
    )

    # Generate 2-5 contact tags
    num_tags = rng.randint(2, 5)
    all_tags = list(GETCONTACT_TAG_TEMPLATES)
    rng.shuffle(all_tags)

    tags = []
    for template in all_tags[:num_tags]:
        tag = template.format(
            first=person['first_name'],
            last=person['last_name'],
            patr=person['patronymic'],
            diminutive=diminutive,
        )
        tags.append(tag)

    return [{
        'name': person['short_name'],
        'phone': phone,
        'tags': tags,
        'tag_count': len(tags),
        'country': 'RU',
    }]


# ---------------------------------------------------------------------------
# NumBuster Mock
# ---------------------------------------------------------------------------

def mock_numbuster(phone: str) -> List[Dict]:
    """
    Mock NumBuster API response.
    Returns name + trust rating for a phone number.
    """
    rng = _seed_rng(f'numbuster:{phone}')
    person = _random_person(rng)

    return [{
        'name': person['short_name'],
        'phone': phone,
        'trust_rating': round(rng.uniform(0.3, 0.95), 2),
        'spam_reports': rng.randint(0, 3),
        'views': rng.randint(5, 500),
        'country': 'RU',
    }]


# ---------------------------------------------------------------------------
# Snusbase Mock
# ---------------------------------------------------------------------------

def mock_snusbase(query: str, query_type: str = 'email') -> List[Dict]:
    """
    Mock Snusbase API response.
    Returns realistic breach records for an email/username.
    """
    rng = _seed_rng(f'snusbase:{query}')

    num_results = rng.randint(1, 4)
    results = []

    for i in range(num_results):
        person = _random_person(rng)
        email = query if '@' in query else _random_email(
            person['first_name'], person['last_name'], rng
        )

        record = {
            'email': email,
            'username': _transliterate(person['first_name']).lower() + str(rng.randint(1, 99)),
            'password': _random_password(rng) if rng.random() > 0.3 else None,
            'hash': _random_md5(rng) if rng.random() > 0.5 else None,
            'name': person['short_name'] if rng.random() > 0.4 else None,
            'breach_name': rng.choice(BREACH_NAMES),
            'source': 'snusbase_mock',
        }
        results.append(record)

    return results


# ---------------------------------------------------------------------------
# DeHashed Mock
# ---------------------------------------------------------------------------

def mock_dehashed(query: str, query_type: str = 'email') -> List[Dict]:
    """
    Mock DeHashed API response.
    Returns realistic breach records with diverse data types.
    """
    rng = _seed_rng(f'dehashed:{query}')

    num_results = rng.randint(1, 5)
    results = []

    for i in range(num_results):
        person = _random_person(rng)
        email = query if '@' in query else _random_email(
            person['first_name'], person['last_name'], rng
        )
        phone = _random_phone(rng) if rng.random() > 0.5 else None

        record = {
            'id': rng.randint(100000000, 999999999),
            'email': email,
            'username': _transliterate(person['first_name']).lower() + '_' + _transliterate(person['last_name']).lower(),
            'password': _random_password(rng) if rng.random() > 0.4 else None,
            'hashed_password': _random_md5(rng) if rng.random() > 0.5 else None,
            'name': person['short_name'],
            'phone': phone,
            'ip_address': f'{rng.randint(5, 95)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}',
            'database_name': rng.choice(BREACH_NAMES),
            'source': 'dehashed_mock',
        }
        results.append(record)

    return results


# ---------------------------------------------------------------------------
# LeakCheck Pro Mock
# ---------------------------------------------------------------------------

def mock_leakcheck_pro(query: str, query_type: str = 'email') -> List[Dict]:
    """
    Mock LeakCheck Pro API response.
    Returns detailed breach results with passwords/hashes.
    """
    rng = _seed_rng(f'leakcheck:{query}')

    num_results = rng.randint(1, 6)
    results = []

    for i in range(num_results):
        breach = rng.choice(BREACH_NAMES)
        has_password = rng.random() > 0.3

        record = {
            'source': {
                'name': breach,
                'breach_date': f'20{rng.randint(12, 24)}-{rng.randint(1, 12):02d}',
                'records_count': rng.randint(10000, 50000000),
            },
            'email': query if '@' in query else None,
            'username': query if '@' not in query else None,
            'password': _random_password(rng) if has_password else None,
            'hash': _random_md5(rng) if not has_password else None,
            'last_breach': breach,
        }
        results.append(record)

    return results


# ---------------------------------------------------------------------------
# HIBP Paid Mock
# ---------------------------------------------------------------------------

def mock_hibp_breaches(email: str) -> List[Dict]:
    """
    Mock HIBP breachedaccount API response.
    Returns a list of breaches the email appeared in.
    """
    rng = _seed_rng(f'hibp:{email}')

    num_breaches = rng.randint(1, 5)
    all_breaches = list(BREACH_NAMES)
    rng.shuffle(all_breaches)

    results = []
    for breach_name in all_breaches[:num_breaches]:
        year = rng.randint(2012, 2024)
        month = rng.randint(1, 12)
        results.append({
            'Name': breach_name,
            'Title': breach_name.replace('_', ' '),
            'Domain': f'{breach_name.split("_")[0].lower()}.ru',
            'BreachDate': f'{year}-{month:02d}-01',
            'PwnCount': rng.randint(10000, 100000000),
            'DataClasses': rng.sample(
                ['Email addresses', 'Passwords', 'Usernames', 'Phone numbers',
                 'IP addresses', 'Names', 'Physical addresses', 'Dates of birth'],
                k=rng.randint(2, 5)
            ),
            'IsVerified': True,
            'IsFabricated': False,
            'IsRetired': False,
            'IsSpamList': False,
        })

    return results


# ---------------------------------------------------------------------------
# Hunter.io Mock
# ---------------------------------------------------------------------------

def mock_hunter_verify(email: str) -> Dict:
    """
    Mock Hunter.io email verification response.
    Returns realistic verification result.
    """
    rng = _seed_rng(f'hunter:{email}')

    domain = email.split('@')[-1] if '@' in email else 'unknown.com'
    is_webmail = domain in ('gmail.com', 'mail.ru', 'yandex.ru', 'inbox.ru',
                            'bk.ru', 'list.ru', 'rambler.ru', 'ya.ru')

    # Most queried emails should appear valid
    status_roll = rng.random()
    if status_roll > 0.15:
        status = 'valid'
        score = rng.randint(70, 99)
    elif status_roll > 0.05:
        status = 'accept_all'
        score = rng.randint(40, 70)
    else:
        status = 'invalid'
        score = rng.randint(0, 30)

    return {
        'data': {
            'status': status,
            'score': score,
            'email': email,
            'regexp': True,
            'gibberish': False,
            'disposable': False,
            'webmail': is_webmail,
            'mx_records': True,
            'smtp_server': True,
            'smtp_check': status == 'valid',
            'accept_all': status == 'accept_all',
            'block': False,
            'sources': [
                {'domain': domain, 'uri': f'https://{domain}', 'extracted_on': '2024-01-15'}
            ] if rng.random() > 0.5 else [],
        },
        'meta': {
            'params': {'email': email},
        },
    }


def mock_hunter_domain(domain: str) -> List[Dict]:
    """
    Mock Hunter.io domain search response.
    Returns mock emails found at a domain.
    """
    rng = _seed_rng(f'hunter_domain:{domain}')

    num_emails = rng.randint(0, 5)
    results = []

    for i in range(num_emails):
        person = _random_person(rng)
        f_lat = _transliterate(person['first_name'])
        l_lat = _transliterate(person['last_name'])
        pattern = rng.choice([
            f'{f_lat}.{l_lat}',
            f'{f_lat[0]}.{l_lat}',
            f'{f_lat}_{l_lat}',
        ])

        results.append({
            'value': f'{pattern}@{domain}',
            'type': 'personal',
            'confidence': rng.randint(50, 95),
            'first_name': person['first_name'],
            'last_name': person['last_name'],
            'position': rng.choice([
                'Менеджер', 'Разработчик', 'Директор', 'Бухгалтер',
                'Аналитик', 'Маркетолог', None
            ]),
            'department': rng.choice([
                'engineering', 'sales', 'management', 'marketing', None
            ]),
        })

    return results


# ---------------------------------------------------------------------------
# HudsonRock Mock
# ---------------------------------------------------------------------------

def mock_hudsonrock(query: str, query_type: str = 'email') -> Dict:
    """
    Mock HudsonRock Cavalier API response.
    Returns infostealer data for an email/username.
    """
    rng = _seed_rng(f'hudsonrock:{query}')

    # 60% chance of having stealer data
    if rng.random() > 0.6:
        return {'stealers': []}

    num_stealers = rng.randint(1, 3)
    stealers = []

    for i in range(num_stealers):
        computer = f'DESKTOP-{rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}{rng.randint(100, 999)}'
        year = rng.randint(2021, 2024)
        month = rng.randint(1, 12)

        credentials = []
        num_creds = rng.randint(1, 4)
        for j in range(num_creds):
            cred_email = query if '@' in query else _random_email(
                rng.choice(RUSSIAN_FIRST_NAMES_M + RUSSIAN_FIRST_NAMES_F),
                rng.choice(RUSSIAN_LAST_NAMES_M + RUSSIAN_LAST_NAMES_F),
                rng,
            )
            credentials.append({
                'url': rng.choice([
                    'https://vk.com', 'https://mail.ru', 'https://ok.ru',
                    'https://yandex.ru', 'https://avito.ru', 'https://ozon.ru',
                    'https://wildberries.ru', 'https://sberbank.ru',
                    'https://gosuslugi.ru', 'https://nalog.ru',
                ]),
                'username': cred_email,
                'password': _random_password(rng),
            })

        top_logins = [
            _transliterate(rng.choice(RUSSIAN_FIRST_NAMES_M + RUSSIAN_FIRST_NAMES_F)).lower()
            + str(rng.randint(1, 999))
            for _ in range(rng.randint(0, 3))
        ]

        stealers.append({
            'computer_name': computer,
            'operating_system': rng.choice([
                'Windows 10 Pro', 'Windows 10 Home', 'Windows 11 Pro',
                'Windows 7 SP1',
            ]),
            'date_compromised': f'{year}-{month:02d}-{rng.randint(1, 28):02d}T00:00:00.000Z',
            'credentials': credentials,
            'top_logins': top_logins,
        })

    return {'stealers': stealers}


# ---------------------------------------------------------------------------
# ProxyNova COMB Mock
# ---------------------------------------------------------------------------

def mock_proxynova(email: str) -> Dict:
    """
    Mock ProxyNova COMB API response.
    Returns email:password combo lines.
    """
    rng = _seed_rng(f'proxynova:{email}')

    # 50% chance of having results
    if rng.random() > 0.5:
        return {'count': 0, 'lines': []}

    num_lines = rng.randint(1, 6)
    lines = []

    for i in range(num_lines):
        password = _random_password(rng)
        # Sometimes return the queried email, sometimes a related one
        if rng.random() > 0.3:
            line_email = email
        else:
            person = _random_person(rng)
            line_email = _random_email(
                person['first_name'], person['last_name'], rng
            )
        lines.append(f'{line_email}:{password}')

    return {
        'count': len(lines),
        'lines': lines,
    }

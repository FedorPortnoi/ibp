"""
VK Identity Signal Counter
===========================
Scores a VK profile against known target data (INN, DOB, business records)
to determine if the profile belongs to the target person.

4 possible signals:
  1. DOB      — VK bdate exactly matches input date of birth
  2. Region   — VK city is in the INN registration region
  3. Career   — business/ИП name from EGRUL appears in VK career or about text
  4. Phone    — a phone from the person's VK wall has the same region as their INN
               (Signal 4 is evaluated in Stage 4 via DaData clean/phone)

Threshold: 3+ signals → profile is "Подтверждён"; otherwise it is discarded.
"""

from __future__ import annotations
import datetime
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# INN first-2-digits → lowercase city/region names that VK might show
_INN_REGION_CITIES: dict[str, list[str]] = {
    '01': ['майкоп', 'адыгея', 'maykop'],
    '02': ['уфа', 'башкортостан', 'стерлитамак', 'салават', 'нефтекамск', 'ufa'],
    '03': ['улан-удэ', 'бурятия', 'ulan-ude', 'buryatia'],
    '04': ['горно-алтайск', 'алтай', 'gorno-altaysk'],
    '05': ['махачкала', 'дагестан', 'дербент', 'хасавюрт', 'makhachkala', 'dagestan'],
    '06': ['магас', 'назрань', 'ингушетия', 'magas', 'nazran'],
    '07': ['нальчик', 'кабардино-балкария', 'nalchik'],
    '08': ['элиста', 'калмыкия', 'elista'],
    '09': ['черкесск', 'карачаево-черкесия', 'cherkessk'],
    '10': ['петрозаводск', 'карелия', 'petrozavodsk', 'karelia'],
    '11': ['сыктывкар', 'коми', 'воркута', 'ухта', 'syktyvkar'],
    '12': ['йошкар-ола', 'марий эл', 'yoshkar-ola'],
    '13': ['саранск', 'мордовия', 'saransk'],
    '14': ['якутск', 'якутия', 'саха', 'yakutsk', 'yakutia'],
    '15': ['владикавказ', 'северная осетия', 'vladikavkaz'],
    '16': ['казань', 'татарстан', 'набережные челны', 'нижнекамск', 'kazan', 'tatarstan'],
    '17': ['кызыл', 'тыва', 'тува', 'kyzyl', 'tuva'],
    '18': ['ижевск', 'удмуртия', 'izhevsk', 'udmurtia'],
    '19': ['абакан', 'хакасия', 'abakan'],
    '20': ['грозный', 'чечня', 'grozny', 'chechnya'],
    '21': ['чебоксары', 'чувашия', 'cheboksary'],
    '22': ['барнаул', 'алтайский край', 'бийск', 'рубцовск', 'barnaul'],
    '23': ['краснодар', 'сочи', 'новороссийск', 'армавир', 'анапа', 'геленджик',
           'krasnodar', 'sochi'],
    '24': ['красноярск', 'норильск', 'krasnoyarsk'],
    '25': ['владивосток', 'находка', 'уссурийск', 'vladivostok', 'primorsky'],
    '26': ['ставрополь', 'пятигорск', 'кисловодск', 'невинномысск', 'stavropol'],
    '27': ['хабаровск', 'комсомольск-на-амуре', 'khabarovsk'],
    '28': ['благовещенск', 'blagoveshchensk'],
    '29': ['архангельск', 'северодвинск', 'arkhangelsk'],
    '30': ['астрахань', 'astrakhan'],
    '31': ['белгород', 'belgorod'],
    '32': ['брянск', 'bryansk'],
    '33': ['владимир', 'ковров', 'vladimir'],
    '34': ['волгоград', 'volgograd'],
    '35': ['вологда', 'череповец', 'vologda'],
    '36': ['воронеж', 'voronezh'],
    '37': ['иваново', 'ivanovo'],
    '38': ['иркутск', 'братск', 'irkutsk'],
    '39': ['калининград', 'kaliningrad'],
    '40': ['калуга', 'kaluga'],
    '41': ['петропавловск-камчатский', 'камчатка', 'petropavlovsk-kamchatsky'],
    '42': ['кемерово', 'новокузнецк', 'kemerovo'],
    '43': ['киров', 'кировская', 'kirov'],
    '44': ['кострома', 'kostroma'],
    '45': ['курган', 'kurgan'],
    '46': ['курск', 'kursk'],
    '47': ['гатчина', 'выборг', 'ленинградская', 'leningrad oblast'],
    '48': ['липецк', 'lipetsk'],
    '49': ['магадан', 'magadan'],
    '50': ['балашиха', 'химки', 'мытищи', 'подольск', 'люберцы', 'королёв',
           'домодедово', 'красногорск', 'одинцово', 'серпухов', 'московская',
           'moscow oblast', 'podmoskovye'],
    '51': ['мурманск', 'murmansk'],
    '52': ['нижний новгород', 'дзержинск', 'nizhny novgorod'],
    '53': ['великий новгород', 'novgorod'],
    '54': ['новосибирск', 'novosibirsk'],
    '55': ['омск', 'omsk'],
    '56': ['оренбург', 'orenburg'],
    '57': ['орёл', 'орел', 'oryol'],
    '58': ['пенза', 'penza'],
    '59': ['пермь', 'perm'],
    '60': ['псков', 'pskov'],
    '61': ['ростов-на-дону', 'таганрог', 'ростов', 'rostov-on-don', 'rostov'],
    '62': ['рязань', 'ryazan'],
    '63': ['самара', 'тольятти', 'samara', 'togliatti'],
    '64': ['саратов', 'saratov'],
    '65': ['южно-сахалинск', 'сахалин', 'yuzhno-sakhalinsk'],
    '66': ['екатеринбург', 'нижний тагил', 'yekaterinburg'],
    '67': ['смоленск', 'smolensk'],
    '68': ['тамбов', 'tambov'],
    '69': ['тверь', 'tver'],
    '70': ['томск', 'tomsk'],
    '71': ['тула', 'tula'],
    '72': ['тюмень', 'tyumen'],
    '73': ['ульяновск', 'ulyanovsk'],
    '74': ['челябинск', 'магнитогорск', 'chelyabinsk'],
    '75': ['чита', 'забайкалье', 'chita'],
    '76': ['ярославль', 'yaroslavl'],
    '77': ['москва', 'moscow'],
    '78': ['санкт-петербург', 'санкт петербург', 'питер', 'петербург',
           'saint petersburg', 'st. petersburg', 'st petersburg', 'спб'],
    '79': ['биробиджан', 'еврейская', 'birobidzhan'],
    '83': ['нарьян-мар', 'ненецкий', 'naryan-mar'],
    '86': ['ханты-мансийск', 'сургут', 'нижневартовск', 'surgut', 'khanty-mansiysk'],
    '87': ['анадырь', 'чукотка', 'anadyr'],
    '89': ['салехард', 'новый уренгой', 'ноябрьск', 'salekhard'],
    '91': ['симферополь', 'керчь', 'феодосия', 'евпатория', 'ялта', 'алушта',
           'крым', 'crimea', 'simferopol', 'sevastopol', 'севастополь'],
    '92': ['севастополь', 'sevastopol'],
    '99': ['байконур', 'baikonur'],
}

# Substrings DaData clean/phone returns in `region` field for each INN region
_INN_REGION_DADATA: dict[str, list[str]] = {
    '02': ['башкортостан'],
    '05': ['дагестан'],
    '16': ['татарстан'],
    '23': ['краснодарский'],
    '47': ['ленинградская'],
    '50': ['московская'],
    '52': ['нижегородская'],
    '54': ['новосибирская'],
    '59': ['пермский'],
    '61': ['ростовская'],
    '63': ['самарская'],
    '66': ['свердловская'],
    '74': ['челябинская'],
    '77': ['москва'],
    '78': ['санкт-петербург'],
    '91': ['крым'],
    '92': ['севастополь'],
}


def _get_inn_region(inn: Optional[str]) -> Optional[str]:
    if not inn or len(inn) < 2:
        return None
    code = inn[:2]
    return code if code.isdigit() else None


def _city_in_region(vk_city: Optional[str], region_code: str) -> bool:
    if not vk_city:
        return False
    lc = vk_city.lower().strip()
    cities = _INN_REGION_CITIES.get(region_code, [])
    return any(c in lc or lc in c for c in cities)


def _dob_matches(vk_bdate: Optional[str], target_dob) -> bool:
    if not vk_bdate or target_dob is None:
        return False
    parts = vk_bdate.split('.')
    if len(parts) != 3:
        return False
    try:
        return (
            int(parts[0]) == target_dob.day
            and int(parts[1]) == target_dob.month
            and int(parts[2]) == target_dob.year
        )
    except (ValueError, IndexError):
        return False


def _career_matches_business(
    career: Optional[list],
    about: Optional[str],
    full_name: Optional[str],
    egrul_names: Optional[list],
) -> bool:
    """True if VK career/about contains any business name or the subject's ИП."""
    career_text = ''
    if career and isinstance(career, list):
        for entry in career:
            if isinstance(entry, dict):
                career_text += ' ' + (entry.get('company') or '').lower()

    combined = career_text + ' ' + (about or '').lower()

    if egrul_names:
        for name in egrul_names:
            if not name:
                continue
            nl = name.lower()
            if nl in combined:
                return True
            # strip legal-form prefix and quotes before matching
            core = re.sub(r'^(ооо|ао|зао|ип|пао|нко|мкп)\s+', '', nl).strip().strip('"«»')
            if len(core) > 4 and core in combined:
                return True

    # Match "ИП Фамилия" pattern using first token of full_name
    if full_name:
        surname = full_name.split()[0].lower()
        if len(surname) >= 3 and surname in combined:
            return True

    return False


def _birth_year_matches(profile: dict, date_of_birth) -> bool:
    """True if the VK profile's age implies the same birth year as target DOB."""
    if date_of_birth is None:
        return False
    age = profile.get('age')
    if age is None:
        return False
    current_year = datetime.date.today().year
    # VK age = floor(years since last birthday), so birth year is one of two values
    return date_of_birth.year in (current_year - age, current_year - age - 1)


def count_signals(
    profile: dict,
    inn: Optional[str],
    full_name: Optional[str],
    date_of_birth=None,
    egrul_names: Optional[list] = None,
) -> tuple[int, list[str]]:
    """
    Count identity confirmation signals for a VK profile dict.

    Returns (count, signal_names).
    Checks: dob (exact) | birth_year (from age) | inn_region | career.
    Signal 4 (phone region via DaData) is added later in Stage 4.
    """
    signals: list[str] = []
    region = _get_inn_region(inn)

    if _dob_matches(profile.get('birth_date'), date_of_birth):
        signals.append('dob')
    elif _birth_year_matches(profile, date_of_birth):
        # Weaker than exact DOB but still meaningful — VK age implies correct birth year
        signals.append('birth_year')

    if region and _city_in_region(
        profile.get('city') or profile.get('home_town'), region
    ):
        signals.append('inn_region')

    if _career_matches_business(
        profile.get('career'),
        profile.get('about'),
        full_name,
        egrul_names,
    ):
        signals.append('career')

    return len(signals), signals


def phone_region_matches_inn(phone_region: str, inn: Optional[str]) -> bool:
    """True if a DaData clean/phone `region` string matches the INN region."""
    if not phone_region or not inn:
        return False
    region = _get_inn_region(inn)
    if not region:
        return False
    pl = phone_region.lower()
    for substr in _INN_REGION_DADATA.get(region, []):
        if substr in pl:
            return True
    # Fallback: city list match
    return _city_in_region(phone_region, region)

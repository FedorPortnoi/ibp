"""
Risk Scoring Engine
===================
Automated 7-dimension risk scoring for OSINT investigations.

Dimensions (0-100 composite):
1. Profile completeness (0-15)
2. Digital footprint (0-20)
3. Social exposure (0-15)
4. Contact exposure (0-15)
5. Business ties (0-15)
6. Behavioral patterns (0-10)
7. OPSEC assessment (0-10)

Categories: LOW (0-25), MODERATE (26-50), ELEVATED (51-75), HIGH (76-100)
"""

import logging
from datetime import datetime

logger = logging.getLogger('ibp.services.risk_scoring')


def get_risk_category(score):
    """Return risk category label and color based on score."""
    if score <= 25:
        return 'LOW', '#10b981', 'Низкий'
    elif score <= 50:
        return 'MODERATE', '#f59e0b', 'Умеренный'
    elif score <= 75:
        return 'ELEVATED', '#f97316', 'Повышенный'
    else:
        return 'HIGH', '#ef4444', 'Высокий'


def _score_profile_completeness(profile, investigation):
    """
    Dimension 1: Profile Completeness (0-15).
    Measures how much personal info is publicly available.
    """
    score = 0
    factors = []

    if profile:
        if profile.photo_url:
            score += 3
            factors.append('Фото профиля доступно')
        if profile.phone or investigation.confirmed_phone:
            score += 3
            factors.append('Телефон найден')
        if profile.email or investigation.confirmed_email:
            score += 3
            factors.append('Email найден')
        if profile.career:
            score += 3
            factors.append('Карьера указана')
        if profile.education:
            score += 3
            factors.append('Образование указано')

    if not factors:
        factors.append('Данные профиля не обнаружены')

    return min(15, score), factors


def _score_digital_footprint(profiles, investigation):
    """
    Dimension 2: Digital Footprint (0-20).
    Measures presence across platforms and content volume.
    """
    score = 0
    factors = []

    # Number of platforms found
    platform_count = len(profiles)
    if platform_count >= 3:
        score += 8
        factors.append(f'Найдено на {platform_count} платформах')
    elif platform_count >= 2:
        score += 5
        factors.append(f'Найдено на {platform_count} платформах')
    elif platform_count == 1:
        score += 2
        factors.append('Найден на 1 платформе')

    # Friends count (use confirmed profile)
    confirmed = next((p for p in profiles if p.is_confirmed), None)
    if confirmed and confirmed.friends_count:
        if confirmed.friends_count > 500:
            score += 6
            factors.append(f'{confirmed.friends_count} друзей (большая сеть)')
        elif confirmed.friends_count > 100:
            score += 4
            factors.append(f'{confirmed.friends_count} друзей')
        else:
            score += 2
            factors.append(f'{confirmed.friends_count} друзей (малая сеть)')

    # Photos count
    if confirmed and confirmed.photos_count:
        if confirmed.photos_count > 100:
            score += 6
            factors.append(f'{confirmed.photos_count} фото (активный)')
        elif confirmed.photos_count > 20:
            score += 4
            factors.append(f'{confirmed.photos_count} фото')
        elif confirmed.photos_count > 0:
            score += 2
            factors.append(f'{confirmed.photos_count} фото')

    if not factors:
        factors.append('Цифровой след минимальный')

    return min(20, score), factors


def _score_social_exposure(profile, investigation):
    """
    Dimension 3: Social Exposure (0-15).
    Measures social network openness and reach.
    """
    score = 0
    factors = []

    if profile:
        # Friends visibility
        if profile.friends_count and profile.friends_count > 200:
            score += 5
            factors.append('Большой круг друзей')
        elif profile.friends_count and profile.friends_count > 50:
            score += 3
            factors.append('Средний круг друзей')

        # Groups
        if profile.groups_count and profile.groups_count > 20:
            score += 5
            factors.append(f'{profile.groups_count} групп (активен в сообществах)')
        elif profile.groups_count and profile.groups_count > 5:
            score += 3
            factors.append(f'{profile.groups_count} групп')

        # Social graph data
        social_graph = investigation.social_graph
        if social_graph and social_graph.get('nodes'):
            node_count = len(social_graph['nodes'])
            if node_count > 20:
                score += 5
                factors.append(f'Социальный граф: {node_count} связей')
            elif node_count > 5:
                score += 3
                factors.append(f'Социальный граф: {node_count} связей')

    if not factors:
        factors.append('Социальная экспозиция не определена')

    return min(15, score), factors


def _score_contact_exposure(investigation):
    """
    Dimension 4: Contact Exposure (0-15).
    Measures how easily contactable the person is.
    """
    score = 0
    factors = []

    phones = investigation.discovered_phones
    emails = investigation.discovered_emails

    # Phone discoverable
    if phones:
        score += 5
        phone_count = len(phones) if isinstance(phones, list) else 1
        factors.append(f'Найдено {phone_count} телефон(ов)')

    # Email found
    if emails:
        score += 5
        email_count = len(emails) if isinstance(emails, list) else 1
        factors.append(f'Найдено {email_count} email(ов)')

    # Multiple contact methods
    if phones and emails:
        score += 5
        factors.append('Доступен по нескольким каналам')

    if not factors:
        factors.append('Контактные данные не обнаружены')

    return min(15, score), factors


def _score_business_ties(business_records, court_records):
    """
    Dimension 5: Business Ties (0-15).
    Measures business and legal exposure.
    """
    score = 0
    factors = []

    # Business records
    biz_count = len(business_records)
    if biz_count > 5:
        score += 7
        factors.append(f'{biz_count} бизнес-записей (высокая активность)')
    elif biz_count > 2:
        score += 5
        factors.append(f'{biz_count} бизнес-записей')
    elif biz_count > 0:
        score += 3
        factors.append(f'{biz_count} бизнес-записей')

    # Active businesses
    active = [b for b in business_records if b.is_active]
    if active:
        factors.append(f'{len(active)} действующих компаний')

    # Court records
    court_count = len(court_records)
    if court_count > 5:
        score += 8
        factors.append(f'{court_count} судебных дел (высокий риск)')
    elif court_count > 2:
        score += 5
        factors.append(f'{court_count} судебных дел')
    elif court_count > 0:
        score += 3
        factors.append(f'{court_count} судебных дел')

    # Defendant cases
    defendant_cases = [c for c in court_records if c.is_defendant]
    if defendant_cases:
        factors.append(f'Ответчик в {len(defendant_cases)} делах')

    if not factors:
        factors.append('Бизнес-связи не обнаружены')

    return min(15, score), factors


def _score_behavioral_patterns(profile, investigation):
    """
    Dimension 6: Behavioral Patterns (0-10).
    Measures posting activity and online behavior.
    """
    score = 0
    factors = []

    if profile:
        # Photos as proxy for posting activity
        if profile.photos_count and profile.photos_count > 50:
            score += 4
            factors.append('Высокая активность публикаций')
        elif profile.photos_count and profile.photos_count > 10:
            score += 2
            factors.append('Средняя активность публикаций')

        # Groups as proxy for interests
        if profile.groups_count and profile.groups_count > 10:
            score += 3
            factors.append('Активное участие в сообществах')

        # Followers count as influence
        if profile.followers_count and profile.followers_count > 100:
            score += 3
            factors.append(f'{profile.followers_count} подписчиков')

    if not factors:
        factors.append('Поведенческие паттерны не определены')

    return min(10, score), factors


def _score_opsec(profile, investigation):
    """
    Dimension 7: OPSEC Assessment (0-10).
    Measures privacy awareness — higher score = WORSE opsec (more exposed).
    """
    score = 0
    factors = []

    if profile:
        # Open profile = worse opsec
        if not profile.is_closed:
            score += 4
            factors.append('Профиль открыт')
        else:
            factors.append('Профиль закрыт (хорошая OPSEC)')

        # Real name used
        if profile.first_name and profile.last_name:
            score += 3
            factors.append('Используется настоящее имя')

        # Contact info visible
        if profile.phone or profile.email:
            score += 3
            factors.append('Контакты видны в профиле')
    else:
        factors.append('Профиль не найден — невозможно оценить OPSEC')

    return min(10, score), factors


def calculate_risk_score(investigation_id):
    """
    Calculate composite risk score for an investigation.

    Args:
        investigation_id: UUID of the investigation

    Returns:
        dict with score, category, breakdown, and metadata
    """
    from app.models import Investigation, SocialProfile, BusinessRecord, CourtRecord

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return None

    # Get related data
    profiles = SocialProfile.query.filter_by(investigation_id=investigation_id).all()
    confirmed_profile = next((p for p in profiles if p.is_confirmed), None)
    business_records = BusinessRecord.query.filter_by(investigation_id=investigation_id).all()
    court_records = CourtRecord.query.filter_by(investigation_id=investigation_id).all()

    # Calculate each dimension
    d1_score, d1_factors = _score_profile_completeness(confirmed_profile, investigation)
    d2_score, d2_factors = _score_digital_footprint(profiles, investigation)
    d3_score, d3_factors = _score_social_exposure(confirmed_profile, investigation)
    d4_score, d4_factors = _score_contact_exposure(investigation)
    d5_score, d5_factors = _score_business_ties(business_records, court_records)
    d6_score, d6_factors = _score_behavioral_patterns(confirmed_profile, investigation)
    d7_score, d7_factors = _score_opsec(confirmed_profile, investigation)

    # Composite score
    total = d1_score + d2_score + d3_score + d4_score + d5_score + d6_score + d7_score
    category_en, color, category_ru = get_risk_category(total)

    breakdown = {
        'profile_completeness': {
            'score': d1_score,
            'max': 15,
            'label': 'Полнота профиля',
            'factors': d1_factors,
        },
        'digital_footprint': {
            'score': d2_score,
            'max': 20,
            'label': 'Цифровой след',
            'factors': d2_factors,
        },
        'social_exposure': {
            'score': d3_score,
            'max': 15,
            'label': 'Социальная экспозиция',
            'factors': d3_factors,
        },
        'contact_exposure': {
            'score': d4_score,
            'max': 15,
            'label': 'Контактная доступность',
            'factors': d4_factors,
        },
        'business_ties': {
            'score': d5_score,
            'max': 15,
            'label': 'Бизнес-связи',
            'factors': d5_factors,
        },
        'behavioral_patterns': {
            'score': d6_score,
            'max': 10,
            'label': 'Поведенческие паттерны',
            'factors': d6_factors,
        },
        'opsec_assessment': {
            'score': d7_score,
            'max': 10,
            'label': 'Оценка OPSEC',
            'factors': d7_factors,
        },
    }

    result = {
        'investigation_id': investigation_id,
        'score': total,
        'max_score': 100,
        'category': category_en,
        'category_ru': category_ru,
        'color': color,
        'breakdown': breakdown,
        'target_name': investigation.input_name,
        'calculated_at': datetime.utcnow().isoformat(),
        'data_summary': {
            'profiles_found': len(profiles),
            'emails_found': len(investigation.discovered_emails) if investigation.discovered_emails else 0,
            'phones_found': len(investigation.discovered_phones) if investigation.discovered_phones else 0,
            'business_records': len(business_records),
            'court_records': len(court_records),
        },
    }

    # Store risk indicators on the investigation
    try:
        indicators = investigation.risk_indicators or []
        indicators.append({
            'type': 'auto_scoring',
            'score': total,
            'category': category_en,
            'calculated_at': result['calculated_at'],
        })
        investigation.risk_indicators = indicators
        from app import db
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save risk indicators: {e}")

    return result


def get_score_breakdown(investigation_id):
    """
    Get detailed score breakdown for an investigation.
    Alias for calculate_risk_score — always recalculates fresh.

    Args:
        investigation_id: UUID of the investigation

    Returns:
        dict with full breakdown or None
    """
    return calculate_risk_score(investigation_id)

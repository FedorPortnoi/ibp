"""
Dossier Generator - Professional Investigation Dossier
=======================================================
Generates professional-grade investigation dossiers consolidating
all investigation data from Phases 1-3.
"""

import logging
import json
import html as html_module
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _esc(text):
    """HTML-escape a string for safe embedding."""
    if not text:
        return ""
    return html_module.escape(str(text))


def _format_date(dt_str):
    """Format ISO date string to DD.MM.YYYY."""
    if not dt_str:
        return None
    try:
        if isinstance(dt_str, str):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = dt_str
        return dt.strftime('%d.%m.%Y')
    except Exception as e:
        logger.debug(f"[DossierGenerator] Date format failed for '{dt_str}': {e}")
        return str(dt_str)


def _format_datetime(dt_str):
    """Format ISO datetime string to DD.MM.YYYY HH:MM."""
    if not dt_str:
        return None
    try:
        if isinstance(dt_str, str):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = dt_str
        return dt.strftime('%d.%m.%Y %H:%M')
    except Exception as e:
        logger.debug(f"[DossierGenerator] Datetime format failed for '{dt_str}': {e}")
        return str(dt_str)


def _safe_json(value, default=None):
    """Safely parse JSON field."""
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception as e:
            logger.debug(f"[DossierGenerator] JSON parse failed: {e}")
            return default
    return default


class DossierGenerator:
    """Generate professional investigation dossiers."""

    def generate_dossier(self, investigation_id: str) -> Dict:
        """
        Consolidate all investigation data into a dossier structure.

        Returns a dict with all sections ready for template rendering.
        """
        from app.models import (
            Investigation, SocialProfile, Friend,
            BusinessRecord, CourtRecord, Connection
        )

        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            return {'error': 'Расследование не найдено'}

        # --- Profiles ---
        all_profiles = SocialProfile.query.filter_by(
            investigation_id=investigation_id
        ).all()
        confirmed_profiles = [p for p in all_profiles if p.is_confirmed]
        confirmed_profile = confirmed_profiles[0] if confirmed_profiles else None

        # --- Friends ---
        friends = Friend.query.filter_by(investigation_id=investigation_id).all()
        friends_sorted = sorted(
            friends, key=lambda f: f.centrality_score or 0, reverse=True
        )

        # --- Business records ---
        business_records = BusinessRecord.query.filter_by(
            investigation_id=investigation_id
        ).all()

        # --- Court records ---
        court_records = CourtRecord.query.filter_by(
            investigation_id=investigation_id
        ).all()

        # --- Connections ---
        connections = Connection.query.filter_by(
            investigation_id=investigation_id
        ).all()

        # --- Parse JSON fields ---
        phones = _safe_json(investigation.discovered_phones, [])
        emails = _safe_json(investigation.discovered_emails, [])
        aliases = _safe_json(investigation.discovered_usernames, [])
        risk_indicators = _safe_json(investigation.risk_indicators, [])
        enforcement_records = _safe_json(investigation.property_records, [])
        group_memberships = _safe_json(investigation.group_memberships, [])
        phase1_stats = _safe_json(investigation.phase1_stats, {})

        # --- Normalize phones ---
        phones_normalized = []
        for p in phones:
            if isinstance(p, dict):
                entry = {
                    'number': p.get('number', p.get('phone', '')),
                    'source': p.get('source', ''),
                    'confidence': p.get('confidence', 'medium'),
                }
                if entry['number']:
                    phones_normalized.append(entry)
            elif isinstance(p, str) and p.strip():
                phones_normalized.append({
                    'number': p.strip(),
                    'source': '',
                    'confidence': 'medium',
                })

        # --- Normalize emails ---
        emails_normalized = []
        for e in emails:
            if isinstance(e, dict):
                entry = {
                    'email': e.get('email', ''),
                    'source': e.get('source', ''),
                    'confidence': e.get('confidence', 'medium'),
                    'services': e.get('services', []),
                }
                if entry['email']:
                    emails_normalized.append(entry)
            elif isinstance(e, str) and e.strip():
                emails_normalized.append({
                    'email': e.strip(),
                    'source': '',
                    'confidence': 'medium',
                    'services': [],
                })

        # --- Build profiles list ---
        profiles_list = []
        seen_ids = set()
        for p in confirmed_profiles:
            key = f"{p.platform}_{p.platform_id}"
            if key not in seen_ids:
                seen_ids.add(key)
                profiles_list.append({
                    'platform': p.platform,
                    'username': p.username or p.platform_id,
                    'full_name': p.full_name,
                    'url': p.profile_url or f"https://vk.com/id{p.platform_id}",
                    'photo_url': p.photo_url,
                    'is_confirmed': True,
                    'city': p.city,
                    'birth_date': p.birth_date,
                    'age': p.age,
                    'gender': p.gender,
                    'education': p.education,
                    'career': p.career,
                    'friends_count': p.friends_count,
                    'followers_count': p.followers_count,
                    'bio': p.bio,
                    'confidence_score': p.confidence_score,
                })

        for p in all_profiles:
            if p.is_confirmed or p.is_rejected:
                continue
            key = f"{p.platform}_{p.platform_id}"
            if key not in seen_ids:
                seen_ids.add(key)
                profiles_list.append({
                    'platform': p.platform,
                    'username': p.username or p.platform_id,
                    'full_name': p.full_name,
                    'url': p.profile_url or f"https://vk.com/id{p.platform_id}",
                    'photo_url': p.photo_url,
                    'is_confirmed': False,
                    'city': p.city,
                    'birth_date': p.birth_date,
                    'age': p.age,
                    'gender': p.gender,
                    'education': p.education,
                    'career': p.career,
                    'friends_count': p.friends_count,
                    'followers_count': p.followers_count,
                    'bio': p.bio,
                    'confidence_score': p.confidence_score,
                })

        # --- Friends sample ---
        friends_sample = []
        for f in friends_sorted[:15]:
            friends_sample.append({
                'name': f.full_name,
                'platform': f.platform,
                'url': f.profile_url or '',
                'city': f.city or '',
                'community_id': f.community_id,
                'centrality_score': f.centrality_score,
                'is_flagged': f.is_flagged,
            })

        # --- Confidence ---
        confidence = 0
        if profiles_list:
            confirmed_count = sum(1 for p in profiles_list if p.get('is_confirmed'))
            confidence += min(30, 10 + confirmed_count * 10)
        if phones_normalized:
            confidence += min(15, len(phones_normalized) * 5)
        if emails_normalized:
            confidence += min(15, len(emails_normalized) * 5)
        if business_records:
            confidence += min(15, len(business_records) * 3)
        if court_records:
            confidence += 5
        if friends:
            confidence += min(5, len(friends) // 10)
        if confirmed_profile and confirmed_profile.photo_url:
            confidence += 10
        if confirmed_profile and confirmed_profile.city:
            confidence += 5
        confidence = min(100, confidence)

        # --- Risk assessment ---
        high_risks = sum(1 for r in risk_indicators if r.get('severity') in ('high', 'critical'))
        med_risks = sum(1 for r in risk_indicators if r.get('severity') == 'medium')
        if high_risks > 0:
            risk_level = 'high'
            risk_label = 'ВЫСОКИЙ'
        elif med_risks > 0:
            risk_level = 'medium'
            risk_label = 'СРЕДНИЙ'
        elif risk_indicators:
            risk_level = 'low'
            risk_label = 'НИЗКИЙ'
        else:
            risk_level = 'none'
            risk_label = 'НЕ ВЫЯВЛЕН'

        # --- Executive summary ---
        summary = self._generate_executive_summary(
            investigation=investigation,
            confirmed_profile=confirmed_profile,
            profiles_count=len(profiles_list),
            phones_count=len(phones_normalized),
            emails_count=len(emails_normalized),
            business_count=len(business_records),
            court_count=len(court_records),
            friends_count=len(friends),
            risk_level=risk_level,
            confidence=confidence,
        )

        # --- Timeline ---
        timeline = self._build_timeline(
            investigation=investigation,
            confirmed_profile=confirmed_profile,
            profiles=all_profiles,
            friends=friends,
            business_records=business_records,
            court_records=court_records,
        )

        # --- Methodology ---
        methodology = self._build_methodology(
            investigation=investigation,
            has_profiles=bool(profiles_list),
            has_phones=bool(phones_normalized),
            has_emails=bool(emails_normalized),
            has_business=bool(business_records),
            has_court=bool(court_records),
            has_friends=bool(friends),
            has_enforcement=bool(enforcement_records),
        )

        # Active business count
        active_business = sum(1 for b in business_records if b.is_active)

        return {
            'investigation': investigation,
            'investigation_id': investigation_id,
            'target_name': investigation.input_name,
            'status': investigation.status,
            'created_at': investigation.created_at,
            'confirmed_profile': confirmed_profile,
            'profiles': profiles_list,
            'all_profiles': all_profiles,
            'phones': phones_normalized,
            'emails': emails_normalized,
            'aliases': aliases,
            'business_records': business_records,
            'active_business_count': active_business,
            'court_records': court_records,
            'enforcement_records': enforcement_records,
            'group_memberships': group_memberships,
            'friends': friends,
            'friends_sample': friends_sample,
            'friends_count': len(friends),
            'connections': connections,
            'risk_indicators': risk_indicators,
            'risk_level': risk_level,
            'risk_label': risk_label,
            'confidence': confidence,
            'summary': summary,
            'timeline': timeline,
            'methodology': methodology,
            'generated_at': datetime.now(),
        }

    def _generate_executive_summary(self, investigation, confirmed_profile,
                                     profiles_count, phones_count, emails_count,
                                     business_count, court_count, friends_count,
                                     risk_level, confidence):
        """Generate executive summary text."""
        name = investigation.input_name or 'Объект'
        lines = []

        # Opening
        lines.append(
            f'В ходе расследования проведён комплексный анализ цифрового следа '
            f'объекта "{name}".'
        )

        # Profiles
        if confirmed_profile:
            platform_names = {'vk': 'ВКонтакте', 'ok': 'Одноклассники', 'telegram': 'Telegram'}
            platform = platform_names.get(
                confirmed_profile.platform, confirmed_profile.platform or 'социальной сети'
            )
            city_part = f', г. {confirmed_profile.city}' if confirmed_profile.city else ''
            lines.append(
                f'Подтверждён профиль в {platform}{city_part}. '
                f'Всего обнаружено {profiles_count} профил(ей/я) в социальных сетях.'
            )

        # Contacts
        contact_parts = []
        if phones_count:
            contact_parts.append(f'{phones_count} телефонн(ый/ых) номер(а/ов)')
        if emails_count:
            contact_parts.append(f'{emails_count} адрес(а/ов) электронной почты')
        if contact_parts:
            lines.append(f'Обнаружено {" и ".join(contact_parts)}.')

        # Business
        if business_count:
            lines.append(
                f'Выявлено {business_count} связ(ь/ей) с юридическими лицами в реестре ЕГРЮЛ.'
            )

        # Court
        if court_count:
            lines.append(f'Обнаружено {court_count} судебн(ое/ых) дел(о/а).')

        # Social
        if friends_count:
            lines.append(f'Проанализирован социальный граф: {friends_count} связей.')

        # Risk
        risk_texts = {
            'high': 'Выявлен ВЫСОКИЙ уровень риска.',
            'medium': 'Выявлен СРЕДНИЙ уровень риска.',
            'low': 'Уровень риска оценивается как НИЗКИЙ.',
            'none': 'Значимых факторов риска не выявлено.',
        }
        lines.append(risk_texts.get(risk_level, ''))

        # Confidence
        lines.append(f'Общая достоверность собранных данных: {confidence}%.')

        return ' '.join(lines)

    def _build_timeline(self, investigation, confirmed_profile, profiles,
                        friends, business_records, court_records):
        """Build investigation timeline."""
        events = []

        # Investigation created
        if investigation.created_at:
            events.append({
                'date': investigation.created_at,
                'label': 'Начало расследования',
                'detail': f'Создано расследование: {investigation.input_name}',
                'phase': 1,
            })

        # Profiles discovered
        for p in profiles:
            if p.discovered_at:
                events.append({
                    'date': p.discovered_at,
                    'label': f'Обнаружен профиль ({p.platform})',
                    'detail': f'{p.full_name} - {p.profile_url or ""}',
                    'phase': 1,
                })

        # Profile confirmed
        if confirmed_profile and confirmed_profile.confirmed_at:
            events.append({
                'date': confirmed_profile.confirmed_at,
                'label': 'Профиль подтверждён',
                'detail': f'{confirmed_profile.full_name} ({confirmed_profile.platform})',
                'phase': 1,
            })

        # Friends discovered (aggregate)
        if friends:
            earliest = min((f.discovered_at for f in friends if f.discovered_at), default=None)
            if earliest:
                events.append({
                    'date': earliest,
                    'label': 'Анализ социального графа',
                    'detail': f'Обнаружено {len(friends)} связей',
                    'phase': 2,
                })

        # Business records
        for br in business_records:
            if br.discovered_at:
                events.append({
                    'date': br.discovered_at,
                    'label': 'Найдена запись ЕГРЮЛ',
                    'detail': f'{br.company_name or br.short_name} (ИНН: {br.inn or "н/д"})',
                    'phase': 3,
                })
                break  # Just first one to avoid clutter

        if business_records:
            events.append({
                'date': business_records[0].discovered_at or investigation.updated_at,
                'label': f'Реестр ЕГРЮЛ',
                'detail': f'Найдено {len(business_records)} записей',
                'phase': 3,
            })

        # Court records
        if court_records:
            events.append({
                'date': court_records[0].discovered_at or investigation.updated_at,
                'label': f'Судебные дела',
                'detail': f'Найдено {len(court_records)} дел',
                'phase': 3,
            })

        # Sort by date
        events.sort(key=lambda e: e['date'] if e['date'] else datetime.min)

        # Deduplicate
        seen = set()
        unique_events = []
        for e in events:
            key = e['label']
            if key not in seen:
                seen.add(key)
                unique_events.append(e)

        return unique_events

    def _build_methodology(self, investigation, has_profiles, has_phones,
                           has_emails, has_business, has_court, has_friends,
                           has_enforcement):
        """Build methodology section listing tools and sources used."""
        methods = []

        methods.append({
            'tool': 'VK People Search API',
            'description': 'Поиск профилей в социальной сети ВКонтакте по имени',
            'used': has_profiles,
        })
        methods.append({
            'tool': 'Fuzzy Name Matching',
            'description': 'Нечёткое сопоставление имён с учётом уменьшительных форм и транслитерации',
            'used': has_profiles,
        })
        methods.append({
            'tool': 'VK API (users.get, wall.get)',
            'description': 'Извлечение контактной информации и данных профиля из VK API',
            'used': has_phones or has_emails,
        })
        methods.append({
            'tool': 'Holehe',
            'description': 'Проверка регистрации email на 120+ сервисах',
            'used': has_emails,
        })
        methods.append({
            'tool': 'SMTP RCPT TO',
            'description': 'Валидация существования адресов электронной почты',
            'used': has_emails,
        })
        methods.append({
            'tool': 'Gravatar API',
            'description': 'Проверка привязки аватара к email',
            'used': has_emails,
        })
        methods.append({
            'tool': 'NetworkX + Louvain',
            'description': 'Анализ социального графа и выявление сообществ',
            'used': has_friends,
        })
        methods.append({
            'tool': 'ФНС ЕГРЮЛ (nalog.ru)',
            'description': 'Поиск в реестре юридических лиц и индивидуальных предпринимателей',
            'used': has_business,
        })
        methods.append({
            'tool': 'Судебные акты (sudact.ru)',
            'description': 'Поиск судебных дел и решений',
            'used': has_court,
        })
        methods.append({
            'tool': 'ФССП России',
            'description': 'Проверка исполнительных производств',
            'used': has_enforcement,
        })

        return methods

    def generate_json(self, investigation_id: str) -> Dict:
        """Generate JSON export of dossier data."""
        dossier = self.generate_dossier(investigation_id)
        if 'error' in dossier:
            return dossier

        inv = dossier['investigation']

        export = {
            'meta': {
                'investigation_id': investigation_id,
                'target_name': dossier['target_name'],
                'status': dossier['status'],
                'created_at': inv.created_at.isoformat() if inv.created_at else None,
                'generated_at': datetime.now().isoformat(),
                'confidence': dossier['confidence'],
                'risk_level': dossier['risk_level'],
                'source': 'IBP - Identity-Based Profiler',
            },
            'executive_summary': dossier['summary'],
            'personal_data': {
                'name': dossier['target_name'],
                'aliases': dossier['aliases'],
                'photo_url': dossier['confirmed_profile'].photo_url if dossier['confirmed_profile'] else None,
                'city': dossier['confirmed_profile'].city if dossier['confirmed_profile'] else None,
                'birth_date': dossier['confirmed_profile'].birth_date if dossier['confirmed_profile'] else None,
                'age': dossier['confirmed_profile'].age if dossier['confirmed_profile'] else None,
                'gender': dossier['confirmed_profile'].gender if dossier['confirmed_profile'] else None,
            },
            'profiles': dossier['profiles'],
            'contacts': {
                'phones': dossier['phones'],
                'emails': dossier['emails'],
            },
            'social_network': {
                'friends_count': dossier['friends_count'],
                'top_connections': dossier['friends_sample'],
                'group_memberships': dossier['group_memberships'],
            },
            'risk_assessment': {
                'level': dossier['risk_level'],
                'label': dossier['risk_label'],
                'indicators': dossier['risk_indicators'],
            },
            'business_records': [b.to_dict() for b in dossier['business_records']],
            'court_records': [c.to_dict() for c in dossier['court_records']],
            'enforcement_records': dossier['enforcement_records'],
            'methodology': [m for m in dossier['methodology'] if m['used']],
        }

        return export


# Singleton
dossier_generator = DossierGenerator()

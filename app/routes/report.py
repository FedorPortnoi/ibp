"""
Report Routes - Identity Card Generation & Export
=================================================
Generate and export identity cards and investigation reports.
"""

import os
import logging
from flask import Blueprint, render_template, request, jsonify, send_file, Response
from datetime import datetime
import json
import io

report_bp = Blueprint('report', __name__, url_prefix='/report')
logger = logging.getLogger(__name__)


def _safe_json_field(value, default=None):
    """Safely parse a JSON field that might be a string, list, dict, or None."""
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


@report_bp.route('/<investigation_id>')
def view(investigation_id):
    """View the generated identity card."""
    from app.models import Investigation

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Расследование не найдено'), 404

    return render_template('identity_card.html',
                         investigation_id=investigation_id,
                         investigation=investigation)


@report_bp.route('/api/investigation-data/<investigation_id>')
def get_investigation_data(investigation_id):
    """Get full investigation data for identity card generation."""
    from app.models import Investigation, SocialProfile, Friend, BusinessRecord, CourtRecord, Connection

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Расследование не найдено'}), 404

    # Get all profiles and confirmed profile
    all_profiles = SocialProfile.query.filter_by(
        investigation_id=investigation_id
    ).all()
    confirmed_profiles = [p for p in all_profiles if p.is_confirmed]
    confirmed_profile = confirmed_profiles[0] if confirmed_profiles else None

    # Get friends
    friends = Friend.query.filter_by(investigation_id=investigation_id).all()

    # Get business records from DB table
    business_records = BusinessRecord.query.filter_by(investigation_id=investigation_id).all()

    # Get court records from DB table
    court_records = CourtRecord.query.filter_by(investigation_id=investigation_id).all()

    # Get connections
    connections = Connection.query.filter_by(investigation_id=investigation_id).all()

    # Parse JSON fields safely
    phones = _safe_json_field(investigation.discovered_phones, [])
    emails = _safe_json_field(investigation.discovered_emails, [])
    aliases = _safe_json_field(investigation.discovered_usernames, [])
    risk_indicators = _safe_json_field(investigation.risk_indicators, [])
    enforcement_records = _safe_json_field(investigation.property_records, [])
    phase1_stats = _safe_json_field(investigation.phase1_stats, {})

    # Build profiles list
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
            })

    # Add non-confirmed profiles
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
            })

    # Add alternate accounts from investigation JSON
    alternate_accounts = _safe_json_field(investigation.alternate_accounts, [])
    seen_urls = {p['url'].lower() for p in profiles_list if p.get('url')}
    for acc in alternate_accounts:
        url = acc.get('url', '')
        if url and url.lower() not in seen_urls:
            profiles_list.append({
                'platform': acc.get('platform', 'unknown'),
                'username': acc.get('username', ''),
                'full_name': acc.get('full_name', ''),
                'url': url,
                'photo_url': acc.get('photo_url', ''),
                'is_confirmed': False,
            })
            seen_urls.add(url.lower())

    # Normalize phones - extract string from dict if needed
    phones_normalized = []
    for p in phones:
        if isinstance(p, dict):
            phone_str = p.get('number', p.get('phone', ''))
            if phone_str:
                phones_normalized.append(phone_str)
        elif isinstance(p, str) and p.strip():
            phones_normalized.append(p.strip())

    # Normalize emails
    emails_normalized = []
    for e in emails:
        if isinstance(e, dict):
            email_str = e.get('email', '')
            if email_str:
                emails_normalized.append(email_str)
        elif isinstance(e, str) and e.strip():
            emails_normalized.append(e.strip())

    # Friends sample (top by centrality)
    friends_sorted = sorted(friends, key=lambda f: f.centrality_score or 0, reverse=True)
    friends_sample = []
    for f in friends_sorted[:10]:
        friends_sample.append({
            'name': f.full_name,
            'platform': f.platform,
            'url': f.profile_url or '',
            'city': f.city or '',
        })

    # Connections sample
    connections_list = []
    for c in connections[:10]:
        connections_list.append(c.to_dict())

    # Calculate confidence score
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

    # Build response
    data = {
        'investigation_id': investigation_id,
        'target_name': investigation.input_name,
        'status': investigation.status,
        'created_at': investigation.created_at.isoformat() if investigation.created_at else None,
        'photo_url': confirmed_profile.photo_url if confirmed_profile else None,
        'city': confirmed_profile.city if confirmed_profile else None,
        'profiles': profiles_list,
        'all_profiles_count': len(all_profiles),
        'phones': phones_normalized,
        'emails': emails_normalized,
        'aliases': aliases,
        'business_records': [r.to_dict() for r in business_records],
        'court_records': [r.to_dict() for r in court_records],
        'enforcement_records': enforcement_records,
        'friends_count': len(friends),
        'friends_sample': friends_sample,
        'connections': connections_list,
        'risk_indicators': risk_indicators,
        'confidence_score': confidence,
        'phase1_stats': phase1_stats,
    }

    return jsonify(data)


@report_bp.route('/generate', methods=['POST'])
def generate():
    """Generate identity card HTML from investigation data."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400

        from app.services.report_generator import report_generator, IdentityCardData

        # Build card data from the API response format
        card_data = IdentityCardData(
            full_name=data.get('target_name', ''),
            aliases=data.get('aliases', []) or [],
            photo_url=data.get('photo_url', '') or '',
            profiles=data.get('profiles', []) or [],
            phones=data.get('phones', []) or [],
            emails=data.get('emails', []) or [],
            city=data.get('city', '') or '',
            companies=data.get('business_records', []) or [],
            court_cases=data.get('court_records', []) or [],
            enforcement_records=data.get('enforcement_records', []) or [],
            social_connections=data.get('friends_sample', []) or [],
            friends_count=data.get('friends_count', 0) or 0,
            risk_indicators=data.get('risk_indicators', []) or [],
            investigation_id=data.get('investigation_id', ''),
            confidence_score=data.get('confidence_score', 0),
            generated_at=datetime.now().isoformat(),
        )

        # Generate HTML
        html_content = report_generator.generate_identity_card_html(card_data)

        return jsonify({
            'success': True,
            'html': html_content,
            'confidence_score': card_data.confidence_score
        })

    except Exception as e:
        logger.error(f"Report generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@report_bp.route('/download/html', methods=['POST'])
def download_html():
    """Download identity card as HTML file."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400

        from app.services.report_generator import report_generator

        card_data = report_generator.compile_data(data)
        html_content = report_generator.generate_identity_card_html(card_data)

        return Response(
            html_content,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename=identity_card_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            }
        )

    except Exception as e:
        logger.error(f"HTML download error: {e}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/download/pdf', methods=['POST'])
def download_pdf():
    """Download investigation report as PDF."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400

        from app.services.report_generator import report_generator

        card_data = report_generator.compile_data(data)
        pdf_bytes = report_generator.generate_pdf_report(card_data, data)

        if not pdf_bytes:
            return jsonify({'error': 'Генерация PDF недоступна. Установите reportlab: pip install reportlab'}), 500

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=investigation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            }
        )

    except Exception as e:
        logger.error(f"PDF download error: {e}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/download/json', methods=['POST'])
def download_json():
    """Download investigation data as JSON."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400

        # Build clean export (strip internal IDs, keep useful data)
        export_data = {
            'investigation_id': data.get('investigation_id', ''),
            'target_name': data.get('target_name', ''),
            'status': data.get('status', ''),
            'created_at': data.get('created_at', ''),
            'photo_url': data.get('photo_url', ''),
            'city': data.get('city', ''),
            'profiles': data.get('profiles', []),
            'phones': data.get('phones', []),
            'emails': data.get('emails', []),
            'aliases': data.get('aliases', []),
            'business_records': data.get('business_records', []),
            'court_records': data.get('court_records', []),
            'enforcement_records': data.get('enforcement_records', []),
            'risk_indicators': data.get('risk_indicators', []),
            'friends_count': data.get('friends_count', 0),
            'friends_sample': data.get('friends_sample', []),
            'confidence_score': data.get('confidence_score', 0),
            'generated_at': datetime.now().isoformat(),
            'source': 'IBP - Identity-Based Profiler'
        }

        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)

        return Response(
            json_str,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=investigation_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )

    except Exception as e:
        logger.error(f"JSON download error: {e}")
        return jsonify({'error': str(e)}), 500

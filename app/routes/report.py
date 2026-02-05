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


@report_bp.route('/<investigation_id>')
def view(investigation_id):
    """View the generated identity card."""
    from app.models import Investigation, SocialProfile, Friend, BusinessRecord, CourtRecord

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Investigation not found'), 404

    # Get confirmed profile
    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    # Get friends
    friends = Friend.query.filter_by(investigation_id=investigation_id).all()

    # Get business records
    business_records = BusinessRecord.query.filter_by(investigation_id=investigation_id).all()

    # Get court records
    court_records = CourtRecord.query.filter_by(investigation_id=investigation_id).all()

    return render_template('identity_card.html',
                         investigation_id=investigation_id,
                         investigation=investigation,
                         profile=confirmed_profile,
                         friends=friends,
                         business_records=business_records,
                         court_records=court_records)


@report_bp.route('/api/investigation-data/<investigation_id>')
def get_investigation_data(investigation_id):
    """Get full investigation data for identity card generation."""
    from app.models import Investigation, SocialProfile, Friend, BusinessRecord, CourtRecord

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Investigation not found'}), 404

    # Get confirmed profile
    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    # Get friends
    friends = Friend.query.filter_by(investigation_id=investigation_id).all()

    # Get business records
    business_records = BusinessRecord.query.filter_by(investigation_id=investigation_id).all()

    # Get court records
    court_records = CourtRecord.query.filter_by(investigation_id=investigation_id).all()

    # Build response
    data = {
        'investigation_id': investigation_id,
        'target_name': investigation.input_name,
        'status': investigation.status,
        'photo_url': confirmed_profile.photo_url if confirmed_profile else None,
        'city': confirmed_profile.city if confirmed_profile else None,
        'profiles': [],
        'phones': investigation.discovered_phones or [],
        'emails': investigation.discovered_emails or [],
        'aliases': investigation.discovered_usernames or [],
        'business_records': [r.to_dict() for r in business_records],
        'court_records': [r.to_dict() for r in court_records],
        'friends_count': len(friends),
    }

    # Add confirmed profile
    if confirmed_profile:
        data['profiles'].append({
            'platform': confirmed_profile.platform,
            'username': confirmed_profile.username or confirmed_profile.platform_id,
            'full_name': confirmed_profile.full_name,
            'url': f"https://vk.com/id{confirmed_profile.platform_id}",
            'photo_url': confirmed_profile.photo_url
        })

    return jsonify(data)


@report_bp.route('/generate', methods=['POST'])
def generate():
    """
    Generate identity card from investigation data.

    Request body:
    {
        "investigation_id": "...",
        "target_name": "...",
        "profiles": [...],
        "phones": [...],
        "emails": [...],
        "business_records": [...],
        "court_records": [...],
        ...
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        from app.services.report_generator import report_generator, IdentityCardData

        # Create IdentityCardData from request
        card_data = IdentityCardData(
            full_name=data.get('target_name', '') or data.get('input_name', ''),
            aliases=data.get('aliases', []) or data.get('discovered_usernames', []),
            photo_url=data.get('photo_url', '') or data.get('input_photo_path', ''),
            profiles=data.get('profiles', []) or data.get('discovered_profiles', []),
            phones=data.get('phones', []) or data.get('discovered_phones', []),
            emails=data.get('emails', []) or data.get('discovered_emails', []),
            city=data.get('city', ''),
            companies=data.get('business_records', []),
            court_cases=data.get('court_records', []),
            investigation_id=data.get('investigation_id', ''),
            generated_at=datetime.now().isoformat()
        )

        # Calculate confidence
        confidence = 0
        if card_data.profiles:
            confidence += 20
        if card_data.phones:
            confidence += 20
        if card_data.emails:
            confidence += 15
        if card_data.companies:
            confidence += 20
        if card_data.photo_url:
            confidence += 10
        if card_data.city:
            confidence += 15
        card_data.confidence_score = min(100, confidence)

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


@report_bp.route('/generate/<investigation_id>', methods=['POST'])
def generate_from_investigation(investigation_id):
    """Generate report from stored investigation."""
    try:
        from app import db
        from app.models.investigation import Investigation
        from app.services.report_generator import report_generator

        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            return jsonify({'error': 'Investigation not found'}), 404

        # Compile data
        card_data = report_generator.compile_data(investigation.to_dict())

        # Generate HTML
        html_content = report_generator.generate_identity_card_html(card_data)

        # Update investigation
        investigation.identity_card_generated = True
        db.session.commit()

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
            return jsonify({'error': 'No data provided'}), 400

        from app.services.report_generator import report_generator

        card_data = report_generator.compile_data(data)
        html_content = report_generator.generate_identity_card_html(card_data)

        # Create file response
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
            return jsonify({'error': 'No data provided'}), 400

        from app.services.report_generator import report_generator

        card_data = report_generator.compile_data(data)
        pdf_bytes = report_generator.generate_pdf_report(card_data, data)

        if not pdf_bytes:
            return jsonify({'error': 'PDF generation not available'}), 500

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
            return jsonify({'error': 'No data provided'}), 400

        # Clean sensitive data
        export_data = {
            'target_name': data.get('target_name', '') or data.get('input_name', ''),
            'profiles': data.get('profiles', []) or data.get('discovered_profiles', []),
            'phones': data.get('phones', []) or data.get('discovered_phones', []),
            'emails': data.get('emails', []) or data.get('discovered_emails', []),
            'business_records': data.get('business_records', []),
            'court_records': data.get('court_records', []),
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


@report_bp.route('/download/<investigation_id>/<format>')
def download(investigation_id, format):
    """Download identity card/report in specified format."""
    try:
        from app import db
        from app.models.investigation import Investigation
        from app.services.report_generator import report_generator

        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            return jsonify({'error': 'Investigation not found'}), 404

        data = investigation.to_dict()
        card_data = report_generator.compile_data(data)

        if format == 'html':
            html_content = report_generator.generate_identity_card_html(card_data)
            return Response(
                html_content,
                mimetype='text/html',
                headers={
                    'Content-Disposition': f'attachment; filename=identity_card_{investigation_id[:8]}.html'
                }
            )

        elif format == 'pdf':
            pdf_bytes = report_generator.generate_pdf_report(card_data, data)
            if not pdf_bytes:
                return jsonify({'error': 'PDF generation not available'}), 500

            return Response(
                pdf_bytes,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=report_{investigation_id[:8]}.pdf'
                }
            )

        elif format == 'json':
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            return Response(
                json_str,
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename=data_{investigation_id[:8]}.json'
                }
            )

        else:
            return jsonify({'error': f'Unknown format: {format}'}), 400

    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500


@report_bp.route('/preview', methods=['POST'])
def preview():
    """Preview identity card (returns rendered HTML)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        from app.services.report_generator import report_generator

        card_data = report_generator.compile_data(data)
        html_content = report_generator.generate_identity_card_html(card_data)

        return html_content, 200, {'Content-Type': 'text/html'}

    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({'error': str(e)}), 500

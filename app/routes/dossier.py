"""
Dossier Routes - Professional Investigation Dossier
====================================================
View and export professional investigation dossiers.
"""

import logging
import json
from datetime import datetime
from flask import Blueprint, render_template, jsonify, Response

from app import limiter

dossier_bp = Blueprint('dossier', __name__, url_prefix='/dossier')
logger = logging.getLogger(__name__)


@dossier_bp.route('/<investigation_id>')
def view(investigation_id):
    """View professional dossier for an investigation."""
    from app.services.dossier_generator import dossier_generator

    dossier = dossier_generator.generate_dossier(investigation_id)
    if 'error' in dossier:
        return render_template('error.html', error=dossier['error']), 404

    return render_template('dossier.html', **dossier)


@dossier_bp.route('/<investigation_id>/json')
@limiter.limit("5 per minute")
def export_json(investigation_id):
    """Export dossier as JSON."""
    from app.services.dossier_generator import dossier_generator

    try:
        data = dossier_generator.generate_json(investigation_id)
        if 'error' in data:
            return jsonify(data), 404

        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)

        return Response(
            json_str,
            mimetype='application/json',
            headers={
                'Content-Disposition': (
                    f'attachment; filename=dossier_{investigation_id[:8]}'
                    f'_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                )
            }
        )
    except Exception as e:
        logger.error(f"Dossier JSON export error: {e}", exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@dossier_bp.route('/<investigation_id>/pdf')
@limiter.limit("5 per minute")
def export_pdf(investigation_id):
    """Export dossier as PDF (Playwright or print-ready HTML fallback)."""
    from app.services.dossier_generator import dossier_generator

    dossier = dossier_generator.generate_dossier(investigation_id)
    if 'error' in dossier:
        return jsonify(dossier), 404

    # Try WeasyPrint
    try:
        import weasyprint
        html_content = render_template('dossier.html', print_mode=True, **dossier)
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': (
                    f'attachment; filename=dossier_{investigation_id[:8]}'
                    f'_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                )
            }
        )
    except ImportError:
        logger.info("WeasyPrint not available, returning print-ready HTML")
    except Exception as e:
        logger.warning(f"WeasyPrint PDF generation failed: {e}")

    # Fallback: render print-ready HTML page with auto-print
    html_content = render_template('dossier.html', print_mode=True, **dossier)
    return Response(
        html_content,
        mimetype='text/html',
        headers={
            'Content-Disposition': (
                f'inline; filename=dossier_{investigation_id[:8]}'
                f'_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            )
        }
    )

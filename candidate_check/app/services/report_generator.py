"""
Report Generator - Identity Card & PDF Export
==============================================
Generate professional identity cards and investigation reports.
"""

import logging
import os
import json
import base64
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import io
import html as html_module

logger = logging.getLogger(__name__)


@dataclass
class IdentityCardData:
    """Data for identity card generation."""
    # Basic info
    full_name: str = ""
    aliases: List[str] = field(default_factory=list)
    photo_url: str = ""

    # Social profiles (Phase 1)
    profiles: List[Dict] = field(default_factory=list)

    # Contact info (Phase 2)
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)

    # Location
    city: str = ""
    country: str = "Russia"

    # Business (Phase 3)
    companies: List[Dict] = field(default_factory=list)
    court_cases: List[Dict] = field(default_factory=list)
    enforcement_records: List[Dict] = field(default_factory=list)

    # Social graph
    social_connections: List[Dict] = field(default_factory=list)
    friends_count: int = 0
    risk_indicators: List[Dict] = field(default_factory=list)

    # Analysis
    overall_risk: str = "low"

    # Phase stats
    phase1_stats: Dict = field(default_factory=dict)
    phase2_stats: Dict = field(default_factory=dict)
    phase3_stats: Dict = field(default_factory=dict)

    # Metadata
    investigation_id: str = ""
    generated_at: str = ""
    confidence_score: float = 0.0


def _esc(text):
    """HTML-escape a string for safe embedding."""
    if not text:
        return ""
    return html_module.escape(str(text))


class ReportGenerator:
    """Generate identity cards and reports from investigation data."""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'reports'
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def compile_data(self, investigation: Dict) -> IdentityCardData:
        """Compile investigation data dict into IdentityCardData."""
        data = IdentityCardData()

        data.full_name = investigation.get('target_name', '') or investigation.get('input_name', '')
        data.investigation_id = investigation.get('investigation_id', '') or investigation.get('id', '')
        data.generated_at = datetime.now().isoformat()
        data.photo_url = investigation.get('photo_url', '') or ''
        data.city = investigation.get('city', '') or ''

        # Profiles
        profiles = investigation.get('profiles', [])
        if isinstance(profiles, str):
            try:
                profiles = json.loads(profiles)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse profiles JSON: {e}")
                profiles = []
        data.profiles = profiles[:10]

        # Aliases
        aliases = investigation.get('aliases', []) or investigation.get('discovered_usernames', [])
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse aliases JSON: {e}")
                aliases = []
        data.aliases = list(set(aliases))[:10]

        # Phones
        phones = investigation.get('phones', []) or investigation.get('discovered_phones', [])
        if isinstance(phones, str):
            try:
                phones = json.loads(phones)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse phones JSON: {e}")
                phones = []
        data.phones = [p.get('number', p) if isinstance(p, dict) else str(p) for p in phones][:5]

        # Emails
        emails = investigation.get('emails', []) or investigation.get('discovered_emails', [])
        if isinstance(emails, str):
            try:
                emails = json.loads(emails)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse emails JSON: {e}")
                emails = []
        data.emails = [e.get('email', e) if isinstance(e, dict) else str(e) for e in emails][:5]

        # Business records
        business = investigation.get('business_records', [])
        if isinstance(business, str):
            try:
                business = json.loads(business)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse business JSON: {e}")
                business = []
        data.companies = business

        # Court cases
        courts = investigation.get('court_records', [])
        if isinstance(courts, str):
            try:
                courts = json.loads(courts)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse courts JSON: {e}")
                courts = []
        data.court_cases = courts

        # Enforcement records
        enforcement = investigation.get('enforcement_records', []) or investigation.get('property_records', [])
        if isinstance(enforcement, str):
            try:
                enforcement = json.loads(enforcement)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse enforcement JSON: {e}")
                enforcement = []
        data.enforcement_records = enforcement

        # Social connections
        connections = investigation.get('friends_sample', []) or investigation.get('social_connections', [])
        if isinstance(connections, str):
            try:
                connections = json.loads(connections)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse connections JSON: {e}")
                connections = []
        data.social_connections = connections[:10]
        data.friends_count = investigation.get('friends_count', 0) or 0

        # Risk indicators
        risks = investigation.get('risk_indicators', [])
        if isinstance(risks, str):
            try:
                risks = json.loads(risks)
            except Exception as e:
                logger.debug(f"[ReportGenerator] Failed to parse risks JSON: {e}")
                risks = []
        data.risk_indicators = risks

        # Confidence
        data.confidence_score = investigation.get('confidence_score', 0) or 0

        # If confidence not pre-calculated, calculate it
        if data.confidence_score == 0:
            confidence = 0
            if data.profiles:
                confidence += min(30, 10 + len(data.profiles) * 5)
            if data.phones:
                confidence += min(15, len(data.phones) * 5)
            if data.emails:
                confidence += min(15, len(data.emails) * 5)
            if data.companies:
                confidence += min(15, len(data.companies) * 3)
            if data.court_cases:
                confidence += 5
            if data.photo_url:
                confidence += 10
            if data.city:
                confidence += 5
            data.confidence_score = min(100, confidence)

        return data

    def generate_identity_card_html(self, data: IdentityCardData) -> str:
        """Generate self-contained HTML identity card with dark theme."""

        # Platform icons
        platform_icons = {
            'vk': ('VK', '#4A76A8'),
            'vkontakte': ('VK', '#4A76A8'),
            'telegram': ('TG', '#0088cc'),
            'ok': ('OK', '#EE8208'),
            'odnoklassniki': ('OK', '#EE8208'),
            'instagram': ('IG', '#E1306C'),
            'facebook': ('FB', '#1877F2'),
            'twitter': ('TW', '#1DA1F2'),
        }

        # Build sections HTML
        # -- Profiles --
        profiles_html = ""
        for p in data.profiles[:6]:
            platform = (p.get('platform', 'unknown') or 'unknown').lower()
            icon_label, icon_color = platform_icons.get(platform, ('@', '#888'))
            url = _esc(p.get('url', '#'))
            username = _esc(p.get('username', 'unknown'))
            confirmed = p.get('is_confirmed', False)
            confirm_badge = ' <span style="color:#22c55e;font-size:10px;">&#10003;</span>' if confirmed else ''
            profiles_html += f'''
            <a href="{url}" target="_blank" rel="noopener" class="profile-link">
                <span style="color:{icon_color};font-weight:600;font-size:13px;">{icon_label}</span>
                <span class="username">{username}{confirm_badge}</span>
            </a>
            '''

        # -- Contacts --
        contacts_html = ""
        for phone in data.phones[:4]:
            contacts_html += f'<div class="contact-item"><span class="label">TEL</span> {_esc(phone)}</div>'
        for email in data.emails[:4]:
            contacts_html += f'<div class="contact-item"><span class="label">EMAIL</span> {_esc(email)}</div>'

        # -- Business --
        business_html = ""
        for company in data.companies[:5]:
            name = _esc(company.get('company_name', '') or company.get('short_name', 'Unknown'))
            role = _esc(company.get('role', ''))
            inn = _esc(company.get('inn', ''))
            status = company.get('status', '')
            status_color = '#22c55e' if status and ('действ' in status.lower() or 'active' in status.lower()) else '#ef4444' if status and ('ликвид' in status.lower()) else '#888'
            status_text = _esc(status) if status else ''
            inn_text = f' <span style="color:rgba(255,255,255,0.4);font-size:10px;">INN {inn}</span>' if inn else ''
            status_badge = f' <span style="color:{status_color};font-size:10px;">{status_text}</span>' if status_text else ''
            business_html += f'''
            <div class="business-item">
                <span class="company-name">{name}{inn_text}</span>
                <span class="role">{role}{status_badge}</span>
            </div>
            '''

        # -- Court cases --
        court_html = ""
        for case in data.court_cases[:5]:
            case_num = _esc(case.get('case_number', '') or 'N/A')
            court_name = _esc(case.get('court_name', ''))
            category = _esc(case.get('category_display', '') or case.get('category', ''))
            source_url = case.get('source_url', '')
            link = f' <a href="{_esc(source_url)}" target="_blank" rel="noopener" style="color:rgba(139,92,246,0.7);font-size:10px;text-decoration:none;">[link]</a>' if source_url else ''
            court_html += f'''
            <div class="court-item">
                <span class="case-number">{case_num}{link}</span>
                <span class="court-name">{court_name}</span>
                <span class="case-type">{category}</span>
            </div>
            '''

        # -- Enforcement --
        enforcement_html = ""
        for proc in data.enforcement_records[:5]:
            debtor = _esc(proc.get('debtor_name', ''))
            amount = proc.get('amount', '')
            status = _esc(proc.get('status', ''))
            dept = _esc(proc.get('department', ''))
            amount_text = f' <span style="color:#eab308;font-weight:500;">{_esc(str(amount))} RUB</span>' if amount else ''
            enforcement_html += f'''
            <div class="enforcement-item">
                <span class="debtor">{debtor}{amount_text}</span>
                <span class="dept">{status} {dept}</span>
            </div>
            '''

        # -- Risk indicators --
        risks_html = ""
        risk_colors = {'critical': '#dc2626', 'high': '#ef4444', 'medium': '#eab308', 'low': '#22c55e'}
        for risk in data.risk_indicators[:5]:
            severity = risk.get('severity', 'low')
            color = risk_colors.get(severity, '#888')
            description = _esc(risk.get('description', ''))
            category = _esc(risk.get('category', '')).upper()
            risks_html += f'''
            <div class="risk-item" style="border-left: 3px solid {color}">
                <span class="risk-category">{category}</span>
                <span class="risk-desc">{description}</span>
            </div>
            '''

        # -- Social connections --
        connections_html = ""
        for conn in data.social_connections[:5]:
            name = _esc(conn.get('name', 'Unknown'))
            platform = _esc(conn.get('platform', ''))
            city = _esc(conn.get('city', ''))
            detail = f"{platform}" + (f", {city}" if city else "")
            connections_html += f'''
            <div class="connection-item">
                <span class="conn-name">{name}</span>
                <span class="conn-rel">{detail}</span>
            </div>
            '''

        # Photo
        if data.photo_url:
            photo_html = f'<img src="{_esc(data.photo_url)}" alt="Photo" class="photo" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"><div class="photo-placeholder" style="display:none"><span>NO PHOTO</span></div>'
        else:
            photo_html = '<div class="photo-placeholder"><span>NO PHOTO</span></div>'

        # Confidence color
        if data.confidence_score >= 70:
            confidence_color = "#22c55e"
        elif data.confidence_score >= 40:
            confidence_color = "#eab308"
        else:
            confidence_color = "#ef4444"

        # Overall risk
        high_risks = sum(1 for r in data.risk_indicators if r.get('severity') in ('high', 'critical'))
        med_risks = sum(1 for r in data.risk_indicators if r.get('severity') == 'medium')
        if high_risks > 0:
            risk_label = "HIGH RISK"
            risk_color = "#ef4444"
        elif med_risks > 0:
            risk_label = "MEDIUM RISK"
            risk_color = "#eab308"
        elif data.risk_indicators:
            risk_label = "LOW RISK"
            risk_color = "#22c55e"
        else:
            risk_label = "NO FLAGS"
            risk_color = "#22c55e"

        # Aliases HTML
        aliases_html = ""
        if data.aliases:
            aliases_items = ''.join(f'<span class="alias">@{_esc(a)}</span>' for a in data.aliases[:5])
            aliases_html = f'<div class="aliases">{aliases_items}</div>'

        # Location HTML
        location_html = f'<div class="location">{_esc(data.city)}</div>' if data.city else ''

        # Friends count
        friends_text = f"{data.friends_count} connections" if data.friends_count else ""

        # Build final card
        html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IBP Identity Card - {_esc(data.full_name)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            background: linear-gradient(135deg, #030014 0%, #0a0618 50%, #110a1f 100%);
            min-height: 100vh;
            display: flex;
            align-items: flex-start;
            justify-content: center;
            padding: 30px 20px;
            font-family: 'Inter', sans-serif;
        }}

        .card {{
            width: 100%;
            max-width: 540px;
            background: linear-gradient(180deg, rgba(139, 92, 246, 0.1) 0%, rgba(17, 10, 31, 0.95) 15%);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 0 60px rgba(139, 92, 246, 0.15), 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}

        .card-header {{
            background: linear-gradient(90deg, #7c3aed 0%, #a855f7 50%, #ec4899 100%);
            padding: 14px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .logo {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 18px;
            color: white;
            letter-spacing: 2px;
        }}

        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 11px;
            color: white;
            font-weight: 600;
            letter-spacing: 1px;
        }}

        .card-body {{ padding: 28px; }}

        .profile-section {{
            display: flex;
            gap: 22px;
            margin-bottom: 24px;
        }}

        .photo {{
            width: 110px;
            height: 110px;
            border-radius: 12px;
            object-fit: cover;
            border: 2px solid rgba(139, 92, 246, 0.5);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
            flex-shrink: 0;
        }}

        .photo-placeholder {{
            width: 110px;
            height: 110px;
            border-radius: 12px;
            background: rgba(139, 92, 246, 0.1);
            border: 2px dashed rgba(139, 92, 246, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}

        .photo-placeholder span {{
            color: rgba(139, 92, 246, 0.5);
            font-size: 11px;
            font-weight: 600;
        }}

        .info {{ flex: 1; min-width: 0; }}

        .name {{
            font-size: 22px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 6px;
            line-height: 1.2;
            word-wrap: break-word;
        }}

        .location {{
            color: rgba(255,255,255,0.6);
            font-size: 13px;
            margin-bottom: 10px;
        }}

        .location::before {{ content: "\\1F4CD "; }}

        .meta-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .confidence {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0,0,0,0.3);
            padding: 5px 10px;
            border-radius: 8px;
        }}

        .confidence-label {{
            font-size: 10px;
            color: rgba(255,255,255,0.5);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .confidence-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 600;
            color: {confidence_color};
        }}

        .risk-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: rgba(0,0,0,0.3);
            padding: 5px 10px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: 600;
            color: {risk_color};
            letter-spacing: 1px;
        }}

        .aliases {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }}

        .alias {{
            background: rgba(139, 92, 246, 0.15);
            color: rgba(139, 92, 246, 0.9);
            padding: 2px 9px;
            border-radius: 12px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }}

        .section {{ margin-bottom: 22px; }}

        .section-title {{
            font-size: 11px;
            color: rgba(139, 92, 246, 0.7);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
            padding-bottom: 7px;
            border-bottom: 1px solid rgba(139, 92, 246, 0.2);
        }}

        .profiles-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}

        .profile-link {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(0,0,0,0.3);
            padding: 9px 12px;
            border-radius: 8px;
            text-decoration: none;
            transition: background 0.2s;
        }}

        .profile-link:hover {{ background: rgba(139, 92, 246, 0.2); }}

        .profile-link .username {{
            color: rgba(255,255,255,0.8);
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .contact-item {{
            color: rgba(255,255,255,0.8);
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            padding: 7px 0;
            border-bottom: 1px solid rgba(139, 92, 246, 0.1);
        }}

        .contact-item:last-child {{ border-bottom: none; }}

        .contact-item .label {{
            color: rgba(139, 92, 246, 0.7);
            font-size: 10px;
            margin-right: 8px;
        }}

        .business-item, .court-item, .enforcement-item {{
            background: rgba(0,0,0,0.3);
            padding: 10px 12px;
            border-radius: 8px;
            margin-bottom: 6px;
        }}

        .business-item .company-name, .court-item .case-number, .enforcement-item .debtor {{
            display: block;
            color: rgba(255,255,255,0.9);
            font-size: 12px;
            font-weight: 500;
        }}

        .business-item .role, .court-item .court-name, .enforcement-item .dept {{
            display: block;
            color: rgba(139, 92, 246, 0.6);
            font-size: 11px;
            margin-top: 2px;
        }}

        .court-item .case-type {{
            display: block;
            color: rgba(255,255,255,0.4);
            font-size: 10px;
            margin-top: 2px;
        }}

        .risk-item {{
            background: rgba(0,0,0,0.3);
            padding: 9px 12px;
            border-radius: 8px;
            margin-bottom: 6px;
            padding-left: 15px;
        }}

        .risk-item .risk-category {{
            display: block;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(255,255,255,0.5);
            margin-bottom: 3px;
        }}

        .risk-item .risk-desc {{
            display: block;
            color: rgba(255,255,255,0.85);
            font-size: 11px;
        }}

        .connection-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 0;
            border-bottom: 1px solid rgba(139, 92, 246, 0.1);
        }}

        .connection-item:last-child {{ border-bottom: none; }}

        .connection-item .conn-name {{
            color: rgba(255,255,255,0.85);
            font-size: 12px;
        }}

        .connection-item .conn-rel {{
            color: rgba(139, 92, 246, 0.6);
            font-size: 11px;
        }}

        .card-footer {{
            background: rgba(0,0,0,0.3);
            padding: 14px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: rgba(255,255,255,0.4);
            font-family: 'JetBrains Mono', monospace;
        }}

        @media print {{
            body {{ background: white; padding: 0; }}
            .card {{ box-shadow: none; border: 1px solid #ddd; }}
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <div class="logo">IBP</div>
            <div class="badge">IDENTITY CARD</div>
        </div>

        <div class="card-body">
            <div class="profile-section">
                {photo_html}
                <div class="info">
                    <div class="name">{_esc(data.full_name) or 'Unknown'}</div>
                    {location_html}
                    <div class="meta-row">
                        <div class="confidence">
                            <span class="confidence-label">Confidence</span>
                            <span class="confidence-value">{data.confidence_score:.0f}%</span>
                        </div>
                        <div class="risk-badge">{risk_label}</div>
                    </div>
                    {aliases_html}
                </div>
            </div>

            {f"""<div class="section">
                <div class="section-title">Social Profiles</div>
                <div class="profiles-grid">{profiles_html}</div>
            </div>""" if profiles_html else ""}

            {f"""<div class="section">
                <div class="section-title">Contact Information</div>
                {contacts_html}
            </div>""" if contacts_html else ""}

            {f"""<div class="section">
                <div class="section-title">Business Affiliations ({len(data.companies)})</div>
                {business_html}
            </div>""" if business_html else ""}

            {f"""<div class="section">
                <div class="section-title">Court Records ({len(data.court_cases)})</div>
                {court_html}
            </div>""" if court_html else ""}

            {f"""<div class="section">
                <div class="section-title">Enforcement Proceedings ({len(data.enforcement_records)})</div>
                {enforcement_html}
            </div>""" if enforcement_html else ""}

            {f"""<div class="section">
                <div class="section-title">Risk Assessment</div>
                {risks_html}
            </div>""" if risks_html else ""}

            {f"""<div class="section">
                <div class="section-title">Social Graph{' (' + friends_text + ')' if friends_text else ''}</div>
                {connections_html}
            </div>""" if connections_html else ""}
        </div>

        <div class="card-footer">
            <span>ID: {_esc(data.investigation_id[:8]) if data.investigation_id and len(data.investigation_id) >= 8 else _esc(data.investigation_id) or 'N/A'}...</span>
            <span>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
        </div>
    </div>
</body>
</html>'''

        return html

    def generate_pdf_report(self, data: IdentityCardData, investigation: Dict) -> bytes:
        """Generate PDF report using ReportLab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                   rightMargin=20*mm, leftMargin=20*mm,
                                   topMargin=20*mm, bottomMargin=20*mm)

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=HexColor('#7c3aed'),
                spaceAfter=10*mm
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=HexColor('#7c3aed'),
                spaceBefore=8*mm,
                spaceAfter=4*mm
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=2*mm
            )

            elements = []

            # Title
            elements.append(Paragraph("IBP Investigation Report", title_style))
            elements.append(Paragraph(f"<b>Subject:</b> {_esc(data.full_name)}", normal_style))
            elements.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
            elements.append(Paragraph(f"<b>Confidence:</b> {data.confidence_score:.0f}%", normal_style))
            if data.city:
                elements.append(Paragraph(f"<b>City:</b> {_esc(data.city)}", normal_style))
            elements.append(Spacer(1, 10*mm))

            # Profiles
            if data.profiles:
                elements.append(Paragraph("Social Media Profiles", heading_style))
                for p in data.profiles[:10]:
                    platform = _esc((p.get('platform', 'Unknown') or 'Unknown').upper())
                    url = _esc(p.get('url', ''))
                    username = _esc(p.get('username', ''))
                    elements.append(Paragraph(f"<b>{platform}:</b> @{username} - {url}", normal_style))

            # Contact Info
            if data.phones or data.emails:
                elements.append(Paragraph("Contact Information", heading_style))
                for phone in data.phones:
                    elements.append(Paragraph(f"<b>Phone:</b> {_esc(phone)}", normal_style))
                for email in data.emails:
                    elements.append(Paragraph(f"<b>Email:</b> {_esc(email)}", normal_style))

            # Business Records
            if data.companies:
                elements.append(Paragraph(f"Business Affiliations ({len(data.companies)})", heading_style))
                for company in data.companies:
                    name = _esc(company.get('company_name', 'Unknown'))
                    role = _esc(company.get('role', ''))
                    inn = _esc(company.get('inn', ''))
                    status = _esc(company.get('status', ''))
                    elements.append(Paragraph(f"<b>{name}</b> ({role})", normal_style))
                    details = []
                    if inn:
                        details.append(f"INN: {inn}")
                    if status:
                        details.append(f"Status: {status}")
                    if details:
                        elements.append(Paragraph(" | ".join(details), normal_style))

            # Court Cases
            if data.court_cases:
                elements.append(Paragraph(f"Court Records ({len(data.court_cases)})", heading_style))
                for case in data.court_cases:
                    number = _esc(case.get('case_number', 'Unknown'))
                    court = _esc(case.get('court_name', ''))
                    case_type = _esc(case.get('category_display', '') or case.get('category', ''))
                    elements.append(Paragraph(f"<b>Case:</b> {number}", normal_style))
                    elements.append(Paragraph(f"Court: {court} | Type: {case_type}", normal_style))

            # Enforcement Proceedings
            if data.enforcement_records:
                elements.append(Paragraph(f"Enforcement Proceedings ({len(data.enforcement_records)})", heading_style))
                for proc in data.enforcement_records:
                    debtor = _esc(proc.get('debtor_name', ''))
                    amount = proc.get('amount', '')
                    status = _esc(proc.get('status', ''))
                    elements.append(Paragraph(f"<b>Debtor:</b> {debtor}", normal_style))
                    if amount:
                        elements.append(Paragraph(f"Amount: {amount} RUB | Status: {status}", normal_style))

            # Risk Indicators
            if data.risk_indicators:
                elements.append(Paragraph("Risk Indicators", heading_style))
                for risk in data.risk_indicators:
                    severity = _esc(risk.get('severity', 'low')).upper()
                    desc = _esc(risk.get('description', ''))
                    elements.append(Paragraph(f"[{severity}] {desc}", normal_style))

            # Social Graph
            if data.friends_count > 0:
                elements.append(Paragraph(f"Social Graph ({data.friends_count} connections)", heading_style))
                for conn in data.social_connections[:10]:
                    name = _esc(conn.get('name', 'Unknown'))
                    platform = _esc(conn.get('platform', ''))
                    elements.append(Paragraph(f"{name} ({platform})", normal_style))

            doc.build(elements)
            return buffer.getvalue()

        except ImportError:
            logger.warning("ReportLab not available, PDF generation skipped")
            return b""

    def save_identity_card(self, data: IdentityCardData, format: str = 'html') -> str:
        """Save identity card to file."""
        filename = f"identity_{data.investigation_id or 'unknown'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format == 'html':
            html_content = self.generate_identity_card_html(data)
            filepath = os.path.join(self.output_dir, f"{filename}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return filepath

        elif format == 'json':
            json_content = {
                'full_name': data.full_name,
                'aliases': data.aliases,
                'profiles': data.profiles,
                'phones': data.phones,
                'emails': data.emails,
                'city': data.city,
                'companies': data.companies,
                'court_cases': data.court_cases,
                'confidence_score': data.confidence_score,
                'generated_at': data.generated_at
            }
            filepath = os.path.join(self.output_dir, f"{filename}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_content, f, ensure_ascii=False, indent=2)
            return filepath

        return ""


# Singleton instance
report_generator = ReportGenerator()

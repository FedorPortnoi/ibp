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

logger = logging.getLogger(__name__)


@dataclass
class IdentityCardData:
    """Data for identity card generation."""
    # Basic info
    full_name: str = ""
    aliases: List[str] = field(default_factory=list)
    photo_url: str = ""

    # Social profiles
    profiles: List[Dict] = field(default_factory=list)

    # Contact info
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)

    # Location
    city: str = ""
    country: str = "Russia"
    locations: List[Dict] = field(default_factory=list)

    # Business
    companies: List[Dict] = field(default_factory=list)
    court_cases: List[Dict] = field(default_factory=list)

    # Analysis
    sentiment: str = "neutral"
    keywords: List[str] = field(default_factory=list)

    # Metadata
    investigation_id: str = ""
    generated_at: str = ""
    confidence_score: float = 0.0


class ReportGenerator:
    """
    Generate identity cards and reports from investigation data.

    Output formats:
    - HTML identity card (styled, responsive)
    - PDF report (full investigation details)
    - PNG identity card (for sharing)
    - JSON export (machine-readable)
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'reports'
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def compile_data(self, investigation: Dict) -> IdentityCardData:
        """Compile investigation data into identity card format."""
        data = IdentityCardData()

        # Basic info
        data.full_name = investigation.get('input_name', '') or investigation.get('target_name', '')
        data.investigation_id = investigation.get('id', '')
        data.generated_at = datetime.now().isoformat()

        # Get confirmed profile
        confirmed = investigation.get('confirmed_profile', {})
        if isinstance(confirmed, str):
            try:
                confirmed = json.loads(confirmed)
            except Exception:
                confirmed = {}

        # Photo
        data.photo_url = (
            confirmed.get('photo_url') or
            investigation.get('input_photo_path', '')
        )

        # City from profile
        data.city = confirmed.get('city', '')

        # Collect profiles
        profiles = investigation.get('discovered_profiles', [])
        if isinstance(profiles, str):
            try:
                profiles = json.loads(profiles)
            except Exception:
                profiles = []

        data.profiles = profiles[:10]  # Top 10 profiles

        # Collect usernames as aliases
        usernames = investigation.get('discovered_usernames', [])
        if isinstance(usernames, str):
            try:
                usernames = json.loads(usernames)
            except Exception:
                usernames = []
        data.aliases = list(set(usernames))[:10]

        # Contact info
        phones = investigation.get('discovered_phones', [])
        if isinstance(phones, str):
            try:
                phones = json.loads(phones)
            except Exception:
                phones = []
        data.phones = [p.get('number', p) if isinstance(p, dict) else str(p) for p in phones][:5]

        emails = investigation.get('discovered_emails', [])
        if isinstance(emails, str):
            try:
                emails = json.loads(emails)
            except Exception:
                emails = []
        data.emails = [e.get('email', e) if isinstance(e, dict) else str(e) for e in emails][:5]

        # Business records
        business = investigation.get('business_records', [])
        if isinstance(business, str):
            try:
                business = json.loads(business)
            except Exception:
                business = []
        data.companies = business[:5]

        # Court cases
        courts = investigation.get('court_records', [])
        if isinstance(courts, str):
            try:
                courts = json.loads(courts)
            except Exception:
                courts = []
        data.court_cases = courts[:5]

        # Calculate confidence
        confidence = 0
        if data.profiles:
            confidence += 20
        if data.phones:
            confidence += 20
        if data.emails:
            confidence += 15
        if data.companies:
            confidence += 20
        if data.photo_url:
            confidence += 10
        if data.city:
            confidence += 15

        data.confidence_score = min(100, confidence)

        return data

    def generate_identity_card_html(self, data: IdentityCardData) -> str:
        """Generate HTML identity card."""
        # Platform icons mapping
        platform_icons = {
            'vk': '<span style="color:#4A76A8">VK</span>',
            'vkontakte': '<span style="color:#4A76A8">VK</span>',
            'telegram': '<span style="color:#0088cc">TG</span>',
            'ok': '<span style="color:#EE8208">OK</span>',
            'odnoklassniki': '<span style="color:#EE8208">OK</span>',
            'instagram': '<span style="color:#E1306C">IG</span>',
            'facebook': '<span style="color:#1877F2">FB</span>',
            'twitter': '<span style="color:#1DA1F2">TW</span>',
        }

        # Build profiles HTML
        profiles_html = ""
        for p in data.profiles[:6]:
            platform = p.get('platform', 'unknown').lower()
            icon = platform_icons.get(platform, '<span style="color:#888">@</span>')
            url = p.get('url', '#')
            username = p.get('username', 'unknown')
            profiles_html += f'''
            <a href="{url}" target="_blank" class="profile-link">
                {icon}
                <span class="username">{username}</span>
            </a>
            '''

        # Build contact HTML
        contacts_html = ""
        for phone in data.phones[:3]:
            contacts_html += f'<div class="contact-item"><span class="label">TEL</span> {phone}</div>'
        for email in data.emails[:3]:
            contacts_html += f'<div class="contact-item"><span class="label">EMAIL</span> {email}</div>'

        # Build business HTML
        business_html = ""
        for company in data.companies[:3]:
            name = company.get('company_name', 'Unknown')
            role = company.get('role', '')
            business_html += f'''
            <div class="business-item">
                <span class="company-name">{name}</span>
                <span class="role">{role}</span>
            </div>
            '''

        # Photo or placeholder
        photo_html = ""
        if data.photo_url:
            photo_html = f'<img src="{data.photo_url}" alt="Photo" class="photo">'
        else:
            photo_html = '<div class="photo-placeholder"><span>NO PHOTO</span></div>'

        # Confidence color
        if data.confidence_score >= 70:
            confidence_color = "#22c55e"  # green
        elif data.confidence_score >= 40:
            confidence_color = "#eab308"  # yellow
        else:
            confidence_color = "#ef4444"  # red

        html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IBP Identity Card - {data.full_name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background: linear-gradient(135deg, #030014 0%, #0a0618 50%, #110a1f 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            font-family: 'Inter', sans-serif;
        }}

        .card {{
            width: 100%;
            max-width: 500px;
            background: linear-gradient(180deg, rgba(139, 92, 246, 0.1) 0%, rgba(17, 10, 31, 0.95) 20%);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 20px;
            overflow: hidden;
            box-shadow:
                0 0 60px rgba(139, 92, 246, 0.15),
                0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}

        .card-header {{
            background: linear-gradient(90deg, #7c3aed 0%, #a855f7 50%, #ec4899 100%);
            padding: 15px 25px;
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
        }}

        .card-body {{
            padding: 30px;
        }}

        .profile-section {{
            display: flex;
            gap: 25px;
            margin-bottom: 25px;
        }}

        .photo {{
            width: 120px;
            height: 120px;
            border-radius: 12px;
            object-fit: cover;
            border: 2px solid rgba(139, 92, 246, 0.5);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
        }}

        .photo-placeholder {{
            width: 120px;
            height: 120px;
            border-radius: 12px;
            background: rgba(139, 92, 246, 0.1);
            border: 2px dashed rgba(139, 92, 246, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .photo-placeholder span {{
            color: rgba(139, 92, 246, 0.5);
            font-size: 11px;
            font-weight: 600;
        }}

        .info {{
            flex: 1;
        }}

        .name {{
            font-size: 24px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 8px;
            line-height: 1.2;
        }}

        .location {{
            color: rgba(255,255,255,0.6);
            font-size: 14px;
            margin-bottom: 12px;
        }}

        .location::before {{
            content: "📍 ";
        }}

        .confidence {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0,0,0,0.3);
            padding: 6px 12px;
            border-radius: 8px;
        }}

        .confidence-label {{
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .confidence-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 600;
            color: {confidence_color};
        }}

        .section {{
            margin-bottom: 25px;
        }}

        .section-title {{
            font-size: 11px;
            color: rgba(139, 92, 246, 0.7);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(139, 92, 246, 0.2);
        }}

        .profiles-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }}

        .profile-link {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(0,0,0,0.3);
            padding: 10px 14px;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s;
        }}

        .profile-link:hover {{
            background: rgba(139, 92, 246, 0.2);
        }}

        .profile-link .username {{
            color: rgba(255,255,255,0.8);
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
        }}

        .contact-item {{
            color: rgba(255,255,255,0.8);
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            padding: 8px 0;
            border-bottom: 1px solid rgba(139, 92, 246, 0.1);
        }}

        .contact-item:last-child {{
            border-bottom: none;
        }}

        .contact-item .label {{
            color: rgba(139, 92, 246, 0.7);
            font-size: 10px;
            margin-right: 10px;
        }}

        .business-item {{
            background: rgba(0,0,0,0.3);
            padding: 12px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
        }}

        .business-item .company-name {{
            display: block;
            color: rgba(255,255,255,0.9);
            font-size: 13px;
            font-weight: 500;
        }}

        .business-item .role {{
            color: rgba(139, 92, 246, 0.7);
            font-size: 11px;
        }}

        .card-footer {{
            background: rgba(0,0,0,0.3);
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: rgba(255,255,255,0.4);
            font-family: 'JetBrains Mono', monospace;
        }}

        .timestamp {{
            opacity: 0.7;
        }}

        /* Aliases section */
        .aliases {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }}

        .alias {{
            background: rgba(139, 92, 246, 0.15);
            color: rgba(139, 92, 246, 0.9);
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .card {{
                box-shadow: none;
                border: 1px solid #ddd;
            }}
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
                    <div class="name">{data.full_name or 'Unknown'}</div>
                    {'<div class="location">' + data.city + '</div>' if data.city else ''}
                    <div class="confidence">
                        <span class="confidence-label">Confidence</span>
                        <span class="confidence-value">{data.confidence_score:.0f}%</span>
                    </div>
                    {'''<div class="aliases">''' + ''.join(f'<span class="alias">@{a}</span>' for a in data.aliases[:5]) + '</div>' if data.aliases else ''}
                </div>
            </div>

            {'''<div class="section">
                <div class="section-title">Social Profiles</div>
                <div class="profiles-grid">''' + profiles_html + '''</div>
            </div>''' if profiles_html else ''}

            {'''<div class="section">
                <div class="section-title">Contact Information</div>''' + contacts_html + '''
            </div>''' if contacts_html else ''}

            {'''<div class="section">
                <div class="section-title">Business Affiliations</div>''' + business_html + '''
            </div>''' if business_html else ''}
        </div>

        <div class="card-footer">
            <span>ID: {data.investigation_id[:8] if data.investigation_id else 'N/A'}...</span>
            <span class="timestamp">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
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
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                   rightMargin=20*mm, leftMargin=20*mm,
                                   topMargin=20*mm, bottomMargin=20*mm)

            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=HexColor('#7c3aed'),
                spaceAfter=10*mm
            )
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=HexColor('#7c3aed'),
                spaceBefore=8*mm,
                spaceAfter=4*mm
            )
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=2*mm
            )

            elements = []

            # Title
            elements.append(Paragraph("IBP Investigation Report", title_style))
            elements.append(Paragraph(f"<b>Subject:</b> {data.full_name}", normal_style))
            elements.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
            elements.append(Paragraph(f"<b>Confidence:</b> {data.confidence_score:.0f}%", normal_style))
            elements.append(Spacer(1, 10*mm))

            # Social Profiles
            if data.profiles:
                elements.append(Paragraph("Social Media Profiles", heading_style))
                for p in data.profiles[:10]:
                    platform = p.get('platform', 'Unknown').upper()
                    url = p.get('url', '')
                    username = p.get('username', '')
                    elements.append(Paragraph(f"<b>{platform}:</b> @{username} - {url}", normal_style))

            # Contact Info
            if data.phones or data.emails:
                elements.append(Paragraph("Contact Information", heading_style))
                for phone in data.phones:
                    elements.append(Paragraph(f"<b>Phone:</b> {phone}", normal_style))
                for email in data.emails:
                    elements.append(Paragraph(f"<b>Email:</b> {email}", normal_style))

            # Business Records
            if data.companies:
                elements.append(Paragraph("Business Affiliations", heading_style))
                for company in data.companies:
                    name = company.get('company_name', 'Unknown')
                    role = company.get('role', '')
                    inn = company.get('inn', '')
                    elements.append(Paragraph(f"<b>{name}</b> ({role})", normal_style))
                    if inn:
                        elements.append(Paragraph(f"INN: {inn}", normal_style))

            # Court Cases
            if data.court_cases:
                elements.append(Paragraph("Court Records", heading_style))
                for case in data.court_cases:
                    number = case.get('case_number', 'Unknown')
                    court = case.get('court_name', '')
                    case_type = case.get('case_type', '')
                    elements.append(Paragraph(f"<b>Case:</b> {number}", normal_style))
                    elements.append(Paragraph(f"Court: {court} | Type: {case_type}", normal_style))

            # Build PDF
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

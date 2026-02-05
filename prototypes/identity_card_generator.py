"""
Identity Card Generator - IBP Prototype B.12
Generate visual identity cards from aggregated profile data

Features:
- HTML identity card generation using Jinja2-like templates
- Photo, name, DOB, locations, contacts, social links
- Visual timeline of activities
- Print-friendly layout
- PDF export (optional)
- Multiple card styles

Requirements:
    pip install jinja2 weasyprint (for PDF)

Usage:
    generator = IdentityCardGenerator()
    html = generator.generate(profile_data)
    generator.save_html(html, "identity_card.html")
"""

import os
import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import html as html_lib
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_JINJA2 = False
HAS_WEASYPRINT = False

try:
    from jinja2 import Environment, BaseLoader, select_autoescape
    HAS_JINJA2 = True
except ImportError:
    logger.warning("jinja2 not installed - using string templates")

try:
    from weasyprint import HTML as WeasyHTML
    HAS_WEASYPRINT = True
except (ImportError, OSError) as e:
    logger.info(f"weasyprint not available - PDF export disabled: {e}")


@dataclass
class SocialLink:
    """Social media profile link"""
    platform: str
    url: str
    username: Optional[str] = None
    followers: Optional[int] = None
    is_verified: bool = False


@dataclass
class ContactInfo:
    """Contact information"""
    contact_type: str  # phone, email, messenger
    value: str
    label: Optional[str] = None
    is_primary: bool = False


@dataclass
class TimelineEvent:
    """Timeline event"""
    date: datetime
    event_type: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    platform: Optional[str] = None


@dataclass
class LocationHistory:
    """Location record"""
    location: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False
    location_type: str = "residence"  # residence, work, education


@dataclass
class IdentityProfile:
    """Aggregated identity profile for card generation"""
    # Basic info
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    aliases: List[str] = field(default_factory=list)

    # Photo
    photo_url: Optional[str] = None
    photo_base64: Optional[str] = None

    # Demographics
    birth_date: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None

    # Locations
    current_city: Optional[str] = None
    current_country: Optional[str] = None
    hometown: Optional[str] = None
    location_history: List[LocationHistory] = field(default_factory=list)

    # Contacts
    contacts: List[ContactInfo] = field(default_factory=list)

    # Social
    social_links: List[SocialLink] = field(default_factory=list)

    # Timeline
    events: List[TimelineEvent] = field(default_factory=list)

    # Work & Education
    occupation: Optional[str] = None
    employer: Optional[str] = None
    education: List[str] = field(default_factory=list)

    # Additional
    bio: Optional[str] = None
    interests: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)

    # Meta
    confidence_score: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    sources: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name

    @property
    def primary_phone(self) -> Optional[str]:
        for contact in self.contacts:
            if contact.contact_type == "phone" and contact.is_primary:
                return contact.value
        phones = [c for c in self.contacts if c.contact_type == "phone"]
        return phones[0].value if phones else None

    @property
    def primary_email(self) -> Optional[str]:
        for contact in self.contacts:
            if contact.contact_type == "email" and contact.is_primary:
                return contact.value
        emails = [c for c in self.contacts if c.contact_type == "email"]
        return emails[0].value if emails else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "aliases": self.aliases,
            "photo_url": self.photo_url,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "age": self.age,
            "gender": self.gender,
            "current_city": self.current_city,
            "current_country": self.current_country,
            "hometown": self.hometown,
            "contacts": [
                {"type": c.contact_type, "value": c.value, "label": c.label}
                for c in self.contacts
            ],
            "social_links": [
                {"platform": s.platform, "url": s.url, "username": s.username}
                for s in self.social_links
            ],
            "occupation": self.occupation,
            "employer": self.employer,
            "education": self.education,
            "bio": self.bio,
            "interests": self.interests,
            "confidence_score": self.confidence_score,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }


# HTML Template
IDENTITY_CARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Identity Card - {{ profile.full_name }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 800px;
            margin: 20px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }

        /* Header Section */
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            display: flex;
            gap: 30px;
            align-items: center;
        }

        .photo-container {
            flex-shrink: 0;
        }

        .photo {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            object-fit: cover;
            border: 4px solid white;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }

        .photo-placeholder {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: #95a5a6;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            color: white;
            border: 4px solid white;
        }

        .header-info {
            flex-grow: 1;
        }

        .name {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .aliases {
            font-size: 14px;
            opacity: 0.8;
            margin-bottom: 10px;
        }

        .quick-info {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 14px;
        }

        .quick-info-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .confidence-badge {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
        }

        /* Content Sections */
        .content {
            padding: 30px;
        }

        .section {
            margin-bottom: 30px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }

        /* Contact Grid */
        .contact-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }

        .contact-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .contact-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            color: white;
        }

        .contact-icon.phone { background: #27ae60; }
        .contact-icon.email { background: #e74c3c; }
        .contact-icon.messenger { background: #9b59b6; }

        .contact-details {
            flex-grow: 1;
        }

        .contact-label {
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
        }

        .contact-value {
            font-weight: 600;
            word-break: break-all;
        }

        /* Social Links */
        .social-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .social-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 15px;
            background: #f8f9fa;
            border-radius: 25px;
            text-decoration: none;
            color: #333;
            transition: all 0.2s;
        }

        .social-link:hover {
            background: #3498db;
            color: white;
        }

        .social-link.vk { border-left: 3px solid #4a76a8; }
        .social-link.telegram { border-left: 3px solid #0088cc; }
        .social-link.instagram { border-left: 3px solid #e1306c; }
        .social-link.facebook { border-left: 3px solid #4267b2; }
        .social-link.twitter { border-left: 3px solid #1da1f2; }
        .social-link.ok { border-left: 3px solid #ed812b; }

        .verified-badge {
            color: #3498db;
            font-size: 12px;
        }

        /* Timeline */
        .timeline {
            position: relative;
            padding-left: 30px;
        }

        .timeline::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #e0e0e0;
        }

        .timeline-item {
            position: relative;
            padding-bottom: 20px;
        }

        .timeline-item::before {
            content: '';
            position: absolute;
            left: -24px;
            top: 5px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #3498db;
        }

        .timeline-date {
            font-size: 12px;
            color: #7f8c8d;
            margin-bottom: 5px;
        }

        .timeline-title {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .timeline-description {
            font-size: 14px;
            color: #666;
        }

        .timeline-platform {
            display: inline-block;
            font-size: 11px;
            padding: 2px 8px;
            background: #ecf0f1;
            border-radius: 10px;
            margin-top: 5px;
        }

        /* Info Grid */
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .info-item {
            display: flex;
            flex-direction: column;
        }

        .info-label {
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            margin-bottom: 5px;
        }

        .info-value {
            font-weight: 500;
        }

        /* Tags */
        .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag {
            display: inline-block;
            padding: 5px 12px;
            background: #ecf0f1;
            border-radius: 15px;
            font-size: 13px;
        }

        /* Footer */
        .footer {
            background: #f8f9fa;
            padding: 20px 30px;
            font-size: 12px;
            color: #7f8c8d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .sources {
            display: flex;
            gap: 10px;
        }

        .source-badge {
            padding: 3px 10px;
            background: #dfe6e9;
            border-radius: 10px;
            font-size: 11px;
        }

        /* Print Styles */
        @media print {
            body {
                background: white;
            }

            .container {
                box-shadow: none;
                margin: 0;
                max-width: 100%;
            }

            .social-link:hover {
                background: #f8f9fa;
                color: #333;
            }

            @page {
                margin: 1cm;
            }
        }

        /* Responsive */
        @media (max-width: 600px) {
            .header {
                flex-direction: column;
                text-align: center;
            }

            .info-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header" style="position: relative;">
            <div class="photo-container">
                {% if profile.photo_url or profile.photo_base64 %}
                <img src="{{ profile.photo_base64 or profile.photo_url }}" alt="Photo" class="photo">
                {% else %}
                <div class="photo-placeholder">{{ profile.full_name[0] }}</div>
                {% endif %}
            </div>
            <div class="header-info">
                <div class="name">{{ profile.full_name }}</div>
                {% if profile.aliases %}
                <div class="aliases">Также известен как: {{ profile.aliases | join(', ') }}</div>
                {% endif %}
                <div class="quick-info">
                    {% if profile.age %}
                    <span class="quick-info-item">📅 {{ profile.age }} лет</span>
                    {% endif %}
                    {% if profile.current_city %}
                    <span class="quick-info-item">📍 {{ profile.current_city }}{% if profile.current_country %}, {{ profile.current_country }}{% endif %}</span>
                    {% endif %}
                    {% if profile.occupation %}
                    <span class="quick-info-item">💼 {{ profile.occupation }}</span>
                    {% endif %}
                </div>
            </div>
            {% if profile.confidence_score > 0 %}
            <div class="confidence-badge">
                Достоверность: {{ (profile.confidence_score * 100) | round }}%
            </div>
            {% endif %}
        </div>

        <div class="content">
            <!-- Personal Info -->
            <div class="section">
                <div class="section-title">Персональные данные</div>
                <div class="info-grid">
                    {% if profile.birth_date %}
                    <div class="info-item">
                        <span class="info-label">Дата рождения</span>
                        <span class="info-value">{{ profile.birth_date }}</span>
                    </div>
                    {% endif %}
                    {% if profile.gender %}
                    <div class="info-item">
                        <span class="info-label">Пол</span>
                        <span class="info-value">{{ profile.gender }}</span>
                    </div>
                    {% endif %}
                    {% if profile.hometown %}
                    <div class="info-item">
                        <span class="info-label">Родной город</span>
                        <span class="info-value">{{ profile.hometown }}</span>
                    </div>
                    {% endif %}
                    {% if profile.employer %}
                    <div class="info-item">
                        <span class="info-label">Место работы</span>
                        <span class="info-value">{{ profile.employer }}</span>
                    </div>
                    {% endif %}
                </div>
                {% if profile.bio %}
                <div class="info-item" style="margin-top: 15px;">
                    <span class="info-label">О себе</span>
                    <span class="info-value">{{ profile.bio }}</span>
                </div>
                {% endif %}
            </div>

            <!-- Contacts -->
            {% if profile.contacts %}
            <div class="section">
                <div class="section-title">Контакты</div>
                <div class="contact-grid">
                    {% for contact in profile.contacts %}
                    <div class="contact-item">
                        <div class="contact-icon {{ contact.contact_type }}">
                            {% if contact.contact_type == 'phone' %}📱{% elif contact.contact_type == 'email' %}✉️{% else %}💬{% endif %}
                        </div>
                        <div class="contact-details">
                            <div class="contact-label">{{ contact.label or contact.contact_type }}</div>
                            <div class="contact-value">{{ contact.value }}</div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Social Links -->
            {% if profile.social_links %}
            <div class="section">
                <div class="section-title">Социальные сети</div>
                <div class="social-grid">
                    {% for link in profile.social_links %}
                    <a href="{{ link.url }}" target="_blank" class="social-link {{ link.platform }}">
                        {{ link.platform | upper }}
                        {% if link.username %}@{{ link.username }}{% endif %}
                        {% if link.is_verified %}<span class="verified-badge">✓</span>{% endif %}
                        {% if link.followers %}<span style="font-size: 11px; opacity: 0.7;">({{ link.followers }})</span>{% endif %}
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Education -->
            {% if profile.education %}
            <div class="section">
                <div class="section-title">Образование</div>
                <div class="tags">
                    {% for edu in profile.education %}
                    <span class="tag">🎓 {{ edu }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Interests -->
            {% if profile.interests %}
            <div class="section">
                <div class="section-title">Интересы</div>
                <div class="tags">
                    {% for interest in profile.interests %}
                    <span class="tag">{{ interest }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Timeline -->
            {% if profile.events %}
            <div class="section">
                <div class="section-title">Хронология</div>
                <div class="timeline">
                    {% for event in profile.events[:10] %}
                    <div class="timeline-item">
                        <div class="timeline-date">{{ event.date }}</div>
                        <div class="timeline-title">{{ event.title }}</div>
                        {% if event.description %}
                        <div class="timeline-description">{{ event.description }}</div>
                        {% endif %}
                        {% if event.platform %}
                        <span class="timeline-platform">{{ event.platform }}</span>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>

        <!-- Footer -->
        <div class="footer">
            <div>
                Сгенерировано: {{ generated_at }}
            </div>
            {% if profile.sources %}
            <div class="sources">
                Источники:
                {% for source in profile.sources %}
                <span class="source-badge">{{ source }}</span>
                {% endfor %}
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


class IdentityCardGenerator:
    """
    Generate visual identity cards from profile data

    Supports HTML output with optional PDF export.
    """

    def __init__(self, template: Optional[str] = None):
        """
        Initialize generator

        Args:
            template: Custom Jinja2 template (uses default if None)
        """
        self.template_str = template or IDENTITY_CARD_TEMPLATE

        if HAS_JINJA2:
            self.env = Environment(
                loader=BaseLoader(),
                autoescape=select_autoescape(['html', 'xml'])
            )
            self.template = self.env.from_string(self.template_str)
        else:
            self.env = None
            self.template = None

    def generate(self, profile: IdentityProfile) -> str:
        """
        Generate HTML identity card

        Args:
            profile: IdentityProfile with person data

        Returns:
            HTML string
        """
        context = {
            'profile': profile,
            'generated_at': datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        if HAS_JINJA2 and self.template:
            return self.template.render(**context)
        else:
            return self._render_simple(profile)

    def _render_simple(self, profile: IdentityProfile) -> str:
        """Simple string-based rendering fallback"""
        html = self.template_str

        # Basic replacements
        html = html.replace('{{ profile.full_name }}', html_lib.escape(profile.full_name))
        html = html.replace('{{ profile.full_name[0] }}', html_lib.escape(profile.full_name[0]))
        html = html.replace('{{ profile.photo_url }}', profile.photo_url or '')
        html = html.replace('{{ profile.photo_base64 or profile.photo_url }}',
                           profile.photo_base64 or profile.photo_url or '')
        html = html.replace('{{ profile.age }}', str(profile.age or ''))
        html = html.replace('{{ profile.current_city }}', html_lib.escape(profile.current_city or ''))
        html = html.replace('{{ profile.current_country }}', html_lib.escape(profile.current_country or ''))
        html = html.replace('{{ profile.occupation }}', html_lib.escape(profile.occupation or ''))
        html = html.replace('{{ profile.birth_date }}',
                           profile.birth_date.strftime('%d.%m.%Y') if profile.birth_date else '')
        html = html.replace('{{ profile.gender }}', html_lib.escape(profile.gender or ''))
        html = html.replace('{{ profile.hometown }}', html_lib.escape(profile.hometown or ''))
        html = html.replace('{{ profile.employer }}', html_lib.escape(profile.employer or ''))
        html = html.replace('{{ profile.bio }}', html_lib.escape(profile.bio or ''))
        html = html.replace('{{ (profile.confidence_score * 100) | round }}',
                           str(round(profile.confidence_score * 100)))
        html = html.replace('{{ generated_at }}', datetime.now().strftime("%d.%m.%Y %H:%M"))
        html = html.replace("{{ profile.aliases | join(', ') }}", ', '.join(profile.aliases))

        # Remove unprocessed Jinja2 blocks for clean output
        import re
        html = re.sub(r'\{%.*?%\}', '', html, flags=re.DOTALL)
        html = re.sub(r'\{\{.*?\}\}', '', html)

        return html

    def generate_from_dict(self, data: Dict[str, Any]) -> str:
        """
        Generate HTML from dictionary data

        Args:
            data: Profile data as dictionary

        Returns:
            HTML string
        """
        profile = self._dict_to_profile(data)
        return self.generate(profile)

    def _dict_to_profile(self, data: Dict[str, Any]) -> IdentityProfile:
        """Convert dictionary to IdentityProfile"""
        contacts = []
        for c in data.get('contacts', []):
            contacts.append(ContactInfo(
                contact_type=c.get('type', c.get('contact_type', 'other')),
                value=c.get('value', ''),
                label=c.get('label'),
                is_primary=c.get('is_primary', False)
            ))

        social_links = []
        for s in data.get('social_links', []):
            social_links.append(SocialLink(
                platform=s.get('platform', 'other'),
                url=s.get('url', ''),
                username=s.get('username'),
                followers=s.get('followers'),
                is_verified=s.get('is_verified', False)
            ))

        events = []
        for e in data.get('events', []):
            event_date = e.get('date')
            if isinstance(event_date, str):
                event_date = datetime.fromisoformat(event_date)
            events.append(TimelineEvent(
                date=event_date or datetime.now(),
                event_type=e.get('event_type', 'other'),
                title=e.get('title', ''),
                description=e.get('description'),
                location=e.get('location'),
                platform=e.get('platform')
            ))

        birth_date = data.get('birth_date')
        if isinstance(birth_date, str):
            birth_date = date.fromisoformat(birth_date)

        return IdentityProfile(
            name=data.get('name', 'Unknown'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            aliases=data.get('aliases', []),
            photo_url=data.get('photo_url'),
            photo_base64=data.get('photo_base64'),
            birth_date=birth_date,
            age=data.get('age'),
            gender=data.get('gender'),
            current_city=data.get('current_city', data.get('city')),
            current_country=data.get('current_country', data.get('country')),
            hometown=data.get('hometown'),
            contacts=contacts,
            social_links=social_links,
            events=events,
            occupation=data.get('occupation'),
            employer=data.get('employer'),
            education=data.get('education', []),
            bio=data.get('bio'),
            interests=data.get('interests', []),
            languages=data.get('languages', []),
            confidence_score=data.get('confidence_score', 0.0),
            sources=data.get('sources', [])
        )

    def save_html(self, html: str, filepath: str) -> str:
        """
        Save HTML to file

        Args:
            html: HTML content
            filepath: Output file path

        Returns:
            Saved file path
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"HTML saved to: {filepath}")
        return filepath

    def save_pdf(self, html: str, filepath: str) -> Optional[str]:
        """
        Save as PDF (requires weasyprint)

        Args:
            html: HTML content
            filepath: Output file path

        Returns:
            Saved file path or None if weasyprint not available
        """
        if not HAS_WEASYPRINT:
            logger.warning("weasyprint not installed - PDF export unavailable")
            return None

        try:
            WeasyHTML(string=html).write_pdf(filepath)
            logger.info(f"PDF saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None

    def generate_and_save(
        self,
        profile: IdentityProfile,
        output_path: str,
        formats: List[str] = ['html']
    ) -> Dict[str, str]:
        """
        Generate and save in multiple formats

        Args:
            profile: IdentityProfile data
            output_path: Base output path (without extension)
            formats: List of formats ['html', 'pdf']

        Returns:
            Dictionary of format -> filepath
        """
        html = self.generate(profile)
        results = {}

        if 'html' in formats:
            html_path = f"{output_path}.html"
            self.save_html(html, html_path)
            results['html'] = html_path

        if 'pdf' in formats:
            pdf_path = f"{output_path}.pdf"
            saved = self.save_pdf(html, pdf_path)
            if saved:
                results['pdf'] = saved

        return results


def demo():
    """Demonstrate identity card generation"""
    print("=" * 60)
    print("Identity Card Generator - IBP Prototype B.12")
    print("=" * 60)
    print()

    # Create sample profile
    profile = IdentityProfile(
        name="Иван Петров",
        first_name="Иван",
        last_name="Петров",
        aliases=["Ivan Petrov", "ivan_p"],
        birth_date=date(1990, 5, 15),
        age=34,
        gender="Мужской",
        current_city="Москва",
        current_country="Россия",
        hometown="Казань",
        occupation="Программист",
        employer="Яндекс",
        bio="Разработчик. Люблю путешествия и фотографию.",
        education=["МГУ им. Ломоносова, факультет ВМК, 2012"],
        interests=["Программирование", "Фотография", "Путешествия", "Музыка"],
        languages=["Русский", "English"],
        contacts=[
            ContactInfo("phone", "+7 (916) 123-45-67", "Личный", True),
            ContactInfo("email", "ivan.petrov@example.com", "Рабочий"),
            ContactInfo("messenger", "@ivan_petrov", "Telegram")
        ],
        social_links=[
            SocialLink("vk", "https://vk.com/ivan_petrov", "ivan_petrov", 1523, True),
            SocialLink("telegram", "https://t.me/ivan_petrov", "ivan_petrov"),
            SocialLink("instagram", "https://instagram.com/ivan.petrov", "ivan.petrov", 892),
            SocialLink("github", "https://github.com/ivanpetrov", "ivanpetrov", 156)
        ],
        events=[
            TimelineEvent(
                date=datetime(2024, 1, 15),
                event_type="post",
                title="Опубликовал пост",
                description="Новый год в Москве был великолепен!",
                platform="VK"
            ),
            TimelineEvent(
                date=datetime(2023, 12, 1),
                event_type="photo",
                title="Добавил фотографии",
                description="Поездка в Санкт-Петербург",
                location="Санкт-Петербург",
                platform="Instagram"
            ),
            TimelineEvent(
                date=datetime(2023, 9, 1),
                event_type="employment",
                title="Устроился на работу",
                description="Начал работать в Яндекс"
            )
        ],
        confidence_score=0.85,
        sources=["VK", "Telegram", "Instagram"]
    )

    print("Demo - Identity Card Generation")
    print("-" * 40)
    print(f"Generating card for: {profile.full_name}")

    # Generate HTML
    generator = IdentityCardGenerator()
    html = generator.generate(profile)

    print(f"\nGenerated HTML: {len(html)} bytes")

    # Save to file
    output_path = "identity_card_demo"
    results = generator.generate_and_save(profile, output_path, formats=['html'])

    for fmt, path in results.items():
        print(f"Saved {fmt.upper()}: {path}")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from identity_card_generator import IdentityCardGenerator, IdentityProfile, ContactInfo, SocialLink

# Create profile
profile = IdentityProfile(
    name="Иван Петров",
    age=34,
    current_city="Москва",
    contacts=[
        ContactInfo("phone", "+7 (916) 123-45-67"),
        ContactInfo("email", "ivan@example.com")
    ],
    social_links=[
        SocialLink("vk", "https://vk.com/ivan", "ivan", 1500),
        SocialLink("telegram", "https://t.me/ivan", "ivan")
    ]
)

# Generate
generator = IdentityCardGenerator()
html = generator.generate(profile)

# Save
generator.save_html(html, "identity_card.html")
generator.save_pdf(html, "identity_card.pdf")  # Requires weasyprint

# Or generate from dictionary
data = {
    "name": "Иван Петров",
    "age": 34,
    "contacts": [{"type": "phone", "value": "+79161234567"}],
    "social_links": [{"platform": "vk", "url": "https://vk.com/ivan"}]
}
html = generator.generate_from_dict(data)
""")

    print("\n" + "=" * 60)
    print("\nProfile Data (JSON):")
    print("-" * 40)
    print(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False, default=str)[:1000] + "...")


if __name__ == "__main__":
    demo()

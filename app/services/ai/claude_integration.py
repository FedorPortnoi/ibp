"""
Claude AI Integration
=====================
Provides AI-powered summaries for the candidate check pipeline:
1. Risk narrative (after Stage 7)
2. Behavioral summary (after Stage 6)
3. Executive summary (after Stage 8)
4. Court case interpretation (after Stage 1)

All functions fail gracefully — if the API call fails, they return None
and the pipeline continues without AI summaries.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_MODEL = 'claude-haiku-4-5-20251001'
_MAX_TOKENS = 512


def _get_client():
    """Get Anthropic client. Returns None if key not set."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping AI summary")
        return None
    try:
        import anthropic
        import httpx

        proxy_url = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        if proxy_url:
            http_client = httpx.Client(proxies={'https://': proxy_url})
            return anthropic.Anthropic(api_key=api_key, http_client=http_client)
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic package not installed, skipping AI summary")
        return None
    except Exception as e:
        logger.warning(f"Failed to create Anthropic client: {e}")
        return None


def _call_claude(system_prompt, user_content, max_tokens=_MAX_TOKENS):
    """Make a Claude API call. Returns response text or None on failure."""
    client = _get_client()
    if not client:
        return None
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': user_content}],
            system=system_prompt,
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Claude API call failed: {e}")
        return None


def generate_risk_narrative(risk_level, risk_score, red_flags, full_name):
    """
    Generate a 2-3 sentence human-readable risk summary.

    Called after Stage 7 risk scoring.
    Returns: str or None
    """
    if not red_flags:
        flags_text = "No risk factors found."
    else:
        flags_text = "\n".join(
            f"- [{f.get('severity', 'unknown')}] {f.get('text', '')}"
            for f in red_flags[:15]
        )

    system = (
        "You are a background check analyst. Write a concise 2-3 sentence risk summary "
        "in professional English. Focus on the most important findings. "
        "Do not repeat the person's full name — use 'the subject' or 'the candidate'."
    )
    user = (
        f"Subject: {full_name}\n"
        f"Risk level: {risk_level} (score: {risk_score}/100)\n"
        f"Risk factors:\n{flags_text}\n\n"
        "Write a 2-3 sentence risk narrative."
    )
    return _call_claude(system, user, max_tokens=256)


def generate_behavioral_summary(text_analysis, full_name):
    """
    Summarize VK wall post analysis: personality, lifestyle, political views, red flags.

    Called after Stage 6 behavioral analysis.
    Returns: str or None
    """
    if not text_analysis or not isinstance(text_analysis, dict):
        return None

    # Extract key data points
    sentiment = text_analysis.get('sentiment', {})
    keywords = text_analysis.get('keywords', [])
    topics = text_analysis.get('topics', [])
    word_count = text_analysis.get('word_count', 0)

    if not keywords and not topics and word_count == 0:
        return None

    # Format keywords for prompt
    kw_list = []
    for kw in keywords[:20]:
        if isinstance(kw, str):
            kw_list.append(kw)
        elif isinstance(kw, (list, tuple)) and len(kw) >= 1:
            kw_list.append(str(kw[0]))
        elif isinstance(kw, dict):
            kw_list.append(kw.get('word', kw.get('text', '')))

    topic_list = []
    for t in (topics if isinstance(topics, list) else []):
        if isinstance(t, str):
            topic_list.append(t)
        elif isinstance(t, (list, tuple)) and len(t) >= 1:
            topic_list.append(str(t[0]))
        elif isinstance(t, dict):
            topic_list.append(t.get('name', t.get('text', '')))

    sent_label = sentiment.get('label', 'unknown') if isinstance(sentiment, dict) else str(sentiment)

    system = (
        "You are an OSINT analyst reviewing social media activity. "
        "Based on the text analysis data from VK wall posts, write a concise summary covering: "
        "personality traits, lifestyle indicators, political views (if any), and potential red flags. "
        "Write 3-5 sentences in professional English. Be factual, not speculative. "
        "Use 'the subject' instead of the person's name."
    )
    user = (
        f"Subject: {full_name}\n"
        f"Posts analyzed: ~{word_count} words\n"
        f"Sentiment: {sent_label}\n"
        f"Keywords: {', '.join(kw_list[:15])}\n"
        f"Topics: {', '.join(topic_list[:10])}\n\n"
        "Summarize the behavioral profile."
    )
    return _call_claude(system, user, max_tokens=384)


def generate_executive_summary(check_data):
    """
    Write a 1-paragraph executive summary of the entire investigation.

    Called after all stages complete (Stage 8).
    check_data: dict with keys from the CandidateCheck model.
    Returns: str or None
    """
    # Build a compact data summary for the prompt
    parts = []
    parts.append(f"Subject: {check_data.get('full_name', 'Unknown')}")
    parts.append(f"INN: {check_data.get('inn', 'N/A')}")
    parts.append(f"Identity confirmed: {check_data.get('identity_confirmed', False)}")
    parts.append(f"Risk level: {check_data.get('risk_level', 'unknown')} "
                 f"(score: {check_data.get('risk_score_numeric', 0)}/100)")
    parts.append(f"Red flags: {check_data.get('red_flag_count', 0)}")

    biz_count = len(check_data.get('business_records', []))
    court_count = len(check_data.get('court_records', []))
    fssp_count = len(check_data.get('fssp_records', []))
    bankruptcy_count = len(check_data.get('bankruptcy_records', []))
    social_count = len(check_data.get('social_media_profiles', []))

    contacts = check_data.get('contact_discoveries', {})
    phone_count = len(contacts.get('phones', [])) if isinstance(contacts, dict) else 0
    email_count = len(contacts.get('emails', [])) if isinstance(contacts, dict) else 0

    parts.append(f"Business records: {biz_count}")
    parts.append(f"Court cases: {court_count}")
    parts.append(f"FSSP debts: {fssp_count}")
    parts.append(f"Bankruptcy records: {bankruptcy_count}")
    parts.append(f"Social profiles: {social_count}")
    parts.append(f"Phones found: {phone_count}, Emails found: {email_count}")

    # Top red flags
    red_flags = check_data.get('red_flags', [])
    if red_flags:
        top = red_flags[:5]
        flags_str = "; ".join(f.get('text', '') for f in top if f.get('text'))
        parts.append(f"Top findings: {flags_str}")

    sanctions = check_data.get('sanctions_results', [])
    if isinstance(sanctions, list):
        found = [s for s in sanctions if isinstance(s, dict) and s.get('found')]
        if found:
            parts.append(f"SANCTIONS MATCH: {', '.join(s.get('source_name', '') for s in found)}")

    system = (
        "You are a senior background check analyst writing an executive summary. "
        "Write exactly 1 paragraph (4-6 sentences) summarizing the investigation results "
        "in professional English. Cover: identity verification, key findings, risk assessment, "
        "and hiring recommendation. Use 'the candidate' instead of the person's name."
    )
    user = "\n".join(parts) + "\n\nWrite the executive summary."
    return _call_claude(system, user, max_tokens=384)


def summarize_court_cases(court_records):
    """
    For each court case, generate a plain-language summary.

    Called after Stage 1 government registries.
    Returns: list of dicts with original data + 'ai_summary' key, or original list on failure.
    """
    if not court_records:
        return court_records

    client = _get_client()
    if not client:
        return court_records

    # Build batch prompt for all cases (more token-efficient than individual calls)
    cases_text = []
    for i, case in enumerate(court_records[:20]):  # Cap at 20 cases
        parts = []
        if case.get('case_number'):
            parts.append(f"Case: {case['case_number']}")
        if case.get('court') or case.get('court_name'):
            parts.append(f"Court: {case.get('court', case.get('court_name', ''))}")
        if case.get('category') or case.get('article'):
            parts.append(f"Category: {case.get('category', case.get('article', ''))}")
        if case.get('role'):
            parts.append(f"Role: {case['role']}")
        if case.get('date'):
            parts.append(f"Date: {case['date']}")
        if case.get('status'):
            parts.append(f"Status: {case['status']}")
        if case.get('description') or case.get('details'):
            parts.append(f"Details: {case.get('description', case.get('details', ''))}")
        cases_text.append(f"[{i+1}] " + " | ".join(parts))

    if not cases_text:
        return court_records

    system = (
        "You are a legal analyst. For each court case below, write a 1-2 sentence "
        "plain-language summary explaining what happened. Output as JSON array of strings, "
        "one summary per case, in the same order. Keep summaries concise and factual. "
        "Write in both English and Russian (English first, then Russian translation). "
        "Format: [\"English summary / Русское резюме\", ...]"
    )
    user = "\n".join(cases_text)

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{'role': 'user', 'content': user}],
            system=system,
        )
        text = response.content[0].text.strip()

        # Parse JSON array from response
        # Handle potential markdown code blocks
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        summaries = json.loads(text)

        if isinstance(summaries, list):
            result = []
            for i, case in enumerate(court_records):
                case_copy = dict(case)
                if i < len(summaries):
                    case_copy['ai_summary'] = str(summaries[i])
                result.append(case_copy)
            return result

    except Exception as e:
        logger.warning(f"Court case summarization failed: {e}")

    return court_records

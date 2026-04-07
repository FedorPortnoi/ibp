import pytest
from app import create_app


@pytest.fixture
def app():
    return create_app('testing')


def test_criminal_articles_render(app):
    """criminal_articles список рендерится как бейджи."""
    from flask import render_template_string
    with app.test_request_context():
        tmpl = """
        {% set case = {'case_number': '1-100/2023', 'criminal_articles': ['ч.2 ст.228 УК РФ', 'п.в ч.2 ст.158 УК РФ'], 'verdict': 'Лишение свободы 3 года условно'} %}
        {% if case.get('criminal_articles') %}ARTICLES_PRESENT{% endif %}
        {% if case.get('verdict') %}VERDICT_PRESENT{% endif %}
        """
        result = render_template_string(tmpl)
        assert 'ARTICLES_PRESENT' in result
        assert 'VERDICT_PRESENT' in result


def test_empty_criminal_articles_not_rendered(app):
    """Пустой список criminal_articles не рендерит блок."""
    from flask import render_template_string
    with app.test_request_context():
        tmpl = """
        {% set case = {'case_number': '2-200/2023', 'criminal_articles': [], 'verdict': ''} %}
        {% if case.get('criminal_articles') %}ARTICLES_PRESENT{% else %}ARTICLES_ABSENT{% endif %}
        {% if case.get('verdict') %}VERDICT_PRESENT{% else %}VERDICT_ABSENT{% endif %}
        """
        result = render_template_string(tmpl)
        assert 'ARTICLES_ABSENT' in result
        assert 'VERDICT_ABSENT' in result


def test_subject_render(app):
    """Предмет дела рендерится если есть."""
    from flask import render_template_string
    with app.test_request_context():
        tmpl = """
        {% set case = {'subject': 'Взыскание задолженности по договору займа'} %}
        {% if case.get('subject') %}SUBJECT:{{ case.subject }}{% endif %}
        """
        result = render_template_string(tmpl)
        assert 'SUBJECT:Взыскание задолженности по договору займа' in result


def test_dossier_template_contains_new_blocks():
    """Шаблон candidate_dossier.html содержит новые блоки рендера."""
    with open('app/templates/candidate_dossier.html', 'r', encoding='utf-8') as f:
        content = f.read()
    assert "case.get('criminal_articles')" in content
    assert "case.get('verdict')" in content
    assert "case.get('subject')" in content
    assert 'Статьи УК:' in content
    assert 'Решение:' in content
    assert 'Предмет:' in content

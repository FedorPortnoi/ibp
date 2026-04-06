"""Tests for _extract_criminal_articles and _extract_verdict methods."""
import pytest
from app.services.phase3.court_search import CourtCase, CourtRecordSearch


TEXT_DRUG_CASE = """
Суд признал Зобова Андрея Борисовича виновным в совершении преступления,
предусмотренного ч.2 ст.228 УК РФ (незаконное хранение наркотических средств
в особо крупном размере) и назначил наказание в виде лишения свободы
условно на срок 4 года.
"""

TEXT_THEFT_CASE = """
Подсудимый осуждён по п.в ч.2 ст.158 УК РФ. Назначено наказание —
штраф 10000 рублей.
"""

TEXT_MULTIPLE = """
Котов Валерий Дмитриевич признан виновным по ч.1 ст.228 УК РФ.
Назначен штраф 25000 рублей. Ранее осуждался по п.в ч.2 ст.158 УК РФ.
"""

TEXT_EMPTY = "Дело прекращено в связи с примирением сторон."


class TestExtractCriminalArticles:
    """Tests for _extract_criminal_articles."""

    def setup_method(self):
        self.searcher = CourtRecordSearch()

    def test_extract_drug_article(self):
        """Extracts article 228 part 2 category 'наркотики' from drug case."""
        articles = self.searcher._extract_criminal_articles(TEXT_DRUG_CASE)
        assert len(articles) >= 1
        art228 = [a for a in articles if a['article'] == '228']
        assert len(art228) >= 1
        assert art228[0]['part'] == '2'
        assert art228[0]['category'] == 'наркотики'

    def test_extract_theft_article(self):
        """Extracts article 158 part 2 paragraph 'в' category 'кража'."""
        articles = self.searcher._extract_criminal_articles(TEXT_THEFT_CASE)
        assert len(articles) >= 1
        art158 = [a for a in articles if a['article'] == '158']
        assert len(art158) >= 1
        assert art158[0]['part'] == '2'
        assert art158[0]['paragraph'] == 'в'
        assert art158[0]['category'] == 'кража'

    def test_extract_multiple_articles(self):
        """Extracts both 228 and 158 from text with multiple articles."""
        articles = self.searcher._extract_criminal_articles(TEXT_MULTIPLE)
        article_numbers = {a['article'] for a in articles}
        assert '228' in article_numbers
        assert '158' in article_numbers
        assert len(articles) >= 2

    def test_extract_empty_text(self):
        """Returns empty list for text with no criminal articles."""
        articles = self.searcher._extract_criminal_articles(TEXT_EMPTY)
        assert articles == []

    def test_extract_verdict_conditional(self):
        """Extracts conditional sentence from drug case verdict."""
        verdict = self.searcher._extract_verdict(TEXT_DRUG_CASE)
        assert 'условно' in verdict or '4' in verdict

    def test_extract_verdict_fine(self):
        """Extracts fine amount from theft case verdict."""
        verdict = self.searcher._extract_verdict(TEXT_THEFT_CASE)
        assert '10000' in verdict

    def test_court_case_has_criminal_articles_field(self):
        """New CourtCase has criminal_articles defaulting to empty list."""
        case = CourtCase(case_number="1-1/2024", court_name="Тест")
        assert hasattr(case, 'criminal_articles')
        assert case.criminal_articles == []
        assert hasattr(case, 'verdict')
        assert case.verdict == ""

#!/usr/bin/env python3
"""
Russian Text Analyzer Prototype for IBP
======================================

Analyzes Russian text from VK wall posts for:
- Sentiment analysis (using dostoevsky)
- Named entity extraction (using natasha)
- Topic/keyword extraction
- Activity patterns
- Character profile generation

Usage:
    python russian_text_analyzer.py --input posts.json
    python russian_text_analyzer.py --text "Привет, как дела?"
    python russian_text_analyzer.py --demo

Dependencies:
    pip install dostoevsky natasha

Author: IBP Project
License: MIT
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import NLP libraries
HAS_DOSTOEVSKY = False
HAS_NATASHA = False

try:
    from dostoevsky.tokenization import RegexTokenizer
    from dostoevsky.models import FastTextSocialNetworkModel
    HAS_DOSTOEVSKY = True
except ImportError:
    logger.warning("dostoevsky not installed. Sentiment analysis will be limited.")
    logger.warning("Install: pip install dostoevsky && python -m dostoevsky download fasttext-social-network-model")

try:
    from natasha import (
        Segmenter, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsSyntaxParser,
        NewsNERTagger, NamesExtractor, Doc
    )
    HAS_NATASHA = True
except ImportError:
    logger.warning("natasha not installed. NER will be disabled.")
    logger.warning("Install: pip install natasha")


# Russian stop words
RUSSIAN_STOP_WORDS = {
    'и', 'в', 'на', 'с', 'по', 'для', 'не', 'что', 'это', 'как', 'от', 'к',
    'из', 'за', 'о', 'но', 'а', 'то', 'все', 'так', 'его', 'же', 'она',
    'он', 'они', 'мы', 'вы', 'ты', 'я', 'или', 'бы', 'у', 'до', 'если',
    'при', 'чтобы', 'который', 'только', 'уже', 'когда', 'этот', 'можно',
    'надо', 'даже', 'будет', 'был', 'была', 'были', 'быть', 'есть',
    'очень', 'где', 'вот', 'себя', 'тоже', 'там', 'потом', 'ещё', 'еще',
    'нет', 'да', 'ну', 'тут', 'чем', 'более', 'через', 'после', 'между',
    'во', 'со', 'под', 'без', 'над', 'об', 'ко'
}

# Risk category keywords
RISK_KEYWORDS = {
    'extremism': [
        'националист', 'ультра', 'радикал', 'революция', 'свержение',
        'ненависть', 'враг', 'уничтожить', 'смерть', 'война'
    ],
    'violence': [
        'убить', 'убью', 'драка', 'насилие', 'избить', 'оружие', 'нож',
        'пистолет', 'взорвать', 'бомба', 'терроризм'
    ],
    'substance_abuse': [
        'наркотик', 'трава', 'кокс', 'героин', 'кислота', 'спайс',
        'пьянка', 'бухло', 'накуриться', 'обдолбаться', 'укуренный'
    ],
    'gambling': [
        'казино', 'ставки', 'покер', 'слоты', 'рулетка', 'букмекер',
        'выигрыш', 'проиграл', 'ставка', 'фонбет', '1xbet'
    ],
    'financial_risk': [
        'кредит', 'долг', 'займ', 'пирамида', 'млм', 'развод',
        'мошенничество', 'схема', 'легкие деньги', 'инвестиция'
    ]
}


@dataclass
class SentimentResult:
    """Sentiment analysis result."""
    positive: float = 0.0
    negative: float = 0.0
    neutral: float = 0.0
    speech: float = 0.0
    skip: float = 0.0
    dominant: str = "neutral"


@dataclass
class NamedEntity:
    """Extracted named entity."""
    text: str
    type: str  # PER, LOC, ORG
    normalized: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk category assessment."""
    category: str
    score: float  # 0.0 - 1.0
    matched_keywords: List[str]
    flagged_posts: List[int]  # Post indices


@dataclass
class ActivityPattern:
    """User activity patterns."""
    posts_by_hour: Dict[int, int]
    posts_by_weekday: Dict[int, int]
    peak_hour: int
    peak_weekday: int
    avg_posts_per_day: float
    most_active_period: str  # morning, afternoon, evening, night


@dataclass
class TextMetrics:
    """Text quality metrics."""
    total_posts: int
    total_words: int
    unique_words: int
    avg_post_length: float
    avg_word_length: float
    vocabulary_richness: float  # unique/total ratio
    emoji_count: int
    emoji_ratio: float
    url_count: int
    hashtag_count: int


@dataclass
class AnalysisResult:
    """Complete text analysis result."""
    sentiment: SentimentResult
    sentiment_by_post: List[SentimentResult]
    entities: List[NamedEntity]
    top_keywords: List[Tuple[str, int]]
    risk_assessment: List[RiskAssessment]
    activity_pattern: Optional[ActivityPattern]
    text_metrics: TextMetrics
    character_profile: str
    analyzed_at: str


class RussianTextAnalyzer:
    """
    Analyzes Russian text content from social media.
    """

    def __init__(self):
        self.sentiment_model = None
        self.tokenizer = None

        # Initialize Natasha components
        self.segmenter = None
        self.morph_vocab = None
        self.emb = None
        self.morph_tagger = None
        self.ner_tagger = None
        self.names_extractor = None

        self._init_models()

    def _init_models(self):
        """Initialize NLP models."""
        # Dostoevsky
        if HAS_DOSTOEVSKY:
            try:
                self.tokenizer = RegexTokenizer()
                self.sentiment_model = FastTextSocialNetworkModel(tokenizer=self.tokenizer)
                logger.info("Dostoevsky sentiment model loaded")
            except Exception as e:
                logger.warning(f"Failed to load dostoevsky model: {e}")
                logger.warning("Run: python -m dostoevsky download fasttext-social-network-model")

        # Natasha
        if HAS_NATASHA:
            try:
                self.segmenter = Segmenter()
                self.morph_vocab = MorphVocab()
                self.emb = NewsEmbedding()
                self.morph_tagger = NewsMorphTagger(self.emb)
                self.ner_tagger = NewsNERTagger(self.emb)
                self.names_extractor = NamesExtractor(self.morph_vocab)
                logger.info("Natasha NLP models loaded")
            except Exception as e:
                logger.warning(f"Failed to load natasha models: {e}")

    def _clean_text(self, text: str) -> str:
        """Clean text for analysis."""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def _extract_words(self, text: str) -> List[str]:
        """Extract words from text, excluding stop words."""
        # Cyrillic and Latin letters only
        words = re.findall(r'[а-яёА-ЯЁa-zA-Z]{3,}', text.lower())
        return [w for w in words if w not in RUSSIAN_STOP_WORDS]

    def analyze_sentiment(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze sentiment of texts."""
        results = []

        if not texts:
            return results

        if self.sentiment_model is None:
            # Fallback: simple keyword-based sentiment
            logger.debug("Using fallback sentiment analysis")
            for text in texts:
                results.append(self._fallback_sentiment(text))
            return results

        try:
            predictions = self.sentiment_model.predict(texts, k=5)

            for pred in predictions:
                result = SentimentResult(
                    positive=pred.get('positive', 0.0),
                    negative=pred.get('negative', 0.0),
                    neutral=pred.get('neutral', 0.0),
                    speech=pred.get('speech', 0.0),
                    skip=pred.get('skip', 0.0)
                )

                # Determine dominant sentiment
                scores = {
                    'positive': result.positive,
                    'negative': result.negative,
                    'neutral': result.neutral
                }
                result.dominant = max(scores, key=scores.get)

                results.append(result)

        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            for text in texts:
                results.append(self._fallback_sentiment(text))

        return results

    def _fallback_sentiment(self, text: str) -> SentimentResult:
        """Simple keyword-based sentiment as fallback."""
        text_lower = text.lower()

        positive_words = ['хорошо', 'отлично', 'прекрасно', 'люблю', 'рад', 'счастлив', 'здорово', 'класс', 'круто', 'супер']
        negative_words = ['плохо', 'ужасно', 'ненавижу', 'злой', 'грустно', 'печально', 'противно', 'отвратительно']

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        total = pos_count + neg_count + 1

        return SentimentResult(
            positive=pos_count / total,
            negative=neg_count / total,
            neutral=1 / total,
            dominant='positive' if pos_count > neg_count else 'negative' if neg_count > pos_count else 'neutral'
        )

    def extract_entities(self, text: str) -> List[NamedEntity]:
        """Extract named entities from text."""
        entities = []

        if not HAS_NATASHA or self.ner_tagger is None:
            return entities

        try:
            doc = Doc(text)
            doc.segment(self.segmenter)
            doc.tag_ner(self.ner_tagger)

            for span in doc.spans:
                entity = NamedEntity(
                    text=span.text,
                    type=span.type,
                    normalized=span.normal if hasattr(span, 'normal') else None
                )
                entities.append(entity)

        except Exception as e:
            logger.debug(f"NER extraction failed: {e}")

        return entities

    def extract_keywords(self, texts: List[str], top_n: int = 20) -> List[Tuple[str, int]]:
        """Extract top keywords from texts."""
        word_counts = Counter()

        for text in texts:
            words = self._extract_words(self._clean_text(text))
            word_counts.update(words)

        return word_counts.most_common(top_n)

    def assess_risk(self, texts: List[str]) -> List[RiskAssessment]:
        """Assess risk categories in texts."""
        assessments = []

        for category, keywords in RISK_KEYWORDS.items():
            matched = []
            flagged = []

            for i, text in enumerate(texts):
                text_lower = text.lower()
                for keyword in keywords:
                    if keyword in text_lower:
                        matched.append(keyword)
                        if i not in flagged:
                            flagged.append(i)

            if matched:
                score = min(len(set(matched)) / len(keywords), 1.0)
                assessments.append(RiskAssessment(
                    category=category,
                    score=score,
                    matched_keywords=list(set(matched)),
                    flagged_posts=flagged
                ))

        # Sort by score descending
        assessments.sort(key=lambda x: x.score, reverse=True)

        return assessments

    def analyze_activity(self, posts: List[Dict]) -> Optional[ActivityPattern]:
        """Analyze posting activity patterns."""
        if not posts:
            return None

        posts_by_hour = defaultdict(int)
        posts_by_weekday = defaultdict(int)

        for post in posts:
            timestamp = post.get('date', 0)
            if not timestamp:
                continue

            dt = datetime.fromtimestamp(timestamp)
            posts_by_hour[dt.hour] += 1
            posts_by_weekday[dt.weekday()] += 1

        if not posts_by_hour:
            return None

        peak_hour = max(posts_by_hour, key=posts_by_hour.get)
        peak_weekday = max(posts_by_weekday, key=posts_by_weekday.get) if posts_by_weekday else 0

        # Determine time period
        if 6 <= peak_hour < 12:
            period = "morning"
        elif 12 <= peak_hour < 18:
            period = "afternoon"
        elif 18 <= peak_hour < 23:
            period = "evening"
        else:
            period = "night"

        # Calculate avg posts per day
        if posts:
            timestamps = [p.get('date', 0) for p in posts if p.get('date')]
            if timestamps:
                time_span = max(timestamps) - min(timestamps)
                days = max(time_span / 86400, 1)
                avg_per_day = len(posts) / days
            else:
                avg_per_day = 0
        else:
            avg_per_day = 0

        return ActivityPattern(
            posts_by_hour=dict(posts_by_hour),
            posts_by_weekday=dict(posts_by_weekday),
            peak_hour=peak_hour,
            peak_weekday=peak_weekday,
            avg_posts_per_day=avg_per_day,
            most_active_period=period
        )

    def calculate_text_metrics(self, texts: List[str]) -> TextMetrics:
        """Calculate text quality metrics."""
        all_words = []
        emoji_count = 0
        url_count = 0
        hashtag_count = 0
        total_length = 0

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )

        for text in texts:
            words = self._extract_words(text)
            all_words.extend(words)
            total_length += len(text)

            # Count emojis
            emoji_count += len(emoji_pattern.findall(text))

            # Count URLs
            url_count += len(re.findall(r'https?://\S+', text))

            # Count hashtags
            hashtag_count += len(re.findall(r'#\w+', text))

        total_words = len(all_words)
        unique_words = len(set(all_words))

        return TextMetrics(
            total_posts=len(texts),
            total_words=total_words,
            unique_words=unique_words,
            avg_post_length=total_length / len(texts) if texts else 0,
            avg_word_length=sum(len(w) for w in all_words) / total_words if total_words else 0,
            vocabulary_richness=unique_words / total_words if total_words else 0,
            emoji_count=emoji_count,
            emoji_ratio=emoji_count / len(texts) if texts else 0,
            url_count=url_count,
            hashtag_count=hashtag_count
        )

    def generate_character_profile(self, result: 'AnalysisResult') -> str:
        """Generate a character profile summary."""
        lines = []

        # Sentiment profile
        sentiment = result.sentiment
        if sentiment.positive > 0.5:
            lines.append("Generally positive and optimistic in communications.")
        elif sentiment.negative > 0.5:
            lines.append("Often expresses negative emotions or complaints.")
        else:
            lines.append("Maintains a balanced, neutral tone in posts.")

        # Activity profile
        if result.activity_pattern:
            ap = result.activity_pattern
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            lines.append(f"Most active during {ap.most_active_period} hours, especially on {weekday_names[ap.peak_weekday]}.")

            if ap.avg_posts_per_day > 5:
                lines.append("Very active poster (>5 posts/day).")
            elif ap.avg_posts_per_day > 1:
                lines.append("Moderately active poster (1-5 posts/day).")
            else:
                lines.append("Occasional poster (<1 post/day).")

        # Text style
        metrics = result.text_metrics
        if metrics.vocabulary_richness > 0.7:
            lines.append("Uses diverse vocabulary, suggesting education or varied interests.")
        elif metrics.vocabulary_richness < 0.3:
            lines.append("Uses repetitive vocabulary, possibly focused on specific topics.")

        if metrics.emoji_ratio > 1:
            lines.append("Frequently uses emojis, indicating casual/expressive communication style.")

        # Risk indicators
        if result.risk_assessment:
            high_risk = [r for r in result.risk_assessment if r.score > 0.3]
            if high_risk:
                categories = [r.category.replace('_', ' ') for r in high_risk]
                lines.append(f"Potential concerns in: {', '.join(categories)}.")

        # Interests from keywords
        if result.top_keywords:
            top_words = [w for w, _ in result.top_keywords[:5]]
            lines.append(f"Frequent topics: {', '.join(top_words)}.")

        return " ".join(lines)

    def analyze(self, posts: List[Dict]) -> AnalysisResult:
        """
        Perform complete text analysis on posts.

        Args:
            posts: List of post dicts with 'text' and optional 'date' fields

        Returns:
            AnalysisResult with all analysis data
        """
        texts = [p.get('text', '') for p in posts if p.get('text')]

        if not texts:
            return AnalysisResult(
                sentiment=SentimentResult(),
                sentiment_by_post=[],
                entities=[],
                top_keywords=[],
                risk_assessment=[],
                activity_pattern=None,
                text_metrics=TextMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                character_profile="No text content to analyze.",
                analyzed_at=datetime.now().isoformat()
            )

        logger.info(f"Analyzing {len(texts)} posts...")

        # Sentiment analysis
        sentiment_results = self.analyze_sentiment(texts)

        # Aggregate sentiment
        avg_sentiment = SentimentResult(
            positive=sum(s.positive for s in sentiment_results) / len(sentiment_results),
            negative=sum(s.negative for s in sentiment_results) / len(sentiment_results),
            neutral=sum(s.neutral for s in sentiment_results) / len(sentiment_results)
        )
        scores = {'positive': avg_sentiment.positive, 'negative': avg_sentiment.negative, 'neutral': avg_sentiment.neutral}
        avg_sentiment.dominant = max(scores, key=scores.get)

        # Entity extraction
        all_entities = []
        for text in texts[:50]:  # Limit for performance
            entities = self.extract_entities(text)
            all_entities.extend(entities)

        # Deduplicate entities
        seen = set()
        unique_entities = []
        for e in all_entities:
            key = (e.text.lower(), e.type)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        # Keywords
        keywords = self.extract_keywords(texts)

        # Risk assessment
        risk = self.assess_risk(texts)

        # Activity patterns
        activity = self.analyze_activity(posts)

        # Text metrics
        metrics = self.calculate_text_metrics(texts)

        # Build result
        result = AnalysisResult(
            sentiment=avg_sentiment,
            sentiment_by_post=sentiment_results,
            entities=unique_entities,
            top_keywords=keywords,
            risk_assessment=risk,
            activity_pattern=activity,
            text_metrics=metrics,
            character_profile="",
            analyzed_at=datetime.now().isoformat()
        )

        # Generate character profile
        result.character_profile = self.generate_character_profile(result)

        logger.info("Analysis complete")
        return result


# ============================================================================
# Demo Mode
# ============================================================================

DEMO_POSTS = [
    {"text": "Отличный день! Погода прекрасная, настроение супер! 🌞", "date": 1706745600},
    {"text": "Сегодня была на концерте в Москве. Незабываемые впечатления!", "date": 1706832000},
    {"text": "Почему так сложно найти хорошую работу в IT? 😔", "date": 1706918400},
    {"text": "Читаю книгу Толстого. Война и мир - шедевр русской литературы.", "date": 1707004800},
    {"text": "Посмотрите мой новый проект на GitHub! Делаю крутое приложение.", "date": 1707091200},
    {"text": "Встретился с друзьями в кафе. Петр рассказал про свою поездку в Питер.", "date": 1707177600},
    {"text": "Опять проблемы с интернетом. Провайдер никак не починит!", "date": 1707264000},
    {"text": "Новый год был отличный! Желаю всем счастья и здоровья! 🎄", "date": 1707350400},
]


def run_demo():
    """Run demo mode."""
    print("\n" + "="*70)
    print("RUSSIAN TEXT ANALYZER - DEMO MODE")
    print("="*70)

    analyzer = RussianTextAnalyzer()
    result = analyzer.analyze(DEMO_POSTS)

    print(f"\n--- SENTIMENT ANALYSIS ---")
    print(f"Overall: {result.sentiment.dominant}")
    print(f"  Positive: {result.sentiment.positive:.2f}")
    print(f"  Negative: {result.sentiment.negative:.2f}")
    print(f"  Neutral:  {result.sentiment.neutral:.2f}")

    print(f"\n--- NAMED ENTITIES ---")
    if result.entities:
        for entity in result.entities[:10]:
            print(f"  [{entity.type}] {entity.text}")
    else:
        print("  (No entities extracted - natasha not installed)")

    print(f"\n--- TOP KEYWORDS ---")
    for word, count in result.top_keywords[:10]:
        print(f"  {word}: {count}")

    print(f"\n--- RISK ASSESSMENT ---")
    if result.risk_assessment:
        for risk in result.risk_assessment:
            print(f"  {risk.category}: {risk.score:.2f} - Keywords: {', '.join(risk.matched_keywords)}")
    else:
        print("  No significant risk indicators found.")

    print(f"\n--- ACTIVITY PATTERN ---")
    if result.activity_pattern:
        ap = result.activity_pattern
        print(f"  Peak hour: {ap.peak_hour}:00")
        print(f"  Most active period: {ap.most_active_period}")
        print(f"  Avg posts/day: {ap.avg_posts_per_day:.2f}")

    print(f"\n--- TEXT METRICS ---")
    m = result.text_metrics
    print(f"  Total posts: {m.total_posts}")
    print(f"  Total words: {m.total_words}")
    print(f"  Vocabulary richness: {m.vocabulary_richness:.2f}")
    print(f"  Avg post length: {m.avg_post_length:.1f} chars")
    print(f"  Emoji ratio: {m.emoji_ratio:.2f} per post")

    print(f"\n--- CHARACTER PROFILE ---")
    print(f"  {result.character_profile}")

    # JSON output
    def result_to_dict(r):
        d = {
            'sentiment': asdict(r.sentiment),
            'entities': [asdict(e) for e in r.entities],
            'top_keywords': r.top_keywords,
            'risk_assessment': [asdict(ra) for ra in r.risk_assessment],
            'activity_pattern': asdict(r.activity_pattern) if r.activity_pattern else None,
            'text_metrics': asdict(r.text_metrics),
            'character_profile': r.character_profile,
            'analyzed_at': r.analyzed_at
        }
        return d

    output = result_to_dict(result)

    print(f"\n{'='*70}")
    print("JSON OUTPUT (truncated):")
    print("="*70)
    print(json.dumps(output, ensure_ascii=False, indent=2)[:1500] + "...")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Russian text from social media posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo
  %(prog)s --input posts.json --output analysis.json
  %(prog)s --text "Привет! Как дела?"

Dependencies:
  pip install dostoevsky natasha
  python -m dostoevsky download fasttext-social-network-model
        """
    )

    parser.add_argument("--input", "-i", help="Input JSON file with posts")
    parser.add_argument("--text", "-t", help="Single text to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.demo:
        output = run_demo()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to: {args.output}")
        return

    if args.text:
        posts = [{"text": args.text, "date": int(datetime.now().timestamp())}]
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            posts = json.load(f)
    else:
        parser.error("--input, --text, or --demo required")

    analyzer = RussianTextAnalyzer()
    result = analyzer.analyze(posts)

    def result_to_dict(r):
        return {
            'sentiment': asdict(r.sentiment),
            'entities': [asdict(e) for e in r.entities],
            'top_keywords': r.top_keywords,
            'risk_assessment': [asdict(ra) for ra in r.risk_assessment],
            'activity_pattern': asdict(r.activity_pattern) if r.activity_pattern else None,
            'text_metrics': asdict(r.text_metrics),
            'character_profile': r.character_profile,
            'analyzed_at': r.analyzed_at
        }

    output = result_to_dict(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Analysis saved to: {args.output}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

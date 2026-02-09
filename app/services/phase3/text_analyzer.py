"""
Text Analyzer - Russian NLP Analysis
====================================
Sentiment analysis, keyword extraction, topic modeling for Russian text.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

# Russian stop words
RUSSIAN_STOP_WORDS = {
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все',
    'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по',
    'только', 'её', 'мне', 'было', 'вот', 'от', 'меня', 'ещё', 'нет', 'о', 'из', 'ему',
    'теперь', 'когда', 'уже', 'вам', 'ни', 'быть', 'был', 'была', 'были', 'есть',
    'их', 'если', 'для', 'или', 'при', 'до', 'того', 'чем', 'об', 'под', 'над',
    'после', 'где', 'сам', 'себя', 'тот', 'эти', 'эта', 'это', 'этот', 'который',
    'которая', 'которое', 'которые', 'мой', 'моя', 'моё', 'мои', 'свой', 'своя',
    'своё', 'свои', 'наш', 'наша', 'наше', 'наши', 'ваш', 'ваша', 'ваше', 'ваши',
    'кто', 'чего', 'кого', 'чему', 'кому', 'чём', 'ком', 'какой', 'какая', 'какое',
    'какие', 'такой', 'такая', 'такое', 'такие', 'один', 'одна', 'одно', 'одни',
    'весь', 'вся', 'всё', 'сам', 'сама', 'само', 'сами', 'самый', 'самая', 'самое',
    'самые', 'чтобы', 'потому', 'тогда', 'можно', 'надо', 'даже', 'ведь', 'более',
    'менее', 'очень', 'тоже', 'также', 'хотя', 'конечно', 'вообще', 'просто'
}

# Sentiment words (simplified Russian sentiment lexicon)
POSITIVE_WORDS = {
    'хорошо', 'отлично', 'прекрасно', 'замечательно', 'великолепно', 'чудесно',
    'радость', 'счастье', 'любовь', 'успех', 'победа', 'праздник', 'красиво',
    'супер', 'класс', 'круто', 'молодец', 'спасибо', 'благодарю', 'нравится',
    'люблю', 'обожаю', 'восторг', 'рад', 'рада', 'счастлив', 'счастлива',
    'веселье', 'улыбка', 'смех', 'добро', 'мир', 'дружба', 'семья', 'лучший'
}

NEGATIVE_WORDS = {
    'плохо', 'ужасно', 'отвратительно', 'грустно', 'печально', 'больно',
    'злость', 'ненависть', 'обида', 'разочарование', 'провал', 'неудача',
    'ужас', 'кошмар', 'катастрофа', 'проблема', 'беда', 'горе', 'слёзы',
    'страх', 'боль', 'злой', 'злая', 'грустный', 'грустная', 'плачу',
    'ненавижу', 'бесит', 'раздражает', 'достало', 'устал', 'устала',
    'надоело', 'противно', 'мерзко', 'дерьмо', 'чёрт', 'блин', 'жаль'
}

# Topic keywords
TOPIC_KEYWORDS = {
    'политика': ['политика', 'выборы', 'президент', 'депутат', 'партия', 'закон', 'государство', 'власть', 'путин', 'правительство'],
    'спорт': ['футбол', 'хоккей', 'матч', 'игра', 'команда', 'спорт', 'тренировка', 'победа', 'чемпионат', 'олимпиада'],
    'путешествия': ['путешествие', 'отпуск', 'море', 'пляж', 'самолёт', 'отель', 'турция', 'египет', 'тайланд', 'экскурсия'],
    'работа': ['работа', 'офис', 'начальник', 'коллега', 'зарплата', 'проект', 'карьера', 'бизнес', 'компания', 'клиент'],
    'семья': ['семья', 'дети', 'ребёнок', 'муж', 'жена', 'родители', 'мама', 'папа', 'бабушка', 'дедушка'],
    'хобби': ['хобби', 'музыка', 'кино', 'фильм', 'книга', 'игра', 'творчество', 'рисование', 'фотография', 'танцы'],
    'еда': ['еда', 'ресторан', 'кафе', 'готовить', 'рецепт', 'вкусно', 'завтрак', 'обед', 'ужин', 'пицца'],
    'технологии': ['компьютер', 'телефон', 'интернет', 'программа', 'приложение', 'сайт', 'айфон', 'андроид', 'обновление', 'софт'],
    'здоровье': ['здоровье', 'врач', 'больница', 'лекарство', 'болезнь', 'лечение', 'диета', 'фитнес', 'спортзал', 'тренировка'],
    'финансы': ['деньги', 'банк', 'кредит', 'зарплата', 'инвестиции', 'акции', 'рубль', 'доллар', 'курс', 'экономика'],
}


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    score: float  # -1 to 1 (negative to positive)
    label: str  # 'positive', 'negative', 'neutral'
    positive_words: List[str] = field(default_factory=list)
    negative_words: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict:
        return {
            'score': self.score,
            'label': self.label,
            'positive_words': self.positive_words,
            'negative_words': self.negative_words,
            'confidence': self.confidence
        }


@dataclass
class TextAnalysisResult:
    """Complete text analysis result."""
    sentiment: SentimentResult = None
    keywords: List[Tuple[str, int]] = field(default_factory=list)
    topics: Dict[str, float] = field(default_factory=dict)
    word_count: int = 0
    avg_word_length: float = 0
    emoji_count: int = 0
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    language: str = "ru"
    posting_times: List[int] = field(default_factory=list)  # Hours of day

    def to_dict(self) -> Dict:
        return {
            'sentiment': self.sentiment.to_dict() if self.sentiment else None,
            'keywords': self.keywords,
            'topics': self.topics,
            'word_count': self.word_count,
            'avg_word_length': self.avg_word_length,
            'emoji_count': self.emoji_count,
            'hashtags': self.hashtags,
            'mentions': self.mentions,
            'language': self.language,
            'posting_times': self.posting_times
        }


class TextAnalyzer:
    """
    Analyze Russian text from social media posts.

    Features:
    - Sentiment analysis (positive/negative/neutral)
    - Keyword extraction
    - Topic classification
    - Writing style analysis
    - Emoji/hashtag/mention extraction
    """

    def __init__(self):
        self._pymorphy = None

    @property
    def morph(self):
        """Lazy load pymorphy2 analyzer."""
        if self._pymorphy is None:
            try:
                import pymorphy2
                self._pymorphy = pymorphy2.MorphAnalyzer()
            except ImportError:
                logger.warning("pymorphy2 not available, using basic analysis")
                self._pymorphy = False
        return self._pymorphy if self._pymorphy else None

    def analyze_posts(self, posts: List[Dict]) -> TextAnalysisResult:
        """
        Analyze a collection of social media posts.

        Args:
            posts: List of post dictionaries with 'text' and optional 'date' keys

        Returns:
            TextAnalysisResult with aggregated analysis
        """
        all_text = []
        all_words = []
        hashtags = []
        mentions = []
        posting_times = []
        emoji_count = 0

        for post in posts:
            text = post.get('text', '') or post.get('content', '') or ''
            if not text:
                continue

            all_text.append(text)

            # Extract hashtags
            hashtags.extend(re.findall(r'#(\w+)', text))

            # Extract mentions
            mentions.extend(re.findall(r'@(\w+)', text))

            # Count emojis
            emoji_count += len(re.findall(
                r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]',
                text
            ))

            # Extract posting time
            date_str = post.get('date', '') or post.get('timestamp', '')
            if date_str:
                try:
                    if isinstance(date_str, (int, float)):
                        dt = datetime.fromtimestamp(date_str)
                    else:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    posting_times.append(dt.hour)
                except Exception:
                    pass

            # Tokenize and collect words
            words = self._tokenize(text)
            all_words.extend(words)

        if not all_text:
            return TextAnalysisResult()

        combined_text = ' '.join(all_text)

        # Sentiment analysis
        sentiment = self._analyze_sentiment(all_words)

        # Keyword extraction
        keywords = self._extract_keywords(all_words)

        # Topic classification
        topics = self._classify_topics(all_words)

        # Calculate stats
        word_count = len(all_words)
        avg_word_length = sum(len(w) for w in all_words) / len(all_words) if all_words else 0

        return TextAnalysisResult(
            sentiment=sentiment,
            keywords=keywords,
            topics=topics,
            word_count=word_count,
            avg_word_length=round(avg_word_length, 2),
            emoji_count=emoji_count,
            hashtags=list(set(hashtags))[:50],
            mentions=list(set(mentions))[:50],
            language=self._detect_language(combined_text),
            posting_times=posting_times
        )

    def analyze(self, text: str) -> TextAnalysisResult:
        """Analyze a single text string. Alias for analyze_single_text."""
        return self.analyze_posts([{'text': text}])

    def analyze_single_text(self, text: str) -> TextAnalysisResult:
        """Analyze a single piece of text."""
        return self.analyze_posts([{'text': text}])

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove special chars but keep Cyrillic
        text = re.sub(r'[^\w\sа-яА-ЯёЁ]', ' ', text)
        # Split and filter
        words = text.lower().split()
        # Remove stop words and short words
        words = [w for w in words if len(w) > 2 and w not in RUSSIAN_STOP_WORDS]
        return words

    def _lemmatize(self, word: str) -> str:
        """Get base form of word using pymorphy2."""
        if self.morph:
            try:
                parsed = self.morph.parse(word)
                if parsed:
                    return parsed[0].normal_form
            except Exception:
                pass
        return word

    def _analyze_sentiment(self, words: List[str]) -> SentimentResult:
        """Analyze sentiment of word list."""
        positive_found = []
        negative_found = []

        for word in words:
            # Check original and lemmatized form
            forms = [word]
            if self.morph:
                forms.append(self._lemmatize(word))

            for form in forms:
                if form in POSITIVE_WORDS:
                    positive_found.append(word)
                    break
                elif form in NEGATIVE_WORDS:
                    negative_found.append(word)
                    break

        pos_count = len(positive_found)
        neg_count = len(negative_found)
        total_sentiment_words = pos_count + neg_count

        if total_sentiment_words == 0:
            return SentimentResult(
                score=0,
                label='neutral',
                positive_words=[],
                negative_words=[],
                confidence=0.3
            )

        # Calculate score
        score = (pos_count - neg_count) / total_sentiment_words

        # Determine label
        if score > 0.2:
            label = 'positive'
        elif score < -0.2:
            label = 'negative'
        else:
            label = 'neutral'

        # Confidence based on sample size
        confidence = min(0.9, 0.3 + (total_sentiment_words / 50))

        return SentimentResult(
            score=round(score, 3),
            label=label,
            positive_words=list(set(positive_found))[:10],
            negative_words=list(set(negative_found))[:10],
            confidence=round(confidence, 2)
        )

    def _extract_keywords(self, words: List[str], top_n: int = 20) -> List[Tuple[str, int]]:
        """Extract top keywords by frequency."""
        # Lemmatize if available
        if self.morph:
            words = [self._lemmatize(w) for w in words]

        # Count frequencies
        word_counts = Counter(words)

        # Get top words
        return word_counts.most_common(top_n)

    def _classify_topics(self, words: List[str]) -> Dict[str, float]:
        """Classify text into topics."""
        topic_scores = {}

        # Lemmatize words for better matching
        word_set = set(words)
        if self.morph:
            word_set.update(self._lemmatize(w) for w in words)

        total_matches = 0

        for topic, keywords in TOPIC_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in word_set)
            if matches > 0:
                topic_scores[topic] = matches
                total_matches += matches

        # Normalize scores
        if total_matches > 0:
            topic_scores = {
                topic: round(score / total_matches, 3)
                for topic, score in topic_scores.items()
            }

        # Sort by score
        topic_scores = dict(sorted(
            topic_scores.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        return topic_scores

    def _detect_language(self, text: str) -> str:
        """Detect language (simplified - check for Cyrillic)."""
        cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
        latin_count = len(re.findall(r'[a-zA-Z]', text))

        if cyrillic_count > latin_count:
            return 'ru'
        elif latin_count > cyrillic_count:
            return 'en'
        else:
            return 'unknown'

    def generate_word_cloud_data(self, words: List[str]) -> List[Dict]:
        """Generate data for word cloud visualization."""
        # Get word frequencies
        if self.morph:
            words = [self._lemmatize(w) for w in words]

        word_counts = Counter(words)

        # Format for visualization
        data = [
            {'text': word, 'value': count}
            for word, count in word_counts.most_common(100)
        ]

        return data

    def get_posting_pattern(self, posting_times: List[int]) -> Dict:
        """Analyze posting time patterns."""
        if not posting_times:
            return {'pattern': 'unknown', 'peak_hours': [], 'timezone_guess': None}

        hour_counts = Counter(posting_times)

        # Find peak hours
        peak_hours = [hour for hour, _ in hour_counts.most_common(3)]

        # Guess activity pattern
        night_posts = sum(hour_counts.get(h, 0) for h in range(0, 6))
        morning_posts = sum(hour_counts.get(h, 0) for h in range(6, 12))
        day_posts = sum(hour_counts.get(h, 0) for h in range(12, 18))
        evening_posts = sum(hour_counts.get(h, 0) for h in range(18, 24))

        total = len(posting_times)
        if total == 0:
            pattern = 'unknown'
        elif night_posts / total > 0.3:
            pattern = 'night_owl'
        elif morning_posts / total > 0.3:
            pattern = 'early_bird'
        elif evening_posts / total > 0.4:
            pattern = 'evening_active'
        else:
            pattern = 'regular'

        return {
            'pattern': pattern,
            'peak_hours': peak_hours,
            'distribution': {
                'night': round(night_posts / total, 2) if total else 0,
                'morning': round(morning_posts / total, 2) if total else 0,
                'day': round(day_posts / total, 2) if total else 0,
                'evening': round(evening_posts / total, 2) if total else 0
            }
        }


# Singleton instance
text_analyzer = TextAnalyzer()

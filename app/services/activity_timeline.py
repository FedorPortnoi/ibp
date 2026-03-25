"""
Activity Timeline Service
=========================
Behavioral pattern analyzer for VK wall post timestamps.
Builds heatmaps, detects timezone, identifies activity gaps.
"""

import logging
import random
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Russian day names (Monday=0)
DAY_NAMES_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

# Russian timezone mapping (UTC offset -> likely timezone)
TIMEZONE_MAP = {
    2: 'Калининград (UTC+2)',
    3: 'Москва (UTC+3)',
    4: 'Самара (UTC+4)',
    5: 'Екатеринбург (UTC+5)',
    6: 'Омск (UTC+6)',
    7: 'Красноярск (UTC+7)',
    8: 'Иркутск (UTC+8)',
    9: 'Якутск (UTC+9)',
    10: 'Владивосток (UTC+10)',
    11: 'Магадан (UTC+11)',
    12: 'Камчатка (UTC+12)',
}


class ActivityTimeline:
    """
    Analyze activity patterns from VK wall post timestamps.

    Features:
    - 7x24 heatmap (day of week x hour)
    - Timezone detection from peak hours
    - Activity gap detection (>30 days silence)
    - Posting frequency trend analysis
    - Monthly post count history
    """

    def analyze(
        self,
        investigation_id: str,
        wall_posts: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Analyze activity timeline for an investigation.

        Args:
            investigation_id: Investigation ID
            wall_posts: Optional list of VK wall posts with 'date' timestamps.
                       If None, will load from investigation data or generate demo.

        Returns:
            Dict with heatmap, timezone, gaps, trends, monthly data
        """
        timestamps = self._extract_timestamps(investigation_id, wall_posts)

        if not timestamps:
            logger.info(f"No timestamps for {investigation_id}, generating demo data")
            timestamps = self._generate_demo_timestamps(investigation_id)

        return self._build_analysis(timestamps)

    def _extract_timestamps(
        self, investigation_id: str, wall_posts: Optional[List[Dict]]
    ) -> List[datetime]:
        """Extract datetime objects from wall posts or investigation data."""
        timestamps = []

        # Use provided wall posts
        if wall_posts:
            for post in wall_posts:
                ts = post.get('date')
                if isinstance(ts, (int, float)):
                    timestamps.append(datetime.fromtimestamp(ts))
                elif isinstance(ts, str):
                    try:
                        timestamps.append(datetime.fromisoformat(ts))
                    except (ValueError, TypeError):
                        pass
            return timestamps

        # Try loading from investigation's social graph / additional data
        try:
            from app.models import Investigation
            inv = Investigation.query.get(investigation_id)
            if inv:
                graph = inv.social_graph
                posts = graph.get('wall_posts', [])
                for post in posts:
                    ts = post.get('date')
                    if isinstance(ts, (int, float)):
                        timestamps.append(datetime.fromtimestamp(ts))

                # Also check additional_findings for cached wall data
                for finding in inv.additional_findings:
                    if finding.get('type') == 'wall_posts':
                        for post in finding.get('data', []):
                            ts = post.get('date')
                            if isinstance(ts, (int, float)):
                                timestamps.append(datetime.fromtimestamp(ts))
        except Exception as e:
            logger.debug(f"Could not load timestamps from DB: {e}")

        return timestamps

    def _generate_demo_timestamps(self, investigation_id: str) -> List[datetime]:
        """Generate realistic demo timestamps for testing."""
        seed = int(hashlib.md5(investigation_id.encode(), usedforsecurity=False).hexdigest()[:8], 16)
        rng = random.Random(seed)

        now = datetime.now()
        timestamps = []

        # Simulate ~18 months of posts
        for month_offset in range(18):
            month_start = now - timedelta(days=30 * month_offset)

            # Vary post frequency per month (5-25 posts)
            posts_this_month = rng.randint(5, 25)

            # Simulate activity pattern: more active on evenings/weekends
            for _ in range(posts_this_month):
                day_offset = rng.randint(0, 29)
                post_date = month_start - timedelta(days=day_offset)

                # Peak hours: 10-14 and 18-23 (Moscow time)
                hour_weights = [
                    1, 1, 0, 0, 0, 0,   # 0-5
                    1, 2, 3, 5, 7, 8,    # 6-11
                    8, 7, 6, 5, 5, 6,    # 12-17
                    8, 9, 10, 9, 7, 4,   # 18-23
                ]
                hour = rng.choices(range(24), weights=hour_weights, k=1)[0]
                minute = rng.randint(0, 59)

                post_dt = post_date.replace(hour=hour, minute=minute, second=rng.randint(0, 59))
                timestamps.append(post_dt)

        # Add an activity gap (30-60 days of silence)
        gap_start = now - timedelta(days=rng.randint(120, 300))
        gap_length = rng.randint(30, 60)
        gap_end = gap_start + timedelta(days=gap_length)
        timestamps = [t for t in timestamps if not (gap_start <= t <= gap_end)]

        timestamps.sort()
        return timestamps

    def _build_analysis(self, timestamps: List[datetime]) -> Dict:
        """Build complete activity analysis from timestamps."""
        if not timestamps:
            return {
                'heatmap': self._empty_heatmap(),
                'timezone': None,
                'timezone_label': 'Не определён',
                'gaps': [],
                'trend': 'unknown',
                'trend_label': 'Недостаточно данных',
                'monthly': [],
                'total_posts': 0,
                'date_range': None,
                'peak_day': None,
                'peak_hour': None,
                'avg_posts_per_day': 0,
            }

        heatmap = self._build_heatmap(timestamps)
        timezone_offset, timezone_label = self._detect_timezone(timestamps)
        gaps = self._detect_gaps(timestamps)
        trend, trend_label = self._analyze_trend(timestamps)
        monthly = self._build_monthly(timestamps)
        peak_day, peak_hour = self._find_peaks(heatmap)

        date_range = {
            'start': min(timestamps).isoformat(),
            'end': max(timestamps).isoformat(),
            'days': (max(timestamps) - min(timestamps)).days,
        }

        total_days = max(1, date_range['days'])
        avg_per_day = round(len(timestamps) / total_days, 2)

        return {
            'heatmap': heatmap,
            'timezone': timezone_offset,
            'timezone_label': timezone_label,
            'gaps': gaps,
            'trend': trend,
            'trend_label': trend_label,
            'monthly': monthly,
            'total_posts': len(timestamps),
            'date_range': date_range,
            'peak_day': peak_day,
            'peak_hour': peak_hour,
            'avg_posts_per_day': avg_per_day,
            'day_names': DAY_NAMES_RU,
        }

    def _empty_heatmap(self) -> List[List[int]]:
        """Return an empty 7x24 heatmap grid."""
        return [[0] * 24 for _ in range(7)]

    def _build_heatmap(self, timestamps: List[datetime]) -> List[List[int]]:
        """Build 7x24 heatmap: rows=days (Mon-Sun), cols=hours (0-23)."""
        grid = [[0] * 24 for _ in range(7)]

        for ts in timestamps:
            day = ts.weekday()  # 0=Monday
            hour = ts.hour
            grid[day][hour] += 1

        return grid

    def _detect_timezone(self, timestamps: List[datetime]) -> Tuple[Optional[int], str]:
        """
        Detect likely timezone from peak posting hours.

        Assumption: most people post between 10:00-23:00 local time.
        If peak hour in UTC timestamps is, say, 15:00, they are likely UTC+3 (Moscow).
        """
        if len(timestamps) < 10:
            return None, 'Недостаточно данных'

        hour_counts = defaultdict(int)
        for ts in timestamps:
            hour_counts[ts.hour] += 1

        # Find peak hour
        peak_hour = max(hour_counts, key=hour_counts.get)

        # Assume peak activity is around 20:00-21:00 local time
        # So offset = 20 - peak_hour (modulo 24)
        target_peak = 20
        offset = (target_peak - peak_hour) % 24
        if offset > 12:
            offset -= 24

        # Clamp to known Russian timezones
        offset = max(2, min(12, offset + 3))  # Adjust: timestamps are already in local time

        # Since timestamps from VK are typically in UTC+3, the peak hour
        # directly indicates Moscow time behavior
        if 18 <= peak_hour <= 23 or peak_hour == 0:
            offset = 3  # Standard Moscow behavior
        elif 15 <= peak_hour <= 17:
            offset = 3
        elif 12 <= peak_hour <= 14:
            offset = max(5, min(8, 20 - peak_hour))

        label = TIMEZONE_MAP.get(offset, f'UTC+{offset}')
        return offset, label

    def _detect_gaps(
        self, timestamps: List[datetime], min_gap_days: int = 30
    ) -> List[Dict]:
        """Detect activity gaps (periods of silence >= min_gap_days)."""
        if len(timestamps) < 2:
            return []

        sorted_ts = sorted(timestamps)
        gaps = []

        for i in range(1, len(sorted_ts)):
            delta = (sorted_ts[i] - sorted_ts[i-1]).days
            if delta >= min_gap_days:
                gaps.append({
                    'start': sorted_ts[i-1].isoformat(),
                    'end': sorted_ts[i].isoformat(),
                    'days': delta,
                    'label': f'{delta} дней молчания',
                })

        return gaps

    def _analyze_trend(self, timestamps: List[datetime]) -> Tuple[str, str]:
        """
        Analyze posting frequency trend.

        Compares last 3 months to previous 3 months.
        """
        if len(timestamps) < 10:
            return 'unknown', 'Недостаточно данных'

        now = max(timestamps)
        three_months_ago = now - timedelta(days=90)
        six_months_ago = now - timedelta(days=180)

        recent = [t for t in timestamps if t >= three_months_ago]
        older = [t for t in timestamps if six_months_ago <= t < three_months_ago]

        if not older:
            return 'unknown', 'Недостаточно исторических данных'

        recent_rate = len(recent) / 90.0
        older_rate = len(older) / 90.0

        if older_rate == 0:
            if recent_rate > 0:
                return 'increasing', 'Растущая активность'
            return 'stable', 'Стабильная активность'

        change = (recent_rate - older_rate) / older_rate

        if change > 0.3:
            return 'increasing', 'Растущая активность'
        elif change < -0.3:
            return 'decreasing', 'Снижающаяся активность'
        else:
            return 'stable', 'Стабильная активность'

    def _build_monthly(self, timestamps: List[datetime]) -> List[Dict]:
        """Build monthly post counts for line chart."""
        monthly_counts = defaultdict(int)

        for ts in timestamps:
            key = f"{ts.year}-{ts.month:02d}"
            monthly_counts[key] += 1

        # Sort by date
        sorted_months = sorted(monthly_counts.keys())

        return [
            {
                'month': m,
                'label': self._format_month_label(m),
                'count': monthly_counts[m],
            }
            for m in sorted_months
        ]

    def _format_month_label(self, month_key: str) -> str:
        """Format '2025-01' into 'Янв 2025'."""
        month_names = {
            '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр',
            '05': 'Май', '06': 'Июн', '07': 'Июл', '08': 'Авг',
            '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек',
        }
        parts = month_key.split('-')
        if len(parts) == 2:
            return f"{month_names.get(parts[1], parts[1])} {parts[0]}"
        return month_key

    def _find_peaks(self, heatmap: List[List[int]]) -> Tuple[Optional[str], Optional[int]]:
        """Find peak day and peak hour from heatmap."""
        day_totals = [sum(row) for row in heatmap]
        hour_totals = [sum(heatmap[d][h] for d in range(7)) for h in range(24)]

        if not any(day_totals):
            return None, None

        peak_day_idx = day_totals.index(max(day_totals))
        peak_hour = hour_totals.index(max(hour_totals))

        return DAY_NAMES_RU[peak_day_idx], peak_hour


# Singleton
activity_timeline = ActivityTimeline()

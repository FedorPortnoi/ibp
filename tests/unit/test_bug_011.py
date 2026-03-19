"""Test BUG-011: Geo extraction from post text."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.phase3.geo_extractor import GeoExtractor, RUSSIAN_CITIES

def test_city_aliases_count():
    """RUSSIAN_CITIES must have >= 50 entries."""
    count = len(RUSSIAN_CITIES)
    assert count >= 50, f"FAIL: only {count} cities, need >= 50"
    print(f"PASS: {count} city entries in RUSSIAN_CITIES")

def test_common_aliases():
    """Common aliases must be present."""
    required = ['питер', 'спб', 'мск', 'екб', 'нск', 'ростов', 'нижний', 'кубань']
    for alias in required:
        assert alias in RUSSIAN_CITIES, f"FAIL: alias '{alias}' not in RUSSIAN_CITIES"
    print(f"PASS: all {len(required)} required aliases present")

def test_extract_locations_from_posts():
    """Must find >= 3 locations from 4 test posts."""
    extractor = GeoExtractor()
    posts = [
        {'text': 'Привет из Питера! #спб', 'date': 1700000000, 'id': 1, 'owner_id': 123},
        {'text': 'Переехал в Краснодар год назад', 'date': 1700100000, 'id': 2, 'owner_id': 123},
        {'text': 'г. Сочи, отдыхаем', 'date': 1700200000, 'id': 3, 'owner_id': 123},
        {'text': 'живу в мск уже 5 лет', 'date': 1700300000, 'id': 4, 'owner_id': 123},
    ]
    locations = extractor.extract_locations_from_posts(posts)
    city_names = [loc.city.lower() for loc in locations]
    print(f"Found {len(locations)} locations: {city_names}")

    assert len(locations) >= 3, f"FAIL: only {len(locations)} locations from 4 posts"

    # Check specific cities
    all_names = ' '.join(city_names)
    has_spb = 'петербург' in all_names or 'питер' in all_names or 'спб' in all_names
    has_krasnodar = 'краснодар' in all_names
    has_sochi = 'сочи' in all_names
    has_moscow = 'москва' in all_names or 'мск' in all_names

    assert has_spb or has_krasnodar, f"FAIL: neither SPb nor Krasnodar found in {city_names}"
    print(f"PASS: found >= 3 locations including expected cities")

if __name__ == '__main__':
    test_city_aliases_count()
    test_common_aliases()
    test_extract_locations_from_posts()
    print("\nAll BUG-011 tests PASSED")

"""Test city matching fix."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.phase1.buratino_vk_search import BuratinoVKSearch
searcher = BuratinoVKSearch.__new__(BuratinoVKSearch)

pairs = [
    ('Москва', 'Moscow', True),
    ('Москва', 'Москва', True),
    ('Москва', 'Moskva', True),
    ('Санкт-Петербург', 'Saint Petersburg', True),
    ('Санкт-Петербург', 'Sankt-Peterburg', True),
    ('Санкт-Петербург', 'St. Petersburg', True),
    ('Новосибирск', 'Novosibirsk', True),
    ('Екатеринбург', 'Yekaterinburg', True),
    ('Казань', 'Kazan', True),
    ('Москва', 'Санкт-Петербург', False),
    ('Москва', 'Novosibirsk', False),
    ('Питер', 'Saint Petersburg', True),
]
all_ok = True
for search_city, profile_city, expected in pairs:
    result = searcher._city_matches(search_city, profile_city)
    status = "OK" if result == expected else "FAIL"
    if result != expected:
        all_ok = False
    print(f"[{status}] {search_city} vs {profile_city} -> {result} (expected {expected})")

print()
print("ALL PASSED" if all_ok else "SOME FAILED")

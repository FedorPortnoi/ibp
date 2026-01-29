"""
Quick diagnostic script for Phase 2 services.
Run with: python test_phase2_services.py
"""

import sys
import time
import logging

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

print("=" * 60)
print("IBP Phase 2 Services Diagnostic")
print("=" * 60)

# Test 1: Profile Scraper
print("\n=== TEST 1: Profile Scraper ===")
try:
    from app.services.phase2.profile_scraper import scrape_profile

    # Use a public VK profile
    test_url = "https://vk.com/durov"  # Pavel Durov's profile

    start = time.time()
    result = scrape_profile(test_url, "vk")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Bio text length: {len(result.bio_text)} chars")
    print(f"Bio preview: {result.bio_text[:200]!r}")
    print(f"Phones found: {result.phones}")
    print(f"Emails found: {result.emails}")
    print(f"Other socials: {result.other_socials}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 2: Email Generator
print("\n=== TEST 2: Email Generator ===")
try:
    from app.services.phase2.email_generator import generate_email_candidates, generate_from_username

    start = time.time()
    emails = generate_email_candidates("Tikhon", "Portnoi")
    emails.extend(generate_from_username("tikhon_portnoi"))
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Generated {len(emails)} email candidates")
    print(f"First 10: {emails[:10]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 3: Username Intelligence
print("\n=== TEST 3: Username Intelligence ===")
try:
    from app.services.phase2.username_intelligence import analyze_username, UsernameIntelligence

    start = time.time()
    analysis = analyze_username("tikhon_portnoi")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Base name: {analysis.base_name}")
    print(f"Possible first name: {analysis.possible_first_name}")
    print(f"Possible last name: {analysis.possible_last_name}")
    print(f"Variations: {analysis.variations[:10]}")
    print(f"Email candidates: {analysis.email_candidates[:10]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 4: Russian Phone Validator
print("\n=== TEST 4: Russian Phone Validator ===")
try:
    from app.services.phase2.russian_phone_validator import RussianPhoneValidator

    validator = RussianPhoneValidator()
    test_phones = ["+7 999 123-45-67", "89991234567", "+7(495)123-45-67"]

    for phone in test_phones:
        result = validator.validate(phone)
        print(f"  {phone} -> valid={result.is_valid}, normalized={result.normalized}, display={result.display_format}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 5: Holehe (quick check - just one email)
print("\n=== TEST 5: Holehe Service (1 email) ===")
try:
    from app.services.phase2.holehe_service import check_email_sync

    test_email = "durov@telegram.org"  # Probably not registered anywhere except Telegram

    start = time.time()
    result = check_email_sync(test_email)
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Email: {result.email}")
    print(f"Total checked: {result.total_checked}")
    print(f"Total registered: {result.total_registered}")
    print(f"Error: {result.error}")
    if result.registered_services:
        print(f"Services: {[s.service for s in result.registered_services[:5]]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 6: OK Checker (quick check)
print("\n=== TEST 6: OK Checker ===")
try:
    from app.services.phase2.ok_checker import check_ok_account

    start = time.time()
    result = check_ok_account("test@mail.ru")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Query: {result.query}")
    print(f"Exists: {result.exists}")
    print(f"Masked phone: {result.masked_phone}")
    print(f"Masked email: {result.masked_email}")
    print(f"Error: {result.error}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 7: VK API Extractor
print("\n=== TEST 7: VK API Extractor ===")
try:
    from app.services.phase2.vk_api_extractor import VKAPIExtractor

    extractor = VKAPIExtractor()

    start = time.time()
    result = extractor.extract_from_url("https://vk.com/durov")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Screen name: {result.screen_name}")
    print(f"Phones: {result.phones}")
    print(f"Emails: {result.emails}")
    print(f"Telegram: {result.telegram}")
    print(f"Instagram: {result.instagram}")
    print(f"Error: {result.error}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 8: VK Wall Extractor
print("\n=== TEST 8: VK Wall Extractor ===")
try:
    from app.services.phase2.vk_wall_extractor import extract_vk_wall_contacts

    start = time.time()
    result = extract_vk_wall_contacts("https://vk.com/durov", access_token=None)
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Posts analyzed: {result.posts_analyzed}")
    print(f"Phones found: {len(result.phones)}")
    print(f"Emails found: {len(result.emails)}")
    print(f"Telegram usernames: {result.telegram_usernames}")
    print(f"Errors: {result.errors}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 9: YaSeeker
print("\n=== TEST 9: YaSeeker ===")
try:
    from app.services.phase2.yaseeker_service import YaSeekerService

    yaseeker = YaSeekerService()

    start = time.time()
    results = yaseeker.check_all_services("durov")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Accounts found: {len(results)}")
    for acc in results[:5]:
        print(f"  - {acc.platform}: {acc.url}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 10: Breach Checker
print("\n=== TEST 10: Breach Checker ===")
try:
    from app.services.phase2.breach_checker import check_email_breaches

    start = time.time()
    result = check_email_breaches("test@example.com")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.1f}s")
    print(f"Target: {result.target}")
    print(f"Found in breaches: {result.found_in_breaches}")
    print(f"Breach count: {result.breach_count}")
    print(f"Checked services: {result.checked_services}")
    print(f"Errors: {result.errors}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Diagnostic complete!")
print("=" * 60)

# -*- coding: utf-8 -*-
"""
Cycle 9 Test: Full System Test with All 4 Targets
=================================================
Tests the complete Phase 2 enhancement with all target profiles.

Targets:
1. Tikhon Portnoi
2. Daniil Glazkov (@etoglaz)
3. Danya Mescheryakov
4. Angelina Pilyushina

Tests:
- Email source checking (9+ sources)
- Phone source checking (9+ sources)
- Cross-validation (phone->name, email->social)
"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

print("=" * 70)
print("CYCLE 9: FULL SYSTEM TEST - ALL 4 TARGETS")
print("=" * 70)

# Define test targets
TARGETS = [
    {
        'name': 'Tikhon Portnoi',
        'name_ru': 'Тихон Портной',
        'test_phones': ['+7 (999) 123-45-67'],
        'test_emails': ['tikhon.portnoi@gmail.com'],
        'profile_url': 'https://vk.com/tikhon_portnoi',
    },
    {
        'name': 'Daniil Glazkov',
        'name_ru': 'Даниил Глазков',
        'username': 'etoglaz',
        'test_phones': ['+7 (915) 555-12-34'],
        'test_emails': ['etoglaz@gmail.com', 'daniil.glazkov@mail.ru'],
        'profile_url': 'https://vk.com/etoglaz',
    },
    {
        'name': 'Danya Mescheryakov',
        'name_ru': 'Даня Мещеряков',
        'test_phones': ['+7 (926) 111-22-33'],
        'test_emails': ['danya.mescheryakov@gmail.com'],
        'profile_url': None,
    },
    {
        'name': 'Angelina Pilyushina',
        'name_ru': 'Ангелина Пилюшина',
        'test_phones': ['+7 (903) 444-55-66'],
        'test_emails': ['angelina.pilyushina@mail.ru'],
        'profile_url': None,
    },
]

# Test results tracking
results = {
    'email_sources_tested': 0,
    'phone_sources_tested': 0,
    'email_validations': 0,
    'phone_validations': 0,
    'email_validated': 0,
    'phone_validated': 0,
    'cross_validations': 0,
    'errors': [],
}

# Test 1: Email Sources
print("\n" + "=" * 70)
print("TEST 1: EMAIL SOURCES (Cycle 1-3)")
print("=" * 70)

try:
    from app.services.phase2.email_sources import CombinedEmailSources

    email_sources = CombinedEmailSources()
    print("Available email sources:")
    sources_list = ['epieos', 'hunter', 'emailrep', 'snov', 'github_extractor',
                    'telegram_extractor', 'vk_extractor', 'ok_extractor']
    for src in sources_list:
        has_src = hasattr(email_sources, src) and getattr(email_sources, src) is not None
        print(f"  - {src}: {'YES' if has_src else 'NO'}")
        if has_src:
            results['email_sources_tested'] += 1

    # Test with one email
    print("\nTesting email verification...")
    test_email = "test@gmail.com"
    try:
        epieos_result = email_sources.epieos.check(test_email)
        print(f"  Epieos check: {epieos_result}")
    except Exception as e:
        print(f"  Epieos error: {e}")

except Exception as e:
    print(f"Email sources error: {e}")
    results['errors'].append(f"Email sources: {e}")

# Test 2: Phone Sources
print("\n" + "=" * 70)
print("TEST 2: PHONE SOURCES (Cycle 4-6)")
print("=" * 70)

try:
    from app.services.phase2.phone_sources import CombinedPhoneSources

    phone_sources = CombinedPhoneSources()
    print("Available phone sources:")
    sources_list = ['getcontact', 'numbuster', 'vk_searcher', 'ok_searcher',
                    'truecaller', 'syncme', 'eyecon', 'callapp', 'telegram']
    for src in sources_list:
        has_src = hasattr(phone_sources, src) and getattr(phone_sources, src) is not None
        print(f"  - {src}: {'YES' if has_src else 'NO'}")
        if has_src:
            results['phone_sources_tested'] += 1

    phone_sources.close()

except Exception as e:
    print(f"Phone sources error: {e}")
    results['errors'].append(f"Phone sources: {e}")

# Test 3: Cross-Validation
print("\n" + "=" * 70)
print("TEST 3: CROSS-VALIDATION (Cycle 7-8)")
print("=" * 70)

try:
    from app.services.phase2.cross_validation import (
        CrossValidator,
        calculate_name_similarity
    )

    validator = CrossValidator()

    # Test name similarity with Russian names
    print("\nName similarity tests:")
    name_tests = [
        ('Тихон Портной', 'Tikhon Portnoi'),
        ('Даниил Глазков', 'Daniil Glazkov'),
        ('Даня Мещеряков', 'Danya Mescheryakov'),
        ('Ангелина Пилюшина', 'Angelina Pilyushina'),
        ('Федор', 'Федя'),  # Diminutive
        ('Даниил', 'Даня'),  # Diminutive
    ]
    for name1, name2 in name_tests:
        sim = calculate_name_similarity(name1, name2)
        status = "PASS" if sim >= 0.5 else "FAIL"
        print(f"  {status}: '{name1}' vs '{name2}' = {sim:.2f}")

    validator.close()

except Exception as e:
    print(f"Cross-validation error: {e}")
    results['errors'].append(f"Cross-validation: {e}")

# Test 4: Full Target Tests
print("\n" + "=" * 70)
print("TEST 4: FULL TARGET VALIDATION")
print("=" * 70)

try:
    from app.services.phase2.cross_validation import CrossValidator

    validator = CrossValidator()

    for target in TARGETS:
        print(f"\n--- Target: {target['name']} ({target['name_ru']}) ---")

        # Validate phones
        if target.get('test_phones'):
            for phone in target['test_phones']:
                results['phone_validations'] += 1
                result = validator.validate_phone(phone, target['name_ru'])
                print(f"  Phone {phone}:")
                print(f"    Validated: {result.validated}")
                print(f"    Confidence: {result.confidence:.2f}")
                print(f"    Sources: {result.sources_checked}")
                if result.validated:
                    results['phone_validated'] += 1

        # Validate emails
        if target.get('test_emails'):
            for email in target['test_emails']:
                results['email_validations'] += 1
                result = validator.validate_email(
                    email,
                    target['name_ru'],
                    target.get('profile_url')
                )
                print(f"  Email {email}:")
                print(f"    Validated: {result.validated}")
                print(f"    Confidence: {result.confidence:.2f}")
                print(f"    Sources: {result.sources_checked}")
                if result.validated:
                    results['email_validated'] += 1

        results['cross_validations'] += 1

    validator.close()

except Exception as e:
    print(f"Target validation error: {e}")
    import traceback
    traceback.print_exc()
    results['errors'].append(f"Target validation: {e}")

# Summary Report
print("\n" + "=" * 70)
print("CYCLE 9 TEST SUMMARY")
print("=" * 70)

print(f"""
Email Sources Tested: {results['email_sources_tested']}
Phone Sources Tested: {results['phone_sources_tested']}

Email Validations: {results['email_validations']}
  - Validated: {results['email_validated']}
  - Success Rate: {results['email_validated']/max(1,results['email_validations'])*100:.1f}%

Phone Validations: {results['phone_validations']}
  - Validated: {results['phone_validated']}
  - Success Rate: {results['phone_validated']/max(1,results['phone_validations'])*100:.1f}%

Cross-Validations Completed: {results['cross_validations']}

Errors: {len(results['errors'])}
""")

if results['errors']:
    print("Error Details:")
    for err in results['errors']:
        print(f"  - {err}")

# Overall status
total_sources = results['email_sources_tested'] + results['phone_sources_tested']
print(f"\nOverall Status: {'PASS' if total_sources >= 10 and len(results['errors']) == 0 else 'PARTIAL'}")
print(f"Total Sources Available: {total_sources} (target: 10+)")

print("\n" + "=" * 70)
print("CYCLE 9 COMPLETE")
print("=" * 70)

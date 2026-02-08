"""Suite 3: Fake Profile Filtering Validation."""
import time
import sys
import io
from playwright.sync_api import sync_playwright

# Fix Windows console encoding for Cyrillic output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = "http://127.0.0.1:5000"

# Test targets with both Cyrillic and Latin name variants
TARGETS = [
    {
        "name": "\u041e\u043b\u044c\u0433\u0430 \u0410\u0445\u0442\u0438\u043d\u0430\u0441",  # Ольга Ахтинас
        "first_variants": ["ольг", "оля", "олен", "леля", "olga", "olya", "olha", "olja"],
        "last_variants": ["ахтинас", "axtinas", "akhtinas", "ahtinas", "akhatina", "aftanas"],
        "known_fakes": ["Егор Гусев", "Иван Петров", "Анна Сидорова", "Egor Gusev", "Ivan Petrov"],
    },
    {
        "name": "\u0412\u043b\u0430\u0434\u0430 \u041a\u043b\u0430\u0434\u043a\u043e",  # Влада Кладко
        "first_variants": ["влад", "vlad"],
        "last_variants": ["кладко", "kladko"],
        "known_fakes": [],
    },
    {
        "name": "\u0422\u0438\u0445\u043e\u043d \u041f\u043e\u0440\u0442\u043d\u043e\u0439",  # Тихон Портной
        "first_variants": ["тихон", "tikhon", "tihon", "tishok"],
        "last_variants": ["портно", "portnoy", "portnoi", "portno"],
        "known_fakes": [],
    },
]


def check_name_match(profile_name, target):
    """Check if a profile name plausibly matches the target."""
    name_lower = profile_name.lower()

    # Check if any first name variant is in the profile name
    first_match = any(v in name_lower for v in target["first_variants"])
    # Check if any last name variant is in the profile name
    last_match = any(v in name_lower for v in target["last_variants"])

    return first_match or last_match


def run():
    results = []
    console_errors = []
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        for target in TARGETS:
            target_name = target["name"]
            print(f"\n  --- Testing: {target_name} ---")

            try:
                # Create investigation
                page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
                page.fill("#target_name", target_name)

                result = page.evaluate("""async () => {
                    const formData = new FormData(document.getElementById('newInvestigationForm'));
                    const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                    return {status: resp.status, body: await resp.json()};
                }""")

                body = result.get("body", {})
                inv_id = body.get("investigation_id")

                if not inv_id:
                    results.append(("FAIL", f"Create investigation for {target_name}", f"Failed: {body}"))
                    print(f"  [FAIL] Could not create investigation")
                    continue

                # Load search results
                t0 = time.time()
                page.goto(f"{BASE}/phase1/search/{inv_id}", wait_until="domcontentloaded", timeout=180000)
                search_time = time.time() - t0
                time.sleep(1)

                slug = target_name.replace(" ", "_")
                page.screenshot(path=f"tests/screenshots/suite3_{slug}.png")

                # Extract profile names
                profile_data = page.evaluate("""() => {
                    const cards = document.querySelectorAll('.profile-card');
                    return Array.from(cards).map(card => {
                        const nameEl = card.querySelector('h3, .font-semibold');
                        const simEl = card.getAttribute('data-similarity');
                        return {
                            name: nameEl ? nameEl.textContent.trim() : card.textContent.trim().substring(0, 50),
                            similarity: simEl
                        };
                    });
                }""")

                total_profiles = len(profile_data)
                suspicious = []
                matched = []

                for pd in profile_data:
                    pname = pd["name"]
                    if check_name_match(pname, target):
                        matched.append(pname)
                    else:
                        suspicious.append(pname)

                # Check for known fake names
                known_fakes_found = []
                for fake in target.get("known_fakes", []):
                    for pd in profile_data:
                        if fake.lower() in pd["name"].lower():
                            known_fakes_found.append(fake)

                # Pass if no known fakes and most results match
                ok = len(known_fakes_found) == 0 and (total_profiles == 0 or len(suspicious) <= max(1, total_profiles * 0.3))
                icon = "PASS" if ok else "FAIL"

                note = f"results={total_profiles}, matched={len(matched)}, suspicious={len(suspicious)}, time={search_time:.1f}s"
                results.append((icon, f"Fake filter: {target_name}", note))
                print(f"  [{icon}] {note}")

                if suspicious:
                    print(f"    Suspicious names: {suspicious[:5]}")
                if known_fakes_found:
                    print(f"    KNOWN FAKES FOUND: {known_fakes_found}")
                if matched:
                    print(f"    Matched names: {matched[:5]}")

            except Exception as e:
                results.append(("FAIL", f"Fake filter: {target_name}", str(e)))
                print(f"  [FAIL] {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite3_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors ({len(console_errors)}):")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 3: FAKE PROFILE FILTERING VALIDATION")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)

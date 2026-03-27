"""
Agent 2 — Court search with region + DOB filtering.
Sources: sudact.ru, судебныерешения.рф, reputation.su
Confidence levels: VERIFIED > LIKELY > POSSIBLE > UNVERIFIED
"""

import asyncio
import io
import json
import re
import sys
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

CANDIDATE = {
    "full_name": "Судин Артем Алексеевич",
    "last_name": "Судин",
    "first_name": "Артем",
    "patronymic": "Алексеевич",
    "dob_year": "1990",
    "dob": "29.11.1990",
    "inn": "232308435186",
    "region": "Краснодарский край",
    "cities": ["Абинск", "Краснодар"],
    "region_keywords": [
        "Краснодарский", "Краснодар", "Абинск", "Кубань",
        "г. Краснодар", "г. Абинск", "Кореновск",
        "Абинский", "Краснодарского",
    ],
}


def assign_confidence(case_text: str, candidate: dict) -> str:
    """
    Assign confidence based on matching signals in case text.
    VERIFIED  — INN found (only kad.arbitr.ru does this)
    LIKELY    — Region match + birth year
    POSSIBLE  — Region match only
    UNVERIFIED — Name only, no region match
    """
    text_lower = case_text.lower()

    if candidate["inn"] in case_text:
        return "VERIFIED"

    has_region = any(
        kw.lower() in text_lower for kw in candidate["region_keywords"]
    )
    has_dob_year = candidate["dob_year"] in case_text
    has_dob_full = candidate["dob"] in case_text

    if has_region and (has_dob_full or has_dob_year):
        return "LIKELY"
    elif has_region:
        return "POSSIBLE"
    else:
        return "UNVERIFIED"


async def search_sudact(candidate: dict) -> list:
    """Search sudact.ru with region filter (23 = Krasnodar Krai)."""
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            # sudact.ru search with region parameter
            name_query = f"{candidate['last_name']} {candidate['first_name']} {candidate['patronymic']}"
            search_url = (
                f"https://sudact.ru/regular/doc/?"
                f"regular-txt={name_query}&"
                f"regular-case_doc=&"
                f"regular-lawchunkinfo=&"
                f"regular-date_from=&"
                f"regular-date_to=&"
                f"regular-workflow_stage=&"
                f"regular-area=1019&"  # Краснодарский край
                f"regular-court=&"
                f"regular-judge=&"
                f"_=1711234567890"
            )

            print(f"[sudact.ru] Loading search...")
            response = await page.goto(search_url, timeout=30000)
            status = response.status if response else 0
            print(f"[sudact.ru] HTTP {status}")

            if status >= 400:
                print(f"[sudact.ru] Error: HTTP {status}")
                return results

            await page.wait_for_timeout(3000)

            # Check for results
            # sudact.ru uses <a> links inside result items
            items = await page.query_selector_all('section.document-list article, div.bm-doc-list div.row')
            if not items:
                items = await page.query_selector_all('a[href*="/regular/doc/"]')

            print(f"[sudact.ru] Found {len(items)} result elements")

            # Also try getting the full page text for context
            page_text = await page.inner_text('body')

            # Try to find result blocks
            result_blocks = await page.query_selector_all('.resultSearch, .searching-results .result')
            if result_blocks:
                items = result_blocks

            # Parse each result
            for i, item in enumerate(items[:30]):
                try:
                    text = await item.inner_text()
                    if len(text.strip()) < 10:
                        continue

                    link_el = await item.query_selector('a[href*="/doc/"]')
                    if not link_el:
                        link_el = await item.query_selector('a')
                    href = ""
                    if link_el:
                        href = await link_el.get_attribute('href') or ""
                        if href and not href.startswith('http'):
                            href = "https://sudact.ru" + href

                    confidence = assign_confidence(text, candidate)

                    # Extract case number if present
                    case_num_match = re.search(
                        r'(?:Дело|дело|№)\s*[:]?\s*(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})',
                        text
                    )
                    case_number = case_num_match.group(1) if case_num_match else ""

                    # Extract court name
                    court_match = re.search(
                        r'([\w\s]+(суд|районный|городской|краевой|мировой)[^\n,]{0,50})',
                        text, re.IGNORECASE
                    )
                    court_name = court_match.group(0).strip()[:80] if court_match else ""

                    # Extract date
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                    date_str = date_match.group(1) if date_match else ""

                    results.append({
                        "source": "sudact.ru",
                        "confidence": confidence,
                        "case_number": case_number,
                        "court_name": court_name,
                        "date": date_str,
                        "text_preview": text.strip()[:250],
                        "url": href,
                    })
                    print(f"  [{confidence}] {case_number or '—'} | {court_name[:40]} | {text[:60]}")

                except Exception as item_err:
                    print(f"  [PARSE ERROR] {item_err}")

            # If no structured results, try to parse the page text directly
            if not results and candidate['last_name'].lower() in page_text.lower():
                print("[sudact.ru] Trying raw text parsing...")
                # Split by document boundaries
                chunks = re.split(r'(?=Дело\s*№|Решение\s|Определение\s|Приговор\s)', page_text)
                for chunk in chunks[:20]:
                    if candidate['last_name'] in chunk and len(chunk) > 50:
                        confidence = assign_confidence(chunk, candidate)
                        case_num_match = re.search(
                            r'(?:Дело|дело|№)\s*[:]?\s*(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})',
                            chunk
                        )
                        results.append({
                            "source": "sudact.ru",
                            "confidence": confidence,
                            "case_number": case_num_match.group(1) if case_num_match else "",
                            "text_preview": chunk.strip()[:250],
                        })

        except Exception as e:
            print(f"[sudact.ru ERROR] {e}")
        finally:
            await browser.close()

    return results


async def search_sudebnye_resheniya(candidate: dict) -> list:
    """Search судебныерешения.рф"""
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            name_query = f"{candidate['last_name']} {candidate['first_name']} {candidate['patronymic']}"
            url = f"https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai/bsr/case?text={name_query}"

            print(f"[судебныерешения.рф] Loading...")
            response = await page.goto(url, timeout=30000)
            status = response.status if response else 0
            print(f"[судебныерешения.рф] HTTP {status}")

            if status >= 400:
                print(f"[судебныерешения.рф] Error: HTTP {status}")
                return results

            await page.wait_for_timeout(3000)

            items = await page.query_selector_all(
                '.bsr-result, .result-item, .search-result-item, article, .case-item'
            )
            print(f"[судебныерешения.рф] Found {len(items)} elements")

            for item in items[:20]:
                try:
                    text = await item.inner_text()
                    if len(text.strip()) < 10:
                        continue

                    confidence = assign_confidence(text, candidate)

                    link_el = await item.query_selector('a')
                    href = ""
                    if link_el:
                        href = await link_el.get_attribute('href') or ""

                    results.append({
                        "source": "судебныерешения.рф",
                        "confidence": confidence,
                        "text_preview": text.strip()[:250],
                        "url": href,
                    })
                    print(f"  [{confidence}] {text[:80]}")
                except Exception as item_err:
                    print(f"  [PARSE ERROR] {item_err}")

        except Exception as e:
            print(f"[судебныерешения.рф ERROR] {e}")
        finally:
            await browser.close()

    return results


async def search_reputation_su(candidate: dict) -> list:
    """Search reputation.su"""
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            name_query = f"{candidate['last_name']}+{candidate['first_name']}+{candidate['patronymic']}"
            url = f"https://reputation.su/?query={name_query}"

            print(f"[reputation.su] Loading...")
            response = await page.goto(url, timeout=30000)
            status = response.status if response else 0
            print(f"[reputation.su] HTTP {status}")

            if status >= 400:
                print(f"[reputation.su] Error: HTTP {status}")
                return results

            await page.wait_for_timeout(3000)

            items = await page.query_selector_all(
                '.case-item, .result-item, article, tr[data-href], .search-result'
            )
            print(f"[reputation.su] Found {len(items)} elements")

            for item in items[:20]:
                try:
                    text = await item.inner_text()
                    if len(text.strip()) < 10:
                        continue

                    confidence = assign_confidence(text, candidate)

                    link_el = await item.query_selector('a')
                    href = ""
                    if link_el:
                        href = await link_el.get_attribute('href') or ""

                    results.append({
                        "source": "reputation.su",
                        "confidence": confidence,
                        "text_preview": text.strip()[:250],
                        "url": href,
                    })
                    print(f"  [{confidence}] {text[:80]}")
                except Exception as item_err:
                    print(f"  [PARSE ERROR] {item_err}")

        except Exception as e:
            print(f"[reputation.su ERROR] {e}")
        finally:
            await browser.close()

    return results


async def main():
    print("=" * 60)
    print(f"AGENT 2: Region + DOB Court Filtering")
    print(f"Кандидат: {CANDIDATE['full_name']}")
    print(f"ИНН: {CANDIDATE['inn']} | Регион: {CANDIDATE['region']}")
    print("=" * 60)

    # Run all three in parallel
    sudact_results, sud_res_results, rep_results = await asyncio.gather(
        search_sudact(CANDIDATE),
        search_sudebnye_resheniya(CANDIDATE),
        search_reputation_su(CANDIDATE),
    )

    all_cases = sudact_results + sud_res_results + rep_results

    # Statistics
    stats = {"VERIFIED": [], "LIKELY": [], "POSSIBLE": [], "UNVERIFIED": []}
    for case in all_cases:
        conf = case.get("confidence", "UNVERIFIED")
        if conf in stats:
            stats[conf].append(case)

    summary = {
        "candidate": CANDIDATE["full_name"],
        "inn": CANDIDATE["inn"],
        "region": CANDIDATE["region"],
        "total_cases": len(all_cases),
        "stats": {k: len(v) for k, v in stats.items()},
        "cases_by_confidence": {k: v for k, v in stats.items() if v},
        "all_cases": all_cases,
    }

    print(f"\n{'=' * 60}")
    print("ИТОГ:")
    print(f"  VERIFIED:   {len(stats['VERIFIED'])} (ИНН подтверждён)")
    print(f"  LIKELY:     {len(stats['LIKELY'])} (регион + год рождения)")
    print(f"  POSSIBLE:   {len(stats['POSSIBLE'])} (только регион)")
    print(f"  UNVERIFIED: {len(stats['UNVERIFIED'])} (только имя)")
    print("=" * 60)

    Path("data").mkdir(exist_ok=True)
    with open("data/court_region_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("AGENT 2 DONE -> data/court_region_results.json")
    return summary


if __name__ == "__main__":
    asyncio.run(main())

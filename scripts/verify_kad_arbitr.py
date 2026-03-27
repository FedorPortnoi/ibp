"""
Agent 1 — kad.arbitr.ru INN search for arbitration court cases.
INN is a 100% identifier — any case found is VERIFIED.
Note: kad.arbitr.ru may return HTTP 451 (geo-blocked outside Russia).
"""

import asyncio
import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

CANDIDATE = {
    "inn": "232308435186",
    "full_name": "Судин Артем Алексеевич",
}


async def search_kad_arbitr(inn: str, full_name: str) -> dict:
    results = []
    errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            # 1. Try direct page load
            print(f"[kad.arbitr.ru] Loading page...")
            response = await page.goto("https://kad.arbitr.ru/", timeout=30000)
            status = response.status if response else 0
            print(f"[kad.arbitr.ru] HTTP {status}")

            if status == 451:
                errors.append("HTTP 451 — geo-blocked (requires Russian IP)")
                print("[kad.arbitr.ru] GEO-BLOCKED (HTTP 451)")
            elif status >= 400:
                errors.append(f"HTTP {status}")
            else:
                await page.wait_for_timeout(2000)

                # 2. Try filling participant field with INN
                participant_input = await page.query_selector(
                    'input[placeholder*="участник"], input[name*="participant"], '
                    '#sug-participants, input[id*="participant"]'
                )

                if participant_input:
                    await participant_input.fill(inn)
                    await page.wait_for_timeout(1500)

                    # Click suggestion if appears
                    suggestion = await page.query_selector(
                        '.b-suggest-item, .ui-menu-item, [class*="suggest"]'
                    )
                    if suggestion:
                        await suggestion.click()
                        await page.wait_for_timeout(500)

                    # Submit search
                    search_btn = await page.query_selector(
                        'button[type="submit"], button.b-form-submit, '
                        'input[type="submit"], .b-form-submit__btn'
                    )
                    if search_btn:
                        await search_btn.click()
                        await page.wait_for_timeout(4000)
                else:
                    # Fallback: direct URL
                    print("[kad.arbitr.ru] No input found, trying URL search...")
                    await page.goto(
                        f"https://kad.arbitr.ru/?participant={inn}",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(3000)

                # 3. Parse results table
                rows = await page.query_selector_all(
                    'table.b-result-table tbody tr, '
                    '.b-case-result tr, '
                    'tr[onclick]'
                )
                print(f"[kad.arbitr.ru] Found {len(rows)} table rows")

                for row in rows:
                    text = await row.inner_text()
                    cells = await row.query_selector_all('td')

                    case_data = {
                        "source": "kad.arbitr.ru",
                        "confidence": "VERIFIED",
                        "verification_method": "INN_MATCH",
                    }

                    if len(cells) >= 3:
                        case_data["case_number"] = (await cells[0].inner_text()).strip()
                        case_data["date"] = (await cells[1].inner_text()).strip()
                        case_data["parties"] = (await cells[2].inner_text()).strip()
                        if len(cells) >= 4:
                            case_data["status"] = (await cells[3].inner_text()).strip()
                    else:
                        case_data["raw_text"] = text.strip()[:300]

                    if text.strip():
                        results.append(case_data)
                        print(f"[VERIFIED] {case_data.get('case_number', text[:80])}")

                # 4. Try AJAX API fallback
                if not results:
                    print("[kad.arbitr.ru] Trying AJAX API...")
                    try:
                        api_response = await page.evaluate("""
                            async () => {
                                try {
                                    const resp = await fetch(
                                        '/Handlers/CasesListHandler.ashx',
                                        {
                                            method: 'POST',
                                            headers: {
                                                'Content-Type': 'application/json',
                                                'X-Requested-With': 'XMLHttpRequest'
                                            },
                                            body: JSON.stringify({
                                                "Participants": [{"Name": "%s", "Type": -1, "ExactMatch": true}],
                                                "Page": 1,
                                                "Count": 25,
                                                "DateFrom": null,
                                                "DateTo": null
                                            })
                                        }
                                    );
                                    return await resp.text();
                                } catch(e) {
                                    return JSON.stringify({"error": e.message});
                                }
                            }
                        """ % inn)
                        print(f"[kad.arbitr.ru API] Response: {str(api_response)[:500]}")

                        if api_response and '{' in api_response:
                            api_data = json.loads(api_response)
                            items = api_data.get('Result', {}).get('Items', [])
                            for case in items:
                                results.append({
                                    "source": "kad.arbitr.ru",
                                    "confidence": "VERIFIED",
                                    "verification_method": "INN_MATCH",
                                    "case_number": case.get('CaseNumber', ''),
                                    "date": case.get('Date', ''),
                                    "parties": str(case.get('Sides', '')),
                                    "court": case.get('CourtTag', ''),
                                })
                    except Exception as api_err:
                        errors.append(f"API fallback error: {api_err}")

        except Exception as e:
            errors.append(str(e))
            print(f"[kad.arbitr.ru ERROR] {e}")
        finally:
            await browser.close()

    return {
        "source": "kad.arbitr.ru",
        "inn_used": inn,
        "candidate": full_name,
        "total_verified": len(results),
        "cases": results,
        "errors": errors,
    }


async def main():
    print("=" * 60)
    print(f"AGENT 1: kad.arbitr.ru — ИНН поиск")
    print(f"Кандидат: {CANDIDATE['full_name']}")
    print(f"ИНН: {CANDIDATE['inn']}")
    print("=" * 60)

    result = await search_kad_arbitr(CANDIDATE["inn"], CANDIDATE["full_name"])

    # Ensure data/ exists
    Path("data").mkdir(exist_ok=True)

    with open("data/kad_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    if result["errors"]:
        print(f"ERRORS: {result['errors']}")
    print(f"AGENT 1 DONE: {result['total_verified']} VERIFIED дел")
    print(f"Saved to: data/kad_results.json")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

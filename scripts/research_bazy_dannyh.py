import asyncio
import json
import sys
import io
from playwright.async_api import async_playwright

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CANDIDATE = {
    "full_name": "Судин Артем Алексеевич",
    "inn": "232308435186",
    "dob": "29.11.1990",
    "phone": "89676573634",
}

BASE_URL = "https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai"


async def research():
    findings = {
        "has_api": False,
        "api_endpoints": [],
        "search_types": [],
        "result_structure": None,
        "auth_required": False,
        "captcha": False,
        "data_categories": [],
        "notes": [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="ru-RU",
        )
        page = await context.new_page()

        # Capture XHR/fetch
        api_calls = []

        async def capture(req):
            url = req.url
            if any(x in url for x in ["api", "ajax", "json", "search", "find", "query", "poisk"]):
                api_calls.append(
                    {"url": url, "method": req.method, "post_data": req.post_data}
                )

        page.on("request", capture)

        # 1. Main page
        try:
            await page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            print(f"Title: {await page.title()}")
            print(f"URL: {page.url}")

            # Get page HTML structure
            html = await page.content()
            findings["page_length"] = len(html)

            await page.screenshot(path="data/bazy_main.png", full_page=True)
        except Exception as e:
            print(f"Main page error: {e}")
            findings["notes"].append(f"main_page_error: {str(e)}")

        # 2. Check search types — all inputs
        search_inputs = await page.query_selector_all(
            'input[type="text"], input[type="search"], input[type="tel"], input[type="number"], textarea'
        )
        print(f"\nInput fields: {len(search_inputs)}")
        for inp in search_inputs:
            placeholder = await inp.get_attribute("placeholder") or ""
            name = await inp.get_attribute("name") or ""
            id_attr = await inp.get_attribute("id") or ""
            input_type = await inp.get_attribute("type") or ""
            print(f"  Input: name={name}, id={id_attr}, type={input_type}, placeholder={placeholder}")
            pl = placeholder.lower()
            nm = name.lower()
            if any(x in pl or x in nm for x in ["имя", "фио", "фамилия", "name"]):
                findings["search_types"].append("name")
            if "инн" in pl or "inn" in nm:
                findings["search_types"].append("inn")
            if any(x in pl or x in nm for x in ["телефон", "phone"]):
                findings["search_types"].append("phone")
            if "паспорт" in pl or "passport" in nm:
                findings["search_types"].append("passport")

        # 3. Check all links/nav for search categories
        links = await page.query_selector_all("a")
        nav_hrefs = []
        for link in links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            if text and len(text) < 60:
                nav_hrefs.append({"href": href, "text": text})
        findings["navigation"] = nav_hrefs[:50]
        print(f"\nNavigation links: {len(nav_hrefs)}")
        for nh in nav_hrefs[:20]:
            print(f"  {nh['text']}: {nh['href']}")

        # 4. Check forms
        forms = await page.query_selector_all("form")
        print(f"\nForms: {len(forms)}")
        form_details = []
        for form in forms:
            action = await form.get_attribute("action") or ""
            method = await form.get_attribute("method") or ""
            form_inputs = await form.query_selector_all("input, select, textarea")
            input_names = []
            for fi in form_inputs:
                n = await fi.get_attribute("name") or ""
                t = await fi.get_attribute("type") or ""
                input_names.append(f"{n}({t})")
            detail = {"action": action, "method": method, "inputs": input_names}
            form_details.append(detail)
            print(f"  Form action={action} method={method} inputs={input_names}")
        findings["forms"] = form_details

        # 5. Try name search
        try:
            search_input = await page.query_selector(
                'input[type="text"], input[type="search"]'
            )
            if search_input:
                await search_input.fill(CANDIDATE["full_name"])
                # Try Enter
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(5000)
                await page.screenshot(path="data/bazy_name_search.png", full_page=True)
                print(f"\nAfter name search URL: {page.url}")

                # Try multiple result selectors
                for sel in [
                    ".result", ".item", ".card", ".person",
                    "[class*='result']", "[class*='person']", "[class*='item']",
                    "table tr", "article", ".list-group-item",
                    ".search-result", ".search-item",
                ]:
                    items = await page.query_selector_all(sel)
                    if len(items) > 0:
                        print(f"  Results by '{sel}': {len(items)}")
                        if len(items) > 1:
                            findings["result_structure"] = sel
                            first_text = await items[0].inner_text()
                            findings["sample_result"] = first_text[:500]
                            break

                # If no results found, get page text
                if not findings.get("result_structure"):
                    body_text = await page.inner_text("body")
                    findings["search_page_text"] = body_text[:2000]
                    print(f"  Page text (first 500): {body_text[:500]}")
            else:
                # Try clicking a search button or link first
                search_btn = await page.query_selector(
                    'button[type="submit"], a[href*="search"], a[href*="poisk"]'
                )
                if search_btn:
                    await search_btn.click()
                    await page.wait_for_timeout(3000)
                    await page.screenshot(path="data/bazy_search_page.png", full_page=True)
                    print(f"\nSearch page URL: {page.url}")
        except Exception as e:
            print(f"Name search error: {e}")
            findings["notes"].append(f"name_search_error: {str(e)}")

        # 6. CAPTCHA check
        captcha = await page.query_selector(
            'img[src*="captcha"], .captcha, [class*="captcha"], '
            'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], '
            '[data-sitekey], .g-recaptcha, .h-captcha'
        )
        findings["captcha"] = captcha is not None
        print(f"\nCAPTCHA: {findings['captcha']}")

        # 7. Auth check
        auth_signs = await page.query_selector(
            'input[type="password"], a[href*="login"], a[href*="auth"], '
            'a[href*="register"], a[href*="signin"], '
            'button[data-action*="login"], .login-form'
        )
        findings["auth_required"] = auth_signs is not None
        print(f"Auth required: {findings['auth_required']}")

        # 8. Check for paywall signs
        paywall = await page.query_selector(
            '[class*="paywall"], [class*="premium"], [class*="subscribe"], '
            '[class*="pricing"], [class*="tariff"], [class*="тариф"]'
        )
        findings["paywall"] = paywall is not None
        print(f"Paywall signs: {findings['paywall']}")

        # 9. API calls
        findings["api_endpoints"] = api_calls
        findings["has_api"] = len(api_calls) > 0
        print(f"\nAPI calls captured: {len(api_calls)}")
        for c in api_calls:
            print(f"  {c['method']} {c['url']}")
            if c.get("post_data"):
                print(f"    POST data: {c['post_data'][:200]}")

        await browser.close()

    with open("data/bazy_research.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)

    print("\n=== AGENT 1 DONE === -> data/bazy_research.json")
    return findings


if __name__ == "__main__":
    asyncio.run(research())

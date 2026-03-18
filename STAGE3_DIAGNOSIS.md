# Stage 3 Social Media — Diagnosis Report

## People Search Path (WORKS)

```
User types "Артем Судин" into /api/search/page form (First Last order)
  → POST /api/search/vk  (app/routes/api_search.py:31)
    → buratino_vk_search.search(query="Артем Судин", city=..., age_from=..., age_to=...)
      (app/services/phase1/buratino_vk_search.py:450)
      → VKWebSearch(service_token=...).search(query="Артем Судин")
        (app/services/phase1/vk_web_search.py:205)
        → _playwright_search() → _users_search_with_token(token, "Артем Судин")
          → VK API users.search?q=Артем+Судин  (NO birth_day/month/year filters)
          → Name verification:
            search_first = "артем"   (query.split()[0])
            search_last  = "судин"   (query.split()[1])
            VK profile: first_name="Артем", last_name="Судин"
            → last_sim("судин", "судин") = 1.0 ≥ 0.7 ✓
            → first_sim("артем", "артем") = 1.0 ≥ 0.65 ✓
            → ACCEPTED ✓
        → _enrich_profiles() → same name verification → ACCEPTED ✓
      → _parse_profile(item, target_name="Артем Судин")
        → _calculate_name_similarity("Артем Судин", "Артем Судин") = 100% ✓
        → name_match = True ✓
    → Returns 600-800 profiles ✓
```

**Key:** People Search gets name in **First Last** order from the form, which matches VK's internal format.

## Candidate Check Path (BROKEN)

```
User submits "Судин Артем Алексеевич" via /candidate/start (Last First Patronymic)
  → pipeline.py:283  name_parts = check.name_parts
    → {'last': 'Судин', 'first': 'Артем', 'patronymic': 'Алексеевич'}
  → pipeline.py:433  effective_name = "Судин Артем Алексеевич"

  STAGE 3 (pipeline.py:744):
  → buratino_vk_search.search(
      query="Судин Артем Алексеевич",     ← Last First Patronymic order
      city="Краснодарский край",
      age_from=32, age_to=38,
      birth_day=29, birth_month=11, birth_year=1990   ← DOB filters!
    )
    → VKWebSearch.search("Судин Артем Алексеевич", birth_day=29, ...)
      → _playwright_search() → _users_search_with_token(token, "Судин Артем Алексеевич")
        → VK API users.search?q=Судин+Артем+Алексеевич&birth_day=29&birth_month=11&birth_year=1990
        → VK returns profiles (VK handles name order internally) ← PROFILES EXIST
        → Name verification (vk_web_search.py:587-594):
          search_first = "судин"        ← query.split()[0] — THIS IS THE LAST NAME!
          search_last  = "артем"        ← query.split()[1] — THIS IS THE FIRST NAME!
          VK profile: first_name="Артем", last_name="Судин"
          → last_sim("артем", "судин") = ~0.18 → < 0.7 → HARD REJECT ✗
          → ALL PROFILES REJECTED ✗
      → _enrich_profiles() → same verification → ALL REJECTED ✗
    → Returns [], 0 ← ZERO PROFILES
```

## Root Cause

**THREE compounding issues, with #1 being the primary cause:**

### ROOT CAUSE 1: First/Last Name Swap (PRIMARY — causes 0 results)

`VKWebSearch` assumes `query.split()[0]` is the first name and `query.split()[1]` is the last name. This appears in TWO places:

**Location A** — `vk_web_search.py:587-594` (`_users_search_with_token`):
```python
query_parts = query.lower().split()
if len(query_parts) >= 2:
    search_first = query_parts[0]   # ← WRONG for "Судин Артем Алексеевич"
    search_last = query_parts[1]    # ← WRONG
    verified_items = [
        item for item in human_items
        if verify_profile_name_matches_query(item, search_first, search_last)
    ]
```

**Location B** — `vk_web_search.py:1009-1012` (`_enrich_profiles`):
```python
query_parts = query.lower().split()
if len(query_parts) >= 2:
    search_first = query_parts[0]   # ← WRONG for "Судин Артем Алексеевич"
    search_last = query_parts[1]    # ← WRONG
```

**Location C** — `buratino_vk_search.py:276-279` (`_calculate_name_similarity`):
```python
target_parts = target_lat.split()    # ["sudin", "artem", "alekseevich"]
target_first_lat = target_parts[0]   # "sudin" ← WRONG (last name)
target_last_lat = target_parts[-1]   # "alekseevich" ← WRONG (patronymic, not last name)
```

The `verify_profile_name_matches_query` function has a HARD REJECT threshold:
- `last_sim < 0.7 → return False` — comparing "артем" (query[1]) vs "судин" (VK last_name) → ~0.18 → **REJECTED**

This means **every single legitimate VK profile is rejected**, giving exactly 0 results.

People Search avoids this because users typically enter names in **First Last** order ("Артем Судин"), which matches the code's assumption. The Candidate Check form uses Russian convention **Last First Patronymic** ("Судин Артем Алексеевич").

### ROOT CAUSE 2: DOB Filtering Reduces VK Results (SECONDARY)

Pipeline passes `birth_day`, `birth_month`, `birth_year` to VK API:
```python
search_params['birth_day'] = 29
search_params['birth_month'] = 11
search_params['birth_year'] = 1990
```

VK only returns profiles where the user has set their birthday publicly AND it matches. Most VK users hide their full DOB. This dramatically reduces the result pool even before the name verification bug eliminates everything.

People Search does NOT pass DOB filters — it gets the full, unfiltered result set.

### ROOT CAUSE 3: Expired/Missing VK Web Token (TERTIARY)

On the production server, `VKWebSearch._playwright_search()` needs:
1. A cached web token at `vk_session/web_token.json`, OR
2. A saved browser session at `vk_session/state.json`, OR
3. `VK_LOGIN` + `VK_PASSWORD` env vars for auto-login

**Local status:** `vk_session/web_token.json` has token expiring at timestamp 1772128905 (~Feb 27, 2026) — **EXPIRED 3 weeks ago**.

**Server status:** `vk_session/` is likely not present (not in git, likely not deployed). Without a web token, `_playwright_search()` returns []. Only `_newsfeed_search()` (service token, low yield) and screen name guessing (service token, low yield) remain.

Even if the web token worked, ROOT CAUSE 1 would still reject all results.

## Evidence: Comparison Table

| Aspect | People Search (works) | Candidate Check (broken) |
|---|---|---|
| Route | POST /api/search/vk | POST /candidate/start |
| Route file | api_search.py:31 | candidate_check.py:33 → pipeline.py |
| Service file | buratino_vk_search.py → vk_web_search.py | buratino_vk_search.py → vk_web_search.py |
| Service class | BuratinoVKSearch → VKWebSearch | BuratinoVKSearch → VKWebSearch |
| VK API method | users.search (via web token) | users.search (via web token) |
| VK token type | Web token (cached) | Web token (cached) |
| **Name format** | **"Артем Судин" (First Last)** | **"Судин Артем Алексеевич" (Last First Patronymic)** |
| **Name verification assumes** | **query[0]=first ✓** | **query[0]=first ✗ (it's last name!)** |
| DOB filters | None | birth_day=29, birth_month=11, birth_year=1990 |
| City filter | User-typed city name | check.region ("Краснодарский край") |
| Age filter | From form (may be None) | ±3 years from DOB |
| **Result** | **600-800 profiles** | **0 profiles** |

## Evidence: Name Verification Trace

For query `"Судин Артем Алексеевич"` matching VK profile `{first_name: "Артем", last_name: "Судин"}`:

```
vk_web_search.py:587-594:
  query_parts = ["судин", "артем", "алексеевич"]
  search_first = "судин"      ← pipeline thinks this is first name
  search_last  = "артем"      ← pipeline thinks this is last name

verify_profile_name_matches_query(profile, "судин", "артем"):
  profile_first = "артем"   (from VK)
  profile_last  = "судин"   (from VK)

  RULE 1: last_sim = SequenceMatcher("артем", "судин") = 0.18
          0.18 < 0.7 → HARD REJECT → return False

  ⟹ Profile rejected despite being the CORRECT person
```

## Recommended Fix

**Fix 1 (ROOT CAUSE 1):** In `vk_web_search.py`, detect Russian name order and swap accordingly. The pipeline already correctly parses names via `check.name_parts` — the fix should use that parsed format OR detect the order from the query.

Options:
- **A.** Have `BuratinoVKSearch.search()` accept explicit `first_name` and `last_name` parameters (in addition to `query`), and pass them through to `VKWebSearch` for name verification. The pipeline already has `name_parts['first']` and `name_parts['last']`.
- **B.** In `VKWebSearch._users_search_with_token()` and `_enrich_profiles()`, try BOTH name orders (First Last AND Last First) and accept if either matches.
- **C.** Restructure `effective_name` in `pipeline.py` to use First Last order: `effective_name = f"{name_parts['first']} {name_parts['last']}"` — but this changes the query sent to VK API and other stages.

**Recommended: Option A** — cleanest, preserves VK query format while fixing verification.

**Fix 2 (ROOT CAUSE 2):** Remove or relax DOB filters in the pipeline VK search. Pass them as post-search boost criteria (like the pipeline already does at line 818-834) rather than as VK API pre-filters.

**Fix 3 (ROOT CAUSE 3):** Renew the VK web token locally and deploy `vk_session/` to the server, OR set `VK_LOGIN`/`VK_PASSWORD` in the server's .env for auto-login.

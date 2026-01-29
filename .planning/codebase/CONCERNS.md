# Concerns

## Technical Debt

### In-Memory Task Storage
**Location**: `app/routes/phase1.py:tasks = {}`

Tasks stored in global dict - lost on server restart.

**Impact**: Search results lost if server restarts during search.

**Fix**: Use Redis, database, or file-based storage for tasks.

### No VK Direct Search
**Location**: `app/services/combined_search.py`

Currently relies on Maigret/Sherlock to find VK profiles. Should add direct `vk.com/{username}` checking similar to Telegram.

**Impact**: Missing VK accounts that exist but aren't in Maigret database.

### Maigret Output Truncation
**Location**: `app/services/combined_search.py:_run_maigret_batch()`

With 3+ usernames, VK URLs get truncated in stdout. Workaround: Chunking to 2 usernames per batch.

**Impact**: Performance overhead from multiple Maigret invocations.

### Config Duplication
**Location**: `config.py` vs `app/__init__.py`

Config values defined in both places with potential for drift:
- `config.py` defines `UPLOAD_FOLDER` as `app/static/uploads`
- `app/__init__.py` defines it as `../uploads`

## Security Concerns

### Hardcoded Secret Key
**Location**: `app/__init__.py:23`

```python
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
```

**Impact**: Insecure in production if not overridden.

### No Input Sanitization for Subprocess
**Location**: `app/services/combined_search.py`

Usernames passed directly to Maigret/Sherlock subprocess. While unlikely to be exploitable, could benefit from validation.

### Photo Upload Without Validation
**Location**: `app/routes/phase1.py`

Photos saved with UUID prefix but content not validated beyond extension check.

## Performance Issues

### Sequential Telegram Checks
**Location**: `app/services/telegram_search.py:check_telegram_usernames()`

Usernames checked one-by-one sequentially. Could be parallelized.

### Face Matching Latency
**Location**: `app/services/ultimate_face_matcher.py`

Face matching on multiple photos per profile is slow (~0.3s delay between photos).

### No Caching
OSINT results not cached - repeated searches for same name hit external services again.

## Missing Features

### Phase 2 & 3 Not Implemented
`app/routes/phase2.py` and `app/routes/phase3.py` are skeleton implementations with TODO comments.

### No Account Linking
Accounts from same person not automatically grouped/linked. User requirement mentions this but not implemented.

### No Yandex Reverse Image Search
Listed in requirements but not implemented.

## Code Quality

### Large Files
- `username_generator.py`: 930 lines
- `ultimate_face_matcher.py`: 1200 lines
- `combined_search.py`: 665 lines

Could be split into smaller modules.

### Inconsistent Error Handling
Some functions return `None`, others raise exceptions, others return dicts with `success: False`.

### No Type Checking
Type hints present but no mypy or type checker configured.

## Windows-Specific Issues

### Unicode Console Output
**Location**: Various print statements

Windows console may have issues with Cyrillic/emoji characters. Commit `87982f1` added fixes but may still have edge cases.

### Path Separators
Code uses forward slashes in some paths, may need normalization on Windows.

# Testing

## Current State

**No test framework configured.** The codebase has testing infrastructure placeholders but no actual tests.

## Available Test Configuration

### TestingConfig in `config.py`
```python
class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### Diagnostic Functions

Some services have built-in diagnostics:

**`combined_search.py:run_diagnostic()`**
```python
def run_diagnostic(username: str = "testuser") -> Dict:
    """Run diagnostics to see what's working."""
    # Tests Maigret/Sherlock installation
    # Runs quick search
    # Returns status dict
```

**`username_generator.py` main block**
```python
if __name__ == "__main__":
    # Test diminutives, transliteration
    usernames = generate_usernames("Дмитрий Медведев")
```

## Testing Recommendations

### Suggested Framework
- **pytest** - Standard Python testing
- **pytest-flask** - Flask-specific fixtures

### Test Structure
```
tests/
├── conftest.py           # Fixtures (app, client, db)
├── test_username_generator.py
├── test_telegram_search.py
├── test_combined_search.py
└── test_routes_phase1.py
```

### Key Test Cases Needed

1. **Username Generator**
   - Diminutive lookup (Russian name → nicknames)
   - Transliteration (Cyrillic → Latin variants)
   - Surname nickname extraction

2. **Telegram Search**
   - Valid username detection
   - Profile info extraction
   - Error handling for invalid usernames

3. **Combined Search Pipeline**
   - Username generation integration
   - Maigret/Sherlock output parsing
   - Result deduplication

4. **Phase 1 Routes**
   - Task creation and tracking
   - Progress polling
   - Results rendering

## Running Diagnostics

```bash
# Test Maigret/Sherlock installation
python -c "from app.services.combined_search import run_diagnostic; print(run_diagnostic())"

# Test username generator
python app/services/username_generator.py

# Test face matcher availability
python app/services/ultimate_face_matcher.py
```

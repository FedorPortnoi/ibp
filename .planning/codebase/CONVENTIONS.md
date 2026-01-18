# Conventions

## Code Style

### Python
- **PEP 8** generally followed
- **Type hints** used in service classes (e.g., `def search(self, target_name: str, ...) -> Dict[str, Any]`)
- **Docstrings** with triple quotes, multi-line descriptions
- **f-strings** for string formatting

### Comments
- Header blocks with `=====` separators in service files
- Section comments with `# ======= SECTION =======`
- Inline comments for complex logic

## Patterns

### JSON Serialization in Models
Complex data stored as JSON strings with property getters/setters:

```python
# Storage field (private)
_discovered_profiles = db.Column(db.Text, default='[]')

# Property for transparent access
@property
def discovered_profiles(self):
    return json.loads(self._discovered_profiles or '[]')

@discovered_profiles.setter
def discovered_profiles(self, value):
    self._discovered_profiles = json.dumps(value)
```

### Service Class Pattern
Services are instantiated with config, expose a main `search()` method:

```python
class CombinedSearchService:
    def __init__(self, max_usernames=15, timeout=30, ...):
        self.max_usernames = max_usernames
        self.timeout = timeout
        self.progress = SearchProgress()

    def search(self, target_name, target_photo_path=None, progress_callback=None) -> Dict:
        # Main entry point
```

### Progress Callback Pattern
Services accept optional callbacks for real-time progress:

```python
def search(self, name, photo=None, progress_callback=None):
    self._update_progress(phase="searching", message="...")
    if self.progress_callback:
        self.progress_callback(self.progress.to_dict())
```

### Dataclass for Results
Results returned as dataclasses or dicts with consistent keys:

```python
@dataclass
class SearchProgress:
    phase: str = "initializing"
    current_step: int = 0
    accounts_found: int = 0
    # ...

    def to_dict(self) -> Dict:
        return { ... }
```

## Error Handling

### Try/Except with Logging
```python
try:
    result = subprocess.run(cmd, timeout=timeout)
except subprocess.TimeoutExpired:
    self.progress.log(f"Maigret timeout after {timeout}s")
except FileNotFoundError:
    self.progress.log("Maigret not installed")
```

### Graceful Degradation
Optional features check availability and skip gracefully:
```python
if not FACE_RECOGNITION_AVAILABLE:
    return accounts  # Return without face matching
```

## Naming

### Constants
- SCREAMING_SNAKE_CASE: `PRIORITY_PLATFORMS`, `MAX_PHOTOS_PER_PROFILE`

### Private Methods
- Leading underscore: `_run_maigret_batch()`, `_parse_osint_output()`

### Blueprint Names
- `{phase}_bp`: `main_bp`, `phase1_bp`, `phase2_bp`

## Import Organization

```python
# Standard library
import os
import sys
import json

# Third party
from flask import Blueprint, render_template
import requests

# Local
from app.services.username_generator import SmartUsernameGenerator
```

## Configuration

### Environment-based Config Classes
```python
class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
```

### Config Dictionary
```python
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

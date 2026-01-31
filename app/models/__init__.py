"""
IBP Models Package
==================
Database models for storing investigation data.

Enhanced for Буратино-style workflow with:
- ProfileMatch: Rich profile data with confidence scoring
- Phase1Result: Complete Phase 1 search results
- Investigation: Main investigation record
"""

from app.models.investigation import Investigation
from app.models.profile import (
    ProfileMatch,
    Phase1Result,
    Platform,
    ConfidenceLevel,
    convert_legacy_results_to_phase1
)

"""
Phase 4 Services - Advanced OSINT Features
==========================================
Agent-developed modules:
- Agent 5: EntityResolver, ConnectionAnalyzer (COMPLETE)
- Agent 2: VK People Search (pending)
- Agent 3: Telegram Search (COMPLETE)
- Agent 4: OK People Search (COMPLETE)
- Agent 1: Research Orchestrator (pending)
"""

from app.services.phase4.entity_resolver import EntityResolver, entity_resolver
from app.services.phase4.connection_analyzer import ConnectionAnalyzer, connection_analyzer
from app.services.phase4.ok_people_search import OKPeopleSearch, ok_people_search
from app.services.phase4.telegram_search import TelegramSearch, telegram_search

__all__ = [
    'EntityResolver',
    'entity_resolver',
    'ConnectionAnalyzer',
    'connection_analyzer',
    'OKPeopleSearch',
    'ok_people_search',
    'TelegramSearch',
    'telegram_search',
]

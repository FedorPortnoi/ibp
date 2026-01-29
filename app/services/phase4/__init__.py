"""
Phase 4 Services - Advanced OSINT Features
==========================================
All Agent modules COMPLETE:
- Agent 5: EntityResolver, ConnectionAnalyzer
- Agent 3: TelegramSearch
- Agent 4: OKPeopleSearch
- Agent 1: ResearchOrchestrator (orchestrates all)

VK uses username-based search from app.services.vk_search
"""

from app.services.phase4.entity_resolver import EntityResolver, entity_resolver
from app.services.phase4.connection_analyzer import ConnectionAnalyzer, connection_analyzer
from app.services.phase4.ok_people_search import OKPeopleSearch, ok_people_search
from app.services.phase4.telegram_search import TelegramSearch, telegram_search
from app.services.phase4.research_orchestrator import ResearchOrchestrator, research_orchestrator

__all__ = [
    'EntityResolver',
    'entity_resolver',
    'ConnectionAnalyzer',
    'connection_analyzer',
    'OKPeopleSearch',
    'ok_people_search',
    'TelegramSearch',
    'telegram_search',
    'ResearchOrchestrator',
    'research_orchestrator',
]

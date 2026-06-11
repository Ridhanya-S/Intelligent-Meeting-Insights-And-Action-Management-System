"""
Integrations Module

External integrations for task management and knowledge base storage.
"""

from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.integrations.knowledge_base import KnowledgeBase

__all__ = [
    "ActionItemManager",
    "KnowledgeBase",
]


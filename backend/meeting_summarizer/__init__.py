"""
Meeting Summarizer Package

A comprehensive Python application for processing meeting transcripts,
generating structured summaries, and tracking action items.
"""

__version__ = "1.0.0"

from backend.meeting_summarizer.config import Config
from backend.meeting_summarizer.models import (
    ActionItem,
    ActionItemStatus,
    AgendaTopic,
    Decision,
    MeetingSummary,
    MeetingTranscript,
    Risk,
)

__all__ = [
    "Config",
    "ActionItem",
    "ActionItemStatus",
    "AgendaTopic",
    "Decision",
    "MeetingSummary",
    "MeetingTranscript",
    "Risk",
]


"""
Data Models Module

Defines Pydantic models for meeting transcripts, summaries, and related entities.
All models use Pydantic for validation and serialization.
"""

# Standard library imports
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Third-party imports
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class ActionItemStatus(str, Enum):
    """Status enumeration for action items."""
    NEW = "new"  # Newly added item
    PENDING = "pending"  # Same item repeated with no progress
    DOING = "doing"  # Same item has some progress
    DONE = "done"  # Item is completed
    BLOCKED = "blocked"  # Item is blocked


# ============================================================================
# Core Models
# ============================================================================

class ActionItem(BaseModel):
    """
    Represents an action item from a meeting.
    
    Attributes:
        id: Unique identifier for the action item
        description: Description of the action item
        owner: Person responsible for the action item
        deadline: Due date and time for the action item
        status: Current status of the action item
        dependencies: List of dependencies for this action item
        tags: List of tags associated with the action item
        created_at: Timestamp when the action item was created
        updated_at: Timestamp when the action item was last updated
        external_id: ID in external system (e.g., Trello card ID)
    """
    id: Optional[str] = None
    description: str
    owner: str
    deadline: Optional[datetime] = None
    status: ActionItemStatus = ActionItemStatus.NEW
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    external_id: Optional[str] = None  # ID in Trello/Planner


class Decision(BaseModel):
    """
    Represents a decision made in a meeting.
    
    Attributes:
        id: Unique identifier for the decision
        description: Description of the decision
        context: Additional context around the decision
        decision_makers: List of people who made the decision
        timestamp: When the decision was made
    """
    id: Optional[str] = None
    description: str
    context: Optional[str] = None
    decision_makers: List[str] = Field(default_factory=list)
    timestamp: Optional[datetime] = None


class Risk(BaseModel):
    """
    Represents a risk or blocker identified in a meeting.
    
    Attributes:
        id: Unique identifier for the risk
        description: Description of the risk
        severity: Severity level (low, medium, high, critical)
        impact: Impact description
        mitigation: Mitigation strategy if mentioned
        owner: Person responsible for addressing the risk
    """
    id: Optional[str] = None
    description: str
    severity: str = "medium"  # low, medium, high, critical
    impact: Optional[str] = None
    mitigation: Optional[str] = None
    owner: Optional[str] = None


# ============================================================================
# Composite Models
# ============================================================================

class AgendaTopic(BaseModel):
    """
    Represents an agenda topic discussed in a meeting.
    
    Attributes:
        topic: Name of the agenda topic
        summary: Summary of discussion on this topic
        key_points: List of key points discussed
        decisions: List of decisions made during this topic
        action_items: List of action items from this topic
        risks: List of risks identified during this topic
        duration_minutes: Duration of discussion in minutes
    """
    topic: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    duration_minutes: Optional[float] = None


class MeetingSummary(BaseModel):
    """
    Complete summary of a meeting.
    
    Attributes:
        id: Unique identifier for the meeting summary
        project_name: Name of the project
        meeting_title: Title of the meeting
        meeting_date: Date and time of the meeting
        meeting_type: Type of meeting (discussion, KT, decision_making, general)
        participants: List of participants
        duration_minutes: Duration of the meeting in minutes
        agenda_topics: List of agenda topics discussed
        overall_summary: Overall summary of the meeting
        all_action_items: All action items from the meeting
        all_decisions: All decisions made in the meeting
        all_risks: All risks identified in the meeting
        tags: List of tags for categorization
        transcript_path: Path to the transcript file
        created_at: Timestamp when summary was created
        updated_at: Timestamp when summary was last updated
        metadata: Additional metadata as key-value pairs
    """
    id: Optional[str] = None
    project_name: str
    meeting_title: str
    meeting_date: datetime
    meeting_type: Optional[str] = "general"  # discussion, KT, decision_making, general
    participants: List[str] = Field(default_factory=list)
    duration_minutes: Optional[float] = None
    agenda_topics: List[AgendaTopic] = Field(default_factory=list)
    overall_summary: str
    all_action_items: List[ActionItem] = Field(default_factory=list)
    all_decisions: List[Decision] = Field(default_factory=list)
    all_risks: List[Risk] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    transcript_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MeetingTranscript(BaseModel):
    """
    Raw transcript data from a meeting.
    
    Attributes:
        id: Unique identifier for the transcript
        project_name: Name of the project
        file_path: Path to the transcript file
        file_type: Type of file (audio, video, transcript)
        transcript_text: Full text of the transcript
        segments: List of timestamped segments
        language: Detected language of the transcript
        meeting_date: Extracted meeting date from transcript (if found)
        participants: Extracted participants from transcript (if found)
        created_at: Timestamp when transcript was created
    """
    id: Optional[str] = None
    project_name: str
    file_path: str
    file_type: str  # audio, video, transcript
    transcript_text: str
    segments: List[Dict[str, Any]] = Field(default_factory=list)  # Timestamped segments
    language: Optional[str] = None
    meeting_date: Optional[datetime] = None  # Extracted from transcript
    participants: List[str] = Field(default_factory=list)  # Extracted from transcript
    created_at: datetime = Field(default_factory=datetime.now)

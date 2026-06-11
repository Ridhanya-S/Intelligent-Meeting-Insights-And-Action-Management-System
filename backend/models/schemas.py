"""
API Request/Response Schemas
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProcessTranscriptRequest(BaseModel):
    """Request model for processing a transcript"""
    project_name: str = Field(..., description="Name of the project")
    meeting_title: Optional[str] = Field(None, description="Title of the meeting")
    meeting_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    participants: Optional[List[str]] = Field(default_factory=list, description="List of participants")
    skip_sync: bool = Field(False, description="Skip syncing to Trello")
    analyze_project: bool = Field(False, description="Run multi-meeting analysis")


class ActionItemResponse(BaseModel):
    """Response model for action item"""
    id: Optional[str] = None
    description: str
    owner: str
    deadline: Optional[datetime] = None
    status: str
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response model for meeting summary"""
    id: Optional[str] = None
    project_name: str
    meeting_title: str
    meeting_date: datetime
    meeting_type: Optional[str] = "general"  # discussion, KT, decision_making, general
    participants: List[str] = Field(default_factory=list)
    duration_minutes: Optional[float] = None
    overall_summary: str
    action_items_count: int
    decisions_count: int
    risks_count: int
    tags: List[str] = Field(default_factory=list)
    transcript_path: Optional[str] = None
    created_at: datetime
    # Full details (optional for backward compatibility)
    all_action_items: Optional[List[ActionItemResponse]] = Field(default=None)
    all_decisions: Optional[List[dict]] = Field(default=None)
    all_risks: Optional[List[dict]] = Field(default=None)
    confluence_url: Optional[str] = Field(default=None)
    trello_board_url: Optional[str] = Field(default=None)


class RecordingMetadata(BaseModel):
    """Metadata for a recording found in SharePoint"""
    index: int
    name: str
    modified: str
    size: int
    source: str


class ProcessTranscriptResponse(BaseModel):
    """Response model for transcript processing"""
    success: bool
    message: str
    summary: Optional[SummaryResponse] = None
    summaries: Optional[List[SummaryResponse]] = None  # Multiple summaries when processing multiple files
    summary_id: Optional[str] = None
    summary_ids: Optional[List[str]] = None  # Multiple summary IDs when processing multiple files
    process_id: Optional[str] = None  # For progress tracking
    requires_confirmation: bool = False  # If meeting is old, requires user confirmation
    confirmation_prompt: Optional[str] = None  # Message asking for confirmation
    meeting_details: Optional[dict] = None  # Teams meeting details (when no transcript provided)
    requires_selection: bool = False  # If multiple recordings found, requires user selection
    recordings: Optional[List[RecordingMetadata]] = None  # List of recordings for selection
    transcripts: Optional[List[dict]] = None  # List of transcripts found


class ConfirmationRequest(BaseModel):
    """Request model for confirming old meeting processing"""
    process_id: str
    add_to_trello: bool = True
    add_to_confluence: bool = True


class ProjectInfo(BaseModel):
    """Project information"""
    name: str
    meeting_count: int
    latest_meeting_date: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


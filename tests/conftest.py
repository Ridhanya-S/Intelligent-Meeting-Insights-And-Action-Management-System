"""
Pytest configuration and fixtures
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import models after path setup
try:
    from backend.meeting_summarizer.models import (
        ActionItem, ActionItemStatus, Decision, Risk,
        MeetingSummary, MeetingTranscript, AgendaTopic
    )
except ImportError:
    # Fallback for testing without full backend setup
    pass


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_action_item():
    """Create a sample action item for testing"""
    return ActionItem(
        description="Test action item",
        owner="Test User",
        deadline=datetime(2024, 12, 31),
        status=ActionItemStatus.PENDING,
        tags=["test", "urgent"],
        dependencies=["dep1", "dep2"]
    )


@pytest.fixture
def sample_decision():
    """Create a sample decision for testing"""
    return Decision(
        description="Test decision",
        context="Test context",
        decision_makers=["Alice", "Bob"],
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_risk():
    """Create a sample risk for testing"""
    return Risk(
        description="Test risk",
        severity="high",
        impact="High impact",
        mitigation="Test mitigation",
        owner="Risk Owner"
    )


@pytest.fixture
def sample_transcript():
    """Create a sample transcript for testing"""
    return MeetingTranscript(
        project_name="TestProject",
        file_path="/test/path.txt",
        file_type="transcript",
        transcript_text="This is a test transcript. Meeting discussion about project planning."
    )


@pytest.fixture
def sample_summary():
    """Create a sample meeting summary for testing"""
    return MeetingSummary(
        project_name="TestProject",
        meeting_title="Test Meeting",
        meeting_date=datetime.now(),
        participants=["Alice", "Bob", "Charlie"],
        duration_minutes=60.0,
        overall_summary="Test meeting summary",
        all_action_items=[
            ActionItem(
                description="Action 1",
                owner="Alice",
                status=ActionItemStatus.PENDING
            )
        ],
        all_decisions=[
            Decision(
                description="Decision 1",
                decision_makers=["Alice", "Bob"]
            )
        ],
        all_risks=[
            Risk(
                description="Risk 1",
                severity="medium"
            )
        ],
        tags=["test", "meeting"]
    )


@pytest.fixture
def sample_transcript_text():
    """Sample transcript text for testing"""
    return """
    Meeting Transcript - Project Planning
    
    Alice: Welcome everyone. Let's discuss the project timeline.
    Bob: I think we should aim for Q1 completion.
    Charlie: That sounds reasonable. What about resources?
    Alice: We'll need 3 developers and 1 designer.
    Bob: I can handle the backend development.
    Charlie: I'll take the frontend.
    
    Action Items:
    - Bob: Complete backend API by end of month
    - Charlie: Design mockups by next week
    
    Decisions:
    - Timeline: Q1 completion approved
    - Team size: 4 members confirmed
    
    Risks:
    - Resource availability: Medium risk
    """


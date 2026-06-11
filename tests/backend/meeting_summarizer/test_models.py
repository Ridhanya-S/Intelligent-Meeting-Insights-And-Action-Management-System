"""
Tests for data models
"""
import pytest
from datetime import datetime
from backend.meeting_summarizer.models import (
    ActionItem, ActionItemStatus, Decision, Risk,
    MeetingSummary, MeetingTranscript, AgendaTopic
)


class TestActionItem:
    """Test ActionItem model"""
    
    def test_action_item_creation(self, sample_action_item):
        """Test creating an action item"""
        assert sample_action_item.description == "Test action item"
        assert sample_action_item.owner == "Test User"
        assert sample_action_item.status == ActionItemStatus.PENDING
        assert len(sample_action_item.tags) == 2
    
    def test_action_item_defaults(self):
        """Test action item default values"""
        item = ActionItem(
            description="Test",
            owner="User"
        )
        assert item.status == ActionItemStatus.PENDING
        assert item.dependencies == []
        assert item.tags == []
        assert item.external_id is None
    
    def test_action_item_status_enum(self):
        """Test action item status enum values"""
        assert ActionItemStatus.PENDING == "pending"
        assert ActionItemStatus.IN_PROGRESS == "in_progress"
        assert ActionItemStatus.COMPLETED == "completed"
        assert ActionItemStatus.BLOCKED == "blocked"


class TestDecision:
    """Test Decision model"""
    
    def test_decision_creation(self, sample_decision):
        """Test creating a decision"""
        assert sample_decision.description == "Test decision"
        assert len(sample_decision.decision_makers) == 2
        assert sample_decision.context == "Test context"
    
    def test_decision_defaults(self):
        """Test decision default values"""
        decision = Decision(description="Test")
        assert decision.context is None
        assert decision.decision_makers == []
        assert decision.timestamp is None


class TestRisk:
    """Test Risk model"""
    
    def test_risk_creation(self, sample_risk):
        """Test creating a risk"""
        assert sample_risk.description == "Test risk"
        assert sample_risk.severity == "high"
        assert sample_risk.owner == "Risk Owner"
    
    def test_risk_defaults(self):
        """Test risk default values"""
        risk = Risk(description="Test")
        assert risk.severity == "medium"
        assert risk.impact is None
        assert risk.mitigation is None
        assert risk.owner is None


class TestMeetingTranscript:
    """Test MeetingTranscript model"""
    
    def test_transcript_creation(self, sample_transcript):
        """Test creating a transcript"""
        assert sample_transcript.project_name == "TestProject"
        assert sample_transcript.file_type == "transcript"
        assert "test transcript" in sample_transcript.transcript_text.lower()
    
    def test_transcript_defaults(self):
        """Test transcript default values"""
        transcript = MeetingTranscript(
            project_name="Test",
            file_path="/test",
            file_type="transcript",
            transcript_text="Test"
        )
        assert transcript.segments == []
        assert transcript.language is None


class TestMeetingSummary:
    """Test MeetingSummary model"""
    
    def test_summary_creation(self, sample_summary):
        """Test creating a meeting summary"""
        assert sample_summary.project_name == "TestProject"
        assert sample_summary.meeting_title == "Test Meeting"
        assert len(sample_summary.all_action_items) == 1
        assert len(sample_summary.all_decisions) == 1
        assert len(sample_summary.all_risks) == 1
    
    def test_summary_defaults(self):
        """Test summary default values"""
        summary = MeetingSummary(
            project_name="Test",
            meeting_title="Title",
            meeting_date=datetime.now(),
            overall_summary="Summary"
        )
        assert summary.participants == []
        assert summary.all_action_items == []
        assert summary.all_decisions == []
        assert summary.all_risks == []
        assert summary.tags == []
        assert summary.metadata == {}


class TestAgendaTopic:
    """Test AgendaTopic model"""
    
    def test_agenda_topic_creation(self):
        """Test creating an agenda topic"""
        topic = AgendaTopic(
            topic="Test Topic",
            summary="Topic summary",
            key_points=["Point 1", "Point 2"]
        )
        assert topic.topic == "Test Topic"
        assert len(topic.key_points) == 2
        assert topic.decisions == []
        assert topic.action_items == []
        assert topic.risks == []


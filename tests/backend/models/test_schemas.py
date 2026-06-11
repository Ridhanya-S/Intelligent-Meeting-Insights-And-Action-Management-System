"""
Tests for API schemas
"""
import pytest
from datetime import datetime
from backend.models.schemas import (
    ActionItemResponse, SummaryResponse, ProcessTranscriptResponse,
    ProjectInfo
)


class TestActionItemResponse:
    """Test ActionItemResponse schema"""
    
    def test_action_item_response_creation(self):
        """Test creating an ActionItemResponse"""
        item = ActionItemResponse(
            id="test-id",
            description="Test action",
            owner="Test User",
            deadline=datetime.now(),
            status="pending",
            dependencies=["dep1"],
            tags=["tag1"],
            external_id="trello-123"
        )
        assert item.id == "test-id"
        assert item.description == "Test action"
        assert item.owner == "Test User"
        assert item.status == "pending"
        assert item.external_id == "trello-123"


class TestSummaryResponse:
    """Test SummaryResponse schema"""
    
    def test_summary_response_creation(self):
        """Test creating a SummaryResponse"""
        summary = SummaryResponse(
            id="test-id",
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"],
            duration_minutes=60.0,
            overall_summary="Test summary",
            action_items_count=5,
            decisions_count=3,
            risks_count=2,
            tags=["test"],
            created_at=datetime.now()
        )
        assert summary.id == "test-id"
        assert summary.project_name == "TestProject"
        assert summary.action_items_count == 5
        assert len(summary.participants) == 2


class TestProcessTranscriptResponse:
    """Test ProcessTranscriptResponse schema"""
    
    def test_process_transcript_response_success(self):
        """Test successful transcript processing response"""
        summary = SummaryResponse(
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
            overall_summary="Test",
            action_items_count=0,
            decisions_count=0,
            risks_count=0,
            tags=[],
            created_at=datetime.now()
        )
        response = ProcessTranscriptResponse(
            success=True,
            message="Success",
            summary=summary,
            summary_id="test-id"
        )
        assert response.success is True
        assert response.summary_id == "test-id"


class TestProjectInfo:
    """Test ProjectInfo schema"""
    
    def test_project_info_creation(self):
        """Test creating ProjectInfo"""
        project = ProjectInfo(
            name="TestProject",
            meeting_count=5,
            latest_meeting_date=datetime.now()
        )
        assert project.name == "TestProject"
        assert project.meeting_count == 5


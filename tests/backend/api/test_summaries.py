"""
Tests for summaries API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app
from backend.meeting_summarizer.models import MeetingSummary, ActionItem, Decision, Risk
from datetime import datetime


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestSummariesAPI:
    """Test summaries API endpoints"""
    
    @patch('backend.api.summaries.Storage')
    def test_get_summary_success(self, mock_storage, client):
        """Test getting a summary successfully"""
        mock_summary = MeetingSummary(
            id="test-id",
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
            overall_summary="Test summary",
            all_action_items=[],
            all_decisions=[],
            all_risks=[],
            tags=[],
            created_at=datetime.now()
        )
        mock_storage.return_value.get_summary.return_value = mock_summary
        
        response = client.get("/api/summaries/test-id")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
        assert data["project_name"] == "TestProject"
    
    @patch('backend.api.summaries.Storage')
    def test_get_summary_not_found(self, mock_storage, client):
        """Test getting a non-existent summary"""
        mock_storage.return_value.get_summary.return_value = None
        
        response = client.get("/api/summaries/nonexistent-id")
        assert response.status_code == 404
    
    @patch('backend.api.summaries.Storage')
    def test_get_summary_with_full_details(self, mock_storage, client):
        """Test getting summary with full details"""
        mock_summary = MeetingSummary(
            id="test-id",
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
            overall_summary="Test summary",
            all_action_items=[
                ActionItem(
                    description="Action 1",
                    owner="Alice",
                    status="pending"
                )
            ],
            all_decisions=[
                Decision(description="Decision 1")
            ],
            all_risks=[
                Risk(description="Risk 1", severity="high")
            ],
            tags=[],
            created_at=datetime.now()
        )
        mock_storage.return_value.get_summary.return_value = mock_summary
        
        response = client.get("/api/summaries/test-id?full_details=true")
        assert response.status_code == 200
        data = response.json()
        assert "all_action_items" in data or data.get("all_action_items") is not None
    
    @patch('backend.api.summaries.Storage')
    def test_get_project_summaries(self, mock_storage, client):
        """Test getting summaries for a project"""
        mock_summary = MeetingSummary(
            id="test-id",
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
            overall_summary="Test summary",
            all_action_items=[],
            all_decisions=[],
            all_risks=[],
            tags=[],
            created_at=datetime.now()
        )
        mock_storage.return_value.get_project_meetings.return_value = ["test-id"]
        mock_storage.return_value.get_summary.return_value = mock_summary
        
        response = client.get("/api/summaries/project/TestProject")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0


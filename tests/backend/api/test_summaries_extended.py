"""
Extended tests for summaries API endpoints
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


class TestSummariesAPIExtended:
    """Extended tests for summaries API"""
    
    @patch('backend.api.summaries.Storage')
    @patch('backend.api.summaries.ActionItemManager')
    def test_get_summary_with_trello_url(self, mock_action_manager, mock_storage, client):
        """Test getting summary with Trello board URL"""
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
                    status="pending",
                    external_id="card123"
                )
            ],
            all_decisions=[],
            all_risks=[],
            tags=[],
            created_at=datetime.now()
        )
        mock_storage.return_value.get_summary.return_value = mock_summary
        
        # Mock Trello board
        mock_manager = MagicMock()
        mock_manager._get_or_create_board.return_value = "board123"
        mock_manager.trello_client = MagicMock()
        mock_action_manager.return_value = mock_manager
        
        response = client.get("/api/summaries/test-id?full_details=true")
        assert response.status_code == 200
    
    @patch('backend.api.summaries.Storage')
    def test_get_summary_with_confluence_url(self, mock_storage, client):
        """Test getting summary with Confluence URL"""
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
            created_at=datetime.now(),
            metadata={"confluence_url": "https://confluence.test/page/123"}
        )
        mock_storage.return_value.get_summary.return_value = mock_summary
        
        response = client.get("/api/summaries/test-id")
        assert response.status_code == 200
        data = response.json()
        assert "confluence_url" in data or data.get("confluence_url") is not None


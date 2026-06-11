"""
Tests for action items API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestActionItemsAPI:
    """Test action items API endpoints"""
    
    @patch('backend.api.action_items.Storage')
    @patch('backend.api.action_items.ActionItemManager')
    def test_get_action_items(self, mock_action_manager, mock_storage, client):
        """Test getting action items"""
        mock_storage.return_value.get_action_items_by_owner.return_value = [
            {
                "id": "ai1",
                "meeting_id": "m1",
                "description": "Test action",
                "owner": "Alice",
                "deadline": None,
                "status": "pending",
                "dependencies": [],
                "tags": [],
                "external_id": None
            }
        ]
        
        response = client.get("/api/action-items/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('backend.api.action_items.Storage')
    @patch('backend.api.action_items.ActionItemManager')
    def test_get_action_items_with_filters(self, mock_action_manager, mock_storage, client):
        """Test getting action items with filters"""
        mock_storage.return_value.get_action_items_by_owner.return_value = []
        
        response = client.get("/api/action-items/?owner=Alice&status=pending")
        assert response.status_code == 200
    
    @patch('backend.api.action_items.ActionItemManager')
    def test_send_reminders(self, mock_action_manager, client):
        """Test sending reminders"""
        mock_action_manager.return_value.send_all_pending_reminders.return_value = {
            "total": 5,
            "sent": 4,
            "failed": 1
        }
        
        response = client.post("/api/action-items/send-reminders")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total" in data
        assert "sent" in data


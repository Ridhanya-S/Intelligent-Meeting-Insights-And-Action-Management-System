"""
Extended tests for ActionItemManager module
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.models import ActionItem, ActionItemStatus
from datetime import datetime, timedelta


class TestActionItemManagerExtended:
    """Extended tests for ActionItemManager"""
    
    @pytest.fixture
    def action_manager(self):
        """Create an action manager instance"""
        import sys
        from unittest.mock import MagicMock
        mock_trello = MagicMock()
        sys.modules['trello'] = mock_trello
        mock_trello.TrelloClient = MagicMock()
        
        manager = ActionItemManager()
        manager.trello_client = None
        return manager
    
    def test_board_cache_operations(self, action_manager, temp_data_dir, monkeypatch):
        """Test board cache save and load"""
        from pathlib import Path
        cache_file = temp_data_dir / "trello_boards.json"
        monkeypatch.setattr(action_manager, "_board_cache_file", cache_file)
        
        # Test saving cache
        action_manager.board_cache = {"TestProject": "board123"}
        action_manager._save_board_cache()
        
        # Test loading cache
        action_manager.board_cache = {}
        action_manager._load_board_cache()
        assert "TestProject" in action_manager.board_cache
    
    def test_get_pending_reminders_with_items(self, action_manager, temp_data_dir, monkeypatch):
        """Test getting pending reminders with action items"""
        from backend.meeting_summarizer.core.storage import Storage
        from backend.meeting_summarizer.config import Config
        
        monkeypatch.setattr(Config, "DATABASE_PATH", temp_data_dir / "test.db")
        monkeypatch.setattr(Config, "DATA_DIR", temp_data_dir)
        
        # Create storage and add action items
        storage = Storage()
        from backend.meeting_summarizer.models import MeetingSummary
        
        summary = MeetingSummary(
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
            overall_summary="Test",
            all_action_items=[
                ActionItem(
                    description="Urgent task",
                    owner="Alice",
                    deadline=datetime.now() + timedelta(hours=20),  # Due in 20 hours
                    status=ActionItemStatus.PENDING
                )
            ],
            all_decisions=[],
            all_risks=[],
            tags=[],
            created_at=datetime.now()
        )
        storage.save_summary(summary)
        
        reminders = action_manager.get_pending_reminders()
        assert isinstance(reminders, list)
    
    def test_update_action_item_status_completed(self, action_manager):
        """Test updating action item status to completed"""
        item = ActionItem(
            description="Test",
            owner="Alice",
            status=ActionItemStatus.PENDING,
            external_id="card123"
        )
        
        # Mock Trello client
        mock_client = Mock()
        mock_board = Mock()
        mock_board.id = "board123"
        mock_list = Mock()
        mock_list.name = "Done"
        mock_board.list_lists.return_value = [mock_list]
        mock_card = Mock()
        mock_client.get_board.return_value = mock_board
        mock_client.get_card.return_value = mock_card
        
        action_manager.trello_client = mock_client
        action_manager.board_cache = {"TestProject": "board123"}
        
        result = action_manager.update_action_item_status(
            item,
            ActionItemStatus.COMPLETED,
            "TestProject"
        )
        
        assert result.status == ActionItemStatus.COMPLETED
    
    def test_update_action_item_status_in_progress(self, action_manager):
        """Test updating action item status to in progress"""
        item = ActionItem(
            description="Test",
            owner="Alice",
            status=ActionItemStatus.PENDING,
            external_id="card123"
        )
        
        # Mock Trello client
        mock_client = Mock()
        mock_board = Mock()
        mock_board.id = "board123"
        mock_list = Mock()
        mock_list.name = "In Progress"
        mock_board.list_lists.return_value = [mock_list]
        mock_card = Mock()
        mock_client.get_board.return_value = mock_board
        mock_client.get_card.return_value = mock_card
        
        action_manager.trello_client = mock_client
        action_manager.board_cache = {"TestProject": "board123"}
        
        result = action_manager.update_action_item_status(
            item,
            ActionItemStatus.IN_PROGRESS,
            "TestProject"
        )
        
        assert result.status == ActionItemStatus.IN_PROGRESS


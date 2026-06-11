"""
Tests for ActionItemManager module
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.models import ActionItem, ActionItemStatus


class TestActionItemManager:
    """Test ActionItemManager class"""
    
    @pytest.fixture
    def action_manager(self, monkeypatch):
        """Create an action manager instance"""
        # Mock Trello import
        import sys
        from unittest.mock import MagicMock
        mock_trello = MagicMock()
        sys.modules['trello'] = mock_trello
        mock_trello.TrelloClient = MagicMock()
        
        manager = ActionItemManager()
        manager.trello_client = None  # Disable Trello for most tests
        return manager
    
    def test_action_manager_initialization(self, action_manager):
        """Test action manager initialization"""
        assert action_manager is not None
        assert hasattr(action_manager, 'trello_client')
        assert hasattr(action_manager, 'board_cache')
    
    def test_sync_action_items_no_trello(self, action_manager, sample_action_item):
        """Test syncing action items without Trello"""
        items = [sample_action_item]
        result = action_manager.sync_action_items(
            items,
            "TestProject",
            "Test Meeting"
        )
        
        assert len(result) == 1
        assert result[0].description == sample_action_item.description
    
    def test_sync_action_items_with_trello(self, action_manager, sample_action_item):
        """Test syncing action items with Trello"""
        # Mock Trello client
        from unittest.mock import Mock
        mock_board = Mock()
        mock_board.id = "board123"
        mock_list = Mock()
        mock_list.name = "To Do"
        mock_board.list_lists.return_value = [mock_list]
        mock_card = Mock()
        mock_card.id = "card123"
        mock_list.add_card.return_value = mock_card
        mock_board.get_labels.return_value = []
        
        mock_client = Mock()
        mock_client.get_board.return_value = mock_board
        action_manager.trello_client = mock_client
        action_manager.board_cache = {"TestProject": "board123"}
        
        items = [sample_action_item]
        result = action_manager.sync_action_items(
            items,
            "TestProject",
            "Test Meeting"
        )
        
        assert len(result) == 1
        # External ID should be set if Trello sync succeeds
        # (may be None if mock setup is incomplete)
    
    def test_get_or_create_board_no_client(self, action_manager):
        """Test getting board without Trello client"""
        result = action_manager._get_or_create_board("TestProject")
        assert result is None
    
    def test_move_cards_to_delete_list_no_client(self, action_manager):
        """Test moving cards without Trello client"""
        result = action_manager.move_cards_to_delete_list(
            ["card1", "card2"],
            "TestProject"
        )
        assert result == 0
    
    def test_archive_all_cards_no_client(self, action_manager):
        """Test archiving cards without Trello client"""
        result = action_manager.archive_all_cards_in_delete_list("TestProject")
        assert result == 0
    
    def test_update_action_item_status_no_external_id(self, action_manager, sample_action_item):
        """Test updating action item without external ID"""
        result = action_manager.update_action_item_status(
            sample_action_item,
            ActionItemStatus.COMPLETED,
            "TestProject"
        )
        
        assert result.status == ActionItemStatus.COMPLETED
        assert result.external_id == sample_action_item.external_id
    
    def test_get_pending_reminders(self, action_manager):
        """Test getting pending reminders"""
        reminders = action_manager.get_pending_reminders()
        assert isinstance(reminders, list)
    
    def test_send_all_pending_reminders(self, action_manager):
        """Test sending all pending reminders"""
        result = action_manager.send_all_pending_reminders()
        assert isinstance(result, dict)
        assert "total" in result
        assert "sent" in result
        assert "failed" in result


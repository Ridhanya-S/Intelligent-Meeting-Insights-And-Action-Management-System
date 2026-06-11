"""
Tests for Storage module
"""
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
from backend.meeting_summarizer.core.storage import Storage
from backend.meeting_summarizer.models import (
    MeetingSummary, ActionItem, ActionItemStatus
)
from backend.meeting_summarizer.config import Config


class TestStorage:
    """Test Storage class"""
    
    @pytest.fixture
    def storage(self, temp_data_dir, monkeypatch):
        """Create a storage instance with temporary database"""
        # Patch the database path
        monkeypatch.setattr(Config, "DATABASE_PATH", temp_data_dir / "test.db")
        monkeypatch.setattr(Config, "DATA_DIR", temp_data_dir)
        return Storage()
    
    def test_storage_initialization(self, storage):
        """Test storage initialization creates database"""
        assert storage.db_path.exists()
    
    def test_save_and_get_summary(self, storage, sample_summary):
        """Test saving and retrieving a summary"""
        summary_id = storage.save_summary(sample_summary)
        assert summary_id == sample_summary.id
        
        retrieved = storage.get_summary(summary_id)
        assert retrieved is not None
        assert retrieved.project_name == sample_summary.project_name
        assert retrieved.meeting_title == sample_summary.meeting_title
    
    def test_get_nonexistent_summary(self, storage):
        """Test getting a summary that doesn't exist"""
        result = storage.get_summary("nonexistent-id")
        assert result is None
    
    def test_get_project_meetings(self, storage, sample_summary):
        """Test getting meetings for a project"""
        storage.save_summary(sample_summary)
        meetings = storage.get_project_meetings("TestProject")
        assert len(meetings) > 0
        assert sample_summary.id in meetings
    
    def test_get_action_items_by_owner(self, storage, sample_summary):
        """Test getting action items by owner"""
        storage.save_summary(sample_summary)
        items = storage.get_action_items_by_owner("Alice", None)
        assert len(items) > 0
        assert items[0]["owner"] == "Alice"
    
    def test_get_action_items_by_status(self, storage, sample_summary):
        """Test getting action items by status"""
        storage.save_summary(sample_summary)
        items = storage.get_action_items_by_owner("", ActionItemStatus.PENDING)
        assert len(items) > 0
        assert items[0]["status"] == ActionItemStatus.PENDING
    
    def test_mark_file_processed(self, storage):
        """Test marking a file as processed"""
        file_id = storage.mark_file_processed(
            file_path="/test/path.txt",
            project_name="TestProject",
            meeting_id="test-meeting-id",
            trello_synced=True,
            confluence_stored=True
        )
        assert file_id is not None
    
    def test_is_file_processed(self, storage):
        """Test checking if a file is processed"""
        file_path = "/test/path.txt"
        storage.mark_file_processed(file_path, "TestProject")
        
        result = storage.is_file_processed(file_path)
        assert result is True
        
        result = storage.is_file_processed("/nonexistent/path.txt")
        assert result is False
    
    def test_calculate_file_hash(self, storage, temp_data_dir):
        """Test file hash calculation"""
        test_file = temp_data_dir / "test.txt"
        test_file.write_text("test content")
        
        hash1 = storage.calculate_file_hash(str(test_file))
        hash2 = storage.calculate_file_hash(str(test_file))
        
        assert hash1 == hash2
        assert len(hash1) > 0
    
    def test_update_file_processing_status(self, storage):
        """Test updating file processing status"""
        file_path = "/test/path.txt"
        storage.mark_file_processed(file_path, "TestProject")
        
        storage.update_file_processing_status(
            file_path,
            trello_synced=True,
            confluence_stored=True
        )
        
        # Verify update worked
        result = storage.is_file_processed(file_path)
        assert result is True
    
    def test_get_processed_file_info(self, storage):
        """Test getting processed file info"""
        file_path = "/test/path.txt"
        storage.mark_file_processed(file_path, "Project1")
        
        info = storage.get_processed_file_info(file_path)
        assert info is not None
        assert info["project_name"] == "Project1"


"""
Tests for transcripts API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app
from backend.meeting_summarizer.models import MeetingSummary, ActionItem
from datetime import datetime


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def mock_summary():
    """Create a mock summary"""
    return MeetingSummary(
        id="test-id",
        project_name="TestProject",
        meeting_title="Test Meeting",
        meeting_date=datetime.now(),
        participants=["Alice", "Bob"],
        duration_minutes=60.0,
        overall_summary="Test summary",
        all_action_items=[
            ActionItem(
                description="Action 1",
                owner="Alice",
                status="pending"
            )
        ],
        all_decisions=[],
        all_risks=[],
        tags=["test"]
    )


class TestTranscriptsAPI:
    """Test transcript processing API"""
    
    @patch('backend.api.transcripts.TranscriptProcessor')
    @patch('backend.api.transcripts.MeetingSummarizer')
    @patch('backend.api.transcripts.Storage')
    @patch('backend.api.transcripts.ActionItemManager')
    @patch('backend.api.transcripts.KnowledgeBase')
    def test_process_transcript_success(
        self, mock_kb, mock_action, mock_storage, 
        mock_summarizer, mock_processor, client, temp_data_dir
    ):
        """Test successful transcript processing"""
        # Setup mocks
        mock_transcript = MagicMock()
        mock_transcript.transcript_text = "Test transcript"
        mock_processor.return_value.process_input.return_value = mock_transcript
        mock_processor.return_value.save_transcript.return_value = "/test/transcript.json"
        mock_processor.return_value.copy_uploaded_file.return_value = "/test/file.txt"
        
        mock_summary = MagicMock()
        mock_summary.id = "test-id"
        mock_summary.project_name = "TestProject"
        mock_summary.meeting_title = "Test Meeting"
        mock_summary.meeting_date = datetime.now()
        mock_summary.participants = []
        mock_summary.duration_minutes = 60.0
        mock_summary.overall_summary = "Test summary"
        mock_summary.all_action_items = []
        mock_summary.all_decisions = []
        mock_summary.all_risks = []
        mock_summary.tags = []
        mock_summary.transcript_path = None
        mock_summary.created_at = datetime.now()
        mock_summarizer.return_value.summarize.return_value = mock_summary
        
        mock_storage.return_value.save_summary.return_value = "test-id"
        mock_action.return_value.sync_action_items.return_value = []
        mock_kb.return_value.store_summary.return_value = None
        
        # Create a test file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test transcript content")
            temp_file = f.name
        
        try:
            # Make request
            with open(temp_file, 'rb') as file:
                response = client.post(
                    "/api/transcripts/process",
                    files={"file": ("test.txt", file, "text/plain")},
                    data={
                        "project_name": "TestProject",
                        "meeting_title": "Test Meeting"
                    }
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            import os
            os.unlink(temp_file)
    
    def test_process_transcript_missing_file(self, client):
        """Test processing transcript without file"""
        response = client.post(
            "/api/transcripts/process",
            data={"project_name": "TestProject"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_process_transcript_missing_project(self, client):
        """Test processing transcript without project name"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as file:
                response = client.post(
                    "/api/transcripts/process",
                    files={"file": ("test.txt", file, "text/plain")}
                )
            assert response.status_code == 422  # Validation error
        finally:
            import os
            os.unlink(temp_file)


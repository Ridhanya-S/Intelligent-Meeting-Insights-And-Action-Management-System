"""
Extended tests for transcripts API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestTranscriptsAPIExtended:
    """Extended tests for transcript processing API"""
    
    @patch('backend.api.transcripts.TranscriptProcessor')
    @patch('backend.api.transcripts.MeetingSummarizer')
    @patch('backend.api.transcripts.Storage')
    @patch('backend.api.transcripts.ActionItemManager')
    @patch('backend.api.transcripts.KnowledgeBase')
    def test_process_transcript_with_participants(
        self, mock_kb, mock_action, mock_storage, 
        mock_summarizer, mock_processor, client
    ):
        """Test processing transcript with participants"""
        import tempfile
        from datetime import datetime
        
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
        mock_summary.participants = ["Alice", "Bob"]
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test transcript content")
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as file:
                response = client.post(
                    "/api/transcripts/process",
                    files={"file": ("test.txt", file, "text/plain")},
                    data={
                        "project_name": "TestProject",
                        "meeting_title": "Test Meeting",
                        "participants": '["Alice", "Bob"]'
                    }
                )
            
            assert response.status_code == 200
        finally:
            import os
            os.unlink(temp_file)
    
    @patch('backend.api.transcripts.TranscriptProcessor')
    def test_process_transcript_error_handling(self, mock_processor, client):
        """Test error handling in transcript processing"""
        import tempfile
        
        mock_processor.return_value.process_input.side_effect = Exception("Processing error")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as file:
                response = client.post(
                    "/api/transcripts/process",
                    files={"file": ("test.txt", file, "text/plain")},
                    data={"project_name": "TestProject"}
                )
            
            assert response.status_code == 500
        finally:
            import os
            os.unlink(temp_file)


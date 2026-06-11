"""
Tests for TranscriptProcessor module
"""
import pytest
from pathlib import Path
from datetime import datetime
from backend.meeting_summarizer.core.transcript_processor import TranscriptProcessor
from backend.meeting_summarizer.config import Config


class TestTranscriptProcessor:
    """Test TranscriptProcessor class"""
    
    @pytest.fixture
    def processor(self, temp_data_dir, monkeypatch):
        """Create a processor instance with temporary data directory"""
        monkeypatch.setattr(Config, "DATA_DIR", temp_data_dir)
        return TranscriptProcessor()
    
    def test_process_text_file(self, processor, temp_data_dir, sample_transcript_text):
        """Test processing a text file"""
        test_file = temp_data_dir / "test.txt"
        test_file.write_text(sample_transcript_text)
        
        transcript = processor.process_input(
            project_name="TestProject",
            file_path=str(test_file),
            file_type="transcript"
        )
        
        assert transcript is not None
        assert transcript.project_name == "TestProject"
        assert transcript.file_type == "transcript"
        assert len(transcript.transcript_text) > 0
    
    def test_save_transcript(self, processor, sample_transcript, temp_data_dir, monkeypatch):
        """Test saving a transcript"""
        monkeypatch.setattr(Config, "DATA_DIR", temp_data_dir)
        
        transcript_path = processor.save_transcript(sample_transcript, datetime.now())
        
        assert transcript_path is not None
        assert Path(transcript_path).exists()
    
    def test_copy_uploaded_file(self, processor, temp_data_dir, monkeypatch):
        """Test copying an uploaded file"""
        monkeypatch.setattr(Config, "DATA_DIR", temp_data_dir)
        
        source_file = temp_data_dir / "source.txt"
        source_file.write_text("test content")
        
        copied_path = processor.copy_uploaded_file(
            str(source_file),
            "TestProject",
            datetime.now()
        )
        
        assert copied_path is not None
        assert Path(copied_path).exists()
        assert Path(copied_path).read_text() == "test content"
    
    def test_get_meeting_dir(self, processor, temp_data_dir, monkeypatch):
        """Test getting meeting directory"""
        from backend.meeting_summarizer.config import Config as ConfigClass
        monkeypatch.setattr(ConfigClass, "DATA_DIR", temp_data_dir)
        
        # Use Config method instead
        meeting_dir = ConfigClass.get_meeting_dir("TestProject", datetime.now())
        
        assert meeting_dir.exists()
        assert "TestProject" in str(meeting_dir)


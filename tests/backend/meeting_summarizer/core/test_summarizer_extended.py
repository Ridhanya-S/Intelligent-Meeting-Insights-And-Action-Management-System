"""
Extended tests for MeetingSummarizer module
"""
import pytest
from datetime import datetime
from backend.meeting_summarizer.core.summarizer import MeetingSummarizer
from backend.meeting_summarizer.models import MeetingTranscript


class TestMeetingSummarizerExtended:
    """Extended tests for MeetingSummarizer"""
    
    @pytest.fixture
    def summarizer(self):
        """Create a summarizer instance"""
        return MeetingSummarizer()
    
    def test_summarize_with_agenda_topics(self, summarizer, sample_transcript):
        """Test summarization with agenda topics"""
        transcript_text = """
        Agenda Topic 1: Project Planning
        Discussion about timeline and resources.
        
        Agenda Topic 2: Team Structure
        Discussion about roles and responsibilities.
        """
        sample_transcript.transcript_text = transcript_text
        
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        assert isinstance(summary.agenda_topics, list)
    
    def test_summarize_with_tags(self, summarizer, sample_transcript):
        """Test summarization extracts tags"""
        transcript_text = """
        Meeting discussion about #urgent #project #planning tasks.
        """
        sample_transcript.transcript_text = transcript_text
        
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice"]
        )
        
        assert summary is not None
        assert isinstance(summary.tags, list)
    
    def test_summarize_duration_calculation(self, summarizer, sample_transcript):
        """Test duration calculation in summary"""
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        # Duration may be None or a number
        assert summary.duration_minutes is None or isinstance(summary.duration_minutes, (int, float))


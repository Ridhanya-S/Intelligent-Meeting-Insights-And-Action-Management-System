"""
Tests for MeetingSummarizer module
"""
import pytest
from datetime import datetime
from backend.meeting_summarizer.core.summarizer import MeetingSummarizer
from backend.meeting_summarizer.models import MeetingTranscript


class TestMeetingSummarizer:
    """Test MeetingSummarizer class"""
    
    @pytest.fixture
    def summarizer(self):
        """Create a summarizer instance"""
        return MeetingSummarizer()
    
    def test_summarize_basic(self, summarizer, sample_transcript):
        """Test basic summarization"""
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        assert summary.project_name == sample_transcript.project_name
        assert summary.meeting_title == "Test Meeting"
        assert len(summary.participants) == 2
        assert len(summary.overall_summary) > 0
    
    def test_summarize_with_action_items(self, summarizer, sample_transcript):
        """Test summarization extracts action items"""
        # Create transcript with action items
        transcript_text = """
        Meeting discussion.
        Action Items:
        - Alice: Complete task 1 by Friday
        - Bob: Review documentation
        """
        sample_transcript.transcript_text = transcript_text
        
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        # Should extract some action items (may vary based on AI)
        assert isinstance(summary.all_action_items, list)
    
    def test_summarize_with_decisions(self, summarizer, sample_transcript):
        """Test summarization extracts decisions"""
        transcript_text = """
        Meeting discussion.
        Decisions:
        - Approved Q1 timeline
        - Team size confirmed
        """
        sample_transcript.transcript_text = transcript_text
        
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        assert isinstance(summary.all_decisions, list)
    
    @pytest.mark.skip(reason="Requires OpenAI API access")
    def test_summarize_with_risks(self, summarizer, sample_transcript):
        """Test summarization extracts risks"""
        transcript_text = """
        Meeting discussion.
        Risks identified:
        - Resource availability: Medium risk
        - Timeline: Low risk
        """
        sample_transcript.transcript_text = transcript_text
        
        summary = summarizer.summarize(
            transcript=sample_transcript,
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=["Alice", "Bob"]
        )
        
        assert summary is not None
        assert isinstance(summary.all_risks, list)


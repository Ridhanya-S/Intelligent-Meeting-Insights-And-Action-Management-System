"""
Tests for MultiMeetingAnalyzer module
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.meeting_summarizer.analysis.multi_meeting_analyzer import MultiMeetingAnalyzer
from backend.meeting_summarizer.models import MeetingSummary, ActionItem
from datetime import datetime, timedelta


class TestMultiMeetingAnalyzer:
    """Test MultiMeetingAnalyzer class"""
    
    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance"""
        return MultiMeetingAnalyzer()
    
    def test_analyze_project_meetings(self, analyzer):
        """Test analyzing project meetings"""
        from unittest.mock import Mock, patch
        from backend.meeting_summarizer.core.storage import Storage
        
        # Mock storage
        mock_summary = MeetingSummary(
            project_name="TestProject",
            meeting_title="Test Meeting",
            meeting_date=datetime.now(),
            participants=[],
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
            tags=[],
            created_at=datetime.now()
        )
        
        with patch.object(Storage, 'get_project_meetings', return_value=["meeting1"]):
            with patch.object(Storage, 'get_summary', return_value=mock_summary):
                storage = Storage()
                analyzer.storage = storage
                result = analyzer.analyze_project_meetings("TestProject", days_back=30)
                
                assert result is not None
                assert isinstance(result, dict)
    
    def test_analyze_project_meetings_empty(self, analyzer):
        """Test analyzing project with no meetings"""
        from unittest.mock import patch
        from backend.meeting_summarizer.core.storage import Storage
        
        with patch.object(Storage, 'get_project_meetings', return_value=[]):
            storage = Storage()
            analyzer.storage = storage
            result = analyzer.analyze_project_meetings("EmptyProject", days_back=30)
            
            assert result is not None
            assert isinstance(result, dict)


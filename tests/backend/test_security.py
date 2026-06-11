"""
Tests for security validation functions
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.security import validate_teams_url_only


class TestTeamsURLValidation:
    """Test Teams URL validation function"""
    
    def test_valid_teams_url_with_teams_microsoft_com(self):
        """Test valid Teams URL with teams.microsoft.com"""
        url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123"
        is_valid, error = validate_teams_url_only(url)
        assert is_valid is True
        assert error is None
    
    def test_valid_teams_url_with_microsoft_com_l(self):
        """Test valid Teams URL with microsoft.com/l/"""
        url = "https://microsoft.com/l/meetup-join/19%3ameeting_abc123"
        is_valid, error = validate_teams_url_only(url)
        assert is_valid is True
        assert error is None
    
    def test_valid_teams_url_with_meetup_join(self):
        """Test valid Teams URL with /meetup-join/"""
        url = "https://teams.microsoft.com/l/meetup-join/19:meeting_abc123def456"
        is_valid, error = validate_teams_url_only(url)
        assert is_valid is True
        assert error is None
    
    def test_valid_teams_url_with_meeting_path(self):
        """Test valid Teams URL with /meeting/"""
        url = "https://teams.microsoft.com/meeting/abc123"
        is_valid, error = validate_teams_url_only(url)
        assert is_valid is True
        assert error is None
    
    def test_empty_url(self):
        """Test empty URL"""
        is_valid, error = validate_teams_url_only("")
        assert is_valid is False
        assert "required" in error.lower()
    
    def test_none_url(self):
        """Test None URL"""
        # Type checker expects str, but we test None for robustness
        is_valid, error = validate_teams_url_only(None)  # type: ignore
        assert is_valid is False
        assert error is not None
        assert "required" in error.lower()
    
    def test_whitespace_only_url(self):
        """Test URL with only whitespace"""
        is_valid, error = validate_teams_url_only("   ")
        assert is_valid is False
        assert "required" in error.lower()
    
    def test_zoom_url_rejected(self):
        """Test that Zoom URLs are rejected"""
        zoom_urls = [
            "https://zoom.us/j/123456789",
            "https://us02web.zoom.us/j/123456789",
            "https://zoom.com/j/123456789",
            "https://example.zoom.us/j/123456789",
        ]
        for url in zoom_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"Zoom URL should be rejected: {url}"
            assert url_error is not None
            assert "zoom" in url_error.lower() or "not supported" in url_error.lower()
            assert "teams" in url_error.lower() or "only" in url_error.lower()
    
    def test_google_meet_url_rejected(self):
        """Test that Google Meet URLs are rejected"""
        google_meet_urls = [
            "https://meet.google.com/abc-defg-hij",
            "https://meet.google.com/abc-defg-hij?hs=123",
            "https://meet.google.com/abc-defg-hij?pli=1",
        ]
        for url in google_meet_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"Google Meet URL should be rejected: {url}"
            assert url_error is not None
            assert "google meet" in url_error.lower() or "not supported" in url_error.lower()
            assert "teams" in url_error.lower() or "only" in url_error.lower()
    
    def test_webex_url_rejected(self):
        """Test that Webex URLs are rejected"""
        webex_urls = [
            "https://example.webex.com/example/j.php?MTID=abc123",
            "https://webex.com/example/j.php?MTID=abc123",
        ]
        for url in webex_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"Webex URL should be rejected: {url}"
            assert url_error is not None
            assert "webex" in url_error.lower() or "not supported" in url_error.lower()
    
    def test_gotomeeting_url_rejected(self):
        """Test that GoToMeeting URLs are rejected"""
        gotomeeting_urls = [
            "https://global.gotomeeting.com/join/123456789",
            "https://gotomeeting.com/join/123456789",
        ]
        for url in gotomeeting_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"GoToMeeting URL should be rejected: {url}"
            assert url_error is not None
            assert "gotomeeting" in url_error.lower() or "not supported" in url_error.lower()
    
    def test_skype_url_rejected(self):
        """Test that Skype URLs are rejected"""
        skype_urls = [
            "https://join.skype.com/abc123",
            "https://skype.com/join/abc123",
        ]
        for url in skype_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"Skype URL should be rejected: {url}"
            assert url_error is not None
            assert "skype" in url_error.lower() or "not supported" in url_error.lower()
    
    def test_other_platforms_rejected(self):
        """Test that other meeting platforms are rejected"""
        other_platforms = [
            ("https://whereby.com/room123", "whereby"),
            ("https://meet.jit.si/room123", "jitsi"),
            ("https://jitsi.org/room123", "jitsi"),
            ("https://bigbluebutton.example.com/room123", "bigbluebutton"),
            ("https://ringcentral.com/join/123456", "ringcentral"),
        ]
        for url, platform_name in other_platforms:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"{platform_name} URL should be rejected: {url}"
            assert url_error is not None
            # Some platforms may not be in the rejected list, but should still be rejected
            # with either platform-specific error or generic Teams-only error
            assert (
                platform_name.lower() in url_error.lower() 
                or "not supported" in url_error.lower()
                or "only microsoft teams" in url_error.lower()
            )
    
    def test_invalid_teams_url_format(self):
        """Test invalid Teams URL format"""
        invalid_urls = [
            "https://microsoft.com/not-a-meeting",
            "https://example.com/meeting",
            "not-a-url",
            "ftp://teams.microsoft.com/meeting",  # Invalid protocol
        ]
        for url in invalid_urls:
            is_valid, url_error = validate_teams_url_only(url)
            assert is_valid is False, f"Invalid URL should be rejected: {url}"
            assert url_error is not None
            # Should either mention protocol or Teams format
            assert (
                "protocol" in url_error.lower() 
                or "http" in url_error.lower()
                or "teams" in url_error.lower()
            )
    
    def test_case_insensitive_validation(self):
        """Test that validation is case-insensitive"""
        # Valid Teams URL in different cases
        valid_urls = [
            "https://TEAMS.MICROSOFT.COM/l/meetup-join/19:meeting_abc123",
            "https://Teams.Microsoft.com/l/meetup-join/19:meeting_abc123",
            "https://teams.microsoft.com/L/MEETUP-JOIN/19:meeting_abc123",
        ]
        for url in valid_urls:
            is_valid, error = validate_teams_url_only(url)
            assert is_valid is True, f"URL should be valid (case-insensitive): {url}"
        
        # Rejected platforms in different cases
        rejected_urls = [
            "https://ZOOM.US/j/123456789",
            "https://Zoom.Us/j/123456789",
            "https://MEET.GOOGLE.COM/abc-defg-hij",
            "https://Meet.Google.Com/abc-defg-hij",
        ]
        for url in rejected_urls:
            is_valid, error = validate_teams_url_only(url)
            assert is_valid is False, f"URL should be rejected (case-insensitive): {url}"


class TestTeamsURLValidationAPI:
    """Test Teams URL validation through API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create a test client"""
        return TestClient(app)
    
    def test_process_teams_url_rejects_zoom(self, client):
        """Test that /process-teams-url endpoint rejects Zoom URLs"""
        response = client.post(
            "/api/transcripts/process-teams-url",
            data={
                "teams_url": "https://zoom.us/j/123456789",
                "project_name": "TestProject",
            },
        )
        assert response.status_code == 400
        assert "zoom" in response.json()["detail"].lower() or "not supported" in response.json()["detail"].lower()
    
    def test_process_teams_url_rejects_google_meet(self, client):
        """Test that /process-teams-url endpoint rejects Google Meet URLs"""
        response = client.post(
            "/api/transcripts/process-teams-url",
            data={
                "teams_url": "https://meet.google.com/abc-defg-hij",
                "project_name": "TestProject",
            },
        )
        assert response.status_code == 400
        assert "google meet" in response.json()["detail"].lower() or "not supported" in response.json()["detail"].lower()
    
    def test_process_sharepoint_url_rejects_zoom(self, client):
        """Test that /process-sharepoint-url endpoint rejects Zoom URLs"""
        response = client.post(
            "/api/transcripts/process-sharepoint-url",
            data={
                "teams_url": "https://zoom.us/j/123456789",
                "project_name": "TestProject",
            },
        )
        assert response.status_code == 400
        assert "zoom" in response.json()["detail"].lower() or "not supported" in response.json()["detail"].lower()
    
    def test_process_sharepoint_url_rejects_google_meet(self, client):
        """Test that /process-sharepoint-url endpoint rejects Google Meet URLs"""
        response = client.post(
            "/api/transcripts/process-sharepoint-url",
            data={
                "teams_url": "https://meet.google.com/abc-defg-hij",
                "project_name": "TestProject",
            },
        )
        assert response.status_code == 400
        assert "google meet" in response.json()["detail"].lower() or "not supported" in response.json()["detail"].lower()
    
    def test_process_sharepoint_url_rejects_empty_url(self, client):
        """Test that /process-sharepoint-url endpoint rejects empty URLs"""
        response = client.post(
            "/api/transcripts/process-sharepoint-url",
            data={
                "teams_url": "",
                "project_name": "TestProject",
            },
        )
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()


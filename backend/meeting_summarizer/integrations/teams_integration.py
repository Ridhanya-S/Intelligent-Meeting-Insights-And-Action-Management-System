"""
Microsoft Teams Integration Module

Fetches meeting details from Teams meeting URLs using Microsoft Graph API
with OnlineMeeting.Read permission.
"""
import re
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from backend.meeting_summarizer.config import Config


class TeamsIntegration:
    """
    Integration with Microsoft Teams to fetch meeting details from URLs.
    
    Uses Microsoft Graph API with OnlineMeeting.Read permission to retrieve
    meeting information including participants, start/end times, and recordings.
    """
    
    def __init__(self):
        """Initialize Teams integration with Graph API credentials."""
        self.tenant_id = Config.MS_GRAPH_TENANT_ID
        self.client_id = Config.MS_GRAPH_CLIENT_ID
        self.client_secret = Config.MS_GRAPH_CLIENT_SECRET
        self.api_base = Config.MS_GRAPH_API_BASE
        self._access_token: Optional[str] = None
    
    def _get_access_token(self) -> str:
        """
        Get Microsoft Graph API access token using client credentials flow.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If authentication fails
        """
        if self._access_token:
            # Token is cached, return it
            # Note: In production, implement token refresh logic
            return self._access_token
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Microsoft Graph API credentials not configured. "
                "Set MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, and MS_GRAPH_CLIENT_SECRET"
            )
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/.default",
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            response = httpx.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data.get("access_token")
            
            if not self._access_token:
                raise ValueError("Failed to obtain access token from Microsoft Graph API")
            
            return self._access_token
            
        except httpx.HTTPStatusError as e:
            raise Exception(f"Failed to authenticate with Microsoft Graph API: {e.response.text}")
        except Exception as e:
            raise Exception(f"Error getting access token: {str(e)}")
    
    def _extract_meeting_id_from_url(self, meeting_url: str) -> Optional[str]:
        """
        Extract meeting ID from Teams meeting URL.
        
        Teams URLs can be in various formats:
        - https://teams.microsoft.com/l/meetup-join/...
        - https://teams.microsoft.com/l/meeting/...
        - https://teams.microsoft.com/_#/meeting/...
        
        Args:
            meeting_url: Teams meeting URL
            
        Returns:
            Meeting ID (threadId or meetingId) if found, None otherwise
        """
        # Try to extract from URL path
        parsed = urlparse(meeting_url)
        
        # Pattern 1: /l/meetup-join/{threadId}/{organizerId}/{tenantId}
        match = re.search(r'/l/meetup-join/([^/]+)', parsed.path)
        if match:
            return match.group(1)
        
        # Pattern 2: /l/meeting/{threadId}/{organizerId}/{tenantId}
        match = re.search(r'/l/meeting/([^/]+)', parsed.path)
        if match:
            return match.group(1)
        
        # Pattern 3: /_#/meeting/{threadId}
        match = re.search(r'/_#/meeting/([^/?]+)', parsed.path)
        if match:
            return match.group(1)
        
        # Pattern 4: Check query parameters
        query_params = parse_qs(parsed.query)
        if 'threadId' in query_params:
            return query_params['threadId'][0]
        if 'meetingId' in query_params:
            return query_params['meetingId'][0]
        
        return None
    
    def _get_meeting_by_thread_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get meeting details by thread ID using Graph API.
        
        Args:
            thread_id: Teams meeting thread ID
            
        Returns:
            Meeting details dictionary or None if not found
        """
        access_token = self._get_access_token()
        
        # Try to get online meeting by thread ID
        # Note: This requires OnlineMeeting.Read permission
        url = f"{self.api_base}/me/onlineMeetings"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Filter by threadId
        params = {
            "$filter": f"ThreadId eq '{thread_id}'",
            "$top": 1
        }
        
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=30.0)
            
            if response.status_code == 404:
                # Try alternative endpoint: get by joinWebUrl
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("value") and len(data["value"]) > 0:
                return data["value"][0]
            
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise Exception(f"Failed to fetch meeting from Graph API: {e.response.text}")
        except Exception as e:
            raise Exception(f"Error fetching meeting details: {str(e)}")
    
    def _get_meeting_by_join_url(self, meeting_url: str) -> Optional[Dict[str, Any]]:
        """
        Get meeting details by join URL using Graph API.
        
        Args:
            meeting_url: Teams meeting join URL
            
        Returns:
            Meeting details dictionary or None if not found
        """
        access_token = self._get_access_token()
        
        # Use the joinWebUrl to get meeting details
        url = f"{self.api_base}/me/onlineMeetings"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Filter by joinWebUrl
        params = {
            "$filter": f"joinWebUrl eq '{meeting_url}'",
            "$top": 1
        }
        
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=30.0)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("value") and len(data["value"]) > 0:
                return data["value"][0]
            
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise Exception(f"Failed to fetch meeting from Graph API: {e.response.text}")
        except Exception as e:
            raise Exception(f"Error fetching meeting details: {str(e)}")
    
    def get_meeting_details(self, meeting_url: str) -> Dict[str, Any]:
        """
        Get all details of a Teams meeting from its URL.
        
        Uses Microsoft Graph API with OnlineMeeting.Read permission to fetch:
        - Meeting subject/title
        - Start and end times
        - Participants
        - Organizer
        - Join URL
        - Recording information (if available)
        
        Args:
            meeting_url: Teams meeting URL
            
        Returns:
            Dictionary containing meeting details:
            {
                "subject": str,
                "startDateTime": datetime,
                "endDateTime": datetime,
                "participants": List[str],
                "organizer": Dict[str, str],
                "joinWebUrl": str,
                "threadId": str,
                "meetingId": str,
                "recording": Optional[Dict]  # If recording is available
            }
            
        Raises:
            ValueError: If meeting URL is invalid or meeting not found
            Exception: If API call fails
        """
        if not meeting_url or not meeting_url.strip():
            raise ValueError("Meeting URL is required")
        
        meeting_url = meeting_url.strip()
        
        # Try to get meeting by join URL first
        meeting_data = self._get_meeting_by_join_url(meeting_url)
        
        # If not found, try extracting thread ID and searching
        if not meeting_data:
            thread_id = self._extract_meeting_id_from_url(meeting_url)
            if thread_id:
                meeting_data = self._get_meeting_by_thread_id(thread_id)
        
        if not meeting_data:
            raise ValueError(
                f"Meeting not found for URL: {meeting_url}. "
                "Ensure the meeting exists and you have OnlineMeeting.Read permission."
            )
        
        # Extract participants
        participants = []
        if "participants" in meeting_data:
            for participant in meeting_data["participants"]:
                identity = participant.get("identity", {})
                user_info = identity.get("user", {})
                display_name = user_info.get("displayName") or identity.get("displayName", "Unknown")
                participants.append(display_name)
        
        # Extract organizer
        organizer = {}
        if "organizer" in meeting_data:
            org_identity = meeting_data["organizer"].get("identity", {})
            org_user = org_identity.get("user", {})
            organizer = {
                "displayName": org_user.get("displayName") or org_identity.get("displayName", "Unknown"),
                "email": org_user.get("id", "")
            }
        
        # Parse datetime strings
        start_datetime = None
        end_datetime = None
        
        if "startDateTime" in meeting_data:
            try:
                start_datetime = datetime.fromisoformat(
                    meeting_data["startDateTime"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        
        if "endDateTime" in meeting_data:
            try:
                end_datetime = datetime.fromisoformat(
                    meeting_data["endDateTime"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        
        # Get recording if available
        recording = None
        if "recordings" in meeting_data and meeting_data["recordings"]:
            recording = meeting_data["recordings"][0]  # Get first recording
        
        return {
            "subject": meeting_data.get("subject", "Untitled Meeting"),
            "startDateTime": start_datetime,
            "endDateTime": end_datetime,
            "participants": participants,
            "organizer": organizer,
            "joinWebUrl": meeting_data.get("joinWebUrl", meeting_url),
            "threadId": meeting_data.get("threadId", ""),
            "meetingId": meeting_data.get("id", ""),
            "recording": recording,
            "raw_data": meeting_data  # Include full response for debugging
        }
    
    def is_valid_teams_url(self, url: str) -> bool:
        """
        Check if a URL is a valid Teams meeting URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears to be a Teams meeting URL
        """
        if not url:
            return False
        
        url_lower = url.lower()
        return (
            "teams.microsoft.com" in url_lower or
            "microsoft.com/l/" in url_lower or
            "/meeting/" in url_lower or
            "/meetup-join/" in url_lower
        )


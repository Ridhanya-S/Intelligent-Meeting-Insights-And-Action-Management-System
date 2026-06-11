"""
Security utilities for input validation and sanitization
"""
import re
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# File size limits (in bytes)
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MAX_TEXT_FILE_SIZE = 10 * 1024 * 1024  # 10MB for text files

# Allowed file extensions
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}
ALLOWED_TEXT_EXTENSIONS = {'.txt', '.md', '.transcript', '.docx', '.doc'}
ALLOWED_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_TEXT_EXTENSIONS

# Project name validation
PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_PROJECT_NAME_LENGTH = 100
MAX_MEETING_TITLE_LENGTH = 200
MAX_PARTICIPANT_NAME_LENGTH = 100


def validate_file_upload(file: any, content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate uploaded file.
    
    Returns:
        (is_valid, error_message)
    """
    # Check file size
    file_size = len(content)
    
    # Determine max size based on file type
    file_ext = Path(file.filename).suffix.lower() if file.filename else ''
    max_size = MAX_TEXT_FILE_SIZE if file_ext in ALLOWED_TEXT_EXTENSIONS else MAX_FILE_SIZE
    
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"File too large. Maximum size: {max_mb:.0f}MB"
    
    if file_size == 0:
        return False, "File is empty"
    
    # Check file extension
    if file.filename:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    
    # Check for suspicious file names
    if file.filename:
        filename = Path(file.filename).name
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, "Invalid filename"
    
    return True, None


def sanitize_project_name(project_name: str) -> str:
    """Sanitize and validate project name"""
    if not project_name or not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    
    project_name = project_name.strip()
    
    if len(project_name) > MAX_PROJECT_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Project name too long. Maximum {MAX_PROJECT_NAME_LENGTH} characters"
        )
    
    if not PROJECT_NAME_PATTERN.match(project_name):
        raise HTTPException(
            status_code=400,
            detail="Project name can only contain letters, numbers, underscores, and hyphens"
        )
    
    return project_name


def sanitize_meeting_title(title: Optional[str]) -> Optional[str]:
    """Sanitize meeting title"""
    if not title:
        return None
    
    title = title.strip()
    
    if len(title) > MAX_MEETING_TITLE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Meeting title too long. Maximum {MAX_MEETING_TITLE_LENGTH} characters"
        )
    
    # Remove potentially dangerous characters
    title = re.sub(r'[<>"\']', '', title)
    
    return title if title else None


def sanitize_participants(participants: Optional[str]) -> list[str]:
    """Sanitize and validate participants list"""
    if not participants:
        return []
    
    try:
        import json
        participant_list = json.loads(participants)
        if not isinstance(participant_list, list):
            raise ValueError("Participants must be a list")
    except (json.JSONDecodeError, ValueError):
        # Try comma-separated
        participant_list = [p.strip() for p in participants.split(",") if p.strip()]
    except Exception:
        # Fallback: empty list on any other error
        participant_list = []
    
    # Validate and sanitize each participant name
    sanitized = []
    for participant in participant_list:
        if not isinstance(participant, str):
            continue
        
        participant = participant.strip()
        if not participant:
            continue
        
        if len(participant) > MAX_PARTICIPANT_NAME_LENGTH:
            continue  # Skip invalid names
        
        # Remove potentially dangerous characters
        participant = re.sub(r'[<>"\']', '', participant)
        if participant:
            sanitized.append(participant)
    
    return sanitized[:50]  # Limit to 50 participants


def validate_file_path(file_path: str) -> bool:
    """Validate file path to prevent path traversal attacks"""
    try:
        Path(file_path).resolve()
        # Ensure the path doesn't escape the data directory
        # This is a basic check - adjust based on your needs
        return True
    except (ValueError, OSError):
        return False


def validate_teams_url_only(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a URL is a Teams meeting URL and reject other platforms.
    
    This function explicitly checks for Teams URLs and rejects:
    - Zoom URLs (zoom.us, zoom.com)
    - Google Meet URLs (meet.google.com)
    - Other meeting platforms
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if URL is a valid Teams URL, False otherwise
        - error_message: Error message if URL is invalid, None if valid
    """
    if not url or not url.strip():
        return False, "Teams meeting URL is required"
    
    url = url.strip().lower()
    
    # Check for valid protocol (http or https)
    if not url.startswith(("http://", "https://")):
        return False, "Invalid URL format. URL must start with http:// or https://"
    
    # List of non-Teams meeting platform patterns to reject
    rejected_platforms = [
        ("zoom.us", "Zoom"),
        ("zoom.com", "Zoom"),
        ("meet.google.com", "Google Meet"),
        ("meet.google", "Google Meet"),
        ("webex.com", "Webex"),
        ("gotomeeting.com", "GoToMeeting"),
        ("gotomeet", "GoToMeeting"),
        ("bluejeans.com", "BlueJeans"),
        ("bluejeans", "BlueJeans"),
        ("join.skype.com", "Skype"),
        ("skype.com", "Skype"),
        ("whereby.com", "Whereby"),
        ("jitsi.org", "Jitsi"),
        ("jitsi", "Jitsi"),
        ("bigbluebutton", "BigBlueButton"),
        ("ringcentral.com", "RingCentral"),
        ("ringcentral", "RingCentral"),
    ]
    
    # Check for rejected platforms first
    for pattern, platform_name in rejected_platforms:
        if pattern in url:
            return False, f"Only Microsoft Teams URLs are allowed. {platform_name} URLs are not supported."
    
    # Check for Teams URL patterns
    teams_patterns = [
        "teams.microsoft.com",
        "microsoft.com/l/",
        "/meetup-join/",
        "/meeting/",
    ]
    
    # At least one Teams pattern must be present
    has_teams_pattern = any(pattern in url for pattern in teams_patterns)
    
    if not has_teams_pattern:
        return False, (
            "Invalid Teams meeting URL format. "
            "URL must contain 'teams.microsoft.com' or 'microsoft.com/l/' or '/meetup-join/' or '/meeting/'. "
            "Only Microsoft Teams URLs are allowed."
        )
    
    # Additional validation: Check for /meetup-join/ pattern (most common Teams format)
    if "/meetup-join/" in url:
        try:
            parts = url.split("/meetup-join/")
            if len(parts) < 2:
                return False, "Invalid Teams meeting URL format. Could not extract meeting ID"
            
            meeting_id_part = parts[1].split("/")[0].split("?")[0]
            if not meeting_id_part or len(meeting_id_part) < 10:
                return False, "Invalid Teams meeting URL format. Meeting ID appears to be missing or invalid"
        except Exception as e:
            return False, f"Invalid Teams meeting URL format: {str(e)}"
    
    return True, None


# ============================================================================
# Bearer Token Authentication
# ============================================================================

security_scheme = HTTPBearer(auto_error=False)


async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> None:
    """
    Verify bearer token for API authentication.
    
    This function is used as a dependency for endpoints that require authentication.
    If API_BEARER_TOKEN is not configured, authentication is disabled (for development).
    
    Args:
        credentials: HTTP Authorization credentials from the request header
        
    Raises:
        HTTPException: If authentication fails
    """
    from backend.meeting_summarizer.config import Config
    
    # If no bearer token is configured, allow access (development mode)
    if not Config.API_BEARER_TOKEN:
        return
    
    # If credentials are not provided, raise 401
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify the token matches the configured token
    if credentials.credentials != Config.API_BEARER_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Invalid bearer token. Access denied.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency that can be used in route decorators
BearerTokenAuth = Depends(verify_bearer_token)


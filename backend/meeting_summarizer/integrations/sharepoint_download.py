"""
SharePoint Recording Download Integration
Downloads Teams meeting recordings and transcripts from SharePoint/OneDrive
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import unquote, parse_qs, urlparse
import json
import requests
import subprocess

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.config import Config
import tempfile


class SharePointDownloader:
    """Download Teams recordings and transcripts from SharePoint/OneDrive"""
    
    def __init__(self, tenant_id: Optional[str] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """Initialize SharePoint downloader with credentials"""
        # Allow override from parameters or use config
        self.tenant_id = tenant_id or Config.MS_GRAPH_TENANT_ID
        self.client_id = client_id or Config.MS_GRAPH_CLIENT_ID
        self.client_secret = client_secret or Config.MS_GRAPH_CLIENT_SECRET
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Microsoft credentials not configured.")
    
    def get_app_token(self) -> str:
        """Get app-only access token."""
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        r = requests.post(url, data=data, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]
    
    def validate_teams_url(self, join_url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Teams meeting URL format.
        
        Returns:
            (is_valid, error_message)
        """
        if not join_url or not join_url.strip():
            return False, "Teams meeting URL is required"
        
        join_url = join_url.strip()
        
        # Check if it's a Teams URL
        if 'teams.microsoft.com' not in join_url and 'microsoft.com/l/' not in join_url:
            return False, "Invalid Teams meeting URL format. URL must contain 'teams.microsoft.com' or 'microsoft.com/l/'"
        
        # Check if it contains meetup-join
        if '/meetup-join/' not in join_url:
            return False, "Invalid Teams meeting URL format. URL must contain '/meetup-join/'"
        
        # Try to extract meeting ID to validate format
        try:
            parts = join_url.split('/meetup-join/')
            if len(parts) < 2:
                return False, "Invalid Teams meeting URL format. Could not extract meeting ID"
            
            meeting_id_part = parts[1].split('/')[0]
            if not meeting_id_part or len(meeting_id_part) < 10:
                return False, "Invalid Teams meeting URL format. Meeting ID appears to be missing or invalid"
            
            # Check if it looks like a valid meeting ID (should contain 'meeting_' or similar)
            if 'meeting_' not in meeting_id_part.lower():
                return False, "Invalid Teams meeting URL format. Meeting ID format is incorrect"
        except Exception as e:
            return False, f"Invalid Teams meeting URL format: {str(e)}"
        
        return True, None
    
    def extract_meeting_id_from_url(self, join_url: str) -> str:
        """Extract meeting ID from Teams join URL."""
        try:
            return unquote(join_url.split('/meetup-join/')[1].split('/')[0])
        except (IndexError, AttributeError) as e:
            raise ValueError(f"Could not extract meeting ID from URL: {str(e)}")
    
    def extract_user_object_id_from_url(self, join_url: str) -> str:
        """Extract user object ID from Teams join URL."""
        try:
            parsed = urlparse(join_url)
            params = parse_qs(parsed.query)
            if 'context' in params:
                context_str = unquote(params['context'][0])
                context_json = json.loads(context_str)
                oid = context_json.get('Oid', '')
                if not oid:
                    raise ValueError("User object ID (Oid) not found in URL context")
                return oid
            return ''
        except (KeyError, json.JSONDecodeError, AttributeError) as e:
            raise ValueError(f"Could not extract user object ID from URL: {str(e)}")
    
    def format_datetime_for_filename(self, datetime_str: str) -> str:
        """Format datetime string for use in filename."""
        if not datetime_str:
            return datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return dt.strftime("%Y%m%d_%H%M%S")
        except Exception:
            return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string to datetime object."""
        if not datetime_str:
            return datetime.min
        
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.min
    
    def is_recording_related_to_meeting(
        self, 
        file_name: str, 
        file_metadata: Optional[dict] = None, 
        meeting_id: Optional[str] = None, 
        meeting_title: Optional[str] = None
    ) -> bool:
        """Check if a recording file is related to a specific meeting."""
        file_name_lower = file_name.lower()
        
        # Strategy 1: Match by meeting title (if provided)
        if meeting_title:
            title_lower = meeting_title.lower().strip()
            title_words = [w for w in title_lower.split() if len(w) > 3]
            
            if title_words:
                matching_words = sum(1 for word in title_words if word in file_name_lower)
                if matching_words >= min(2, len(title_words)):
                    return True
            
            if len(title_lower) > 10:
                if title_lower[:20] in file_name_lower or title_lower[-20:] in file_name_lower:
                    return True
            elif title_lower in file_name_lower:
                return True
        
        # Strategy 2: Match by meeting ID (if provided)
        if meeting_id:
            meeting_id_lower = meeting_id.lower()
            guid_part = None
            if '_' in meeting_id:
                guid_part = meeting_id.split('_')[-1].split('@')[0]
            
            if meeting_id_lower in file_name_lower:
                return True
            
            if guid_part:
                guid_lower = guid_part.lower()
                if guid_lower in file_name_lower:
                    return True
                if len(guid_lower) >= 20:
                    if guid_lower[:20] in file_name_lower or guid_lower[-20:] in file_name_lower:
                        return True
        
        return False
    
    def search_recordings_for_meeting(
        self, 
        token: str, 
        user_id: str, 
        meeting_id: Optional[str] = None, 
        meeting_title: Optional[str] = None
    ) -> List[Dict]:
        """Search for recordings for a specific meeting in SharePoint/OneDrive."""
        found_recordings = []
        
        # Extract GUID from meeting ID for searching (if provided)
        guid_part = None
        if meeting_id and '_' in meeting_id:
            guid_part = meeting_id.split('_')[-1].split('@')[0]
        
        # Extract searchable parts for initial filtering
        search_terms = []
        if guid_part:
            search_terms.append(guid_part)
            search_terms.append(guid_part[:20])
            search_terms.append(guid_part[-20:])
        
        if meeting_title:
            title_words = [w for w in meeting_title.lower().split() if len(w) > 3]
            search_terms.extend(title_words[:5])
        
        # Try to find recordings in user's OneDrive
        if user_id:
            try:
                endpoint = f"https://graph.microsoft.com/v1.0/users/{user_id}/drive/root:/Recordings:/children"
                headers = {"Authorization": f"Bearer {token}"}
                r = requests.get(endpoint, headers=headers, timeout=30)
                
                if r.status_code == 200:
                    files = r.json().get("value", [])
                    
                    for f in files:
                        file_name = f.get('name', '')
                        file_id = f.get('id', '')
                        modified_date = f.get('lastModifiedDateTime', '')
                        
                        # Only include video files
                        if not any(ext in file_name.lower() for ext in ['.mp4', '.m4v', '.mov', '.avi', '.mkv', '.webm']):
                            continue
                        
                        # Check if this file is related to our specific meeting
                        # If meeting_title is None, include all recordings (no title filter)
                        if meeting_title is None or self.is_recording_related_to_meeting(file_name, f, meeting_id, meeting_title):
                            parent_ref = f.get('parentReference', {})
                            drive_id = parent_ref.get('driveId', '')
                            item_id = file_id
                            
                            found_recordings.append({
                                'name': f.get('name', 'N/A'),
                                'id': f"{drive_id}!{item_id}" if drive_id else item_id,
                                'drive_id': drive_id,
                                'item_id': item_id,
                                'download_url': f.get('@microsoft.graph.downloadUrl', ''),
                                'modified': modified_date,
                                'size': f.get('size', 0),
                                'source': 'OneDrive'
                            })
            except Exception as e:
                pass
        
        # Try searching in SharePoint sites
        try:
            endpoint = "https://graph.microsoft.com/v1.0/sites?search=Meeting Recordings"
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.get(endpoint, headers=headers, timeout=30)
            
            if r.status_code == 200:
                sites = r.json().get("value", [])
                
                for site in sites[:5]:  # Limit to first 5 sites
                    site_id = site.get('id', '')
                    site_name = site.get('displayName', 'Unknown')
                    
                    try:
                        drives_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
                        drives_r = requests.get(drives_endpoint, headers=headers, timeout=30)
                        
                        if drives_r.status_code == 200:
                            drives = drives_r.json().get("value", [])
                            for drive in drives:
                                drive_id = drive.get("id", "")
                                
                                if meeting_id:
                                    search_endpoint = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='{meeting_id[:20]}')"
                                    search_r = requests.get(search_endpoint, headers=headers, timeout=30)
                                    
                                    if search_r.status_code == 200:
                                        results = search_r.json().get("value", [])
                                        for result in results:
                                            file_name = result.get('name', '')
                                            
                                            if not any(ext in file_name.lower() for ext in ['.mp4', '.m4v', '.mov', '.avi', '.mkv', '.webm']):
                                                continue
                                            
                                            # If meeting_title is None, include all recordings (no title filter)
                                            if meeting_title is None or self.is_recording_related_to_meeting(file_name, result, meeting_id, meeting_title):
                                                file_id = result.get('id', '')
                                                parent_ref = result.get('parentReference', {})
                                                drive_id_result = parent_ref.get('driveId', '')
                                                item_id = file_id
                                                
                                                found_recordings.append({
                                                    'name': file_name,
                                                    'id': f"{drive_id_result}!{item_id}" if drive_id_result else item_id,
                                                    'drive_id': drive_id_result,
                                                    'item_id': item_id,
                                                    'download_url': result.get('@microsoft.graph.downloadUrl', ''),
                                                    'modified': result.get('lastModifiedDateTime', ''),
                                                    'size': result.get('size', 0),
                                                    'source': f'SharePoint: {site_name}'
                                                })
                    except Exception:
                        continue
        except Exception:
            pass
        
        return found_recordings
    
    def search_transcripts_for_meeting(
        self, 
        token: str, 
        user_id: str, 
        meeting_id: Optional[str] = None, 
        meeting_title: Optional[str] = None
    ) -> List[Dict]:
        """Search for transcripts for a specific meeting."""
        found_transcripts = []
        transcript_extensions = ['.vtt', '.txt', '.srt', '.transcript', '.json']
        
        # Try to find transcripts in user's OneDrive
        if user_id:
            try:
                endpoint = f"https://graph.microsoft.com/v1.0/users/{user_id}/drive/root:/Recordings:/children"
                headers = {"Authorization": f"Bearer {token}"}
                r = requests.get(endpoint, headers=headers, timeout=30)
                
                if r.status_code == 200:
                    files = r.json().get("value", [])
                    
                    for f in files:
                        file_name = f.get('name', '')
                        file_id = f.get('id', '')
                        modified_date = f.get('lastModifiedDateTime', '')
                        
                        if any(ext in file_name.lower() for ext in transcript_extensions):
                            if self.is_recording_related_to_meeting(file_name, f, meeting_id, meeting_title):
                                parent_ref = f.get('parentReference', {})
                                drive_id = parent_ref.get('driveId', '')
                                item_id = file_id
                                
                                found_transcripts.append({
                                    'name': file_name,
                                    'id': f"{drive_id}!{item_id}" if drive_id else item_id,
                                    'drive_id': drive_id,
                                    'item_id': item_id,
                                    'download_url': f.get('@microsoft.graph.downloadUrl', ''),
                                    'modified': modified_date,
                                    'size': f.get('size', 0),
                                    'source': 'OneDrive'
                                })
            except Exception:
                pass
        
        return found_transcripts
    
    def download_file(
        self, 
        token: str, 
        file_id: str, 
        file_path: Path, 
        drive_id: str = None, 
        download_url: str = None
    ) -> Optional[Path]:
        """Download a file from SharePoint/OneDrive."""
        headers = {"Authorization": f"Bearer {token}"}
        
        # Parse file ID
        if '!' in file_id:
            parts = file_id.split('!')
            parsed_drive_id = parts[0]
            parsed_item_id = parts[1]
        else:
            parsed_drive_id = drive_id
            parsed_item_id = file_id
        
        # Method 1: Graph API content endpoint
        if parsed_drive_id and parsed_item_id:
            try:
                content_endpoint = f"https://graph.microsoft.com/v1.0/drives/{parsed_drive_id}/items/{parsed_item_id}/content"
                response = requests.get(content_endpoint, headers=headers, stream=True, timeout=300)
                
                if response.status_code == 200:
                    return self._save_file(response, file_path)
            except Exception:
                pass
        
        # Method 2: Get fresh download URL from metadata
        try:
            if parsed_drive_id and parsed_item_id:
                metadata_endpoint = f"https://graph.microsoft.com/v1.0/drives/{parsed_drive_id}/items/{parsed_item_id}"
            else:
                metadata_endpoint = f"https://graph.microsoft.com/v1.0/me/drive/items/{parsed_item_id}"
            
            meta_response = requests.get(metadata_endpoint, headers=headers, timeout=30)
            if meta_response.status_code == 200:
                metadata = meta_response.json()
                fresh_download_url = metadata.get('@microsoft.graph.downloadUrl', '')
                
                if fresh_download_url:
                    response = requests.get(fresh_download_url, stream=True, timeout=300, allow_redirects=True)
                    if response.status_code == 200:
                        return self._save_file(response, file_path)
        except Exception:
            pass
        
        # Method 3: Use provided download URL
        if download_url:
            try:
                response = requests.get(download_url, headers=headers, stream=True, timeout=300, allow_redirects=True)
                if response.status_code == 200:
                    return self._save_file(response, file_path)
                
                # Try without auth header
                response = requests.get(download_url, stream=True, timeout=300, allow_redirects=True)
                if response.status_code == 200:
                    return self._save_file(response, file_path)
            except Exception:
                pass
        
        return None
    
    def _save_file(self, response: requests.Response, file_path: Path) -> Path:
        """Helper function to save downloaded file."""
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"  ⬇️  Downloading: {percent:.1f}%", end='\r')
        
        if downloaded == 0:
            if file_path.exists():
                file_path.unlink()
            return None
        
        return file_path
    
    def get_latest_recording(self, recordings: List[Dict]) -> List[Dict]:
        """Get the latest recording based on modified date."""
        if not recordings:
            return []
        
        sorted_recordings = sorted(
            recordings,
            key=lambda x: self.parse_datetime(x.get('modified', '')),
            reverse=True
        )
        
        return [sorted_recordings[0]]
    
    def download_recordings_and_transcripts(
        self,
        join_url: str,
        meeting_title: Optional[str] = None,
        output_dir: Optional[Path] = None,
        prefer_transcript: bool = True  # noqa: ARG002
    ) -> Tuple[List[Path], List[Path]]:
        """
        Download recordings and transcripts for a Teams meeting.
        
        Args:
            join_url: Teams meeting join URL
            meeting_title: Optional meeting title for filtering
            output_dir: Directory to save files (default: temp directory)
            prefer_transcript: If True, prefer transcript over recording
        
        Returns:
            Tuple of (recording_paths, transcript_paths)
        """
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp())
        else:
            output_dir.mkdir(exist_ok=True)
        
        # Extract meeting info
        meeting_id = self.extract_meeting_id_from_url(join_url)
        user_id = self.extract_user_object_id_from_url(join_url)
        
        # Get access token
        token = self.get_app_token()
        
        # Search for recordings
        recordings = self.search_recordings_for_meeting(token, user_id, meeting_id, meeting_title)
        
        # Search for transcripts
        transcripts = self.search_transcripts_for_meeting(token, user_id, meeting_id, meeting_title)
        
        # Filter: if multiple recordings, get latest
        if len(recordings) > 1:
            recordings = self.get_latest_recording(recordings)
        
        downloaded_recordings = []
        downloaded_transcripts = []
        
        # Download recordings
        for rec in recordings:
            file_id = rec.get('id', '')
            drive_id = rec.get('drive_id', '')
            modified_date = rec.get('modified', '')
            
            datetime_str = self.format_datetime_for_filename(modified_date)
            file_path = output_dir / f"recording_{datetime_str}.mp4"
            
            # Check if already exists
            if file_path.exists():
                downloaded_recordings.append(file_path)
                continue
            
            saved_path = self.download_file(token, file_id, file_path, drive_id, rec.get('download_url', ''))
            if saved_path:
                downloaded_recordings.append(saved_path)
        
        # Download transcripts
        for trans in transcripts:
            file_id = trans.get('id', '')
            drive_id = trans.get('drive_id', '')
            modified_date = trans.get('modified', '')
            file_name = trans.get('name', 'transcript')
            
            # Determine extension
            ext = '.txt'
            if '.' in file_name:
                ext = '.' + file_name.split('.')[-1].lower()
                if ext not in ['.vtt', '.txt', '.srt', '.transcript', '.json']:
                    ext = '.txt'
            
            datetime_str = self.format_datetime_for_filename(modified_date)
            file_path = output_dir / f"transcript_{datetime_str}{ext}"
            
            # Check if already exists
            if file_path.exists():
                downloaded_transcripts.append(file_path)
                continue
            
            saved_path = self.download_file(token, file_id, file_path, drive_id, trans.get('download_url', ''))
            if saved_path:
                downloaded_transcripts.append(saved_path)
        
        return downloaded_recordings, downloaded_transcripts
    
    def get_video_duration(self, video_path: Path) -> Optional[float]:
        """
        Get video duration in seconds using ffprobe.
        
        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            # Try using ffprobe (from ffmpeg)
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return duration
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, subprocess.SubprocessError):
            pass
        
        # Fallback: estimate from file size (rough approximation)
        # Average bitrate assumption: ~1MB per minute for compressed video
        try:
            file_size_mb = video_path.stat().st_size / (1024 * 1024)
            # Rough estimate: 1MB ≈ 1 minute for typical meeting recordings
            estimated_duration = file_size_mb * 60
            return estimated_duration
        except Exception:
            pass
        
        return None
    
    def validate_recording_duration(self, recording_path: Path, min_duration_seconds: float = 10.0) -> Tuple[bool, Optional[str]]:
        """
        Validate that recording is long enough to be useful.
        
        Args:
            recording_path: Path to the recording file
            min_duration_seconds: Minimum duration in seconds (default: 10)
        
        Returns:
            (is_valid, error_message)
        """
        if not recording_path.exists():
            return False, f"Recording file not found: {recording_path}"
        
        # Check file size first (quick check)
        file_size = recording_path.stat().st_size
        if file_size < 1024:  # Less than 1KB is suspicious
            return False, f"Recording file is too small ({file_size} bytes). File may be corrupted or empty."
        
        # Get actual duration
        duration = self.get_video_duration(recording_path)
        
        if duration is None:
            # If we can't determine duration, check file size as fallback
            # Very small files (< 100KB) are likely too short
            if file_size < 100 * 1024:
                return False, "Recording file appears to be too short or corrupted. Unable to verify duration."
            # Otherwise, allow it (might be a valid short recording)
            return True, None
        
        if duration < min_duration_seconds:
            return False, f"Recording is too short ({duration:.1f} seconds). Minimum required: {min_duration_seconds} seconds."
        
        return True, None


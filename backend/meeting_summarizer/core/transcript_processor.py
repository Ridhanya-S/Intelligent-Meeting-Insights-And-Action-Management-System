"""
Transcript Retrieval & Processing Module
Handles audio/video transcription and transcript file processing
"""
import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import whisper
from pydub import AudioSegment
import tempfile

from ..models import MeetingTranscript
from ..config import Config


class TranscriptProcessor:
    """Process audio/video files and transcript files to extract text"""
    
    def __init__(self):
        """Initialize the transcript processor"""
        self.model = None
        self._load_whisper_model()
    
    def _load_whisper_model(self):
        """Load Whisper model for transcription"""
        try:
            model_name = Config.WHISPER_MODEL
            print(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name)
            print("Whisper model loaded successfully")
        except Exception as e:
            print(f"Warning: Could not load Whisper model: {e}")
            print("Transcription will require manual transcript files")
    
    def process_input(
        self,
        project_name: str,
        file_path: str,
        file_type: Optional[str] = None
    ) -> MeetingTranscript:
        """
        Process input file (audio, video, or transcript)
        
        Args:
            project_name: Name of the project
            file_path: Path to the file
            file_type: Type of file (audio, video, transcript). Auto-detected if None
        
        Returns:
            MeetingTranscript object
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Auto-detect file type if not provided
        if file_type is None:
            file_type = self._detect_file_type(file_path_obj)
        
        # Process based on file type
        if file_type == "transcript":
            return self._process_transcript_file(project_name, file_path_obj)
        elif file_type in ["audio", "video"]:
            return self._process_media_file(project_name, file_path_obj, file_type)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type based on extension"""
        extension = file_path.suffix.lower()
        
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        transcript_extensions = {'.txt', '.json', '.srt', '.vtt'}
        
        if extension in audio_extensions:
            return "audio"
        elif extension in video_extensions:
            return "video"
        elif extension in transcript_extensions:
            return "transcript"
        else:
            # Try to read as text file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(100)  # Read first 100 chars
                return "transcript"
            except:
                raise ValueError(f"Could not determine file type for: {file_path}")
    
    def _process_transcript_file(
        self,
        project_name: str,
        file_path: Path
    ) -> MeetingTranscript:
        """Process a transcript text file and extract meeting date"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse as JSON (structured transcript)
            segments = []
            meeting_date = None
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    transcript_text = data.get('text', content)
                    segments = data.get('segments', [])
                    # Check for date in JSON data
                    if 'date' in data:
                        meeting_date = self._parse_date(data['date'])
                    elif 'meeting_date' in data:
                        meeting_date = self._parse_date(data['meeting_date'])
                elif isinstance(data, list):
                    # List of segments
                    segments = data
                    transcript_text = '\n'.join([s.get('text', '') for s in segments])
                else:
                    transcript_text = content
            except json.JSONDecodeError:
                # Plain text file
                transcript_text = content
                # Try to parse SRT/VTT format
                if file_path.suffix.lower() in ['.srt', '.vtt']:
                    segments = self._parse_subtitle_file(file_path)
            
            # Extract date from transcript text if not found in JSON
            if meeting_date is None:
                meeting_date = self._extract_date_from_text(transcript_text)
            
            # Extract participants from transcript text
            participants = self._extract_participants_from_text(transcript_text)
            
            return MeetingTranscript(
                project_name=project_name,
                file_path=str(file_path),
                file_type="transcript",
                transcript_text=transcript_text,
                segments=segments,
                meeting_date=meeting_date,
                participants=participants
            )
        except Exception as e:
            raise ValueError(f"Error processing transcript file: {e}")
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """
        Extract meeting date from transcript text.
        
        Looks for common date patterns:
        - Date: YYYY-MM-DD
        - Meeting Date: YYYY-MM-DD
        - YYYY-MM-DD patterns in first few lines
        - DD/MM/YYYY or MM/DD/YYYY patterns
        
        Args:
            text: Transcript text content
            
        Returns:
            datetime object if date found, None otherwise
        """
        import re
        from datetime import datetime
        
        if not text:
            return None
        
        # Check first 20 lines for date patterns (most likely to be in header)
        lines = text.split('\n')[:20]
        text_to_search = '\n'.join(lines)
        
        # Pattern 1: "Date: YYYY-MM-DD" or "Meeting Date: YYYY-MM-DD"
        date_patterns = [
            r'(?:Date|Meeting Date|Meeting date|DATE):\s*(\d{4})[-/](\d{2})[-/](\d{2})',
            r'(?:Date|Meeting Date|Meeting date|DATE):\s*(\d{2})[-/](\d{2})[-/](\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        # Try YYYY-MM-DD format first
                        try:
                            year, month, day = groups
                            if len(year) == 4:  # YYYY-MM-DD
                                return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                        
                        # Try DD-MM-YYYY format
                        try:
                            day, month, year = groups
                            if len(year) == 4:  # DD-MM-YYYY
                                return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                except (ValueError, IndexError):
                    continue
        
        # Pattern 2: Standalone date patterns in first few lines
        standalone_patterns = [
            r'\b(\d{4})[-/](\d{2})[-/](\d{2})\b',  # YYYY-MM-DD or YYYY/MM/DD
            r'\b(\d{2})[-/](\d{2})[-/](\d{4})\b',  # DD-MM-YYYY or MM/DD/YYYY
        ]
        
        for pattern in standalone_patterns:
            matches = re.findall(pattern, text_to_search)
            for match in matches[:3]:  # Check first 3 matches
                try:
                    if len(match) == 3:
                        # Try YYYY-MM-DD format
                        try:
                            year, month, day = match
                            if len(year) == 4 and int(month) <= 12 and int(day) <= 31:
                                return datetime(int(year), int(month), int(day))
                        except (ValueError, IndexError):
                            pass
                        
                        # Try DD-MM-YYYY format (ambiguous with MM/DD/YYYY)
                        try:
                            part1, part2, year = match
                            if len(year) == 4:
                                # Try DD-MM-YYYY first (more common internationally)
                                if int(part1) <= 31 and int(part2) <= 12:
                                    return datetime(int(year), int(part2), int(part1))
                                # Fallback to MM-DD-YYYY
                                elif int(part1) <= 12 and int(part2) <= 31:
                                    return datetime(int(year), int(part1), int(part2))
                        except (ValueError, IndexError):
                            pass
                except Exception:
                    continue
        
        # Pattern 3: Written date formats (e.g., "January 15, 2024")
        written_patterns = [
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
            r'(\d{1,2})\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})',
        ]
        
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        for pattern in written_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 2:
                        # Format: "Month Day, Year" or "Day Month Year"
                        if any(month in match.group(0).lower() for month in month_map.keys()):
                            month_name = None
                            for name, num in month_map.items():
                                if name in match.group(0).lower():
                                    month_name = name
                                    break
                            
                            if month_name:
                                if groups[0].isdigit() and groups[1].isdigit():
                                    # "Day Month Year" format
                                    day, year = int(groups[0]), int(groups[1])
                                    if 1 <= day <= 31:
                                        return datetime(year, month_map[month_name], day)
                                elif groups[1].isdigit():
                                    # "Month Day, Year" format
                                    year = int(groups[1])
                                    day_str = groups[0]
                                    if day_str.isdigit():
                                        day = int(day_str)
                                        if 1 <= day <= 31:
                                            return datetime(year, month_map[month_name], day)
                except (ValueError, IndexError, AttributeError):
                    continue
        
        return None
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse date from various formats (string, datetime, timestamp).
        
        Args:
            date_value: Date value in various formats
            
        Returns:
            datetime object if parseable, None otherwise
        """
        from datetime import datetime
        
        if date_value is None:
            return None
        
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, (int, float)):
            # Unix timestamp
            try:
                return datetime.fromtimestamp(date_value)
            except (ValueError, OSError):
                return None
        
        if isinstance(date_value, str):
            # Try various string formats
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
            
            # Try extracting from text using regex
            return self._extract_date_from_text(date_value)
        
        return None
    
    def _extract_participants_from_text(self, text: str) -> List[str]:
        """
        Extract participant names from transcript text.
        
        Looks for common patterns:
        - "Participants:" or "Attendees:" followed by names
        - Speaker labels (e.g., "Speaker 1:", "John:", "Jane:")
        - Names in the first few lines
        
        Args:
            text: Transcript text content
            
        Returns:
            List of participant names (unique)
        """
        import re
        
        if not text:
            return []
        
        participants = set()
        
        # Pattern 1: "Participants:" or "Attendees:" followed by names
        participant_patterns = [
            r'(?:Participants?|Attendees?|Attending|Present):\s*(.+?)(?:\n\n|\n[A-Z]|$)',
            r'(?:Participants?|Attendees?|Attending|Present):\s*(.+?)(?:\n\n|$)',
        ]
        
        for pattern in participant_patterns:
            match = re.search(pattern, text[:1000], re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                participants_str = match.group(1).strip()
                # Split by common delimiters
                names = re.split(r'[,;]|\sand\s|\n', participants_str)
                for name in names:
                    name = name.strip()
                    # Remove common prefixes/suffixes
                    name = re.sub(r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)\s+', '', name, flags=re.IGNORECASE)
                    name = name.strip()
                    if name and len(name) > 1 and name not in ['', 'and', 'or', 'the']:
                        participants.add(name)
        
        # Pattern 2: Speaker labels (e.g., "Speaker 1:", "John:", "Jane:")
        # Look for lines that start with a name followed by colon
        lines = text.split('\n')[:50]  # Check first 50 lines
        speaker_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):\s*'
        
        for line in lines:
            match = re.match(speaker_pattern, line.strip())
            if match:
                speaker_name = match.group(1).strip()
                # Filter out common non-name words
                if speaker_name.lower() not in ['speaker', 'participant', 'attendee', 'person', 'user', 'admin']:
                    # Check if it looks like a name (2-3 words, starts with capital)
                    words = speaker_name.split()
                    if 1 <= len(words) <= 3 and all(word[0].isupper() for word in words if word):
                        participants.add(speaker_name)
        
        # Pattern 3: Look for names in structured formats (e.g., "Name: John Doe")
        name_label_pattern = r'(?:Name|Speaker|Participant):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        matches = re.findall(name_label_pattern, text[:1000], re.IGNORECASE)
        for match in matches:
            name = match.strip()
            if name and len(name) > 1:
                participants.add(name)
        
        # Convert to sorted list and return
        return sorted(list(participants))
    
    def _parse_subtitle_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse SRT or VTT subtitle files"""
        segments = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Simple SRT parser
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.isdigit():  # Sequence number
                    i += 1
                    if i < len(lines):
                        timecode = lines[i].strip()
                        i += 1
                        text_lines = []
                        while i < len(lines) and lines[i].strip():
                            text_lines.append(lines[i].strip())
                            i += 1
                        
                        if text_lines:
                            segments.append({
                                'text': ' '.join(text_lines),
                                'start': self._parse_timecode(timecode.split(' --> ')[0]),
                                'end': self._parse_timecode(timecode.split(' --> ')[1]) if ' --> ' in timecode else None
                            })
                i += 1
        except Exception as e:
            print(f"Warning: Could not parse subtitle file: {e}")
        
        return segments
    
    def _parse_timecode(self, timecode: str) -> float:
        """Parse SRT timecode to seconds"""
        try:
            # Format: HH:MM:SS,mmm or HH:MM:SS.mmm
            timecode = timecode.replace(',', '.')
            parts = timecode.split(':')
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0.0
    
    def _process_media_file(
        self,
        project_name: str,
        file_path: Path,
        file_type: str
    ) -> MeetingTranscript:
        """Process audio or video file using Whisper"""
        if self.model is None:
            raise RuntimeError(
                "Whisper model not loaded. Please install whisper: pip install openai-whisper"
            )
        
        print(f"Transcribing {file_type} file: {file_path}")
        
        try:
            # For video files, extract audio first
            if file_type == "video":
                audio_path = self._extract_audio(file_path)
            else:
                audio_path = file_path
            
            # Transcribe using Whisper
            result = self.model.transcribe(
                str(audio_path),
                language=Config.TRANSCRIPTION_LANGUAGE
            )
            
            # Clean up temporary audio file if created
            if file_type == "video" and audio_path != file_path:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            
            # Extract segments
            segments = []
            for segment in result.get('segments', []):
                segments.append({
                    'text': segment.get('text', ''),
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0)
                })
            
            return MeetingTranscript(
                project_name=project_name,
                file_path=str(file_path),
                file_type=file_type,
                transcript_text=result.get('text', ''),
                segments=segments,
                language=result.get('language', 'en')
            )
        except Exception as e:
            raise RuntimeError(f"Error transcribing {file_type} file: {e}")
    
    def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video file"""
        try:
            # Use pydub to extract audio
            video = AudioSegment.from_file(str(video_path))
            
            # Create temporary audio file
            temp_dir = tempfile.gettempdir()
            audio_path = Path(temp_dir) / f"{video_path.stem}_audio.wav"
            
            video.export(str(audio_path), format="wav")
            return audio_path
        except Exception as e:
            # Fallback: return original path and let Whisper handle it
            print(f"Warning: Could not extract audio, using original file: {e}")
            return video_path
    
    def save_transcript(self, transcript: MeetingTranscript, meeting_date: Optional[datetime] = None) -> str:
        """
        Save transcript to file, organized by project/meetingtime
        
        Args:
            transcript: MeetingTranscript to save
            meeting_date: Meeting date (if None, uses upload date)
        
        Returns:
            Path to saved transcript file
        """
        # Use meeting date or upload date
        date_to_use = meeting_date or transcript.created_at
        
        # Get meeting directory: projectname/meetingtime/
        meeting_dir = Config.get_meeting_dir(transcript.project_name, date_to_use)
        
        # Save transcript file
        filename = "transcript.json"
        file_path = meeting_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(transcript.model_dump(), f, indent=2, default=str)
        
        return str(file_path)
    
    def copy_uploaded_file(self, source_path: str, project_name: str, meeting_date: datetime) -> str:
        """
        Copy uploaded file to organized directory: projectname/meetingtime/
        
        Args:
            source_path: Path to original file
            project_name: Name of the project
            meeting_date: Meeting date or upload date
        
        Returns:
            Path to copied file
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Get meeting directory: projectname/meetingtime/
        meeting_dir = Config.get_meeting_dir(project_name, meeting_date)
        
        # Copy file with original name
        file_extension = source.suffix
        file_stem = source.stem
        dest_filename = f"{file_stem}{file_extension}"
        dest_path = meeting_dir / dest_filename
        
        # If file already exists, add timestamp
        if dest_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_filename = f"{file_stem}_{timestamp}{file_extension}"
            dest_path = meeting_dir / dest_filename
        
        shutil.copy2(source_path, dest_path)
        
        return str(dest_path)


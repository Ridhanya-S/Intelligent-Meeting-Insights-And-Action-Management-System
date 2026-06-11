"""
Transcript Processing API Endpoints
"""
import sys
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import tempfile
import os
import asyncio
import uuid

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.core.transcript_processor import TranscriptProcessor
from backend.meeting_summarizer.core.summarizer import MeetingSummarizer
from backend.meeting_summarizer.core.storage import Storage
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.integrations.knowledge_base import KnowledgeBase
from backend.meeting_summarizer.integrations.teams_integration import TeamsIntegration
from backend.meeting_summarizer.integrations.sharepoint_download import SharePointDownloader
from backend.meeting_summarizer.analysis.multi_meeting_analyzer import MultiMeetingAnalyzer
from backend.meeting_summarizer.models import MeetingSummary
from backend.models.schemas import ProcessTranscriptResponse, SummaryResponse, ConfirmationRequest
from backend.security import (
    validate_file_upload, sanitize_project_name, sanitize_meeting_title,
    sanitize_participants, validate_teams_url_only, MAX_FILE_SIZE, MAX_TEXT_FILE_SIZE
)
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()

# Progress tracking (in-memory, use Redis in production)
processing_progress: dict[str, dict] = {}
# Store pending confirmations for old meetings
pending_confirmations: dict[str, dict] = {}


async def cleanup_progress(process_id: str):
    """Clean up progress tracking after delay"""
    await asyncio.sleep(300)  # 5 minutes
    processing_progress.pop(process_id, None)
    pending_confirmations.pop(process_id, None)


def _is_empty_meeting(summary: MeetingSummary) -> bool:
    """Check if a meeting is empty (no meaningful content)"""
    # Check if transcript text is empty or very short
    if not summary.overall_summary or len(summary.overall_summary.strip()) < 20:
        return True
    
    # Check if there are no action items, decisions, or risks
    if (len(summary.all_action_items) == 0 and 
        len(summary.all_decisions) == 0 and 
        len(summary.all_risks) == 0):
        return True
    
    # Check if overall summary is just placeholder text
    placeholder_texts = [
        "no summary available",
        "meeting summary",
        "summary not available",
        "no content",
        "empty meeting"
    ]
    summary_lower = summary.overall_summary.lower().strip()
    if any(placeholder in summary_lower for placeholder in placeholder_texts):
        if len(summary.all_action_items) == 0:
            return True
    
    return False


def handle_missing_owners(summary: MeetingSummary, project_name: str) -> MeetingSummary:
    """Handle action items with missing or unrecognized owners"""
    from backend.meeting_summarizer.config import Config
    
    # Get project owner from config (or use default)
    project_owner_email = Config.PROJECT_OWNER_EMAIL or "project-owner@example.com"
    project_owner_name = Config.PROJECT_OWNER_NAME or "Project Owner"
    
    unassigned_items = []
    
    for item in summary.all_action_items:
        # Check if owner is missing, unassigned, or unrecognized
        if (not item.owner or 
            item.owner.lower() in ["unassigned", "unknown", "n/a", "none", "tbd", "to be determined", "unrecognized"] or
            len(item.owner.strip()) == 0):
            
            # Assign to project owner
            item.owner = project_owner_name
            unassigned_items.append(item)
    
    # Send email to project owner if there are unassigned items
    if unassigned_items and Config.REMINDER_ENABLED:
        try:
            action_manager = ActionItemManager()
            action_manager.send_unassigned_items_notification(
                project_owner_email,
                project_owner_name,
                unassigned_items,
                summary.meeting_title,
                project_name
            )
        except Exception as e:
            print(f"Warning: Could not send unassigned items notification: {e}")
    
    return summary


@router.get("/process/{process_id}/progress")
async def get_processing_progress(process_id: str):
    """Get processing progress for a transcript"""
    progress = processing_progress.get(
        process_id, 
        {"progress": 0, "status": "unknown", "message": "Process not found"}
    )
    return progress


@router.post("/process/{process_id}/skip")
async def skip_file_processing(process_id: str):
    """Skip processing of an old meeting file"""
    if process_id not in pending_confirmations:
        raise HTTPException(status_code=404, detail="Process ID not found or already processed")
    
    pending_data = pending_confirmations.pop(process_id)
    tmp_file_path = pending_data.get("tmp_file_path")
    
    # Clean up temporary file
    if tmp_file_path and os.path.exists(tmp_file_path):
        try:
            os.unlink(tmp_file_path)
        except Exception:
            pass
    
    # Clean up progress tracking
    processing_progress.pop(process_id, None)
    
    return {"success": True, "message": "File processing skipped"}


@router.post("/process/confirm", response_model=ProcessTranscriptResponse)
async def confirm_old_meeting_processing(confirmation: ConfirmationRequest):
    """Confirm processing of an old meeting (1+ weeks old) or duplicate file"""
    if confirmation.process_id not in pending_confirmations:
        raise HTTPException(status_code=404, detail="Process ID not found or expired")
    
    pending_data = pending_confirmations.pop(confirmation.process_id)
    process_id = confirmation.process_id
    is_duplicate = pending_data.get("is_duplicate", False)
    
    try:
        project_name = pending_data["project_name"]
        # Normalize project name
        project_name = project_name.strip().title()
        
        # Get values with priority: user-provided > extracted
        title = pending_data.get("user_meeting_title") or pending_data.get("meeting_title")
        user_date_str = pending_data.get("user_meeting_date")
        
        # Re-determine meeting date with user-provided priority
        if user_date_str:
            try:
                meeting_datetime = datetime.strptime(user_date_str, "%Y-%m-%d")
            except ValueError:
                meeting_datetime = pending_data.get("meeting_datetime")
        else:
            meeting_datetime = pending_data.get("meeting_datetime")
        
        transcript = pending_data["transcript"]
        tmp_file_path = pending_data.get("tmp_file_path")
        uploaded_file_path = pending_data.get("uploaded_file_path")
        
        # If uploaded_file_path exists and file exists, use it (file was already copied before confirmation)
        # Otherwise, try to copy from tmp_file_path
        if not uploaded_file_path or not os.path.exists(uploaded_file_path):
            if tmp_file_path and os.path.exists(tmp_file_path):
                # File still exists in temp location, copy it now
                try:
                    processor = TranscriptProcessor()
                    uploaded_file_path = processor.copy_uploaded_file(
                        tmp_file_path,
                        project_name,
                        meeting_datetime
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Could not copy file: {e}. File may have been deleted."
                    )
            else:
                # Try to use uploaded_file_path even if it doesn't exist (might be a path issue)
                if uploaded_file_path:
                    # Check if file exists at that path
                    if not os.path.exists(uploaded_file_path):
                        raise HTTPException(
                            status_code=404,
                            detail=f"Source file not found: {uploaded_file_path}. The file may have been deleted or moved."
                        )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="No file path available. The temporary file may have been deleted."
                    )
        
        # Participants: user-provided first, then extracted
        user_participants = pending_data.get("user_participants", [])
        transcript_participants = transcript.participants if transcript else []
        participant_list = []
        seen = set()
        # Add user-provided first
        for p in user_participants:
            if p.lower() not in seen:
                participant_list.append(p)
                seen.add(p.lower())
        # Then add extracted
        for p in transcript_participants:
            if p.lower() not in seen:
                participant_list.append(p)
                seen.add(p.lower())
        
        # Update progress
        processing_progress[process_id] = {"progress": 40, "status": "processing", "message": "Processing confirmed meeting..."}
        
        # File is already copied (uploaded_file_path), no need to copy again
        processor = TranscriptProcessor()
        
        # Save transcript
        processor.save_transcript(transcript, meeting_datetime)
        
        # Generate summary
        # Use title (user-provided or default format)
        if title:
            final_title = title
        else:
            # Default format: YYYY-MM-DD HH:MM - meeting summary
            date_str = meeting_datetime.strftime("%Y-%m-%d %H:%M")
            final_title = f"{date_str} - meeting summary"
        processing_progress[process_id] = {"progress": 60, "status": "processing", "message": "Generating summary..."}
        summarizer = MeetingSummarizer()
        summary = summarizer.summarize(
            transcript=transcript,
            meeting_title=final_title,
            meeting_date=meeting_datetime,
            participants=participant_list
        )
        
        if not summary:
            raise HTTPException(status_code=500, detail="Failed to generate summary")
        
        # Handle missing owners
        summary = handle_missing_owners(summary, project_name)
        
        # Update progress
        processing_progress[process_id] = {"progress": 75, "status": "processing", "message": "Syncing to external services..."}
        
        # Sync action items to Trello (if confirmed)
        trello_synced = False
        if confirmation.add_to_trello:
            try:
                action_manager = ActionItemManager()
                summary.all_action_items = action_manager.sync_action_items(
                    summary.all_action_items,
                    project_name,
                    title
                )
                trello_synced = len([item for item in summary.all_action_items if item.external_id]) > 0
            except Exception as e:
                print(f"Warning: Trello sync failed: {e}")
        
        # Store in knowledge base (if confirmed)
        kb_url = None
        confluence_stored = False
        if confirmation.add_to_confluence:
            try:
                kb = KnowledgeBase()
                kb_url = kb.store_summary(summary, uploaded_file_path=uploaded_file_path)
                confluence_stored = bool(kb_url)
            except Exception as e:
                print(f"Warning: Confluence storage failed: {e}")
        
        # Store Confluence URL in summary metadata
        if kb_url:
            if not summary.metadata:
                summary.metadata = {}
            summary.metadata['confluence_url'] = kb_url
        
        # Update progress
        processing_progress[process_id] = {"progress": 90, "status": "processing", "message": "Saving to database..."}
        
        # Save to database
        storage = Storage()
        summary_id = storage.save_summary(summary)
        # Use uploaded_file_path (permanent location) instead of tmp_file_path for tracking
        storage.mark_file_processed(
            file_path=uploaded_file_path or tmp_file_path,
            project_name=project_name,
            meeting_id=summary_id,
            trello_synced=trello_synced,
            confluence_stored=confluence_stored
        )
        
        # Update progress: Complete
        processing_progress[process_id] = {"progress": 100, "status": "completed", "message": "Processing complete"}
        
        # Build response
        summary_response = SummaryResponse(
            id=summary.id,
            project_name=summary.project_name,
            meeting_title=summary.meeting_title,
            meeting_date=summary.meeting_date,
            meeting_type=summary.meeting_type,
            participants=summary.participants,
            duration_minutes=summary.duration_minutes,
            overall_summary=summary.overall_summary,
            action_items_count=len(summary.all_action_items),
            decisions_count=len(summary.all_decisions),
            risks_count=len(summary.all_risks),
            tags=summary.tags,
            transcript_path=summary.transcript_path,
            created_at=summary.created_at
        )
        
        return ProcessTranscriptResponse(
            success=True,
            message="Old meeting processed successfully",
            summary=summary_response,
            summary_id=summary_id,
            process_id=process_id
        )
        
    except Exception as e:
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=f"Error processing confirmed meeting: {str(e)}")


@router.post("/process", response_model=ProcessTranscriptResponse)
async def process_transcript(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    meeting_title: Optional[str] = Form(None),
    meeting_date: Optional[str] = Form(None),
    participants: Optional[str] = Form(None),
    skip_sync: bool = Form(False),
    analyze_project: bool = Form(True)
):
    """
    Process an uploaded transcript file (audio, video, or text).
    
    Returns:
        ProcessTranscriptResponse with summary information
    """
    process_id = None
    tmp_file_path = None
    
    try:
        # Security: Validate and sanitize inputs
        project_name = sanitize_project_name(project_name)
        # Normalize project name to avoid case sensitivity issues
        project_name = project_name.strip().title()
        
        # Sanitize user-provided values (will be prioritized later)
        meeting_title = sanitize_meeting_title(meeting_title)
        form_participants = sanitize_participants(participants)
        
        # Edge case: Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        # Read file content
        content = await file.read()
        
        # Security: Validate file upload
        is_valid, error_msg = validate_file_upload(file, content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Edge case: Handle empty content
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Generate process ID for progress tracking
        process_id = str(uuid.uuid4())
        processing_progress[process_id] = {"progress": 0, "status": "processing", "message": "Starting..."}
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Define helper function for determining meeting datetime
            def get_meeting_datetime(
                file_path: str, 
                provided_date: Optional[str] = None,
                filename: Optional[str] = None,
                transcript_text: Optional[str] = None
            ) -> datetime:
                """
                Determine meeting datetime from multiple sources in priority order:
                1. User-provided date
                2. Filename patterns (YYYY-MM-DD, YYYYMMDD, etc.)
                3. Transcript content (Date: YYYY-MM-DD)
                4. File modification time
                5. Current date (fallback)
                """
                import re
                
                # 1. Check user-provided date
                if provided_date:
                    try:
                        return datetime.strptime(provided_date, "%Y-%m-%d")
                    except ValueError:
                        pass
                
                # 2. Check filename for date patterns
                if filename:
                    # Pattern 1: YYYY-MM-DD or YYYY_MM_DD
                    date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', filename)
                    if date_match:
                        try:
                            year, month, day = date_match.groups()
                            return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                    
                    # Pattern 2: YYYYMMDD
                    date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
                    if date_match:
                        try:
                            year, month, day = date_match.groups()
                            return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                    
                    # Pattern 3: DD-MM-YYYY or DD_MM_YYYY
                    date_match = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', filename)
                    if date_match:
                        try:
                            day, month, year = date_match.groups()
                            return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                
                # 3. Check transcript content for date
                if transcript_text:
                    # Look for "Date: YYYY-MM-DD" pattern
                    date_match = re.search(r'Date:\s*(\d{4})[-/](\d{2})[-/](\d{2})', transcript_text, re.IGNORECASE)
                    if date_match:
                        try:
                            year, month, day = date_match.groups()
                            return datetime(int(year), int(month), int(day))
                        except ValueError:
                            pass
                    
                    # Look for standalone date patterns in first few lines
                    lines = transcript_text.split('\n')[:10]  # Check first 10 lines
                    for line in lines:
                        date_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', line)
                        if date_match:
                            try:
                                year, month, day = date_match.groups()
                                return datetime(int(year), int(month), int(day))
                            except ValueError:
                                pass
                
                # 4. Check file modification time
                try:
                    if os.path.exists(file_path):
                        mtime = os.path.getmtime(file_path)
                        return datetime.fromtimestamp(mtime)
                except Exception:
                    pass
                
                # 5. Fallback to current date
                return datetime.now()
            
            # Update progress: File uploaded (10%)
            processing_progress[process_id] = {"progress": 10, "status": "processing", "message": "File uploaded, checking for duplicates..."}
            
            # Check if file has been processed before IN THIS PROJECT
            # Note: Same file uploaded to different project is treated as new file
            storage = Storage()
            file_already_processed = False
            existing_meeting_info = None
            
            try:
                # Check only within the current project
                file_already_processed = storage.is_file_processed(tmp_file_path, project_name=project_name)
                
                # If file was processed in this project, get information about the existing meeting
                if file_already_processed:
                    file_hash = storage.calculate_file_hash(tmp_file_path)
                    conn = storage.db_path
                    import sqlite3
                    db_conn = sqlite3.connect(conn)
                    cursor = db_conn.cursor()
                    
                    # Get meeting info from processed_files table (only for this project)
                    cursor.execute('''
                        SELECT pf.meeting_id, m.meeting_title, m.meeting_date, m.project_name
                        FROM processed_files pf
                        LEFT JOIN meetings m ON pf.meeting_id = m.id
                        WHERE pf.file_hash = ? AND pf.project_name = ?
                        ORDER BY pf.processed_at DESC
                        LIMIT 1
                    ''', (file_hash, project_name))
                    result = cursor.fetchone()
                    db_conn.close()
                    
                    if result:
                        existing_meeting_info = {
                            "meeting_id": result[0],
                            "meeting_title": result[1],
                            "meeting_date": result[2],
                            "project_name": result[3]
                        }
            except Exception as e:
                print(f"Warning: Could not check for duplicate file: {e}")
                # Continue processing if check fails
            
            # If file was already processed, ask for confirmation
            if file_already_processed:
                # Process transcript first to get meeting info
                processing_progress[process_id] = {"progress": 20, "status": "processing", "message": "Processing transcript to get meeting details..."}
                processor = TranscriptProcessor()
                transcript = processor.process_input(
                    project_name=project_name,
                    file_path=tmp_file_path,
                    file_type=None  # Auto-detect
                )
                
                # Edge case: Validate transcript was created
                if not transcript or not transcript.transcript_text:
                    raise HTTPException(status_code=400, detail="Failed to process transcript. File may be corrupted or unsupported.")
                
                # Determine meeting date
                meeting_datetime = get_meeting_datetime(
                    tmp_file_path,
                    meeting_date,
                    file.filename,
                    transcript.transcript_text
                )
                
                # IMPORTANT: Copy file to permanent location BEFORE confirmation
                # This prevents the temp file from being deleted before user confirms
                uploaded_file_path = None
                try:
                    uploaded_file_path = processor.copy_uploaded_file(
                        tmp_file_path,
                        project_name,
                        meeting_datetime
                    )
                except Exception as e:
                    # If copy fails, still store temp path but log warning
                    print(f"Warning: Could not copy duplicate file before confirmation: {e}")
                    uploaded_file_path = tmp_file_path
                
                # Get meeting title (user-provided or default format)
                # NOTE: Do NOT use filename as title - always use default format if no user title provided
                if not meeting_title:
                    # Default format: YYYY-MM-DD HH:MM - meeting summary
                    date_str = meeting_datetime.strftime("%Y-%m-%d %H:%M")
                    final_meeting_title = f"{date_str} - meeting summary"
                else:
                    final_meeting_title = meeting_title
                
                # Get participants
                transcript_participants = transcript.participants if transcript else []
                participant_list = []
                seen = set()
                # First add user-provided participants
                for p in form_participants:
                    if p.lower() not in seen:
                        participant_list.append(p)
                        seen.add(p.lower())
                # Then add extracted participants (if not already in list)
                for p in transcript_participants:
                    if p.lower() not in seen:
                        participant_list.append(p)
                        seen.add(p.lower())
                
                # Store pending confirmation for duplicate file
                pending_confirmations[process_id] = {
                    "project_name": project_name,
                    "meeting_title": final_meeting_title,
                    "meeting_datetime": meeting_datetime,
                    "user_meeting_title": meeting_title,
                    "user_meeting_date": meeting_date,
                    "user_participants": form_participants,
                    "is_duplicate": True,
                    "existing_meeting_info": existing_meeting_info,
                    "transcript": transcript,
                    "tmp_file_path": tmp_file_path,  # Keep for cleanup
                    "uploaded_file_path": uploaded_file_path,  # Permanent location
                    "participant_list": participant_list
                }
                
                # Return early with confirmation prompt
                existing_info_text = ""
                if existing_meeting_info:
                    existing_date = existing_meeting_info.get("meeting_date", "")
                    if existing_date:
                        try:
                            existing_date_obj = datetime.fromisoformat(existing_date.replace('Z', '+00:00'))
                            existing_date_str = existing_date_obj.strftime('%Y-%m-%d')
                        except:
                            existing_date_str = existing_date
                    else:
                        existing_date_str = "unknown date"
                    existing_info_text = f"\n\nPreviously processed as:\n- Meeting: {existing_meeting_info.get('meeting_title', 'Unknown')}\n- Date: {existing_date_str}\n- Project: {existing_meeting_info.get('project_name', 'Unknown')}"
                
                return ProcessTranscriptResponse(
                    success=False,
                    message="This file has been processed before. Please confirm if you want to process it again.",
                    requires_confirmation=True,
                    confirmation_prompt=f"This file was already processed.{existing_info_text}\n\nDo you want to:\n- Process it again (will create a new meeting entry)?\n- Or skip this file?",
                    process_id=process_id
                )
            
            # Process transcript
            processing_progress[process_id] = {"progress": 20, "status": "processing", "message": "Processing transcript..."}
            processor = TranscriptProcessor()
            transcript = processor.process_input(
                project_name=project_name,
                file_path=tmp_file_path,
                file_type=None  # Auto-detect
            )
            
            # Edge case: Validate transcript was created
            if not transcript or not transcript.transcript_text:
                raise HTTPException(status_code=400, detail="Failed to process transcript. File may be corrupted or unsupported.")
            
            # Get meeting date from multiple sources
            # Priority: 1. User-provided, 2. Extracted from transcript, 3. Filename, 4. File time, 5. Current date
            transcript_text = transcript.transcript_text if transcript else None
            
            # Priority 1: Use user-provided date if available
            if meeting_date:
                try:
                    meeting_datetime = datetime.strptime(meeting_date, "%Y-%m-%d")
                except ValueError:
                    # If parsing fails, fall through to other sources
                    meeting_datetime = None
            else:
                meeting_datetime = None
            
            # Priority 2: If no user-provided date, check transcript extraction
            if not meeting_datetime and transcript and transcript.meeting_date:
                meeting_datetime = transcript.meeting_date
            
            # Priority 3-5: Fallback to other sources (filename, file time, current date)
            if not meeting_datetime:
                meeting_datetime = get_meeting_datetime(
                    tmp_file_path, 
                    provided_date=None,  # Don't pass meeting_date again, already checked
                    filename=file.filename,
                    transcript_text=transcript_text
                )
            
            # Priority: User-provided values FIRST, then extracted from transcript
            # 1. Meeting Title: User-provided > Default format (datetime - meeting summary)
            # NOTE: Do NOT use filename as title - always use default format if no user title provided
            final_meeting_title = meeting_title
            if not final_meeting_title:
                # Default format: YYYY-MM-DD HH:MM - meeting summary
                date_str = meeting_datetime.strftime("%Y-%m-%d %H:%M")
                final_meeting_title = f"{date_str} - meeting summary"
            
            # 2. Participants: User-provided > Extracted from transcript
            transcript_participants = transcript.participants if transcript else []
            
            # Prioritize user-provided participants, then add extracted ones
            participant_list = []
            seen = set()
            # First add user-provided participants
            for p in form_participants:
                if p.lower() not in seen:
                    participant_list.append(p)
                    seen.add(p.lower())
            # Then add extracted participants (if not already in list)
            for p in transcript_participants:
                if p.lower() not in seen:
                    participant_list.append(p)
                    seen.add(p.lower())
            
            # Check if meeting is older than 1 week
            days_old = (datetime.now() - meeting_datetime).days
            is_old_meeting = days_old >= 7
            
            if is_old_meeting:
                # IMPORTANT: Copy file to permanent location BEFORE confirmation
                # This prevents the temp file from being deleted before user confirms
                try:
                    uploaded_file_path = processor.copy_uploaded_file(
                        tmp_file_path,
                        project_name,
                        meeting_datetime
                    )
                except Exception as e:
                    # If copy fails, still store temp path but log warning
                    print(f"Warning: Could not copy file before confirmation: {e}")
                    uploaded_file_path = tmp_file_path
                
                # Store pending confirmation (preserve user-provided values separately)
                pending_confirmations[process_id] = {
                    "project_name": project_name,
                    "meeting_title": final_meeting_title,
                    "meeting_datetime": meeting_datetime,
                    "user_meeting_title": meeting_title,  # Store user-provided separately
                    "user_meeting_date": meeting_date,  # Store user-provided date string
                    "user_participants": form_participants,  # Store user-provided participants
                    "days_old": days_old,
                    "transcript": transcript,
                    "tmp_file_path": tmp_file_path,  # Keep for cleanup
                    "uploaded_file_path": uploaded_file_path,  # Permanent location
                    "participant_list": participant_list  # Combined list (user + extracted)
                }
                
                # Return early with confirmation prompt
                return ProcessTranscriptResponse(
                    success=False,
                    message=f"This meeting is {days_old} days old. Please confirm if you want to proceed.",
                    requires_confirmation=True,
                    confirmation_prompt=f"This meeting occurred {days_old} days ago ({meeting_datetime.strftime('%Y-%m-%d')}). Do you want to:\n- Add action items to Trello?\n- Add summary to Confluence?\n- Or skip this file?",
                    process_id=process_id
                )
            
            # Update progress: Transcript processed (40%)
            processing_progress[process_id] = {"progress": 40, "status": "processing", "message": "Transcript processed, generating summary..."}
            
            # Copy file to organized directory
            uploaded_file_path = processor.copy_uploaded_file(
                tmp_file_path,
                project_name,
                meeting_datetime
            )
            
            # Save transcript
            processor.save_transcript(transcript, meeting_datetime)
            
            # Generate summary
            # Use final_meeting_title (already prioritized: user-provided > filename)
            processing_progress[process_id] = {"progress": 60, "status": "processing", "message": "Generating summary..."}
            summarizer = MeetingSummarizer()
            summary = summarizer.summarize(
                transcript=transcript,
                meeting_title=final_meeting_title,
                meeting_date=meeting_datetime,
                participants=participant_list
            )
            
            # Edge case: Validate summary was created
            if not summary:
                raise HTTPException(status_code=500, detail="Failed to generate summary")
            
            # Handle missing owners - assign to project owner
            summary = handle_missing_owners(summary, project_name)
            
            # Update progress: Summary generated (75%)
            processing_progress[process_id] = {"progress": 75, "status": "processing", "message": "Syncing to external services..."}
            
            # Sync action items to Trello
            trello_synced = False
            if not skip_sync:
                try:
                    action_manager = ActionItemManager()
                    summary.all_action_items = action_manager.sync_action_items(
                        summary.all_action_items,
                        project_name,
                        final_meeting_title
                    )
                    trello_synced = len([item for item in summary.all_action_items if item.external_id]) > 0
                except Exception as e:
                    # Edge case: Trello sync failure shouldn't fail entire request
                    print(f"Warning: Trello sync failed: {e}")
            
            # Store in knowledge base
            kb_url = None
            confluence_stored = False
            if not skip_sync:
                try:
                    kb = KnowledgeBase()
                    kb_url = kb.store_summary(summary, uploaded_file_path=uploaded_file_path)
                    confluence_stored = bool(kb_url)
                except Exception as e:
                    # Edge case: Confluence storage failure shouldn't fail entire request
                    print(f"Warning: Confluence storage failed: {e}")
            
            # Store Confluence URL in summary metadata
            if kb_url:
                if not summary.metadata:
                    summary.metadata = {}
                summary.metadata['confluence_url'] = kb_url
            
            # Update progress: External sync complete (90%)
            processing_progress[process_id] = {"progress": 90, "status": "processing", "message": "Saving to database..."}
            
            # Save to database
            storage = Storage()
            summary_id = storage.save_summary(summary)
            # Mark the uploaded file (not temp file) as processed
            storage.mark_file_processed(
                file_path=uploaded_file_path,  # Use permanent uploaded file path, not temp
                project_name=project_name,
                meeting_id=summary_id,
                trello_synced=trello_synced,
                confluence_stored=confluence_stored
            )
            
            # Multi-meeting analysis if requested
            if analyze_project:
                try:
                    analyzer = MultiMeetingAnalyzer()
                    analyzer.analyze_project_meetings(project_name, days_back=90)
                except Exception as e:
                    # Edge case: Analysis failure shouldn't fail entire request
                    print(f"Warning: Multi-meeting analysis failed: {e}")
            
            # Update progress: Complete (100%)
            processing_progress[process_id] = {"progress": 100, "status": "completed", "message": "Processing complete"}
            
            # Build response
            summary_response = SummaryResponse(
                id=summary.id,
                project_name=summary.project_name,
                meeting_title=summary.meeting_title,
                meeting_date=summary.meeting_date,
                participants=summary.participants,
                duration_minutes=summary.duration_minutes,
                overall_summary=summary.overall_summary,
                action_items_count=len(summary.all_action_items),
                decisions_count=len(summary.all_decisions),
                risks_count=len(summary.all_risks),
                tags=summary.tags,
                transcript_path=summary.transcript_path,
                created_at=summary.created_at
            )
            
            response_data = ProcessTranscriptResponse(
                success=True,
                message="Transcript processed successfully",
                summary=summary_response,
                summary_id=summary_id,
                process_id=process_id
            )
            
            return response_data
            
        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass
            
            # Schedule progress cleanup
            if process_id:
                # Store task reference to prevent garbage collection
                _ = asyncio.create_task(cleanup_progress(process_id))
                
    except HTTPException:
        # Re-raise HTTP exceptions
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": "Processing failed"}
        raise
    except Exception as e:
        # Edge case: Catch all other exceptions
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=f"Error processing transcript: {str(e)}")


class ProcessTeamsUrlRequest(BaseModel):
    """Request model for Teams URL processing"""
    teams_url: str
    project_name: str
    meeting_title: Optional[str] = None
    meeting_date: Optional[str] = None
    participants: Optional[str] = None
    skip_sync: bool = False
    analyze_project: bool = True
    file: Optional[UploadFile] = None


@router.post("/process-teams-url", response_model=ProcessTranscriptResponse)
async def process_teams_url(
    teams_url: str = Form(...),
    project_name: str = Form(...),
    meeting_title: Optional[str] = Form(None),
    meeting_date: Optional[str] = Form(None),
    participants: Optional[str] = Form(None),
    skip_sync: bool = Form(False),
    analyze_project: bool = Form(True),
    file: Optional[UploadFile] = File(default=None)
):
    """
    Process a Teams meeting URL to fetch meeting details and optionally process a transcript file.
    
    Uses Microsoft Graph API with OnlineMeeting.Read permission to fetch:
    - Meeting subject/title
    - Start and end times
    - Participants
    - Organizer
    - Recording information (if available)
    
    If a transcript file is provided, it will be processed similar to the regular upload endpoint.
    If no file is provided, only meeting metadata will be fetched and returned.
    
    Returns:
        ProcessTranscriptResponse with meeting details and optionally processed summary
    """
    process_id = None
    tmp_file_path = None
    
    try:
        # Security: Validate and sanitize inputs
        project_name = sanitize_project_name(project_name)
        project_name = project_name.strip().title()
        
        meeting_title = sanitize_meeting_title(meeting_title)
        form_participants = sanitize_participants(participants)
        
        # Validate Teams URL - only Teams URLs allowed, reject Zoom, Google Meet, etc.
        teams_url = teams_url.strip() if teams_url else ""
        is_valid_url, url_error = validate_teams_url_only(teams_url)
        if not is_valid_url:
            raise HTTPException(status_code=400, detail=url_error or "Invalid Teams meeting URL")
        
        # Generate process ID for progress tracking
        process_id = str(uuid.uuid4())
        processing_progress[process_id] = {"progress": 10, "status": "processing", "message": "Fetching Teams meeting details..."}
        
        # Fetch meeting details from Teams
        try:
            teams_integration = TeamsIntegration()
            
            if not teams_integration.is_valid_teams_url(teams_url):
                raise HTTPException(status_code=400, detail="Invalid Teams meeting URL format")
            
            meeting_details = teams_integration.get_meeting_details(teams_url)
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch Teams meeting details: {str(e)}")
        
        # Update progress
        processing_progress[process_id] = {"progress": 30, "status": "processing", "message": "Meeting details fetched, processing transcript..."}
        
        # Determine meeting datetime (priority: user-provided > Teams meeting start time > current date)
        meeting_datetime = None
        if meeting_date:
            try:
                meeting_datetime = datetime.strptime(meeting_date, "%Y-%m-%d")
            except ValueError:
                pass
        
        if not meeting_datetime and meeting_details.get("startDateTime"):
            meeting_datetime = meeting_details["startDateTime"]
        
        if not meeting_datetime:
            meeting_datetime = datetime.now()
        
        # Determine meeting title (priority: user-provided > Teams meeting subject > default format)
        final_meeting_title = meeting_title
        if not final_meeting_title:
            final_meeting_title = meeting_details.get("subject")
        if not final_meeting_title:
            date_str = meeting_datetime.strftime("%Y-%m-%d %H:%M")
            final_meeting_title = f"{date_str} - meeting summary"
        
        # Determine participants (priority: user-provided > Teams meeting participants)
        participant_list = []
        seen = set()
        
        # Add user-provided participants first
        for p in form_participants:
            if p.lower() not in seen:
                participant_list.append(p)
                seen.add(p.lower())
        
        # Add Teams meeting participants
        teams_participants = meeting_details.get("participants", [])
        for p in teams_participants:
            if p.lower() not in seen:
                participant_list.append(p)
                seen.add(p.lower())
        
        # Add organizer if not already in list
        organizer = meeting_details.get("organizer", {})
        organizer_name = organizer.get("displayName", "")
        if organizer_name and organizer_name.lower() not in seen:
            participant_list.append(organizer_name)
            seen.add(organizer_name.lower())
        
        # If no file provided, return meeting details only
        if file is None or not file.filename:
            # Return meeting details without processing transcript
            return ProcessTranscriptResponse(
                success=True,
                message="Teams meeting details fetched successfully. No transcript file provided.",
                summary=None,
                summary_id=None,
                process_id=process_id,
                meeting_details={
                    "subject": meeting_details.get("subject"),
                    "startDateTime": meeting_details.get("startDateTime").isoformat() if meeting_details.get("startDateTime") else None,
                    "endDateTime": meeting_details.get("endDateTime").isoformat() if meeting_details.get("endDateTime") else None,
                    "participants": participant_list,
                    "organizer": organizer,
                    "joinWebUrl": meeting_details.get("joinWebUrl"),
                    "recording": meeting_details.get("recording")
                }
            )
        
        # Process transcript file if provided
        # Read file content
        content = await file.read()
        
        # Security: Validate file upload
        is_valid, error_msg = validate_file_upload(file, content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Update progress
            processing_progress[process_id] = {"progress": 40, "status": "processing", "message": "Processing transcript..."}
            
            # Process transcript
            processor = TranscriptProcessor()
            transcript = processor.process_input(
                project_name=project_name,
                file_path=tmp_file_path,
                file_type=None  # Auto-detect
            )
            
            if not transcript or not transcript.transcript_text:
                raise HTTPException(status_code=400, detail="Failed to process transcript. File may be corrupted or unsupported.")
            
            # Copy file to organized directory
            uploaded_file_path = processor.copy_uploaded_file(
                tmp_file_path,
                project_name,
                meeting_datetime
            )
            
            # Save transcript
            processor.save_transcript(transcript, meeting_datetime)
            
            # Generate summary
            processing_progress[process_id] = {"progress": 60, "status": "processing", "message": "Generating summary..."}
            summarizer = MeetingSummarizer()
            summary = summarizer.summarize(
                transcript=transcript,
                meeting_title=final_meeting_title,
                meeting_date=meeting_datetime,
                participants=participant_list
            )
            
            if not summary:
                raise HTTPException(status_code=500, detail="Failed to generate summary")
            
            # Handle missing owners
            summary = handle_missing_owners(summary, project_name)
            
            # Update progress: Summary generated (75%)
            processing_progress[process_id] = {"progress": 75, "status": "processing", "message": "Syncing to external services..."}
            
            # Sync action items to Trello
            trello_synced = False
            if not skip_sync:
                try:
                    action_manager = ActionItemManager()
                    summary.all_action_items = action_manager.sync_action_items(
                        summary.all_action_items,
                        project_name,
                        final_meeting_title
                    )
                    trello_synced = len([item for item in summary.all_action_items if item.external_id]) > 0
                except Exception as e:
                    print(f"Warning: Trello sync failed: {e}")
            
            # Store in knowledge base
            kb_url = None
            confluence_stored = False
            if not skip_sync:
                try:
                    kb = KnowledgeBase()
                    kb_url = kb.store_summary(summary, uploaded_file_path=uploaded_file_path)
                    confluence_stored = bool(kb_url)
                except Exception as e:
                    print(f"Warning: Confluence storage failed: {e}")
            
            # Store Confluence URL in summary metadata
            if kb_url:
                if not summary.metadata:
                    summary.metadata = {}
                summary.metadata['confluence_url'] = kb_url
                summary.metadata['teams_url'] = teams_url
                summary.metadata['teams_meeting_id'] = meeting_details.get("meetingId", "")
            
            # Update progress: External sync complete (90%)
            processing_progress[process_id] = {"progress": 90, "status": "processing", "message": "Saving to database..."}
            
            # Save to database
            storage = Storage()
            summary_id = storage.save_summary(summary)
            storage.mark_file_processed(
                file_path=uploaded_file_path,
                project_name=project_name,
                meeting_id=summary_id,
                trello_synced=trello_synced,
                confluence_stored=confluence_stored
            )
            
            # Multi-meeting analysis if requested
            if analyze_project:
                try:
                    analyzer = MultiMeetingAnalyzer()
                    analyzer.analyze_project_meetings(project_name, days_back=90)
                except Exception as e:
                    print(f"Warning: Multi-meeting analysis failed: {e}")
            
            # Update progress: Complete (100%)
            processing_progress[process_id] = {"progress": 100, "status": "completed", "message": "Processing complete"}
            
            # Build response
            summary_response = SummaryResponse(
                id=summary.id,
                project_name=summary.project_name,
                meeting_title=summary.meeting_title,
                meeting_date=summary.meeting_date,
                participants=summary.participants,
                duration_minutes=summary.duration_minutes,
                overall_summary=summary.overall_summary,
                action_items_count=len(summary.all_action_items),
                decisions_count=len(summary.all_decisions),
                risks_count=len(summary.all_risks),
                tags=summary.tags,
                transcript_path=summary.transcript_path,
                created_at=summary.created_at
            )
            
            return ProcessTranscriptResponse(
                success=True,
                message="Teams meeting processed successfully",
                summary=summary_response,
                summary_id=summary_id,
                process_id=process_id
            )
            
        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass
            
            # Schedule progress cleanup
            if process_id:
                _ = asyncio.create_task(cleanup_progress(process_id))
                
    except HTTPException:
        # Re-raise HTTP exceptions
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": "Processing failed"}
        raise
    except Exception as e:
        # Edge case: Catch all other exceptions
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=f"Error processing Teams meeting: {str(e)}")


@router.post("/process-sharepoint-url", response_model=ProcessTranscriptResponse)
async def process_sharepoint_url(
    teams_url: str = Form(...),
    project_name: str = Form(...),
    meeting_title: Optional[str] = Form(None),
    meeting_date: Optional[str] = Form(None),
    participants: Optional[str] = Form(None),
    skip_sync: bool = Form(False),
    analyze_project: bool = Form(True),
    prefer_transcript: bool = Form(True),
    selected_recording_indices: Optional[str] = Form(None)  # Comma-separated indices like "0,2,3"
):
    """
    Process a Teams meeting URL by downloading recordings/transcripts from SharePoint
    and processing them through the pipeline.
    
    Flow:
    1. Extract meeting ID and user ID from URL
    2. Download recordings/transcripts from SharePoint
    3. Process downloaded files through existing pipeline
    4. Generate summary and sync to Trello/Confluence
    
    Args:
        teams_url: Teams meeting join URL
        project_name: Project name for categorization
        meeting_title: Optional meeting title for filtering
        meeting_date: Optional meeting date
        participants: Optional comma-separated participants
        skip_sync: Skip Trello/Confluence sync
        analyze_project: Run multi-meeting analysis
        prefer_transcript: Prefer transcript over recording if both found
    
    Returns:
        ProcessTranscriptResponse with summary information
    """
    process_id = None
    tmp_file_path = None
    temp_dir = None
    
    try:
        # Security: Validate and sanitize inputs
        project_name = sanitize_project_name(project_name)
        project_name = project_name.strip().title()
        
        meeting_title = sanitize_meeting_title(meeting_title)
        form_participants = sanitize_participants(participants)
        
        # Validate Teams URL - only Teams URLs allowed, reject Zoom, Google Meet, etc.
        teams_url = teams_url.strip() if teams_url else ""
        is_valid_url, url_error = validate_teams_url_only(teams_url)
        if not is_valid_url:
            # Generate process ID for progress tracking (even for errors)
            process_id = str(uuid.uuid4())
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": url_error or "Invalid URL"}
            raise HTTPException(status_code=400, detail=url_error or "Invalid Teams meeting URL")
        
        # Generate process ID for progress tracking
        process_id = str(uuid.uuid4())
        processing_progress[process_id] = {"progress": 5, "status": "processing", "message": "Validating Teams URL..."}
        await asyncio.sleep(0)  # Yield control immediately so frontend can start polling
        
        # Initialize SharePoint downloader
        try:
            sharepoint_downloader = SharePointDownloader()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize SharePoint downloader: {str(e)}")
        
        # Additional Teams URL format validation (for SharePoint-specific checks)
        is_valid_url, url_error = sharepoint_downloader.validate_teams_url(teams_url)
        if not is_valid_url:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": url_error or "Invalid URL"}
            raise HTTPException(status_code=400, detail=url_error or "Invalid Teams meeting URL format")
        
        processing_progress[process_id] = {"progress": 10, "status": "processing", "message": "Downloading recordings from SharePoint..."}
        
        # Create temporary directory for downloads
        temp_dir = Path(tempfile.mkdtemp())
        
        # Search for recordings and transcripts (without downloading yet)
        try:
            meeting_id = sharepoint_downloader.extract_meeting_id_from_url(teams_url)
            user_id = sharepoint_downloader.extract_user_object_id_from_url(teams_url)
            token = sharepoint_downloader.get_app_token()
            
            # If meeting title is empty, search all recordings (no title filter)
            # Otherwise, search recordings filtered by meeting title
            if not meeting_title or not meeting_title.strip():
                # Search all recordings when meeting title is empty (pass None for meeting_title)
                # This will return all recordings without title filtering
                recordings_list = sharepoint_downloader.search_recordings_for_meeting(token, user_id, meeting_id, None)
                transcripts_list = sharepoint_downloader.search_transcripts_for_meeting(token, user_id, meeting_id, None)
            else:
                # Search recordings filtered by meeting title
                recordings_list = sharepoint_downloader.search_recordings_for_meeting(token, user_id, meeting_id, meeting_title)
                transcripts_list = sharepoint_downloader.search_transcripts_for_meeting(token, user_id, meeting_id, meeting_title)
            
            # If user provided selected indices, filter recordings to only selected ones
            if selected_recording_indices and recordings_list and selected_recording_indices.strip():
                try:
                    indices = [int(x.strip()) for x in selected_recording_indices.split(',')]
                    print(f"Filtering recordings: Selected indices: {indices}, Total recordings: {len(recordings_list)}")
                    # Filter to only selected recordings
                    filtered_recordings = [recordings_list[i] for i in indices if 0 <= i < len(recordings_list)]
                    print(f"Filtered to {len(filtered_recordings)} recording(s)")
                    recordings_list = filtered_recordings
                    
                    if not recordings_list:
                        raise HTTPException(status_code=400, detail="No valid recordings found for selected indices")
                except (ValueError, IndexError) as e:
                    raise HTTPException(status_code=400, detail=f"Invalid recording indices provided: {str(e)}")
        except ValueError as e:
            # Handle URL parsing errors
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": str(e)}
            raise HTTPException(status_code=400, detail=f"Invalid Teams meeting URL: {str(e)}")
        except Exception as e:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": f"Search failed: {str(e)}"}
            raise HTTPException(status_code=500, detail=f"Failed to search SharePoint: {str(e)}")
        
        # Ensure recordings_list is a list (not None)
        if recordings_list is None:
            recordings_list = []
        if transcripts_list is None:
            transcripts_list = []
        
        print(f"After filtering: recordings_list length = {len(recordings_list)}, selected_recording_indices = {selected_recording_indices}")
        
        # Check if we need user selection (multiple recordings found)
        # Only show selection modal if user hasn't already selected recordings
        has_selection = selected_recording_indices and selected_recording_indices.strip()
        print(f"has_selection = {has_selection}, len(recordings_list) = {len(recordings_list)}, prefer_transcript = {prefer_transcript}, transcripts_list length = {len(transcripts_list) if transcripts_list else 0}")
        
        if len(recordings_list) > 1 and not (prefer_transcript and transcripts_list) and not has_selection:
            print("Returning selection requirement to frontend")
            # Return recordings list for frontend selection
            processing_progress[process_id] = {"progress": 15, "status": "selection_required", "message": f"Found {len(recordings_list)} recordings. Please select which ones to process."}
            
            # Return recordings metadata for frontend selection
            from backend.models.schemas import RecordingMetadata
            recordings_metadata = []
            for i, rec in enumerate(recordings_list):
                try:
                    recordings_metadata.append(RecordingMetadata(
                        index=i,
                        name=rec.get('name', 'N/A') if isinstance(rec, dict) else str(rec.get('name', 'N/A')),
                        modified=rec.get('modified', '') if isinstance(rec, dict) else str(rec.get('modified', '')),
                        size=int(rec.get('size', 0)) if isinstance(rec, dict) else int(getattr(rec, 'size', 0)),
                        source=rec.get('source', 'Unknown') if isinstance(rec, dict) else str(getattr(rec, 'source', 'Unknown'))
                    ))
                except Exception as e:
                    print(f"Warning: Error creating RecordingMetadata for recording {i}: {e}")
                    # Create a basic metadata entry even if there's an error
                    recordings_metadata.append(RecordingMetadata(
                        index=i,
                        name=f"Recording {i+1}",
                        modified="",
                        size=0,
                        source="Unknown"
                    ))
            
            transcripts_metadata = []
            if transcripts_list:
                for t in transcripts_list:
                    try:
                        transcripts_metadata.append({
                            'name': t.get('name', 'N/A') if isinstance(t, dict) else str(getattr(t, 'name', 'N/A')),
                            'modified': t.get('modified', '') if isinstance(t, dict) else str(getattr(t, 'modified', ''))
                        })
                    except Exception:
                        transcripts_metadata.append({
                            'name': 'N/A',
                            'modified': ''
                        })
            
            # Return selection requirement (not an error - FastAPI will return 200 OK)
            # FastAPI automatically returns 200 OK for Pydantic models, but we ensure it's explicit
            response_data = ProcessTranscriptResponse(
                success=False,  # False because processing hasn't started yet
                message=f"Found {len(recordings_list)} recording(s). Please select which ones to process.",
                requires_selection=True,
                recordings=recordings_metadata,
                transcripts=transcripts_metadata if transcripts_metadata else None,
                process_id=process_id
            )
            # Return the response - FastAPI will serialize it as JSON with 200 status
            return response_data
        
        # If we get here, user has already selected recordings or there's only one recording
        # Continue with processing
        print(f"Continuing with processing: {len(recordings_list)} recording(s) to process")
        
        # Ensure recordings_list and transcripts_list are lists (not None)
        if recordings_list is None:
            recordings_list = []
        if transcripts_list is None:
            transcripts_list = []
        
        # Download recordings and transcripts (single recording or user already selected)
        try:
            # If single recording or transcript preferred, proceed with download
            if prefer_transcript and transcripts_list:
                # Download only transcripts
                recording_paths = []
                transcript_paths = []
                for trans in transcripts_list:
                    file_id = trans.get('id', '')
                    drive_id = trans.get('drive_id', '')
                    modified_date = trans.get('modified', '')
                    file_name = trans.get('name', 'transcript')
                    
                    ext = '.txt'
                    if '.' in file_name:
                        ext = '.' + file_name.split('.')[-1].lower()
                        if ext not in ['.vtt', '.txt', '.srt', '.transcript', '.json']:
                            ext = '.txt'
                    
                    datetime_str = sharepoint_downloader.format_datetime_for_filename(modified_date)
                    file_path = temp_dir / f"transcript_{datetime_str}{ext}"
                    
                    saved_path = sharepoint_downloader.download_file(token, file_id, file_path, drive_id, trans.get('download_url', ''))
                    if saved_path:
                        transcript_paths.append(saved_path)
            elif recordings_list:
                # Download selected recordings (or all if single)
                recording_paths = []
                for rec in recordings_list:
                    file_id = rec.get('id', '')
                    drive_id = rec.get('drive_id', '')
                    modified_date = rec.get('modified', '')
                    
                    datetime_str = sharepoint_downloader.format_datetime_for_filename(modified_date)
                    file_path = temp_dir / f"recording_{datetime_str}.mp4"
                    
                    saved_path = sharepoint_downloader.download_file(token, file_id, file_path, drive_id, rec.get('download_url', ''))
                    if saved_path:
                        recording_paths.append(saved_path)
                
                # Download transcripts if available
                transcript_paths = []
                for trans in transcripts_list:
                    file_id = trans.get('id', '')
                    drive_id = trans.get('drive_id', '')
                    modified_date = trans.get('modified', '')
                    file_name = trans.get('name', 'transcript')
                    
                    ext = '.txt'
                    if '.' in file_name:
                        ext = '.' + file_name.split('.')[-1].lower()
                        if ext not in ['.vtt', '.txt', '.srt', '.transcript', '.json']:
                            ext = '.txt'
                    
                    datetime_str = sharepoint_downloader.format_datetime_for_filename(modified_date)
                    file_path = temp_dir / f"transcript_{datetime_str}{ext}"
                    
                    saved_path = sharepoint_downloader.download_file(token, file_id, file_path, drive_id, trans.get('download_url', ''))
                    if saved_path:
                        transcript_paths.append(saved_path)
            else:
                recording_paths = []
                transcript_paths = []
        except Exception as e:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": f"Download failed: {str(e)}"}
            raise HTTPException(status_code=500, detail=f"Failed to download from SharePoint: {str(e)}")
        
        # Validate file sizes before processing
        processing_progress[process_id] = {
            "progress": 15, 
            "status": "processing", 
            "message": "Validating downloaded files..."
        }
        await asyncio.sleep(0)  # Yield control
        
        # Validate file sizes for all downloaded files (both transcripts and recordings)
        files_to_validate = []
        # Add transcripts to validation list
        if transcript_paths:
            files_to_validate.extend([(path, 'transcript') for path in transcript_paths])
        # Add recordings to validation list
        if recording_paths:
            files_to_validate.extend([(path, 'recording') for path in recording_paths])
        
        oversized_files = []
        for file_path, file_type in files_to_validate:
            if not file_path.exists():
                continue
            
            file_size = file_path.stat().st_size
            
            # Determine max size based on file type
            if file_type == 'transcript':
                max_size = MAX_TEXT_FILE_SIZE  # 10MB for text files
                max_size_mb = 10
            else:  # recording
                max_size = MAX_FILE_SIZE  # 500MB for audio/video files
                max_size_mb = 500
            
            if file_size > max_size:
                file_size_mb = file_size / (1024 * 1024)
                oversized_files.append({
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "file_type": file_type,
                    "file_size_mb": round(file_size_mb, 2),
                    "max_size_mb": max_size_mb
                })
        
        if oversized_files:
            file_list = "\n".join([
                f"  - {f['file_name']} ({f['file_type']}): {f['file_size_mb']} MB (max: {f['max_size_mb']} MB)"
                for f in oversized_files
            ])
            error_message = (
                f"One or more downloaded files exceed the maximum size limit:\n{file_list}\n\n"
                f"Maximum file sizes:\n"
                f"  - Recordings/Audio/Video: {MAX_FILE_SIZE / (1024 * 1024):.0f} MB\n"
                f"  - Transcripts/Text files: {MAX_TEXT_FILE_SIZE / (1024 * 1024):.0f} MB"
            )
            processing_progress[process_id] = {
                "progress": 0, 
                "status": "error", 
                "message": error_message
            }
            raise HTTPException(status_code=400, detail=error_message)
        
        # Process multiple recordings sequentially if multiple selected
        all_summaries = []
        total_files = len(files_to_validate)
        
        # Update progress before starting processing
        processing_progress[process_id] = {
            "progress": 20, 
            "status": "processing", 
            "message": f"Starting sequential processing of {total_files} file(s)..."
        }
        await asyncio.sleep(0)  # Yield control
        
        if total_files == 0:
            processing_progress[process_id] = {
                "progress": 0, 
                "status": "error", 
                "message": "No recordings or transcripts found for this meeting"
            }
            raise HTTPException(
                status_code=404, 
                detail="No recordings or transcripts found for this meeting. "
                       "Possible reasons:\n"
                       "- Recording may not be available yet (can take a few hours after meeting ends)\n"
                       "- Recording may be stored in a different location\n"
                       "- Meeting title may not match exactly\n"
                       "- Recording may have been deleted or moved"
            )
        
        # Process files sequentially (one after another)
        # Select which files to process based on preference
        files_to_process = []
        if prefer_transcript and transcript_paths:
            files_to_process = [(path, 'transcript') for path in transcript_paths]
        elif recording_paths:
            files_to_process = [(path, 'recording') for path in recording_paths]
        
        # Sort files by modification time (oldest first) to process in chronological order
        files_to_process.sort(key=lambda x: x[0].stat().st_mtime if x[0].exists() else 0)
        
        # Check for duplicates before processing
        storage = Storage()
        files_to_check = []
        duplicate_files = []
        
        for file_idx, (file_path, file_type) in enumerate(files_to_process):
            # Check if file has been processed before
            try:
                file_already_processed = storage.is_file_processed(str(file_path), project_name=project_name)
                if file_already_processed:
                    # Get existing meeting info
                    file_hash = storage.calculate_file_hash(str(file_path))
                    import sqlite3
                    db_conn = sqlite3.connect(storage.db_path)
                    cursor = db_conn.cursor()
                    cursor.execute('''
                        SELECT pf.meeting_id, m.meeting_title, m.meeting_date, m.project_name
                        FROM processed_files pf
                        LEFT JOIN meetings m ON pf.meeting_id = m.id
                        WHERE pf.file_hash = ? AND pf.project_name = ?
                        ORDER BY pf.processed_at DESC
                        LIMIT 1
                    ''', (file_hash, project_name))
                    result = cursor.fetchone()
                    db_conn.close()
                    
                    existing_info = {}
                    if result:
                        existing_info = {
                            "meeting_id": result[0],
                            "meeting_title": result[1],
                            "meeting_date": result[2],
                            "project_name": result[3]
                        }
                    
                    duplicate_files.append({
                        "file_path": str(file_path),
                        "file_type": file_type,
                        "file_idx": file_idx,
                        "existing_info": existing_info
                    })
                else:
                    files_to_check.append((file_path, file_type, file_idx))
            except Exception as e:
                print(f"Warning: Could not check for duplicate file {file_path}: {e}")
                # Continue processing if check fails
                files_to_check.append((file_path, file_type, file_idx))
        
        # If duplicates found, ask for confirmation
        if duplicate_files:
            duplicate_info = []
            for dup in duplicate_files:
                existing = dup['existing_info']
                file_name = Path(dup['file_path']).name
                if existing.get('meeting_title'):
                    existing_info_text = f"\n  - Meeting: {existing.get('meeting_title')}\n  - Date: {existing.get('meeting_date')}\n  - Project: {existing.get('project_name')}"
                else:
                    existing_info_text = "\n  - File was processed before (details not available)"
                duplicate_info.append(f"File {dup['file_idx'] + 1}: {file_name}{existing_info_text}")
            
            processing_progress[process_id] = {
                "progress": 15,
                "status": "confirmation_required",
                "message": f"Found {len(duplicate_files)} file(s) that were already processed. Please confirm if you want to process them again."
            }
            
            # Store pending confirmation with duplicate info
            pending_confirmations[process_id] = {
                "project_name": project_name,
                "files_to_check": files_to_check,  # Non-duplicate files
                "duplicate_files": duplicate_files,  # Duplicate files
                "all_files": files_to_process,  # All files (for reference)
                "total_files": total_files,
                "meeting_title": meeting_title,
                "meeting_date": meeting_date,
                "participants": form_participants,
                "skip_sync": skip_sync,
                "analyze_project": analyze_project,
                "teams_url": teams_url,
                "prefer_transcript": prefer_transcript,
                "is_duplicate": True,
                "temp_dir": str(temp_dir),
                "token": token
            }
            
            duplicate_prompt = f"Found {len(duplicate_files)} file(s) that were already processed:\n\n" + "\n\n".join(duplicate_info)
            duplicate_prompt += f"\n\nDo you want to:\n- Process them again (will create new meeting entries)?\n- Or skip these files and process only new ones?"
            
            return ProcessTranscriptResponse(
                success=False,
                message=f"Found {len(duplicate_files)} duplicate file(s). Please confirm if you want to process them again.",
                requires_confirmation=True,
                confirmation_prompt=duplicate_prompt,
                process_id=process_id
            )
        
        # No duplicates, proceed with processing all files
        # Process each file sequentially - one completes before next starts
        # Each recording goes through: Download -> Transcribe -> Summarize -> Action Items -> Confluence -> Database
        print(f"Starting sequential processing of {total_files} file(s)")
        for file_idx, (file_path, file_type) in enumerate(files_to_process):
            file_progress_start = int((file_idx / total_files) * 100)
            
            print(f"\n{'='*60}")
            print(f"Processing {file_type} {file_idx + 1} of {total_files}")
            print(f"{'='*60}")
            
            processing_progress[process_id] = {
                "progress": file_progress_start + 5, 
                "status": "processing", 
                "message": f"Processing {file_type} {file_idx + 1} of {total_files}: Starting transcription..."
            }
            await asyncio.sleep(0)  # Yield control to allow progress polling
            
            # Validate recording duration if it's a recording
            if file_type == 'recording':
                processing_progress[process_id] = {
                    "progress": file_progress_start + 8, 
                    "status": "processing", 
                    "message": f"Validating {file_type} {file_idx + 1} of {total_files}..."
                }
                await asyncio.sleep(0)  # Yield control
                is_valid_duration, duration_error = sharepoint_downloader.validate_recording_duration(file_path, min_duration_seconds=10.0)
                
                if not is_valid_duration:
                    processing_progress[process_id] = {
                        "progress": file_progress_start, 
                        "status": "error", 
                        "message": f"Recording {file_idx + 1} too short: {duration_error or 'Recording too short'}"
                    }
                    # Skip this recording and continue with next
                    print(f"Warning: Skipping recording {file_idx + 1} - {duration_error}")
                    continue
            
            tmp_file_path = str(file_path)
            
            # Update progress
            processing_progress[process_id] = {
                "progress": file_progress_start + 10, 
                "status": "processing", 
                "message": f"Processing {file_type} {file_idx + 1} of {total_files}..."
            }
            await asyncio.sleep(0)  # Yield control
            
            # Step 1: Process transcript/recording (sequential - waits for completion)
            # This converts recording to transcript or processes existing transcript
            try:
                print(f"  Step 1/5: Transcribing {file_type} {file_idx + 1}...")
                processor = TranscriptProcessor()
                transcript = processor.process_input(
                    project_name=project_name,
                    file_path=tmp_file_path,
                    file_type=None  # Auto-detect
                )
                
                if not transcript or not transcript.transcript_text:
                    print(f"  ✗ Warning: Failed to transcribe {file_type} {file_idx + 1} of {total_files}. Skipping...")
                    processing_progress[process_id] = {
                        "progress": file_progress_start + 15, 
                        "status": "processing", 
                        "message": f"Skipped {file_type} {file_idx + 1} of {total_files} (transcription failed). Continuing with next file..."
                    }
                    continue
                print(f"  ✓ Transcription complete for {file_type} {file_idx + 1}")
                await asyncio.sleep(0)  # Yield control after transcription
            except Exception as e:
                print(f"  ✗ Error transcribing {file_type} {file_idx + 1} of {total_files}: {e}. Skipping...")
                processing_progress[process_id] = {
                    "progress": file_progress_start + 15, 
                    "status": "processing", 
                    "message": f"Error transcribing {file_type} {file_idx + 1} of {total_files}. Continuing with next file..."
                }
                await asyncio.sleep(0)  # Yield control
                continue
            
            # Determine meeting datetime from file modification time or provided date
            meeting_datetime = None
            if meeting_date:
                try:
                    meeting_datetime = datetime.strptime(meeting_date, "%Y-%m-%d")
                except ValueError:
                    pass
            
            # Use file modification time if no date provided
            if not meeting_datetime and file_path.exists():
                try:
                    mod_time = file_path.stat().st_mtime
                    meeting_datetime = datetime.fromtimestamp(mod_time)
                except Exception:
                    pass
            
            if not meeting_datetime:
                meeting_datetime = datetime.now()
            
            # Determine meeting title
            final_meeting_title = meeting_title
            if not final_meeting_title:
                date_str = meeting_datetime.strftime("%Y-%m-%d %H:%M")
                final_meeting_title = f"{date_str} - meeting summary"
            
            # Add suffix for multiple recordings
            if total_files > 1:
                final_meeting_title = f"{final_meeting_title} ({file_idx + 1}/{total_files})"
            
            # Determine participants
            participant_list = []
            seen = set()
            for p in form_participants:
                if p.lower() not in seen:
                    participant_list.append(p)
                    seen.add(p.lower())
            
            # Add participants from transcript if available
            if transcript.participants:
                for p in transcript.participants:
                    if p.lower() not in seen:
                        participant_list.append(p)
                        seen.add(p.lower())
            
            # Copy file to organized directory
            uploaded_file_path = processor.copy_uploaded_file(
                tmp_file_path,
                project_name,
                meeting_datetime
            )
            
            # Get original file name for tracking
            original_file_name = Path(file_path).name if file_path else None
            
            # Save transcript
            processor.save_transcript(transcript, meeting_datetime)
            
            # Step 2: Generate summary from transcript
            processing_progress[process_id] = {
                "progress": file_progress_start + 40, 
                "status": "processing", 
                "message": f"Step 2/5: Generating summary for {file_type} {file_idx + 1} of {total_files}..."
            }
            await asyncio.sleep(0)  # Yield control
            print(f"  Step 2/5: Generating summary for {file_type} {file_idx + 1}...")
            summarizer = MeetingSummarizer()
            summary = summarizer.summarize(
                transcript=transcript,
                meeting_title=final_meeting_title,
                meeting_date=meeting_datetime,
                participants=participant_list
            )
            
            if not summary:
                print(f"  ✗ Warning: Failed to generate summary for {file_type} {file_idx + 1} of {total_files}. Skipping...")
                processing_progress[process_id] = {
                    "progress": file_progress_start + 45, 
                    "status": "processing", 
                    "message": f"Summary generation failed for {file_type} {file_idx + 1} of {total_files}. Continuing with next file..."
                }
                continue
            print(f"  ✓ Summary generated for {file_type} {file_idx + 1}")
            await asyncio.sleep(0)  # Yield control after summary
            
            # Handle missing owners
            summary = handle_missing_owners(summary, project_name)
            
            # Step 3: Sync action items to Trello
            processing_progress[process_id] = {
                "progress": file_progress_start + 60, 
                "status": "processing", 
                "message": f"Step 3/5: Adding action items to Trello for {file_type} {file_idx + 1} of {total_files}..."
            }
            await asyncio.sleep(0)  # Yield control
            print(f"  Step 3/5: Adding action items to Trello for {file_type} {file_idx + 1}...")
            trello_synced = False
            if not skip_sync:
                try:
                    action_manager = ActionItemManager()
                    summary.all_action_items = action_manager.sync_action_items(
                        summary.all_action_items,
                        project_name,
                        final_meeting_title
                    )
                    trello_synced = len([item for item in summary.all_action_items if item.external_id]) > 0
                    print(f"  ✓ Action items synced to Trello for {file_type} {file_idx + 1}")
                    await asyncio.sleep(0)  # Yield control
                except Exception as e:
                    print(f"  ✗ Warning: Trello sync failed for {file_type} {file_idx + 1}: {e}")
            
            # Step 4: Store in Confluence knowledge base
            processing_progress[process_id] = {
                "progress": file_progress_start + 70, 
                "status": "processing", 
                "message": f"Step 4/5: Adding Confluence page for {file_type} {file_idx + 1} of {total_files}..."
            }
            await asyncio.sleep(0)  # Yield control
            print(f"  Step 4/5: Adding Confluence page for {file_type} {file_idx + 1}...")
            kb_url = None
            confluence_stored = False
            if not skip_sync:
                try:
                    kb = KnowledgeBase()
                    kb_url = kb.store_summary(summary, uploaded_file_path=uploaded_file_path)
                    confluence_stored = bool(kb_url)
                    print(f"  ✓ Confluence page created for {file_type} {file_idx + 1}")
                except Exception as e:
                    print(f"  ✗ Warning: Confluence storage failed for {file_type} {file_idx + 1}: {e}")
            
            # Store Confluence URL and original file name in summary metadata
            if not summary.metadata:
                summary.metadata = {}
            if kb_url:
                summary.metadata['confluence_url'] = kb_url
            if teams_url:
                summary.metadata['teams_url'] = teams_url
            if original_file_name:
                summary.metadata['original_file_name'] = original_file_name
            
            # Check if meeting is empty (no meaningful content)
            is_empty_meeting = _is_empty_meeting(summary)
            summary.metadata['is_empty_meeting'] = is_empty_meeting
            
            # Step 5: Save to database
            processing_progress[process_id] = {
                "progress": file_progress_start + 80, 
                "status": "processing", 
                "message": f"Step 5/5: Saving {file_type} {file_idx + 1} of {total_files} to database..."
            }
            await asyncio.sleep(0)  # Yield control
            print(f"  Step 5/5: Saving {file_type} {file_idx + 1} to database...")
            
            storage = Storage()
            summary_id = storage.save_summary(summary)
            storage.mark_file_processed(
                file_path=uploaded_file_path,
                project_name=project_name,
                meeting_id=summary_id,
                trello_synced=trello_synced,
                confluence_stored=confluence_stored
            )
            print(f"  ✓ {file_type} {file_idx + 1} saved to database (ID: {summary_id})")
            print(f"  ✓ Completed processing {file_type} {file_idx + 1} of {total_files}\n")
            await asyncio.sleep(0)  # Yield control after completing this file
            
            all_summaries.append({
                'summary': summary,
                'summary_id': summary_id,
                'summary_response': SummaryResponse(
                    id=summary.id,
                    project_name=summary.project_name,
                    meeting_title=summary.meeting_title,
                    meeting_date=summary.meeting_date,
                    meeting_type=summary.meeting_type,
                    participants=summary.participants,
                    duration_minutes=summary.duration_minutes,
                    overall_summary=summary.overall_summary,
                    action_items_count=len(summary.all_action_items),
                    decisions_count=len(summary.all_decisions),
                    risks_count=len(summary.all_risks),
                    tags=summary.tags,
                    transcript_path=summary.transcript_path,
                    created_at=summary.created_at
                )
            })
        
        # Check if any files were successfully processed
        if not all_summaries:
            raise HTTPException(
                status_code=400, 
                detail=f"No recordings could be processed successfully out of {total_files} file(s). All files failed processing."
            )
        
        # Multi-meeting analysis if requested (run after ALL recordings are processed sequentially)
        if analyze_project and len(all_summaries) > 0:
            processing_progress[process_id] = {
                "progress": 95, 
                "status": "processing", 
                "message": f"All {len(all_summaries)} file(s) processed sequentially. Running multi-meeting analysis..."
            }
            try:
                analyzer = MultiMeetingAnalyzer()
                analyzer.analyze_project_meetings(project_name, days_back=90)
            except Exception as e:
                print(f"Warning: Multi-meeting analysis failed: {e}")
        
        # Update progress: Complete (100%) - all selected files processed sequentially
        success_count = len(all_summaries)
        failed_count = total_files - success_count
        completion_message = f"Sequential processing complete. Successfully processed {success_count} of {total_files} file(s)."
        if failed_count > 0:
            completion_message += f" {failed_count} file(s) were skipped due to errors."
        
        processing_progress[process_id] = {
            "progress": 100, 
            "status": "completed", 
            "message": completion_message
        }
        
        # Return all summaries (not just the latest)
        all_summary_responses = [s['summary_response'] for s in all_summaries]
        all_summary_ids = [s['summary_id'] for s in all_summaries]
        
        # Also include the latest summary for backward compatibility
        latest_summary_data = max(all_summaries, key=lambda x: x['summary'].meeting_date)
        
        return ProcessTranscriptResponse(
            success=True,
            message=f"Successfully processed {len(all_summaries)} recording(s) from SharePoint",
            summary=latest_summary_data['summary_response'],  # Latest for backward compatibility
            summaries=all_summary_responses,  # All summaries
            summary_id=latest_summary_data['summary_id'],  # Latest ID for backward compatibility
            summary_ids=all_summary_ids,  # All summary IDs
            process_id=process_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if process_id:
            processing_progress[process_id] = {"progress": 0, "status": "error", "message": f"Error: {str(e)}"}
        raise HTTPException(status_code=500, detail=f"Error processing SharePoint URL: {str(e)}")
    
    finally:
        # Clean up temporary files
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except Exception:
                pass
        
        # Clean up temp directory
        if temp_dir and temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass
        
        # Schedule progress cleanup
        if process_id:
            _ = asyncio.create_task(cleanup_progress(process_id))
    
def _is_empty_meeting(summary: MeetingSummary) -> bool:
    """Check if a meeting is empty (no meaningful content)"""
    # Check if transcript text is empty or very short
    if not summary.overall_summary or len(summary.overall_summary.strip()) < 20:
        return True
    
    # Check if there are no action items, decisions, or risks
    if (len(summary.all_action_items) == 0 and 
        len(summary.all_decisions) == 0 and 
        len(summary.all_risks) == 0):
        return True
    
    # Check if overall summary is just placeholder text
    placeholder_texts = [
        "no summary available",
        "meeting summary",
        "summary not available",
        "no content",
        "empty meeting"
    ]
    summary_lower = summary.overall_summary.lower().strip()
    if any(placeholder in summary_lower for placeholder in placeholder_texts):
        if len(summary.all_action_items) == 0:
            return True
    
    return False

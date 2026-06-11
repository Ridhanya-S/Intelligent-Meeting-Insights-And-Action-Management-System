"""
Summary API Endpoints
"""
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.core.storage import Storage
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.integrations.knowledge_base import KnowledgeBase
from backend.models.schemas import SummaryResponse, ActionItemResponse
from backend.security import BearerTokenAuth

router = APIRouter()


@router.get("/{summary_id}", response_model=SummaryResponse, dependencies=[BearerTokenAuth])
async def get_summary(summary_id: str, full_details: bool = False):
    """Get a meeting summary by ID"""
    storage = Storage()
    summary = storage.get_summary(summary_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    # Get Confluence URL from metadata
    confluence_url = summary.metadata.get('confluence_url') if summary.metadata else None
    
    # Get Trello board URL
    trello_board_url = None
    if summary.all_action_items and any(item.external_id for item in summary.all_action_items):
        try:
            action_manager = ActionItemManager()
            board_id = action_manager._get_or_create_board(summary.project_name)
            if board_id and action_manager.trello_client:
                trello_board_url = f"https://trello.com/b/{board_id}"
        except Exception:
            # Trello board URL is optional, continue without it
            pass
    
    # Convert action items to response format
    action_items_response = None
    if full_details:
        action_items_response = [
            ActionItemResponse(
                id=item.id,
                description=item.description,
                owner=item.owner,
                deadline=item.deadline,
                status=item.status.value,
                dependencies=item.dependencies,
                tags=item.tags,
                external_id=item.external_id
            )
            for item in summary.all_action_items
        ]
        
        # Convert decisions and risks to dict format
        decisions_response = [
            {
                "id": d.id,
                "description": d.description,
                "context": d.context,
                "decision_makers": d.decision_makers,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None
            }
            for d in summary.all_decisions
        ]
        
        risks_response = [
            {
                "id": r.id,
                "description": r.description,
                "severity": r.severity,
                "impact": r.impact,
                "mitigation": r.mitigation,
                "owner": r.owner
            }
            for r in summary.all_risks
        ]
    else:
        decisions_response = None
        risks_response = None
    
    return SummaryResponse(
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
        created_at=summary.created_at,
        all_action_items=action_items_response,
        all_decisions=decisions_response,
        all_risks=risks_response,
        confluence_url=confluence_url,
        trello_board_url=trello_board_url
    )


@router.get("/project/{project_name}", response_model=List[SummaryResponse], dependencies=[BearerTokenAuth])
async def get_project_summaries(project_name: str, limit: Optional[int] = 50):
    """Get all summaries for a project"""
    storage = Storage()
    meeting_ids = storage.get_project_meetings(project_name, limit=limit)
    
    summaries = []
    for meeting_id in meeting_ids:
        summary = storage.get_summary(meeting_id)
        if summary:
            summaries.append(SummaryResponse(
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
            ))
    
    return summaries


@router.delete("/{summary_id}", response_model=Dict[str, Any], dependencies=[BearerTokenAuth])
async def delete_summary(summary_id: str, confirm: bool = False):
    """
    Delete a meeting summary and all its resources.
    
    Requires confirmation flag to be True.
    Deletes:
    - Trello cards associated with the meeting
    - Confluence page for the meeting
    - Database records (meeting, action items, processed files)
    - Meeting files (transcript, summary JSON)
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Deletion requires confirmation. Set confirm=true")
    
    storage = Storage()
    
    # Check if meeting exists
    summary = storage.get_summary(summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Meeting '{summary_id}' not found")
    
    project_name = summary.project_name
    
    results = {
        'meeting_id': summary_id,
        'project_name': project_name,
        'trello': {'cards': 0},
        'confluence': {'page_deleted': False},
        'database': {'meetings': 0, 'action_items': 0, 'processed_files': 0},
        'files': {
            'summary_deleted': False, 
            'transcript_deleted': False,
            'directory_deleted': False,
            'uploaded_files_deleted': 0
        }
    }
    
    try:
        # Delete Trello cards
        try:
            action_manager = ActionItemManager()
            cards_deleted = action_manager.delete_meeting_trello_cards(summary_id, project_name)
            results['trello']['cards'] = cards_deleted
        except Exception as e:
            print(f"Warning: Error deleting Trello cards: {e}")
        
        # Delete Confluence page
        try:
            kb = KnowledgeBase()
            page_deleted = kb.delete_meeting_confluence_page(summary_id, project_name)
            results['confluence']['page_deleted'] = page_deleted
        except Exception as e:
            print(f"Warning: Error deleting Confluence page: {e}")
        
        # Delete database records and files
        try:
            db_results = storage.delete_meeting(summary_id)
            results['database'] = db_results
            
            # Verify files and directory deletion status
            files_deleted = True
            if summary.transcript_path and Path(summary.transcript_path).exists():
                files_deleted = False
                results['files']['transcript_deleted'] = False
            else:
                results['files']['transcript_deleted'] = True
                
            if summary.summary_path and Path(summary.summary_path).exists():
                files_deleted = False
                results['files']['summary_deleted'] = False
            else:
                results['files']['summary_deleted'] = True
            
            # Check if meeting directory was deleted
            if summary.summary_path:
                meeting_dir = Path(summary.summary_path).parent
                if meeting_dir.exists():
                    results['files']['directory_deleted'] = False
                    results['files']['directory_path'] = str(meeting_dir)
                else:
                    results['files']['directory_deleted'] = True
            else:
                results['files']['directory_deleted'] = True
                
        except Exception as e:
            print(f"Warning: Error deleting database records: {e}")
            import traceback
            traceback.print_exc()
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting meeting: {str(e)}")


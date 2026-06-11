"""
Action Items API Endpoints
"""
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.core.storage import Storage
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.models import ActionItemStatus
from backend.models.schemas import ActionItemResponse
from backend.security import BearerTokenAuth

router = APIRouter()


@router.get("/", response_model=List[ActionItemResponse], dependencies=[BearerTokenAuth])
async def get_action_items(
    owner: Optional[str] = None,
    status: Optional[str] = None,
    project_name: Optional[str] = None
):
    """
    Get action items with optional filters.
    
    Args:
        owner: Filter by owner name (optional)
        status: Filter by status (new, pending, doing, done, blocked) (optional)
        project_name: Filter by project name (optional)
    
    Returns:
        List of action items matching the filters
    """
    storage = Storage()
    
    # Parse status enum if provided
    status_enum = None
    if status:
        try:
            status_enum = ActionItemStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}. Valid values: new, pending, doing, done, blocked")
    
    # Get action items with all filters applied at database level
    # Project name filtering is case-insensitive at database level
    items = storage.get_action_items_by_owner(
        owner=owner or "",
        status=status_enum,
        project_name=project_name.strip() if project_name else None
    )
    
    # Debug logging
    print(f"DEBUG: Found {len(items)} action items with filters: owner={owner}, status={status}, project_name={project_name}")
    
    # Convert to response format
    result_items = []
    for item in items:
        try:
            result_items.append(
                ActionItemResponse(
                    id=item["id"],
                    description=item["description"],
                    owner=item["owner"],
                    deadline=item["deadline"],
                    status=item["status"].value if hasattr(item["status"], "value") else str(item["status"]),
                    dependencies=item.get("dependencies", []),
                    tags=item.get("tags", []),
                    external_id=item.get("external_id")
                )
            )
        except Exception as e:
            # Log error but continue processing other items
            print(f"Warning: Error converting action item {item.get('id', 'unknown')} to response: {e}")
            continue
    
    return result_items


@router.post("/send-reminders", dependencies=[BearerTokenAuth])
async def send_reminders():
    """
    Manually trigger sending reminders for action items due within 24 hours.
    
    Note: Reminders are also sent automatically in the background if REMINDER_AUTO_SEND is enabled.
    This endpoint allows manual triggering for testing or immediate sending.
    """
    try:
        action_manager = ActionItemManager()
        results = action_manager.send_all_pending_reminders()
        
        return {
            "success": True,
            "total": results["total"],
            "sent": results["sent"],
            "failed": results["failed"],
            "message": f"Reminders sent: {results['sent']}, Failed: {results['failed']}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending reminders: {str(e)}")


@router.get("/reminder-status", dependencies=[BearerTokenAuth])
async def get_reminder_status():
    """Get reminder system status and configuration"""
    from backend.meeting_summarizer.config import Config
    
    return {
        "reminder_enabled": Config.REMINDER_ENABLED,
        "auto_send_enabled": Config.REMINDER_AUTO_SEND,
        "check_interval_minutes": Config.REMINDER_CHECK_INTERVAL_MINUTES,
        "days_before_deadline": Config.REMINDER_DAYS_BEFORE,
        "smtp_configured": bool(Config.SMTP_SERVER and Config.SMTP_USERNAME and Config.SMTP_PASSWORD)
    }


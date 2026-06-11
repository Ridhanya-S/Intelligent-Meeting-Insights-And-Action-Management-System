"""
Projects API Endpoints
"""
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# Add backend directory to Python path
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from backend.meeting_summarizer.core.storage import Storage
from backend.meeting_summarizer.config import Config
from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
from backend.meeting_summarizer.integrations.knowledge_base import KnowledgeBase
from backend.models.schemas import ProjectInfo
from backend.security import BearerTokenAuth

router = APIRouter()


class CreateProjectRequest(BaseModel):
    """Request model for creating a project"""
    project_name: str


def _normalize_project_name(name: str) -> str:
    """
    Normalize project name to avoid case sensitivity issues.
    Uses title case for consistency.
    """
    if not name:
        return ""
    # Convert to title case (first letter of each word capitalized)
    return name.strip().title()


@router.get("", response_model=List[ProjectInfo], include_in_schema=True, dependencies=[BearerTokenAuth])
async def get_projects():
    """Get list of all projects (normalized names)"""
    projects = []
    data_dir = Config.DATA_DIR
    
    if not data_dir.exists():
        return []
    
    # Track normalized names to avoid duplicates
    seen_names = set()
    
    # Scan data directory for project folders
    for project_dir in data_dir.iterdir():
        if project_dir.is_dir() and project_dir.name != "__pycache__":
            project_name = project_dir.name
            normalized_name = _normalize_project_name(project_name)
            
            # Skip if we've already seen this normalized name
            if normalized_name.lower() in seen_names:
                continue
            
            seen_names.add(normalized_name.lower())
            
            # Count meetings
            meeting_count = 0
            latest_date = None
            
            for meeting_dir in project_dir.iterdir():
                if meeting_dir.is_dir():
                    summary_file = meeting_dir / "summary.json"
                    if summary_file.exists():
                        meeting_count += 1
                        try:
                            import json
                            with open(summary_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                meeting_date_str = data.get("meeting_date")
                                if meeting_date_str:
                                    meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
                                    if latest_date is None or meeting_date > latest_date:
                                        latest_date = meeting_date
                        except Exception:
                            pass
            
            projects.append(ProjectInfo(
                name=normalized_name,  # Return normalized name
                meeting_count=meeting_count,
                latest_meeting_date=latest_date
            ))
    
    return sorted(projects, key=lambda p: p.latest_meeting_date or datetime.min, reverse=True)


@router.post("", response_model=ProjectInfo, include_in_schema=True, dependencies=[BearerTokenAuth])
async def create_project(request: CreateProjectRequest):
    """Create a new project (normalizes the name)"""
    project_name = request.project_name.strip()
    
    if not project_name:
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
    
    normalized_name = _normalize_project_name(project_name)
    
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Project name cannot be empty after normalization")
    
    # Check if project already exists (case-insensitive)
    data_dir = Config.DATA_DIR
    meeting_count = 0
    latest_date = None
    
    if data_dir.exists():
        for project_dir in data_dir.iterdir():
            if project_dir.is_dir() and project_dir.name != "__pycache__":
                existing_normalized = _normalize_project_name(project_dir.name)
                if existing_normalized.lower() == normalized_name.lower():
                    # Project already exists, count meetings and return it
                    for meeting_dir in project_dir.iterdir():
                        if meeting_dir.is_dir():
                            summary_file = meeting_dir / "summary.json"
                            if summary_file.exists():
                                meeting_count += 1
                                try:
                                    import json
                                    with open(summary_file, 'r') as f:
                                        data = json.load(f)
                                        meeting_date_str = data.get("meeting_date")
                                        if meeting_date_str:
                                            meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
                                            if latest_date is None or meeting_date > latest_date:
                                                latest_date = meeting_date
                                except:
                                    pass
                    
                    return ProjectInfo(
                        name=normalized_name,
                        meeting_count=meeting_count,
                        latest_meeting_date=latest_date
                    )
    
    # Create project directory
    project_dir = data_dir / normalized_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    return ProjectInfo(
        name=normalized_name,
        meeting_count=0,
        latest_meeting_date=None
    )


class DeleteProjectRequest(BaseModel):
    """Request model for deleting a project"""
    confirm: bool = Field(..., description="Confirmation flag - must be True to delete")


@router.delete("/{project_name}", response_model=Dict[str, Any], dependencies=[BearerTokenAuth])
async def delete_project(project_name: str, confirm: bool = False):
    """
    Delete a project and all its resources.
    
    Requires confirmation flag to be True.
    Deletes:
    - All Trello boards, lists, and cards
    - All Confluence pages
    - All database records (meetings, action items, etc.)
    - Project directory
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Deletion requires confirmation. Set confirm=true")
    
    normalized_name = _normalize_project_name(project_name)
    
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Invalid project name")
    
    # Check if project exists
    data_dir = Config.DATA_DIR
    project_dir = data_dir / normalized_name
    
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{normalized_name}' not found")
    
    results = {
        'project_name': normalized_name,
        'trello': {'boards': 0, 'lists': 0, 'cards': 0},
        'confluence': {'pages': 0, 'spaces': 0},
        'database': {'meetings': 0, 'action_items': 0, 'processed_files': 0, 'email_mappings': 0},
        'files': False
    }
    
    try:
        # Delete Trello resources (including board deletion)
        try:
            action_manager = ActionItemManager()
            trello_results = action_manager.delete_project_trello_resources(normalized_name)
            results['trello'] = trello_results
            if trello_results.get('boards', 0) > 0:
                print(f"✓ Successfully archived {trello_results['boards']} Trello board(s) for project: {normalized_name}")
            elif trello_results.get('boards', 0) == 0:
                print(f"  No Trello board found to archive for project: {normalized_name}")
        except Exception as e:
            print(f"Warning: Error deleting Trello resources: {e}")
            import traceback
            traceback.print_exc()
        
        # Delete Confluence resources
        try:
            kb = KnowledgeBase()
            confluence_results = kb.delete_project_confluence_resources(normalized_name)
            results['confluence'] = confluence_results
        except Exception as e:
            print(f"Warning: Error deleting Confluence resources: {e}")
        
        # Delete database records
        try:
            storage = Storage()
            db_results = storage.delete_project(normalized_name)
            results['database'] = db_results
        except Exception as e:
            print(f"Warning: Error deleting database records: {e}")
        
        # Delete project directory
        try:
            import shutil
            shutil.rmtree(project_dir)
            results['files'] = True
        except Exception as e:
            print(f"Warning: Error deleting project directory: {e}")
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting project: {str(e)}")


@router.post("/{project_name}/extract-emails", dependencies=[BearerTokenAuth])
async def extract_project_emails(project_name: str):
    """
    Extract email addresses from Trello and Confluence for a project.
    """
    normalized_name = _normalize_project_name(project_name)
    
    results = {
        'project_name': normalized_name,
        'total': 0,
        'trello': 0,
        'confluence': 0
    }
    
    try:
        # Extract from Trello (includes project owner)
        try:
            action_manager = ActionItemManager()
            trello_count = action_manager.update_email_mappings_from_trello(normalized_name)
            results['trello'] = trello_count
        except Exception as e:
            print(f"Warning: Error extracting Trello emails: {e}")
        
        # Extract from Confluence (includes project owner)
        try:
            kb = KnowledgeBase()
            confluence_count = kb.update_email_mappings_from_confluence(normalized_name)
            results['confluence'] = confluence_count
        except Exception as e:
            print(f"Warning: Error extracting Confluence emails: {e}")
        
        # Ensure project owner is included (from config)
        try:
            from backend.meeting_summarizer.config import Config
            storage = Storage()
            if Config.PROJECT_OWNER_NAME and Config.PROJECT_OWNER_EMAIL:
                # Check if already saved, if not save it
                existing_email = storage.get_email_mapping(Config.PROJECT_OWNER_NAME)
                if not existing_email or existing_email != Config.PROJECT_OWNER_EMAIL:
                    storage.save_email_mapping(
                        Config.PROJECT_OWNER_NAME,
                        Config.PROJECT_OWNER_EMAIL,
                        'config',
                        normalized_name
                    )
                    # Increment total if it was newly added
                    if not existing_email:
                        results['total'] += 1
        except Exception as e:
            print(f"Warning: Error adding project owner email: {e}")
        
        results['total'] = results['trello'] + results['confluence']
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting emails: {str(e)}")


@router.post("/{project_name}/sync-confluence", dependencies=[BearerTokenAuth])
async def sync_confluence_pages(project_name: str):
    """
    Sync Confluence pages - remove from DB if deleted in Confluence UI.
    """
    normalized_name = _normalize_project_name(project_name)
    
    try:
        kb = KnowledgeBase()
        results = kb.sync_confluence_pages(normalized_name)
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing Confluence pages: {str(e)}")


@router.get("/{project_name}/email-mappings", dependencies=[BearerTokenAuth])
async def get_project_email_mappings(project_name: str):
    """
    Get all email mappings for a project.
    """
    normalized_name = _normalize_project_name(project_name)
    
    try:
        storage = Storage()
        mappings = storage.get_all_email_mappings(normalized_name)
        return {'project_name': normalized_name, 'mappings': mappings}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting email mappings: {str(e)}")


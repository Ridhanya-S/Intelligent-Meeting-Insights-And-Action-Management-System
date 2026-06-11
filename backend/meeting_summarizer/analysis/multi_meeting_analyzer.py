"""
Multi-Meeting Intelligence Module
Analyzes patterns across multiple meetings
"""
import json
from typing import List, Dict, Any
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from ..config import Config


class MultiMeetingAnalyzer:
    """Analyze patterns across multiple meetings"""
    
    def __init__(self):
        """Initialize analyzer"""
    
    def analyze_project_meetings(
        self,
        project_name: str,
        days_back: int = 90
    ) -> Dict[str, Any]:
        """
        Analyze all meetings for a project
        
        Args:
            project_name: Name of the project
            days_back: Number of days to look back
        
        Returns:
            Analysis results
        """
        # Load all meetings for the project
        meetings = self._load_project_meetings(project_name, days_back)
        
        if not meetings:
            return {
                "project": project_name,
                "total_meetings": 0,
                "message": "No meetings found"
            }
        
        # Sort meetings by date (oldest first) for proper chronological analysis
        meetings.sort(key=lambda m: m.get("_parsed_date", m.get("meeting_date", "")))
        
        # Perform various analyses
        analysis = {
            "project": project_name,
            "total_meetings": len(meetings),
            "date_range": {
                "start": min(m.get("_parsed_date", m.get("meeting_date", "")) for m in meetings) if meetings else "",
                "end": max(m.get("_parsed_date", m.get("meeting_date", "")) for m in meetings) if meetings else ""
            },
            "recurring_themes": self._find_recurring_themes(meetings),
            "unresolved_action_items": self._find_unresolved_action_items(meetings),
            "action_item_trends": self._analyze_action_item_trends(meetings),
            "participant_engagement": self._analyze_participant_engagement(meetings),
            "suggested_agenda_items": self._suggest_agenda_items(meetings)
        }
        
        return analysis
    
    def _load_project_meetings(
        self,
        project_name: str,
        days_back: int
    ) -> List[Dict[str, Any]]:
        """Load all meetings for a project within date range"""
        meetings = []
        project_dir = Config.DATA_DIR / project_name
        
        if not project_dir.exists():
            return meetings
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Search in all meeting subdirectories
        summary_files = []
        for meeting_dir in project_dir.iterdir():
            if meeting_dir.is_dir():
                summary_file = meeting_dir / "summary.json"
                if summary_file.exists():
                    summary_files.append(summary_file)
        
        for file_path in summary_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Parse meeting date with timezone awareness
                meeting_date_str = data.get("meeting_date")
                meeting_date = None
                
                if isinstance(meeting_date_str, str):
                    try:
                        # Try ISO format with timezone (e.g., "2024-12-07T21:34:09+00:00")
                        if '+' in meeting_date_str or meeting_date_str.endswith('Z'):
                            meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
                        else:
                            # Try ISO format without timezone (assume UTC)
                            meeting_date = datetime.fromisoformat(meeting_date_str)
                            # Make it timezone-aware (UTC)
                            from datetime import timezone
                            meeting_date = meeting_date.replace(tzinfo=timezone.utc)
                    except ValueError:
                        # Try alternative format
                        try:
                            meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%dT%H:%M:%S")
                            from datetime import timezone
                            meeting_date = meeting_date.replace(tzinfo=timezone.utc)
                        except ValueError:
                            try:
                                # Try date-only format
                                meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d")
                                from datetime import timezone
                                meeting_date = meeting_date.replace(tzinfo=timezone.utc)
                            except ValueError:
                                continue
                elif isinstance(meeting_date_str, dict):
                    # Handle datetime object serialized as dict
                    try:
                        meeting_date = datetime.fromisoformat(meeting_date_str.get('iso', ''))
                    except (ValueError, AttributeError):
                        continue
                else:
                    continue
                
                # Ensure timezone-aware comparison
                if meeting_date.tzinfo is None:
                    from datetime import timezone
                    meeting_date = meeting_date.replace(tzinfo=timezone.utc)
                
                # Compare with timezone-aware cutoff date
                if cutoff_date.tzinfo is None:
                    from datetime import timezone
                    cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
                
                if meeting_date >= cutoff_date:
                    data["_file_path"] = str(file_path)
                    data["_meeting_dir"] = str(file_path.parent)  # Store meeting directory path
                    data["_parsed_date"] = meeting_date.isoformat()  # Store parsed date for sorting
                    meetings.append(data)
            except Exception as e:
                print(f"Warning: Could not load meeting {file_path}: {e}")
        
        return meetings
    
    def _find_recurring_themes(
        self,
        meetings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find themes that appear in multiple meetings"""
        theme_counter = Counter()
        theme_meetings = defaultdict(list)
        
        for meeting in meetings:
            # Extract themes from agenda topics
            for topic in meeting.get("agenda_topics", []):
                topic_name = topic.get("topic", "").lower()
                if topic_name:
                    theme_counter[topic_name] += 1
                    theme_meetings[topic_name].append({
                        "meeting_title": meeting.get("meeting_title"),
                        "meeting_date": meeting.get("meeting_date")
                    })
        
        # Find themes that appear in 2+ meetings
        recurring = []
        for theme, count in theme_counter.most_common():
            if count >= 2:
                recurring.append({
                    "theme": theme,
                    "frequency": count,
                    "meetings": theme_meetings[theme]
                })
        
        return recurring
    
    def _find_unresolved_action_items(
        self,
        meetings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find action items that are still pending across meetings"""
        all_action_items = []
        
        for meeting in meetings:
            for item in meeting.get("all_action_items", []):
                status = item.get("status", "new")
                if status in ["new", "pending", "doing", "blocked"]:
                    item_copy = item.copy()
                    item_copy["meeting_title"] = meeting.get("meeting_title")
                    item_copy["meeting_date"] = meeting.get("meeting_date")
                    all_action_items.append(item_copy)
        
        # Group by owner and description similarity
        unresolved = []
        seen_items = set()
        
        for item in all_action_items:
            # Create a key for deduplication
            key = (item.get("owner", "").lower(), item.get("description", "").lower()[:50])
            
            if key not in seen_items:
                seen_items.add(key)
                unresolved.append({
                    "description": item.get("description"),
                    "owner": item.get("owner"),
                    "deadline": item.get("deadline"),
                    "status": item.get("status"),
                    "first_mentioned": item.get("meeting_date"),
                    "meeting_title": item.get("meeting_title")
                })
        
        return unresolved
    
    def _analyze_action_item_trends(
        self,
        meetings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze trends in action items"""
        trends = {
            "total_action_items": 0,
            "new": 0,
            "pending": 0,
            "doing": 0,
            "done": 0,
            "blocked": 0,
            "overdue": 0,
            "by_owner": defaultdict(int),
            "completion_rate": 0.0
        }
        
        now = datetime.now()
        
        for meeting in meetings:
            for item in meeting.get("all_action_items", []):
                trends["total_action_items"] += 1
                status = item.get("status", "new")
                
                if status == "new":
                    trends["new"] += 1
                elif status == "pending":
                    trends["pending"] += 1
                elif status == "doing":
                    trends["doing"] += 1
                elif status == "done":
                    trends["done"] += 1
                elif status == "blocked":
                    trends["blocked"] += 1
                
                # Check if overdue
                deadline_str = item.get("deadline")
                if deadline_str and status != "done":
                    try:
                        deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
                        if deadline < now:
                            trends["overdue"] += 1
                    except (ValueError, TypeError):
                        pass
                
                # Count by owner
                owner = item.get("owner", "Unassigned")
                trends["by_owner"][owner] += 1
        
        # Calculate completion rate
        if trends["total_action_items"] > 0:
            trends["completion_rate"] = trends["done"] / trends["total_action_items"]
        
        trends["by_owner"] = dict(trends["by_owner"])
        
        return trends
    
    def _analyze_participant_engagement(
        self,
        meetings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze participant engagement across meetings"""
        participant_meetings = defaultdict(int)
        participant_action_items = defaultdict(int)
        
        for meeting in meetings:
            participants = meeting.get("participants", [])
            for participant in participants:
                participant_meetings[participant] += 1
            
            # Count action items per participant
            for item in meeting.get("all_action_items", []):
                owner = item.get("owner", "")
                if owner:
                    participant_action_items[owner] += 1
        
        engagement = {
            "most_active_participants": sorted(
                participant_meetings.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "action_item_owners": sorted(
                participant_action_items.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
        
        return engagement
    
    def _suggest_agenda_items(
        self,
        meetings: List[Dict[str, Any]]
    ) -> List[str]:
        """Suggest agenda items for future meetings based on patterns"""
        suggestions = []
        
        # Find unresolved action items that need follow-up
        unresolved = self._find_unresolved_action_items(meetings)
        if unresolved:
            suggestions.append("Follow-up on unresolved action items")
        
        # Find recurring themes that might need dedicated discussion
        recurring_themes = self._find_recurring_themes(meetings)
        for theme in recurring_themes[:3]:  # Top 3 recurring themes
            suggestions.append(f"Deep dive: {theme['theme']}")
        
        # Find overdue items
        trends = self._analyze_action_item_trends(meetings)
        if trends["overdue"] > 0:
            suggestions.append(f"Review {trends['overdue']} overdue action items")
        
        # Find blocked items
        if trends["blocked"] > 0:
            suggestions.append(f"Address {trends['blocked']} blocked items")
        
        return suggestions


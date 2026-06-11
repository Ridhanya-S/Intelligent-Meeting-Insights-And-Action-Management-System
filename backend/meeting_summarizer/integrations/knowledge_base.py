"""
Knowledge Base Integration Module
Handles storage in SharePoint/Confluence and linking related meetings
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import MeetingSummary, ActionItemStatus
from ..config import Config
from ..core.storage import Storage


class KnowledgeBase:
    """Manage knowledge base integration with SharePoint/Confluence"""
    
    def __init__(self):
        """Initialize knowledge base"""
        self.sharepoint_client = None
        self.confluence_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize SharePoint and Confluence clients if configured"""
        # SharePoint initialization
        if Config.SHAREPOINT_CLIENT_ID and Config.SHAREPOINT_CLIENT_SECRET:
            try:
                # Would use Office365-REST-Python-Client
                print("SharePoint integration available (requires authentication setup)")
            except Exception as e:
                print(f"Warning: Could not initialize SharePoint client: {e}")
        
        # Confluence initialization
        if Config.CONFLUENCE_URL and Config.CONFLUENCE_USERNAME and Config.CONFLUENCE_API_TOKEN:
            try:
                from atlassian import Confluence
                self.confluence_client = Confluence(
                    url=Config.CONFLUENCE_URL,
                    username=Config.CONFLUENCE_USERNAME,
                    password=Config.CONFLUENCE_API_TOKEN
                )
            except ImportError:
                print("Warning: atlassian-python-api not installed. Confluence integration disabled.")
            except Exception as e:
                print(f"Warning: Could not initialize Confluence client: {e}")
    
    def store_summary(
        self,
        summary: MeetingSummary,
        space_key: Optional[str] = None,
        uploaded_file_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Store meeting summary in knowledge base
        
        Args:
            summary: MeetingSummary to store
            space_key: Confluence space key (optional)
            uploaded_file_path: Path to uploaded audio/video/transcript file (optional)
        
        Returns:
            URL or ID of stored document
        """
        # Try Confluence first
        if self.confluence_client:
            try:
                page_url, _ = self._store_in_confluence(summary, space_key, uploaded_file_path)
                
                # File attachment removed - no longer attaching files to Confluence pages
                # if uploaded_file_path and Path(uploaded_file_path).exists():
                #     self._attach_file_to_confluence_page(page_id, uploaded_file_path)
                
                return page_url
            except Exception as e:
                print(f"Warning: Could not store in Confluence: {e}")
                print("Falling back to local storage...")
        
        # Try SharePoint
        if self.sharepoint_client:
            try:
                return self._store_in_sharepoint(summary)
            except Exception as e:
                print(f"Warning: Could not store in SharePoint: {e}")
                print("Falling back to local storage...")
        
        # Fallback: Store locally
        return self._store_locally(summary)
    
    def _store_in_confluence(
        self,
        summary: MeetingSummary,
        space_key: Optional[str],
        uploaded_file_path: Optional[str] = None
    ) -> tuple:
        """Store summary in Confluence space - creates a new page for each meeting"""
        if not self.confluence_client:
            raise RuntimeError("Confluence client not initialized")
        
        if not space_key:
            # Create or get space for the project (workspace)
            space_key = self._get_or_create_space(summary.project_name)
        
        # Create unique page title for this meeting
        # Use meeting title directly (it already includes date if needed)
        # Only add date prefix if title doesn't already start with date
        meeting_time = summary.meeting_date.strftime("%Y-%m-%d %H:%M")
        if summary.meeting_title.startswith(meeting_time.split()[0]):  # Check if title already starts with date
            # Title already has date, use as-is
            page_title = summary.meeting_title
        else:
            # Add date prefix
            page_title = f"{meeting_time} - {summary.meeting_title}"
        
        # Analyze recurring unresolved risks and generate suggestions
        recurring_risks_section = self._generate_recurring_risks_section(summary)
        
        # Generate meeting content
        meeting_content = self._generate_confluence_content(summary, include_heading=True)
        
        # File attachment reference removed - no longer showing file attachment info
        
        # Full content for the meeting page
        full_content = f"""
{meeting_content}
{recurring_risks_section}
"""
        
        try:
            # Check if a page with this title already exists
            try:
                all_pages = self.confluence_client.get_all_pages_from_space(
                    space_key,
                    limit=1000
                )
                
                # Find page with matching title
                existing_page = None
                for page in all_pages:
                    if page.get('title') == page_title:
                        existing_page = page
                        break
            except Exception:
                all_pages = []
                existing_page = None
            
            if existing_page:
                # Update existing page
                page_id = existing_page['id']
                self.confluence_client.update_page(
                    page_id=page_id,
                    title=page_title,
                    body=full_content,
                    version_comment=f"Updated meeting summary: {meeting_time}"
                )
                page_url = f"{Config.CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
                final_page_id = page_id
            else:
                # Create new page for this meeting
                result = self.confluence_client.create_page(
                    space=space_key,
                    title=page_title,
                    body=full_content,
                    parent_id=None,
                    type='page',
                    representation='storage'
                )
                page_url = f"{Config.CONFLUENCE_URL}/pages/viewpage.action?pageId={result['id']}"
                final_page_id = result['id']
            
            # Add labels/tags
            for tag in summary.tags:
                try:
                    self.confluence_client.set_page_label(
                        page_id=final_page_id,
                        label=tag
                    )
                except Exception:
                    pass
            
            return page_url, final_page_id
        except Exception as e:
            raise RuntimeError(f"Error storing in Confluence: {e}")
    
    def _get_or_create_space(self, project_name: str) -> str:
        """Get existing space or create a new one with project name"""
        # Generate space key from project name
        space_key = project_name.replace(" ", "").upper()
        # Ensure space key is valid (max 255 chars, alphanumeric and uppercase)
        space_key = ''.join(c for c in space_key if c.isalnum() or c == '_')[:255]
        
        try:
            # Try to get space info to verify it exists
            self.confluence_client.get_space(space_key, expand='homepage')
            print(f"Using existing Confluence space: {space_key}")
            return space_key
        except Exception:
            # Space doesn't exist, create it
            try:
                print(f"Creating new Confluence space: {space_key} for project: {project_name}")
                # Create space using the API
                # Note: create_space signature: create_space(space_key, space_name)
                self.confluence_client.create_space(
                    space_key,
                    project_name
                )
                print(f"✓ Successfully created Confluence space: {space_key}")
                return space_key
            except Exception as e:
                print(f"Warning: Could not create Confluence space: {e}")
                # Try to use a default space as fallback
                default_spaces = ['~', 'TEAM', 'PROJECTS']
                for default_space in default_spaces:
                    try:
                        self.confluence_client.get_space(default_space, expand='homepage')
                        print(f"Using default space: {default_space}")
                        return default_space
                    except Exception:
                        continue
                
            # If all fails, return the generated key (will fail gracefully)
            return space_key
    
    def _attach_file_to_confluence_page(
        self,
        page_id: str,
        uploaded_file_path: str
    ) -> bool:
        """Attach file to Confluence page"""
        if not uploaded_file_path:
            return False
        
        file_path_obj = Path(uploaded_file_path)
        
        if not file_path_obj.exists():
            print(f"Warning: File does not exist at path: {uploaded_file_path}")
            return False
        
        try:
            file_name = file_path_obj.name
            file_size = file_path_obj.stat().st_size
            
            print(f"\nAttaching file to Confluence: {file_name} ({file_size / 1024 / 1024:.2f} MB)")
            
            # Check file size limit (Confluence typically has 100MB limit)
            if file_size > 100 * 1024 * 1024:
                print(f"Warning: File size may exceed Confluence limits")
            
            # Verify file is not empty
            if file_size == 0:
                raise ValueError("File is empty - cannot upload empty file")
            
            # Determine content type based on file extension
            file_ext = file_path_obj.suffix.lower()
            content_type_map = {
                # Audio formats
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac',
                # Video formats
                '.mp4': 'video/mp4',
                '.avi': 'video/x-msvideo',
                '.mov': 'video/quicktime',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
                '.flv': 'video/x-flv',
                '.wmv': 'video/x-ms-wmv',
                # Text formats
                '.txt': 'text/plain',
                '.srt': 'text/plain',
                '.vtt': 'text/vtt',
                '.json': 'application/json',
                '.csv': 'text/csv',
                '.log': 'text/plain',
                '.md': 'text/markdown',
                # Document formats
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            }
            content_type = content_type_map.get(file_ext, 'application/octet-stream')
            
            # Convert page_id to string
            page_id_str = str(page_id)
            
            # Check if attachment with same name already exists and delete it first
            try:
                existing_attachments = self.confluence_client.get_attachments_from_content(
                    page_id=page_id_str,
                    filename=file_name,
                    limit=1
                )
                if existing_attachments and existing_attachments.get('results'):
                    existing_att = existing_attachments['results'][0]
                    att_id = existing_att.get('id')
                    try:
                        self.confluence_client.delete_attachment_by_id(
                            attachment_id=att_id,
                            version=None
                        )
                        import time
                        time.sleep(1)  # Wait for Confluence to process
                    except Exception:
                        pass  # Continue with upload even if delete fails
            except Exception:
                pass  # No existing attachment, continue
            
            # Upload file attachment using attach_content method
            # Read file content and attach it
            try:
                # Read file content in binary mode
                with open(file_path_obj, 'rb') as f:
                    binary_content = f.read()
                
                # Use attach_content method (most reliable for atlassian-python-api)
                result = self.confluence_client.attach_content(
                    content=binary_content,
                    name=file_name,
                    content_type=content_type,
                    page_id=page_id_str,
                    comment=f"Original meeting file: {file_name}"
                )
                
                if result:
                    print(f"✓ File attached successfully: {file_name}")
                    return True
                else:
                    print(f"Warning: File attachment returned no result")
                    return False
            except Exception as e:
                print(f"Error attaching file to Confluence: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"Error attaching file to Confluence: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_recurring_risks_section(self, summary: MeetingSummary) -> str:
        """
        Generate section highlighting recurring unresolved risks and use LLM to suggest resolutions
        
        Args:
            summary: Current meeting summary
        
        Returns:
            HTML content for recurring risks section
        """
        storage = Storage()
        
        # Get previous meetings for the same project
        try:
            previous_meeting_ids = storage.get_project_meetings(summary.project_name, limit=20)
            
            # Load previous meeting summaries
            current_risk_descriptions = {r.description.lower() for r in summary.all_risks}
            
            recurring_unresolved = []
            
            for meeting_id in previous_meeting_ids:
                if meeting_id == summary.id:
                    continue  # Skip current meeting
                
                prev_summary = storage.get_summary(meeting_id)
                if not prev_summary:
                    continue
                
                # Migration is handled in storage.get_summary() via _migrate_action_item_statuses()
                # This ensures old status values are converted before MeetingSummary object creation
                
                # Check for recurring risks
                for prev_risk in prev_summary.all_risks:
                    prev_desc_lower = prev_risk.description.lower()
                    
                    # Check if this risk appears in current meeting
                    if prev_desc_lower in current_risk_descriptions:
                        # Check if it was resolved (if severity decreased or mitigation was successful)
                        recurring_unresolved.append({
                            "description": prev_risk.description,
                            "severity": prev_risk.severity,
                            "first_mentioned": prev_summary.meeting_date.strftime("%Y-%m-%d"),
                            "times_mentioned": 1,
                            "previous_mitigation": prev_risk.mitigation
                        })
            
            # Count occurrences and deduplicate
            risk_counts = {}
            for risk in recurring_unresolved:
                key = risk["description"].lower()
                if key not in risk_counts:
                    risk_counts[key] = risk
                else:
                    risk_counts[key]["times_mentioned"] += 1
            
            recurring_unresolved = list(risk_counts.values())
            
            if not recurring_unresolved:
                return ""
            
            # Use GenAI to generate resolution suggestions
            suggestions = self._generate_risk_resolution_suggestions(recurring_unresolved, summary)
            
            # Generate HTML section
            section = """
<h2>⚠️ Recurring Unresolved Risks</h2>
<p><strong>Warning:</strong> The following risks have been mentioned in previous meetings but have not been resolved yet.</p>
<table>
<thead>
<tr>
<th>Risk</th>
<th>Severity</th>
<th>First Mentioned</th>
<th>Times Mentioned</th>
<th>Previous Mitigation Attempts</th>
</tr>
</thead>
<tbody>
"""
            
            for risk in recurring_unresolved:
                section += f"""
<tr>
<td><strong>{risk['description']}</strong></td>
<td>{risk['severity'].upper()}</td>
<td>{risk['first_mentioned']}</td>
<td>{risk['times_mentioned']}</td>
<td>{risk['previous_mitigation'] or 'None'}</td>
</tr>
"""
            
            section += """
</tbody>
</table>

<h3>💡 Suggested Resolution Strategies</h3>
<p>The following suggestions are designed to resolve these risks effectively without hindering other tasks:</p>
<ul>
"""
            
            for suggestion in suggestions:
                section += f"<li>{suggestion}</li>\n"
            
            section += """
</ul>
<p><em>Note: These suggestions are AI-generated recommendations. Please review and adapt based on your specific context.</em></p>
"""
            
            return section
            
        except Exception as e:
            print(f"Warning: Could not generate recurring risks section: {e}")
            return ""
    
    def _generate_risk_resolution_suggestions(
        self,
        recurring_risks: List[Dict[str, Any]],
        current_summary: MeetingSummary
    ) -> List[str]:
        """
        Use GenAI to generate effective resolution suggestions for recurring risks
        
        Args:
            recurring_risks: List of recurring unresolved risks
            current_summary: Current meeting summary
        
        Returns:
            List of suggestion strings
        """
        if not Config.OPENAI_API_KEY:
            return ["AI suggestions unavailable - API key not configured"]
        
        try:
            import httpx
            import re
            
            # Determine which LLM provider to use
            llm_provider = Config.LLM_PROVIDER.lower()
            elsai_llm = None
            
            # Initialize Elsai Model if selected
            if llm_provider == "elsai":
                try:
                    from elsai_model.openai import OpenAIConnector
                    elsai_llm = OpenAIConnector(
                        openai_api_key=Config.OPENAI_API_KEY,
                        model_name=Config.OPENAI_MODEL,
                        temperature=Config.ELSAI_TEMPERATURE,
                        implementation=Config.ELSAI_IMPLEMENTATION  # "native" or "langchain"
                    )
                except ImportError:
                    raise ImportError(
                        "Elsai Model not installed. Install with: "
                        "pip install --extra-index-url https://elsai-core-package.optisolbusiness.com/root/elsai-model/ elsai-model"
                    )
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Elsai Model: {e}")
            
            # Validate provider configuration
            if llm_provider == "openai" and not Config.OPENAI_API_KEY:
                raise ValueError("LLM_PROVIDER is set to 'openai' but OPENAI_API_KEY is not configured")
            if llm_provider == "huggingface" and not Config.HUGGINGFACE_API_KEY:
                raise ValueError("LLM_PROVIDER is set to 'huggingface' but HUGGINGFACE_API_KEY is not configured")
            
            # Prepare prompt
            risks_text = "\n".join([
                f"- {r['description']} (Severity: {r['severity']}, Mentioned {r['times_mentioned']} times, "
                f"Previous mitigation: {r['previous_mitigation'] or 'None'})"
                for r in recurring_risks
            ])
            
            current_action_items = "\n".join([
                f"- {item.description} (Owner: {item.owner}, Deadline: {item.deadline or 'Not set'})"
                for item in current_summary.all_action_items
            ])
            
            prompt = f"""You are a risk management expert. Analyze the following recurring unresolved risks and provide actionable suggestions to resolve them effectively.

RECURRING UNRESOLVED RISKS:
{risks_text}

CURRENT ACTION ITEMS IN PROGRESS:
{current_action_items}

PROJECT CONTEXT:
- Project: {current_summary.project_name}
- Current Meeting: {current_summary.meeting_title}
- Participants: {', '.join(current_summary.participants)}

REQUIREMENTS:
1. Provide 3-5 specific, actionable suggestions for resolving these recurring risks
2. Ensure suggestions do NOT interfere with or hinder existing action items
3. Prioritize solutions that can be implemented alongside current work
4. Consider why previous mitigation attempts may have failed
5. Suggest solutions that address root causes, not just symptoms
6. Include resource requirements and timeline estimates if relevant

Format your response as a JSON array of suggestion strings:
["Suggestion 1", "Suggestion 2", "Suggestion 3"]

Respond ONLY with valid JSON array, no additional text.
"""
            
            # Call GenAI API based on configured provider
            if llm_provider == "elsai" and elsai_llm:
                # Use Elsai Model
                messages = [
                    {
                        "role": "system",
                        "content": "You are a risk management expert. Always respond with valid JSON arrays."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
                content = elsai_llm.invoke(messages=messages)
                # Streaming functionality (available in v1.0.1) - optional
                # content = ""
                # for chunk in elsai_llm.stream(messages=messages):
                #     content += chunk
                #     print(chunk, end='', flush=True)
            else:
                # Use OpenAI API (default or when elsai not available)
                url = f"{Config.OPENAI_API_BASE}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": Config.OPENAI_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a risk management expert. Always respond with valid JSON arrays."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.5,
                    "max_tokens": 1000
                }
                
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
            
            # Parse JSON response
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n', '', content)
                content = re.sub(r'\n```$', '', content)
            
            try:
                suggestions = json.loads(content)
                if isinstance(suggestions, list):
                    return suggestions[:5]  # Limit to 5 suggestions
            except json.JSONDecodeError:
                # Try to extract array from text
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    try:
                        suggestions = json.loads(json_match.group())
                        if isinstance(suggestions, list):
                            return suggestions[:5]
                    except Exception:
                        pass
            
            # Fallback: return generic suggestions
            return [
                "Review root causes of recurring risks and address underlying issues",
                "Assign dedicated resources to resolve high-severity recurring risks",
                "Implement preventive measures to avoid risk recurrence",
                "Schedule dedicated risk resolution sessions separate from regular meetings"
            ]
            
        except Exception as e:
            print(f"Warning: Could not generate AI suggestions: {e}")
            return [
                "Review and address root causes of recurring risks",
                "Assign dedicated resources for risk resolution",
                "Implement preventive measures"
            ]
    
    def _generate_confluence_content(self, summary: MeetingSummary, include_heading: bool = True) -> str:
        """Generate Confluence storage format content"""
        duration_str = f"{summary.duration_minutes:.1f} minutes" if summary.duration_minutes else "Not specified"
        
        heading = "<h2>Meeting Summary</h2>\n" if include_heading else ""
        
        # Get original file name from metadata
        original_file_name = summary.metadata.get('original_file_name', '') if summary.metadata else ''
        file_name_section = f"<p><strong>Source File:</strong> {original_file_name}</p>\n" if original_file_name else ""
        
        # Check if meeting is empty
        is_empty = summary.metadata.get('is_empty_meeting', False) if summary.metadata else False
        empty_warning = "<div class=\"confluence-warning\" style=\"background-color: #fff3cd; border: 1px solid #ffc107; padding: 12px; border-radius: 4px; margin: 16px 0;\"><strong>⚠️ Note:</strong> This meeting appears to be empty or contains no meaningful content. The transcript may be incomplete, corrupted, or the meeting may not have had substantial discussion.</div>\n" if is_empty else ""
        
        content = f"""
{heading}<p><strong>Project:</strong> {summary.project_name}</p>
<p><strong>Date:</strong> {summary.meeting_date.strftime('%Y-%m-%d %H:%M')}</p>
<p><strong>Duration:</strong> {duration_str}</p>
<p><strong>Participants:</strong> {', '.join(summary.participants) if summary.participants else 'Not specified'}</p>
{file_name_section}
{empty_warning}

<h2>Overall Summary</h2>
<p>{summary.overall_summary}</p>

<h2>Agenda Topics</h2>
"""
        
        for topic in summary.agenda_topics:
            content += f"""
<h3>{topic.topic}</h3>
<p>{topic.summary or 'No summary available'}</p>
"""
            if topic.key_points:
                content += "<ul>\n"
                for point in topic.key_points:
                    content += f"<li>{point}</li>\n"
                content += "</ul>\n"
        
        content += """
<h2>Action Items</h2>
<table>
<thead>
<tr>
<th>Description</th>
<th>Owner</th>
<th>Deadline</th>
<th>Status</th>
</tr>
</thead>
<tbody>
"""
        
        for item in summary.all_action_items:
            # For done items, don't show deadline
            if item.status.value == "done":
                deadline_str = "N/A"
                status_str = "Done"
            else:
                deadline_str = item.deadline.strftime('%Y-%m-%d') if item.deadline else 'Not specified'
                # Map status values for display
                status_display_map = {
                    "new": "New",
                    "pending": "Pending",
                    "doing": "Doing",
                    "done": "Done",
                    "blocked": "Blocked"
                }
                status_str = status_display_map.get(item.status.value, item.status.value.title())
            description = item.description or 'No description'
            owner = item.owner or 'Unassigned'
            content += f"""
<tr>
<td>{description}</td>
<td>{owner}</td>
<td>{deadline_str}</td>
<td>{status_str}</td>
</tr>
"""
        
        content += """
</tbody>
</table>

<h2>Decisions</h2>
<ul>
"""
        
        for decision in summary.all_decisions:
            content += f"<li><strong>{decision.description}</strong>"
            if decision.context:
                content += f"<br/>{decision.context}"
            content += "</li>\n"
        
        content += """
</ul>

<h2>Risks and Blockers</h2>
<ul>
"""
        
        for risk in summary.all_risks:
            content += f"<li><strong>{risk.description}</strong> (Severity: {risk.severity})"
            if risk.impact:
                content += f"<br/>Impact: {risk.impact}"
            if risk.mitigation:
                content += f"<br/>Mitigation: {risk.mitigation}"
            content += "</li>\n"
        
        content += "</ul>"
        
        return content
    
    def _store_in_sharepoint(self, summary: MeetingSummary) -> str:
        """Store summary in SharePoint (stub implementation)"""
        # Would require Office365-REST-Python-Client setup
        raise NotImplementedError("SharePoint integration requires authentication setup")
    
    def _store_locally(self, summary: MeetingSummary) -> str:
        """Store summary locally as JSON, organized by project/meetingtime"""
        # Get meeting directory: projectname/meetingtime/
        meeting_dir = Config.get_meeting_dir(summary.project_name, summary.meeting_date)
        
        # Save summary file
        filename = "summary.json"
        file_path = meeting_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary.model_dump(), f, indent=2, default=str)
        
        return str(file_path)
    
    def find_related_meetings(
        self,
        summary: MeetingSummary,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find related past meetings based on tags, topics, or participants
        
        Args:
            summary: Current meeting summary
            limit: Maximum number of related meetings to return
        
        Returns:
            List of related meeting summaries
        """
        related = []
        
        # Load all summaries from the same project (search all meeting directories)
        project_dir = Config.DATA_DIR / summary.project_name
        if not project_dir.exists():
            return related
        
        # Search in all meeting subdirectories
        summary_files = []
        for meeting_dir in project_dir.iterdir():
            if meeting_dir.is_dir():
                summary_file = meeting_dir / "summary.json"
                if summary_file.exists():
                    summary_files.append(summary_file)
        
        # Score meetings based on similarity
        scored_meetings = []
        
        for file_path in summary_files:
            if file_path.name.endswith(f"_{summary.meeting_date.strftime('%Y%m%d_%H%M%S')}.json"):
                continue  # Skip current meeting
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                score = self._calculate_similarity_score(summary, data)
                if score > 0:
                    scored_meetings.append((score, data, str(file_path)))
            except Exception as e:
                print(f"Warning: Could not load meeting {file_path}: {e}")
        
        # Sort by score and return top matches
        scored_meetings.sort(key=lambda x: x[0], reverse=True)
        
        for score, data, file_path in scored_meetings[:limit]:
            related.append({
                "summary": data,
                "file_path": file_path,
                "similarity_score": score
            })
        
        return related
    
    def _calculate_similarity_score(
        self,
        current: MeetingSummary,
        other: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between two meetings"""
        score = 0.0
        
        # Tag overlap
        current_tags = set(current.tags)
        other_tags = set(other.get("tags", []))
        if current_tags and other_tags:
            tag_overlap = len(current_tags & other_tags) / len(current_tags | other_tags)
            score += tag_overlap * 0.3
        
        # Participant overlap
        current_participants = {p.lower() for p in current.participants}
        other_participants = {p.lower() for p in other.get("participants", [])}
        if current_participants and other_participants:
            participant_overlap = len(current_participants & other_participants) / len(current_participants | other_participants)
            score += participant_overlap * 0.3
        
        # Topic similarity (simple keyword matching)
        current_topics = ' '.join([t.topic.lower() for t in current.agenda_topics])
        other_topics = ' '.join([t.get("topic", "").lower() for t in other.get("agenda_topics", [])])
        
        if current_topics and other_topics:
            current_words = set(current_topics.split())
            other_words = set(other_topics.split())
            if current_words and other_words:
                word_overlap = len(current_words & other_words) / len(current_words | other_words)
                score += word_overlap * 0.4
        
        return score
    
    def delete_project_confluence_resources(self, project_name: str) -> Dict[str, int]:
        """
        Delete all Confluence pages and workspace/space for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary with counts of deleted resources
        """
        if not self.confluence_client:
            return {'pages': 0, 'spaces': 0}
        
        deleted = {'pages': 0, 'spaces': 0}
        
        try:
            space_key = self._get_or_create_space(project_name)
            
            # Get all pages in the space
            pages = self.confluence_client.get_all_pages_from_space(space_key, limit=1000)
            
            # Delete all pages first
            for page in pages:
                try:
                    self.confluence_client.remove_page(page['id'])
                    deleted['pages'] += 1
                except Exception as e:
                    print(f"Warning: Could not delete page {page.get('title', 'unknown')}: {e}")
            
            # Delete the space/workspace itself
            try:
                # Get space details to verify it exists
                space = self.confluence_client.get_space(space_key, expand='homepage')
                if space:
                    # Delete the space using the API
                    # Note: delete_space may require admin permissions
                    try:
                        # Try to delete the space
                        # The atlassian library may have delete_space method or we need to use REST API directly
                        # For now, we'll try the REST API approach
                        import requests
                        from requests.auth import HTTPBasicAuth
                        from ..config import Config
                        
                        # Build the delete URL
                        delete_url = f"{Config.CONFLUENCE_URL.rstrip('/')}/rest/api/space/{space_key}"
                        
                        # Make DELETE request
                        response = requests.delete(
                            delete_url,
                            auth=HTTPBasicAuth(Config.CONFLUENCE_USERNAME, Config.CONFLUENCE_API_TOKEN),
                            headers={'Content-Type': 'application/json'}
                        )
                        
                        # HTTP 200/204: Immediate deletion success
                        # HTTP 202: Accepted - deletion initiated asynchronously (long-running task)
                        if response.status_code in (200, 204, 202):
                            deleted['spaces'] += 1
                            if response.status_code == 202:
                                # Parse the long-running task info if available
                                try:
                                    task_info = response.json()
                                    task_id = task_info.get('id', 'unknown')
                                    print(f"✓ Confluence space deletion initiated (async): {space_key}")
                                    print(f"  Long-running task ID: {task_id}")
                                    print(f"  Note: Deletion is being processed in the background")
                                except:
                                    print(f"✓ Confluence space deletion initiated (async): {space_key}")
                                    print(f"  Note: Deletion is being processed in the background")
                            else:
                                print(f"✓ Successfully deleted Confluence space: {space_key}")
                        else:
                            print(f"Warning: Could not delete Confluence space {space_key}: HTTP {response.status_code}")
                            print(f"  Response: {response.text}")
                    except ImportError:
                        print(f"Warning: requests library not available. Cannot delete Confluence space.")
                    except Exception as e:
                        print(f"Warning: Error deleting Confluence space {space_key}: {e}")
                        # Try alternative method using confluence client if available
                        try:
                            # Some versions of atlassian library may have delete_space method
                            if hasattr(self.confluence_client, 'delete_space'):
                                self.confluence_client.delete_space(space_key)
                                deleted['spaces'] += 1
                                print(f"✓ Successfully deleted Confluence space: {space_key}")
                        except Exception as e2:
                            print(f"Warning: Alternative delete method also failed: {e2}")
            except Exception as e:
                print(f"Warning: Could not access Confluence space {space_key} for deletion: {e}")
            
        except Exception as e:
            print(f"Warning: Error deleting Confluence resources for {project_name}: {e}")
            import traceback
            traceback.print_exc()
        
        return deleted
    
    def delete_meeting_confluence_page(self, meeting_id: str, project_name: str) -> bool:
        """
        Delete a Confluence page for a specific meeting.
        
        Args:
            meeting_id: ID of the meeting
            project_name: Name of the project
            
        Returns:
            True if page was deleted, False otherwise
        """
        if not self.confluence_client:
            return False
        
        try:
            # Get meeting summary to find Confluence URL
            storage = Storage()
            summary = storage.get_summary(meeting_id)
            
            if not summary:
                return False
            
            # Get Confluence URL from metadata
            confluence_url = None
            if summary.metadata:
                confluence_url = summary.metadata.get('confluence_url')
            
            if not confluence_url:
                # Try to find page by title
                space_key = self._get_or_create_space(project_name)
                page_title = f"{summary.meeting_title} - {summary.meeting_date.strftime('%Y-%m-%d')}"
                
                # Search for page
                pages = self.confluence_client.get_all_pages_from_space(space_key, limit=1000)
                for page in pages:
                    if page.get('title') == page_title:
                        try:
                            self.confluence_client.remove_page(page['id'])
                            return True
                        except Exception as e:
                            print(f"Warning: Could not delete Confluence page: {e}")
                            return False
                
                return False
            
            # Extract page ID from URL
            # Confluence URLs typically: https://domain/.../pages/viewpage.action?pageId=123456
            import re
            page_id_match = re.search(r'pageId=(\d+)', confluence_url)
            if page_id_match:
                page_id = page_id_match.group(1)
                try:
                    self.confluence_client.remove_page(page_id)
                    return True
                except Exception as e:
                    print(f"Warning: Could not delete Confluence page {page_id}: {e}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"Warning: Error deleting meeting Confluence page: {e}")
            return False
    
    def extract_confluence_member_emails(self, project_name: str) -> Dict[str, str]:
        """
        Extract member names and emails from Confluence space.
        Also includes project owner email from config.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary mapping name -> email
        """
        from ..config import Config
        
        email_mappings = {}
        
        # Add project owner email from config (if available)
        if Config.PROJECT_OWNER_NAME and Config.PROJECT_OWNER_EMAIL:
            email_mappings[Config.PROJECT_OWNER_NAME] = Config.PROJECT_OWNER_EMAIL
            print(f"Added project owner email: {Config.PROJECT_OWNER_NAME} -> {Config.PROJECT_OWNER_EMAIL}")
        
        if not self.confluence_client:
            return email_mappings
        
        try:
            space_key = self._get_or_create_space(project_name)
            
            # Get space details
            space = self.confluence_client.get_space(space_key, expand='homepage')
            
            # Get space permissions to find members
            try:
                # Get space permissions
                permissions = self.confluence_client.get_space_permissions(space_key)
                
                # Extract user information from permissions
                for perm in permissions.get('results', []):
                    user = perm.get('user', {})
                    if user:
                        name = user.get('displayName', '') or user.get('username', '')
                        email = user.get('email', '')
                        
                        if name and email:
                            email_mappings[name] = email
            except Exception:
                pass
            
            # Also check page watchers/contributors
            pages = self.confluence_client.get_all_pages_from_space(space_key, limit=100)
            for page in pages:
                try:
                    # Get page watchers
                    watchers = self.confluence_client.get_page_watchers(page['id'])
                    for watcher in watchers.get('results', []):
                        name = watcher.get('displayName', '') or watcher.get('username', '')
                        email = watcher.get('email', '')
                        
                        if name and email:
                            email_mappings[name] = email
                except Exception:
                    pass
                
        except Exception as e:
            print(f"Warning: Error extracting Confluence member emails: {e}")
        
        return email_mappings
    
    def update_email_mappings_from_confluence(self, project_name: str) -> int:
        """
        Extract emails from Confluence and save to database.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Number of mappings saved
        """
        email_mappings = self.extract_confluence_member_emails(project_name)
        
        storage = Storage()
        count = 0
        
        for name, email in email_mappings.items():
            storage.save_email_mapping(name, email, 'confluence', project_name)
            count += 1
        
        return count
    
    def sync_confluence_pages(self, project_name: str) -> Dict[str, int]:
        """
        Sync Confluence pages - remove from DB if deleted in Confluence.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary with sync results
        """
        if not self.confluence_client:
            return {'checked': 0, 'removed': 0}
        
        results = {'checked': 0, 'removed': 0}
        
        try:
            storage = Storage()
            space_key = self._get_or_create_space(project_name)
            
            # Get all pages in Confluence space
            confluence_pages = self.confluence_client.get_all_pages_from_space(space_key, limit=1000)
            confluence_page_ids = {page['id'] for page in confluence_pages}
            
            # Get all summaries for this project
            summaries = storage.get_project_meetings(project_name)
            
            for summary in summaries:
                results['checked'] += 1
                
                # Check if Confluence URL exists in metadata
                if summary.metadata and 'confluence_page_id' in summary.metadata:
                    page_id = summary.metadata['confluence_page_id']
                    
                    # If page doesn't exist in Confluence, remove from metadata
                    if page_id not in confluence_page_ids:
                        # Update metadata to remove Confluence URL
                        if summary.metadata:
                            summary.metadata.pop('confluence_url', None)
                            summary.metadata.pop('confluence_page_id', None)
                            storage.save_summary(summary, replace_existing=True)
                            results['removed'] += 1
                        
        except Exception as e:
            print(f"Warning: Error syncing Confluence pages: {e}")
        
        return results


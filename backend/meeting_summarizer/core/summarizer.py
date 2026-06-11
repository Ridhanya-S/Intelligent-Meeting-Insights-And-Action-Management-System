"""
Structured Summarization Module using GenAI
Extracts structured information from meeting transcripts
"""
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

# Elsai Model Integration (commented out - ready to use when needed)
# from elsai_model.openai import OpenAIConnector

from ..models import (
    MeetingSummary, MeetingTranscript, AgendaTopic,
    ActionItem, Decision, Risk, ActionItemStatus
)
from ..config import Config


class MeetingSummarizer:
    """Generate structured summaries from meeting transcripts using GenAI"""
    
    def __init__(self):
        """Initialize the summarizer"""
        # Determine which LLM provider to use
        self.llm_provider = Config.LLM_PROVIDER.lower()
        
        # Validate provider selection
        valid_providers = ["elsai", "openai", "huggingface"]
        if self.llm_provider not in valid_providers:
            raise ValueError(
                f"Invalid LLM_PROVIDER: {self.llm_provider}. "
                f"Must be one of: {', '.join(valid_providers)}. "
                f"Set LLM_PROVIDER environment variable."
            )
        
        self.api_key = Config.OPENAI_API_KEY
        self.api_base = Config.OPENAI_API_BASE
        self.model = Config.OPENAI_MODEL
        self.use_huggingface = False
        
        # Initialize Elsai Model if selected
        if self.llm_provider == "elsai":
            try:
                from elsai_model.openai import OpenAIConnector
                self.elsai_llm = OpenAIConnector(
                    openai_api_key=self.api_key or Config.OPENAI_API_KEY,
                    model_name=self.model or Config.OPENAI_MODEL,
                    temperature=Config.ELSAI_TEMPERATURE,
                    implementation=Config.ELSAI_IMPLEMENTATION  # "native" or "langchain"
                )
                print(f"✓ Initialized Elsai Model connector (implementation: {Config.ELSAI_IMPLEMENTATION})")
            except ImportError:
                raise ImportError(
                    "Elsai Model not installed. Install with: "
                    "pip install --extra-index-url https://elsai-core-package.optisolbusiness.com/root/elsai-model/ elsai-model"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Elsai Model: {e}")
        
        # Fallback to HuggingFace if OpenAI not configured and HuggingFace is available
        if self.llm_provider == "huggingface" or (not self.api_key and Config.HUGGINGFACE_API_KEY):
            if not Config.HUGGINGFACE_API_KEY:
                raise ValueError(
                    f"LLM_PROVIDER is set to '{self.llm_provider}' but HUGGINGFACE_API_KEY is not configured. "
                    f"Set HUGGINGFACE_API_KEY environment variable."
                )
            self.use_huggingface = True
            self.api_key = Config.HUGGINGFACE_API_KEY
        
        # Validate OpenAI configuration if selected
        if self.llm_provider == "openai" and not self.api_key:
            raise ValueError(
                "LLM_PROVIDER is set to 'openai' but OPENAI_API_KEY is not configured. "
                "Set OPENAI_API_KEY environment variable."
            )
        
        print(f"✓ LLM Provider: {self.llm_provider.upper()}")
    
    def summarize(
        self,
        transcript: MeetingTranscript,
        meeting_title: str,
        meeting_date: Optional[datetime] = None,
        participants: Optional[List[str]] = None
    ) -> MeetingSummary:
        """
        Generate structured summary from transcript
        
        Args:
            transcript: MeetingTranscript object
            meeting_title: Title of the meeting
            meeting_date: Date of the meeting
            participants: List of participant names
        
        Returns:
            MeetingSummary object
        """
        if meeting_date is None:
            meeting_date = datetime.now()
        
        # Prepare prompt for GenAI
        prompt = self._create_summarization_prompt(transcript, meeting_title, participants)
        
        # Call GenAI API
        response = self._call_genai(prompt)
        
        # Parse response into structured format
        summary_data = self._parse_genai_response(response)
        
        # Create MeetingSummary object
        summary = self._build_summary(
            transcript=transcript,
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            participants=participants or [],
            summary_data=summary_data
        )
        
        return summary
    
    def _create_summarization_prompt(
        self,
        transcript: MeetingTranscript,
        meeting_title: str,
        participants: Optional[List[str]]
    ) -> str:
        """Create a structured prompt for GenAI summarization"""
        
        prompt = f"""You are an expert meeting analyst. Analyze the following meeting transcript and extract structured information.

MEETING DETAILS:
- Title: {meeting_title}
- Project: {transcript.project_name}
- Participants: {', '.join(participants) if participants else 'Not specified'}

TRANSCRIPT:
{transcript.transcript_text}

Please analyze this transcript and provide a structured JSON response with the following format:
{{
    "meeting_type": "discussion|KT|decision_making|general",
    "overall_summary": "A comprehensive summary of the entire meeting (2-3 paragraphs)",
    "agenda_topics": [
        {{
            "topic": "Topic name",
            "summary": "Summary of discussion on this topic",
            "key_points": ["point1", "point2", ...],
            "duration_minutes": 15.5
        }}
    ],
    "action_items": [
        {{
            "description": "Clear description of the action item",
            "owner": "Person responsible",
            "deadline": "YYYY-MM-DD or null if not specified",
            "status": "new|pending|doing|done",
            "dependencies": ["dependency1", ...],
            "tags": ["tag1", "tag2"]
        }}
    ],
    "decisions": [
        {{
            "description": "What was decided",
            "context": "Context around the decision",
            "decision_makers": ["person1", "person2"]
        }}
    ],
    "risks": [
        {{
            "description": "Risk or blocker description",
            "severity": "low|medium|high|critical",
            "impact": "Impact description",
            "mitigation": "Mitigation strategy if mentioned",
            "owner": "Person responsible"
        }}
    ],
    "tags": ["tag1", "tag2", ...]
}}

IMPORTANT:
- Extract ALL action items with clear owners and deadlines if mentioned
- CRITICAL: Even if a task is COMPLETED, you MUST still extract it as an action item with status "done"
- Do NOT skip completed tasks - they are still action items that need to be tracked
- For ALL action items (including done ones), extract tags and dependencies if mentioned in the conversation
- Tags and dependencies are important even for completed tasks - they help track relationships and categorization
- For action item status, CAREFULLY analyze the context and verb tense:
  * Use "done" ONLY if the task is ALREADY COMPLETED (past tense/completed actions). Look for keywords like:
    - PAST TENSE: "completed", "finished", "has been completed", "was done", "has been done"
    - COMPLETION STATEMENTS: "I completed X", "X has been completed", "finished X", "X was finished"
    - PAST TIME REFERENCES: "that's been completed", "completed yesterday", "finished last week"
    - EXPLICIT COMPLETION: "that task from [day] is done" (when referring to a past completed task)
    - Examples: "I completed the API integration yesterday" → Status: "done"
    - Examples: "The API integration has been completed" → Status: "done"
    - Examples: "That task from Tuesday is done" → Status: "done" (if referring to past completion)
    - CRITICAL: Only use "done" when the task is ALREADY FINISHED, not when it's planned for the future
  
  * Use "new" or "pending" for FUTURE TASKS (future tense/planned actions). These are NOT completed:
    - FUTURE TENSE: "needs to be done", "will be done", "should be done", "has to be done"
    - CONDITIONAL FUTURE: "once X is done", "after X is done", "when X is done" (referring to future completion)
    - PLANNING STATEMENTS: "we need to do X", "X needs to be completed", "X will be completed"
    - Examples: "The API integration needs to be done" → Status: "new" (NOT "done")
    - Examples: "Once the fixes are done, we can proceed" → Status: "new" (NOT "done")
    - Examples: "The scoring will be lower after the fixes are done" → Status: "new" (NOT "done")
    - Examples: "So once you've done the integration" → Status: "new" (NOT "done")
    - CRITICAL: Phrases like "needs to be done", "will be done", "once X is done" indicate FUTURE work, NOT completed work
    - If someone says "X needs to be done", they mean it SHOULD BE done in the future, not that it IS done
  
  * Use "doing" if the task is actively being worked on or has some progress:
    - "I'm working on X", "currently doing X", "in progress", "60% done"
    - "started implementing", "about X% done", "making progress"
  
  * Use "pending" if the same task is mentioned again but with NO progress reported
  
  * Use "new" for newly mentioned tasks (first time this task appears) or future planned tasks

CRITICAL DISTINCTION BETWEEN COMPLETED vs FUTURE TASKS:
- COMPLETED (status: "done"): Past tense, already finished
  ✓ "I completed X" → done
  ✓ "X has been completed" → done
  ✓ "X is done" (when confirming completion) → done
  ✓ "That task from Tuesday is done" → done (if confirming past completion)
  
- FUTURE (status: "new" or "pending"): Future tense, needs to be done
  ✗ "X needs to be done" → new (NOT done)
  ✗ "X will be done" → new (NOT done)
  ✗ "Once X is done" → new (NOT done)
  ✗ "After X is done" → new (NOT done)
  ✗ "X should be done" → new (NOT done)
  ✗ "We need to do X" → new (NOT done)
  
KEY RULE: If the phrase indicates something that SHOULD/MUST/WILL happen in the future, it's NOT "done" - it's "new" or "pending"

CRITICAL: When reviewing status updates from previous meetings:
- If someone says "I completed [task]" or "[task] has been completed" or "that's been completed" → YOU MUST extract this as an action item with status "done"
- If someone says "[task] - completed" or "[task] was completed" → YOU MUST extract this as an action item with status "done"
- Pay attention to phrases like "that task from Monday is done" (if confirming past completion) → Status: "done"
- When listing status updates, if it says "completed" or "was done" (past tense), extract as action item with status "done"
- NEVER skip completed tasks - they MUST be included in the action_items array

CRITICAL: DO NOT confuse FUTURE tasks with COMPLETED tasks:
- "X needs to be done" → Status: "new" (NOT "done") - This is a future requirement
- "X will be done" → Status: "new" (NOT "done") - This is a future plan
- "Once X is done" → Status: "new" (NOT "done") - This refers to future completion
- "After X is done" → Status: "new" (NOT "done") - This refers to future completion
- "X should be done" → Status: "new" (NOT "done") - This is a future requirement
- "We need to do X" → Status: "new" (NOT "done") - This is a future task
- "X has to be done" → Status: "new" (NOT "done") - This is a future requirement

Remember: "needs to be done", "will be done", "should be done", "has to be done" = FUTURE work = Status "new"
          "has been done", "was done", "completed", "finished" = PAST work = Status "done"

EXAMPLES - COMPLETED TASKS (status: "done"):
- "I completed the API integration yesterday. It's tested and ready. That task from Tuesday is done." 
  → Extract: Action item: "API integration", Status: "done", Owner: "Bob" (speaker), Deadline: null, Dependencies: [], Tags: [], Description: "API integration - completed yesterday"
- "Yes, I completed the API integration yesterday. It's tested and ready. That task from Tuesday is done."
  → Extract: Action item: "API integration", Status: "done", Owner: [speaker name], Deadline: null, Dependencies: [], Tags: [], Description: "API integration - completed yesterday. That task from Tuesday is done"
- "That task from Tuesday is done" (when confirming past completion)
  → Extract: Action item: "[task name from context]", Status: "done", Owner: [speaker name], Deadline: null, Dependencies: [], Tags: []
- "Bob's API integration - completed" 
  → Extract: Action item: "API integration", Status: "done", Owner: "Bob", Deadline: null, Dependencies: [], Tags: []
- "Charlie and David's sync - completed" 
  → Extract: Action item: "sync", Status: "done", Owner: "Charlie" (or "David" if only one owner), Deadline: null, Dependencies: [], Tags: []
- "I completed the frontend dashboard (depends on API integration, tagged as 'frontend' and 'high-priority')"
  → Extract: Action item: "frontend dashboard", Status: "done", Owner: [speaker], Deadline: null, Dependencies: ["API integration"], Tags: ["frontend", "high-priority"]

EXAMPLES - FUTURE TASKS (status: "new" or "pending") - NOT "done":
- "The API integration needs to be done"
  → Extract: Action item: "API integration", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []
- "Once the fixes are done, we can proceed"
  → Extract: Action item: "fixes", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []
- "The scoring will be lower after the fixes are done"
  → Extract: Action item: "fixes", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []
- "So once you've done the integration"
  → Extract: Action item: "integration", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []
- "It means, they are going to do it"
  → Extract: Action item: "[task from context]", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []
- "Which we have - done" (if this means "which we need to have done" = future)
  → Extract: Action item: "[task from context]", Status: "new", Owner: [speaker or "Unassigned"], Deadline: null, Dependencies: [], Tags: []

CRITICAL: Phrases like "needs to be done", "will be done", "once X is done", "after X is done" indicate FUTURE work that needs to be completed, NOT work that is already completed. These should have status "new" or "pending", NOT "done".

CRITICAL: For action items with status "done":
  * The "owner" field MUST be the person's NAME (e.g., "Bob", "Alice", "Charlie")
  * The "owner" field MUST NOT be a date (e.g., "2025-11-28", "yesterday", "Tuesday")
  * The "owner" field MUST NOT be "Date", "Deadline", "N/A", "None", or any other placeholder
  * The "deadline" field should be null for done items
  * The "dependencies" field should still be extracted if mentioned (e.g., "depends on X", "blocked by Y")
  * The "tags" field should still be extracted if mentioned (e.g., "frontend", "backend", "urgent", "high-priority")
  * If someone says "I completed X", the owner is the speaker's name
  * If someone says "Bob completed X", the owner is "Bob"
  * If someone says "That task from Tuesday is done", the owner is the speaker's name (NOT "Tuesday")
  * If the owner cannot be determined from context, use "Unassigned" (NOT "Date" or any placeholder)
  * Dates go in the "deadline" field (or description), NOT in the "owner" field
  * Always extract the actual person's name as the owner, never dates, time references, or placeholders like "Date"
  * ALWAYS extract tags and dependencies for done items if they are mentioned in the conversation

- Identify ALL decisions made during the meeting
- Highlight risks, blockers, or dependencies
- Group discussions by agenda topics if identifiable
- Use null for missing optional fields
- Be precise with dates - use YYYY-MM-DD format or null
- Extract participant names accurately

MEETING TYPE CLASSIFICATION:
Classify the meeting type based on the content and purpose:
- "discussion": General discussion, brainstorming, information sharing, status updates, or open-ended conversations
- "KT": Knowledge transfer, training, onboarding, documentation review, or educational sessions
- "decision_making": Meetings focused on making decisions, approvals, voting, or reaching conclusions
- "general": Default fallback if the meeting doesn't clearly fit into the above categories

Consider the following indicators:
- Discussion: Frequent back-and-forth, multiple perspectives, exploratory conversations
- KT: Teaching, explaining concepts, sharing knowledge, tutorials, walkthroughs
- Decision making: Clear decision points, voting, approvals, finalizing choices, selecting options
- General: Mixed purposes or unclear primary objective

Respond ONLY with valid JSON, no additional text.
"""
        return prompt
    
    def _call_genai(self, prompt: str) -> str:
        """Call GenAI API based on configured provider (Elsai, OpenAI, or HuggingFace)"""
        
        if self.llm_provider == "elsai":
            return self._call_elsai(prompt)
        elif self.llm_provider == "huggingface" or self.use_huggingface:
            return self._call_huggingface(prompt)
        else:  # openai (default)
            return self._call_openai(prompt)
    
    def _call_elsai(self, prompt: str) -> str:
        """Call Elsai Model API using OpenAIConnector"""
        if not hasattr(self, 'elsai_llm'):
            raise ValueError("Elsai Model not initialized. Check LLM_PROVIDER configuration.")
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts structured information from meeting transcripts. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            response = self.elsai_llm.invoke(messages=messages)
            return response
        except Exception as e:
            raise RuntimeError(f"Error calling Elsai Model API: {e}")
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI-compatible API"""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts structured information from meeting transcripts. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Error calling OpenAI API: {e}")
    
    def _call_huggingface(self, prompt: str) -> str:
        """Call HuggingFace Inference API as fallback"""
        # This is a simplified implementation
        # For production, you'd use a proper HuggingFace model endpoint
        raise NotImplementedError(
            "HuggingFace integration not fully implemented. "
            "Please use OpenAI API or implement HuggingFace endpoint."
        )
    
    def _parse_genai_response(self, response: str) -> Dict[str, Any]:
        """Parse GenAI response and extract JSON"""
        # Try to extract JSON from response
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            response = re.sub(r'^```(?:json)?\n', '', response)
            response = re.sub(r'\n```$', '', response)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            # Try to extract JSON object from text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Fallback: create basic structure
            print(f"Warning: Could not parse JSON response: {e}")
            print(f"Response: {response[:500]}")
            return {
                "meeting_type": "general",
                "overall_summary": response[:500],
                "agenda_topics": [],
                "action_items": [],
                "decisions": [],
                "risks": [],
                "tags": []
            }
    
    def _build_summary(
        self,
        transcript: MeetingTranscript,
        meeting_title: str,
        meeting_date: datetime,
        participants: List[str],
        summary_data: Dict[str, Any]
    ) -> MeetingSummary:
        """Build MeetingSummary object from parsed data"""
        
        # Parse agenda topics
        agenda_topics = []
        for topic_data in summary_data.get("agenda_topics", []):
            # Extract action items and decisions for this topic
            topic_action_items = [
                self._parse_action_item(ai, meeting_date=meeting_date) for ai in topic_data.get("action_items", [])
            ]
            topic_decisions = [
                self._parse_decision(d) for d in topic_data.get("decisions", [])
            ]
            topic_risks = [
                self._parse_risk(r) for r in topic_data.get("risks", [])
            ]
            
            agenda_topics.append(AgendaTopic(
                topic=topic_data.get("topic", "General Discussion"),
                summary=topic_data.get("summary", ""),
                key_points=topic_data.get("key_points", []),
                decisions=topic_decisions,
                action_items=topic_action_items,
                risks=topic_risks,
                duration_minutes=topic_data.get("duration_minutes")
            ))
        
        # Parse all action items
        all_action_items = [
            self._parse_action_item(ai, meeting_date=meeting_date) for ai in summary_data.get("action_items", [])
        ]
        
        # Add action items from agenda topics
        for topic in agenda_topics:
            all_action_items.extend(topic.action_items)
        
        # Post-process: Scan transcript for completed tasks that LLM might have missed
        completed_tasks = self._extract_completed_tasks_from_transcript(transcript, participants)
        for completed_task in completed_tasks:
            # Check if this task is already in action items
            task_already_exists = any(
                self._tasks_match(completed_task["description"], item.description) 
                for item in all_action_items
            )
            if not task_already_exists:
                # Validate owner before adding
                owner = completed_task.get("owner", "Unassigned")
                owner_str = str(owner).strip() if owner else "Unassigned"
                # Check for invalid owners (date, deadline, etc.)
                invalid_owners = ["date", "deadline", "n/a", "na", "none", "null", "unknown", "tbd"]
                if owner_str.lower() in invalid_owners:
                    owner = "Unassigned"
                    print(f"  Warning: Post-processed completed task has invalid owner '{owner_str}' - setting to 'Unassigned'")
                
                # Add the completed task as an action item
                all_action_items.append(ActionItem(
                    description=completed_task["description"],
                    owner=owner,
                    deadline=None,  # Done items have no deadline
                    status=ActionItemStatus.DONE,
                    dependencies=[],
                    tags=[]
                ))
                print(f"  → Post-processed: Added completed task '{completed_task['description'][:50]}...' as DONE")
        
        # Parse decisions
        all_decisions = [
            self._parse_decision(d) for d in summary_data.get("decisions", [])
        ]
        for topic in agenda_topics:
            all_decisions.extend(topic.decisions)
        
        # Parse risks
        all_risks = [
            self._parse_risk(r) for r in summary_data.get("risks", [])
        ]
        for topic in agenda_topics:
            all_risks.extend(topic.risks)
        
        # Calculate duration
        duration = None
        if transcript.segments:
            last_segment = max(transcript.segments, key=lambda s: s.get('end', 0))
            duration = last_segment.get('end', 0) / 60  # Convert to minutes
        
        # Extract meeting type (validate it's one of the allowed values)
        meeting_type_raw = summary_data.get("meeting_type", "general")
        allowed_types = ["discussion", "KT", "decision_making", "general"]
        meeting_type = meeting_type_raw if meeting_type_raw in allowed_types else "general"
        
        return MeetingSummary(
            project_name=transcript.project_name,
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            meeting_type=meeting_type,
            participants=participants,
            duration_minutes=duration,
            agenda_topics=agenda_topics,
            overall_summary=summary_data.get("overall_summary", ""),
            all_action_items=all_action_items,
            all_decisions=all_decisions,
            all_risks=all_risks,
            tags=summary_data.get("tags", []),
            transcript_path=transcript.file_path
        )
    
    def _parse_action_item(self, data: Dict[str, Any], meeting_date: Optional[datetime] = None, default_deadline_days: int = 3) -> ActionItem:
        """Parse action item from dictionary
        
        Args:
            data: Action item data dictionary
            meeting_date: Meeting date/time to calculate default deadline from
            default_deadline_days: Number of days to add to meeting date if no deadline specified (default: 3)
        """
        deadline_str = data.get("deadline")
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str)
            except ValueError:
                try:
                    deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                except ValueError:
                    deadline = None
        
        # Get status first to check if item is done
        status_str = data.get("status", "new")
        try:
            status = ActionItemStatus(status_str)
        except ValueError:
            status = ActionItemStatus.NEW
        
        # Check description for completion keywords as fallback
        description = data.get("description", "").lower()
        has_completion = any(phrase in description for phrase in [
            "completed", "finished", "is done", "has been completed",
            "that's been completed", "that task is done", "completed yesterday",
            "has been finished", "task completed", "is finished", "done",
            "i completed", "i finished", "completed the", "finished the"
        ])
        
        if has_completion and status != ActionItemStatus.DONE:
            status = ActionItemStatus.DONE
        
        # If no deadline was mentioned, set default to 3 days from meeting date
        # BUT: For done items, don't set a deadline (or set to None)
        if status == ActionItemStatus.DONE:
            deadline = None
        elif deadline is None and meeting_date is not None:
            deadline = meeting_date + timedelta(days=default_deadline_days)
            # Set time to end of day (23:59:59) for the deadline
            deadline = deadline.replace(hour=23, minute=59, second=59, microsecond=0)
        
        # Handle None values for list fields (when key exists but value is None)
        dependencies = data.get("dependencies")
        if dependencies is None:
            dependencies = []
        
        tags = data.get("tags")
        if tags is None:
            tags = []
        
        # Get status first to check if item is done
        status_str = data.get("status", "new")
        try:
            status = ActionItemStatus(status_str)
        except ValueError:
            status = ActionItemStatus.NEW
        
        # Check description for completion keywords as fallback
        description = data.get("description", "").lower()
        has_completion = any(phrase in description for phrase in [
            "completed", "finished", "is done", "has been completed",
            "that's been completed", "that task is done", "completed yesterday",
            "has been finished", "task completed", "is finished", "done",
            "i completed", "i finished", "completed the", "finished the"
        ])
        
        if has_completion and status != ActionItemStatus.DONE:
            status = ActionItemStatus.DONE
        
        # If no deadline was mentioned, set default to 3 days from meeting date
        # BUT: For done items, don't set a deadline (or set to None)
        if status == ActionItemStatus.DONE:
            deadline = None
        elif deadline is None and meeting_date is not None:
            deadline = meeting_date + timedelta(days=default_deadline_days)
            # Set time to end of day (23:59:59) for the deadline
            deadline = deadline.replace(hour=23, minute=59, second=59, microsecond=0)
        
        # Validate and fix owner field - ensure it's not a date or invalid value
        owner = data.get("owner", "Unassigned")
        if owner:
            owner_str = str(owner).strip()
            # Check if owner looks like a date (YYYY-MM-DD, MM/DD/YYYY, etc.)
            date_patterns = [
                r'^\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'^\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
                r'^\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
                r'yesterday', r'today', r'tomorrow',  # Relative dates
                r'monday', r'tuesday', r'wednesday', r'thursday', r'friday', r'saturday', r'sunday',  # Days
            ]
            is_date = any(re.match(pattern, owner_str.lower()) for pattern in date_patterns)
            
            # Also check for invalid owner values (placeholders that shouldn't be used)
            # Note: "Unassigned" (capitalized) is valid as a default, but lowercase variants and placeholders are not
            invalid_owners = ["date", "deadline", "n/a", "na", "none", "null", "unknown", "tbd", "to be determined"]
            is_invalid = owner_str.lower() in invalid_owners
            
            if is_date or is_invalid:
                # Owner is invalid - set to Unassigned since we can't determine the actual owner
                print(f"  Warning: Owner field contains invalid value '{owner_str}' - setting to 'Unassigned'")
                owner = "Unassigned"
        
        # Use the status we determined (with completion detection)
        return ActionItem(
            description=data.get("description", ""),
            owner=owner,
            deadline=deadline,
            status=status,  # Use the status we determined above (with completion detection)
            dependencies=dependencies,
            tags=tags
        )
    
    def _parse_decision(self, data: Dict[str, Any]) -> Decision:
        """Parse decision from dictionary"""
        # Handle None values for list fields (when key exists but value is None)
        decision_makers = data.get("decision_makers")
        if decision_makers is None:
            decision_makers = []
        
        return Decision(
            description=data.get("description", ""),
            context=data.get("context"),
            decision_makers=decision_makers
        )
    
    def _parse_risk(self, data: Dict[str, Any]) -> Risk:
        """Parse risk from dictionary"""
        return Risk(
            description=data.get("description", ""),
            severity=data.get("severity", "medium"),
            impact=data.get("impact"),
            mitigation=data.get("mitigation"),
            owner=data.get("owner")
        )
    
    def _extract_completed_tasks_from_transcript(
        self, 
        transcript: MeetingTranscript, 
        participants: List[str]
    ) -> List[Dict[str, str]]:
        """
        Post-process transcript to extract completed tasks that LLM might have missed.
        
        Looks for patterns like:
        - "I completed [task]"
        - "[task] is done"
        - "That task from [day] is done"
        - "[task] - completed"
        
        Returns:
            List of dictionaries with 'description' and 'owner' keys
        """
        completed_tasks = []
        transcript_text = transcript.transcript_text.lower()
        
        # Pattern 1: "I completed [task]" or "I finished [task]"
        pattern1 = r'(?:i|we)\s+(?:completed|finished)\s+([^.,!?]+?)(?:\.|,|!|\s+yesterday|\s+today|\s+last\s+week)'
        matches1 = re.finditer(pattern1, transcript_text, re.IGNORECASE)
        for match in matches1:
            task_desc = match.group(1).strip()
            # Find the speaker (look backwards for speaker name)
            speaker = self._find_speaker_for_text(transcript, match.start(), participants)
            if task_desc and len(task_desc) > 3:
                completed_tasks.append({
                    "description": f"{task_desc} - completed",
                    "owner": speaker or "Unassigned"
                })
        
        # Pattern 2: "[task] is done" or "[task] - completed"
        pattern2 = r'([^.,!?]+?)\s+(?:is\s+)?done(?:\.|,|!|\s+from\s+\w+day)?'
        matches2 = re.finditer(pattern2, transcript_text, re.IGNORECASE)
        for match in matches2:
            task_desc = match.group(1).strip()
            # Skip if it's just "that" or "this" or "it"
            if task_desc.lower() in ["that", "this", "it", "the task", "that task"]:
                continue
            speaker = self._find_speaker_for_text(transcript, match.start(), participants)
            if task_desc and len(task_desc) > 3 and not any(word in task_desc.lower() for word in ["that", "this", "it"]):
                completed_tasks.append({
                    "description": f"{task_desc} - done",
                    "owner": speaker or "Unassigned"
                })
        
        # Pattern 3: "That task from [day] is done"
        pattern3 = r'(?:that|the)\s+task\s+from\s+\w+day\s+is\s+done'
        matches3 = re.finditer(pattern3, transcript_text, re.IGNORECASE)
        for match in matches3:
            # Try to find the task name from context (look for mentions of tasks before this)
            speaker = self._find_speaker_for_text(transcript, match.start(), participants)
            # Try to extract task name from surrounding context
            context_start = max(0, match.start() - 200)
            context = transcript_text[context_start:match.start()]
            # Look for task mentions in context
            task_match = re.search(r'(?:api\s+integration|schema|sync|reporting|features)', context, re.IGNORECASE)
            if task_match:
                task_name = task_match.group(0)
                completed_tasks.append({
                    "description": f"{task_name} - completed (from previous meeting)",
                    "owner": speaker or "Unassigned"
                })
        
        # Remove duplicates
        seen = set()
        unique_tasks = []
        for task in completed_tasks:
            task_key = (task["description"].lower(), task["owner"].lower())
            if task_key not in seen:
                seen.add(task_key)
                unique_tasks.append(task)
        
        return unique_tasks
    
    def _find_speaker_for_text(
        self, 
        transcript: MeetingTranscript, 
        text_position: int, 
        participants: List[str]
    ) -> Optional[str]:
        """
        Find the speaker who said the text at the given position.
        
        Args:
            transcript: Meeting transcript
            text_position: Character position in transcript text
            participants: List of participant names
            
        Returns:
            Speaker name or None
        """
        if not transcript.segments:
            # Try to find speaker from transcript text format (e.g., "Bob: ...")
            transcript_text = transcript.transcript_text[:text_position]
            # Look backwards for speaker pattern
            speaker_match = re.search(r'(\w+):\s*[^:]*$', transcript_text, re.MULTILINE)
            if speaker_match:
                return speaker_match.group(1)
            return None
        
        # Find which segment contains this position
        current_pos = 0
        for segment in transcript.segments:
            segment_text = segment.get("text", "")
            segment_length = len(segment_text)
            
            if current_pos <= text_position < current_pos + segment_length:
                speaker = segment.get("speaker")
                if speaker:
                    return speaker
            
            current_pos += segment_length + 1  # +1 for newline
        
        return None
    
    def _tasks_match(self, desc1: str, desc2: str) -> bool:
        """
        Check if two task descriptions match (fuzzy match).
        
        Args:
            desc1: First description
            desc2: Second description
            
        Returns:
            True if tasks match
        """
        desc1_lower = desc1.lower()
        desc2_lower = desc2.lower()
        
        # Extract key phrases (remove common words)
        words1 = set(re.findall(r'\b\w{4,}\b', desc1_lower))
        words2 = set(re.findall(r'\b\w{4,}\b', desc2_lower))
        
        # Remove common action words
        common_words = {"completed", "finished", "done", "task", "from", "that", "this", "the", "with"}
        words1 = words1 - common_words
        words2 = words2 - common_words
        
        # Check overlap
        if not words1 or not words2:
            return False
        
        overlap = len(words1.intersection(words2))
        total_unique = len(words1.union(words2))
        
        # If 50%+ overlap, consider it a match
        return overlap / total_unique >= 0.5 if total_unique > 0 else False


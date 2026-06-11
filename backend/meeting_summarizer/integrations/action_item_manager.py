"""
Action Item Management Module

Handles integration with Trello for task tracking and email reminder system
for action items approaching their deadlines.
"""

# Standard library imports
import json
import smtplib
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import httpx

# Local imports
from ..config import Config
from ..models import ActionItem, ActionItemStatus
from ..core.storage import Storage


class ActionItemManager:
    """
    Manage action items and integrate with task management tools.
    
    Handles Trello integration for syncing action items and sending
    email reminders for items approaching deadlines.
    """
    
    # ============================================================================
    # Initialization
    # ============================================================================
    
    def __init__(self) -> None:
        """Initialize action item manager with Trello client and board cache."""
        self.trello_client = None
        self.board_cache: Dict[str, str] = {}  # Cache: project_name -> board_id
        self._board_cache_file = Config.DATA_DIR / "trello_boards.json"
        self._graph_access_token: Optional[str] = None  # Cache for Graph API token
        self._graph_token_expires_at: Optional[datetime] = None  # Token expiration time
        self._initialize_trello_client()
        self._load_board_cache()
    
    def _initialize_trello_client(self) -> None:
        """Initialize Trello client if API credentials are configured."""
        if Config.TRELLO_API_KEY and Config.TRELLO_API_TOKEN:
            try:
                from trello import TrelloClient
                self.trello_client = TrelloClient(
                    api_key=Config.TRELLO_API_KEY,
                    token=Config.TRELLO_API_TOKEN
                )
            except ImportError:
                print("Warning: py-trello not installed. Trello integration disabled.")
            except Exception as e:
                print(f"Warning: Could not initialize Trello client: {e}")
    
    # ============================================================================
    # Board Cache Management
    # ============================================================================
    
    def _load_board_cache(self) -> None:
        """Load board ID cache from JSON file."""
        if self._board_cache_file.exists():
            try:
                with open(self._board_cache_file, 'r', encoding='utf-8') as f:
                    self.board_cache = json.load(f)
            except Exception:
                self.board_cache = {}
    
    def _save_board_cache(self) -> None:
        """Save board ID cache to JSON file."""
        try:
            with open(self._board_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.board_cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save board cache: {e}")
    
    # ============================================================================
    # Board Management
    # ============================================================================
    
    def _get_or_create_board(self, project_name: str) -> Optional[str]:
        """
        Get existing board ID or create a new board for the project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Board ID or None if creation fails
        """
        if not self.trello_client:
            return None
        
        # Check cache first
        if project_name in self.board_cache:
            board_id = self.board_cache[project_name]
            try:
                # Verify board still exists and is not closed
                board = self.trello_client.get_board(board_id)
                if board.closed:
                    # Board is closed, delete it and remove from cache
                    print(f"Found closed board in cache: {project_name}. Deleting it...")
                    try:
                        board.delete()
                        print(f"✓ Deleted closed board from cache: {project_name}")
                    except Exception as e:
                        print(f"Warning: Could not delete closed board: {e}")
                    del self.board_cache[project_name]
                    self._save_board_cache()
                else:
                    return board_id
            except Exception:
                # Board doesn't exist, remove from cache
                del self.board_cache[project_name]
                self._save_board_cache()
        
        # Try to find existing board by name (including closed boards)
        try:
            all_boards = self.trello_client.list_boards(board_filter='all')  # Include closed boards
            for board in all_boards:
                if board.name == project_name:
                    # If board is closed, delete it first and create a new one
                    if board.closed:
                        print(f"Found closed Trello board: {project_name}. Deleting it to create a new one...")
                        try:
                            board.delete()
                            print(f"✓ Deleted closed board: {project_name}")
                        except Exception as e:
                            print(f"Warning: Could not delete closed board: {e}")
                            # If delete fails, try to reopen it
                            try:
                                board.open()
                                board_id = board.id
                                self.board_cache[project_name] = board_id
                                self._save_board_cache()
                                print(f"✓ Reopened closed Trello board: {project_name} (ID: {board_id})")
                                return board_id
                            except Exception:
                                pass
                        # Continue to create new board below
                        break
                    else:
                        # Board exists and is open
                        board_id = board.id
                        self.board_cache[project_name] = board_id
                        self._save_board_cache()
                        print(f"✓ Found existing Trello board: {project_name} (ID: {board_id})")
                        return board_id
        except Exception as e:
            print(f"Warning: Could not list boards: {e}")
        
        # Create new board
        try:
            print(f"Creating new Trello board for project: {project_name}")
            # add_board creates default lists automatically (To Do, Doing, Done)
            new_board = self.trello_client.add_board(project_name, default_lists=True)
            board_id = new_board.id
            self.board_cache[project_name] = board_id
            self._save_board_cache()
            print(f"✓ Created Trello board: {project_name} (ID: {board_id})")
            print("  Default lists created automatically")
            return board_id
        except Exception as e:
            print(f"Error creating Trello board: {e}")
            return None
    
    # ============================================================================
    # List Management
    # ============================================================================
    
    def _get_or_create_delete_list(self, board_id: str) -> Optional[object]:
        """
        Get or create a "delete" list on the board for archiving cards.
        
        Args:
            board_id: ID of the board
            
        Returns:
            List object or None if creation fails
        """
        if not self.trello_client:
            return None
        
        try:
            board = self.trello_client.get_board(board_id)
            list_name = "delete"
            
            # Try to find existing "delete" list
            for lst in board.list_lists():
                if lst.name.lower() == list_name.lower():
                    return lst
            
            # Create "delete" list if it doesn't exist
            delete_list = board.add_list(list_name)
            print("  ✓ Created 'delete' list on board")
            return delete_list
        except Exception as e:
            print(f"Warning: Could not get or create delete list: {e}")
            return None
    
    def _get_or_create_list(self, board_id: str, list_name: str) -> Optional[object]:
        """
        Get or create a list on the board.
        
        Args:
            board_id: ID of the board
            list_name: Name of the list to get or create
            
        Returns:
            List object or None if creation fails
        """
        if not self.trello_client:
            return None
        
        try:
            board = self.trello_client.get_board(board_id)
            
            # Try to find existing list (case-insensitive)
            for lst in board.list_lists():
                if lst.name.lower() == list_name.lower():
                    return lst
            
            # Create list if it doesn't exist
            new_list = board.add_list(list_name)
            print(f"  ✓ Created '{list_name}' list on board")
            return new_list
        except Exception as e:
            print(f"Warning: Could not get or create list '{list_name}': {e}")
            return None
    
    def _get_existing_action_items_for_project(self, project_name: str) -> List[Dict]:
        """
        Get existing action items for a project from the database.
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of action item dictionaries
        """
        storage = Storage()
        project_meetings = storage.get_project_meetings(project_name)
        
        existing_items = []
        for meeting_id in project_meetings:
            # Get all action items for this meeting
            items = storage.get_action_items_by_owner("", None)  # Get all items
            # Filter by meeting_id
            for item in items:
                if item.get("meeting_id") == meeting_id:
                    existing_items.append(item)
        
        return existing_items
    
    def _extract_key_phrases(self, description: str) -> set:
        """
        Extract key phrases from action item description for better matching.
        Removes common action words and focuses on the core task.
        
        Args:
            description: Action item description
            
        Returns:
            Set of key phrases
        """
        desc_lower = description.lower()
        
        # Remove common action words
        action_words = [
            "complete", "finish", "continue", "work on", "do", "implement",
            "create", "build", "develop", "fix", "resolve", "update",
            "start", "begin", "handle", "manage", "sync", "sync up"
        ]
        
        # Extract meaningful words (3+ characters, not common words)
        words = desc_lower.split()
        key_words = [w for w in words if len(w) >= 3 and w not in action_words]
        
        # Create phrases (2-3 word combinations)
        phrases = set()
        for i in range(len(key_words)):
            # Single key words
            if len(key_words[i]) >= 4:
                phrases.add(key_words[i])
            # Two-word phrases
            if i < len(key_words) - 1:
                phrases.add(f"{key_words[i]} {key_words[i+1]}")
            # Three-word phrases
            if i < len(key_words) - 2:
                phrases.add(f"{key_words[i]} {key_words[i+1]} {key_words[i+2]}")
        
        return phrases
    
    def _match_action_item(self, new_item: ActionItem, existing_items: List[Dict]) -> Optional[Dict]:
        """
        Match a new action item with an existing one.
        
        Matches by:
        1. external_id if both have it
        2. description + owner (fuzzy match with key phrase extraction)
        
        Args:
            new_item: New action item to match
            existing_items: List of existing action items
            
        Returns:
            Matched existing item dict or None
        """
        # First try to match by external_id
        if new_item.external_id:
            for existing in existing_items:
                if existing.get("external_id") == new_item.external_id:
                    return existing
        
        # Extract key phrases from new item
        new_desc_lower = new_item.description.lower().strip()
        new_owner_lower = new_item.owner.lower().strip()
        new_key_phrases = self._extract_key_phrases(new_desc_lower)
        
        best_match = None
        best_score = 0
        
        for existing in existing_items:
            existing_desc_lower = existing.get("description", "").lower().strip()
            existing_owner_lower = existing.get("owner", "").lower().strip()
            
            # Owner must match
            if existing_owner_lower != new_owner_lower:
                continue
            
            # Extract key phrases from existing item
            existing_key_phrases = self._extract_key_phrases(existing_desc_lower)
            
            # Calculate match score based on overlapping key phrases
            common_phrases = new_key_phrases.intersection(existing_key_phrases)
            if common_phrases:
                score = len(common_phrases) / max(len(new_key_phrases), len(existing_key_phrases), 1)
                if score > best_score:
                    best_score = score
                    best_match = existing
            
            # Also check exact/substring matches (fallback)
            if (existing_desc_lower == new_desc_lower or 
                new_desc_lower in existing_desc_lower or 
                existing_desc_lower in new_desc_lower):
                if best_score < 0.5:  # Prefer key phrase match if score is low
                    return existing
        
        # Return best match if score is reasonable (at least 30% overlap)
        if best_match and best_score >= 0.3:
            return best_match
        
        return None
    
    # ============================================================================
    # Card Management
    # ============================================================================
    
    def _create_trello_card(
        self,
        action_item: ActionItem,
        meeting_title: str,
        board_id: str,
        target_list_name: str = "To Do"
    ) -> str:
        """
        Create a Trello card for an action item in the specified list.
        
        Args:
            action_item: Action item to create card for
            meeting_title: Title of the meeting
            board_id: ID of the Trello board
            target_list_name: Name of the list to create card in (default: "To Do")
            
        Returns:
            Card ID
            
        Raises:
            RuntimeError: If Trello client is not initialized
        """
        if not self.trello_client:
            raise RuntimeError("Trello client not initialized")
        
        board = self.trello_client.get_board(board_id)
        
        # Get or create the target list
        target_list = self._get_or_create_list(board_id, target_list_name)
        if not target_list:
            # Fallback to "To Do" if target list creation fails
            target_list = self._get_or_create_list(board_id, "To Do")
            if not target_list:
                raise RuntimeError("Could not create or find any list on board")
        
        # Create card with formatted description
        card_name = action_item.description[:100]  # Trello card name limit
        
        # For done items, don't show deadline
        if action_item.status == ActionItemStatus.DONE:
            deadline_str = "N/A"
        else:
            deadline_str = action_item.deadline.strftime('%Y-%m-%d') if action_item.deadline else 'Not specified'
        
        card_desc = f"""
**Owner:** {action_item.owner}
**Deadline:** {deadline_str}
**Status:** {action_item.status.value}
**Meeting:** {meeting_title}

**Description:**
{action_item.description}

**Dependencies:**
{chr(10).join(f'- {dep}' for dep in action_item.dependencies) if action_item.dependencies else 'None'}

**Tags:** {', '.join(action_item.tags)}
"""
        
        card = target_list.add_card(card_name, card_desc)
        
        # Set due date only if available and item is not done
        if action_item.deadline and action_item.status != ActionItemStatus.DONE:
            card.set_due(action_item.deadline)
        
        # Add labels/tags
        for tag in action_item.tags:
            try:
                # Try to find existing label
                label = None
                for lbl in board.get_labels():
                    if lbl.name.lower() == tag.lower():
                        label = lbl
                        break
                
                if label:
                    card.add_label(label)
                else:
                    # Create new label
                    label = board.add_label(tag, 'blue')
                    card.add_label(label)
            except Exception as e:
                print(f"Warning: Could not add label {tag}: {e}")
        
        return card.id
    
    def _move_trello_card_to_list(
        self,
        card_id: str,
        board_id: str,
        target_list_name: str,
        remove_deadline: bool = False
    ) -> bool:
        """
        Move an existing Trello card to a different list.
        
        Args:
            card_id: ID of the Trello card
            board_id: ID of the Trello board
            target_list_name: Name of the target list
            remove_deadline: If True, remove deadline from card (for done items)
            
        Returns:
            True if card was moved successfully, False otherwise
        """
        if not self.trello_client:
            return False
        
        try:
            card = self.trello_client.get_card(card_id)
            target_list = self._get_or_create_list(board_id, target_list_name)
            
            if target_list:
                card.change_list(target_list.id)
                
                # Remove deadline if moving to Done list (done items)
                if remove_deadline and card.due_date:
                    try:
                        card.set_due(None)
                    except Exception as e:
                        print(f"Warning: Could not remove deadline from card {card_id}: {e}")
                
                return True
        except Exception as e:
            print(f"Warning: Could not move card {card_id} to {target_list_name}: {e}")
        
        return False
    
    def move_cards_to_delete_list(
        self,
        card_ids: List[str],
        project_name: str
    ) -> int:
        """
        Move multiple cards to the "delete" list.
        
        Args:
            card_ids: List of card IDs to move
            project_name: Name of the project (to get board)
            
        Returns:
            Number of cards successfully moved
        """
        if not self.trello_client or not card_ids:
            return 0
        
        board_id = self._get_or_create_board(project_name)
        if not board_id:
            return 0
        
        delete_list = self._get_or_create_delete_list(board_id)
        if not delete_list:
            return 0
        
        moved_count = 0
        for card_id in card_ids:
            try:
                card = self.trello_client.get_card(card_id)
                card.change_list(delete_list.id)
                moved_count += 1
            except Exception as e:
                print(f"    Warning: Could not move card {card_id}: {e}")
        
        return moved_count
    
    def archive_all_cards_in_delete_list(self, project_name: str) -> int:
        """
        Archive all cards in the "delete" list.
        
        Args:
            project_name: Name of the project (to get board)
            
        Returns:
            Number of cards successfully archived
        """
        if not self.trello_client:
            return 0
        
        board_id = self._get_or_create_board(project_name)
        if not board_id:
            return 0
        
        try:
            board = self.trello_client.get_board(board_id)
            delete_list = None
            
            # Find "delete" list
            for lst in board.list_lists():
                if lst.name.lower() == "delete":
                    delete_list = lst
                    break
            
            if not delete_list:
                print("  No 'delete' list found - nothing to archive")
                return 0
            
            # Get all cards in the delete list (filter out already archived cards)
            cards = delete_list.list_cards()
            archived_count = 0
            
            for card in cards:
                try:
                    # Skip if already archived
                    if card.closed:
                        continue
                    card.set_closed(True)
                    archived_count += 1
                except Exception as e:
                    print(f"    Warning: Could not archive card {card.id}: {e}")
            
            return archived_count
        except Exception as e:
            print(f"Warning: Could not archive cards in delete list: {e}")
            return 0
    
    # ============================================================================
    # Action Item Synchronization
    # ============================================================================
    
    def sync_action_items(
        self,
        action_items: List[ActionItem],
        project_name: str,
        meeting_title: str
    ) -> List[ActionItem]:
        """
        Sync action items to Trello, categorizing them into appropriate lists:
        - Done tasks → "Done" list
        - Doing tasks (in progress) → "Doing" list
        - New and pending tasks → "To Do" list
        
        Args:
            action_items: List of action items to sync
            project_name: Name of the project
            meeting_title: Title of the meeting
            
        Returns:
            Updated list of action items with external IDs
        """
        synced_items = []
        
        # Get or create board for the project
        board_id = self._get_or_create_board(project_name)
        if not board_id:
            print("Warning: Could not get or create Trello board. Skipping sync.")
            return action_items
        
        # Get existing action items for the project to determine status
        existing_items = self._get_existing_action_items_for_project(project_name)
        
        # Ensure required lists exist
        if self.trello_client:
            self._get_or_create_list(board_id, "To Do")
            self._get_or_create_list(board_id, "Doing")
            self._get_or_create_list(board_id, "Done")
            self._get_or_create_list(board_id, "Pending")  # For overdue items
        
        for item in action_items:
            # Match with existing action item
            matched_item = self._match_action_item(item, existing_items)
            
            # If existing item has external_id, use it
            if matched_item and matched_item.get("external_id"):
                item.external_id = matched_item.get("external_id")
            
            # Get status from matched item if available
            existing_status = None
            if matched_item:
                existing_status = matched_item.get("status")
                # Handle both enum and string status
                if isinstance(existing_status, str):
                    try:
                        existing_status = ActionItemStatus(existing_status)
                    except ValueError:
                        existing_status = None
            
            # Determine status progression logic:
            # - If item is matched and has progress mentioned → DOING
            # - If item is matched with no progress → PENDING
            # - If item is done → DONE
            # - If item is new (no match) → NEW
            
            # Check if item is done (highest priority)
            # Priority: LLM-assigned status > completion keywords > existing status
            is_done = (item.status == ActionItemStatus.DONE) or \
                     (existing_status == ActionItemStatus.DONE)
            
            # Also check description for completion keywords (even if status not set by LLM)
            description_lower = item.description.lower()
            has_completion_in_desc = any(phrase in description_lower for phrase in [
                "completed", "finished", "is done", "has been completed",
                "that's been completed", "that task is done", "completed yesterday",
                "has been finished", "task completed", "is finished", "done",
                "i completed", "i finished", "completed the", "finished the"
            ])
            
            if has_completion_in_desc and not is_done:
                # LLM might have missed it, but description indicates completion
                is_done = True
                item.status = ActionItemStatus.DONE
                print(f"  → Detected completion in description '{item.description[:50]}...' → Marking as DONE")
            
            # Determine target list and status based on progression
            target_list_name = "To Do"  # Default
            
            if is_done:
                # Done items always go to Done list
                target_list_name = "Done"
                item.deadline = None
                item.status = ActionItemStatus.DONE
                print(f"  → Action item '{item.description[:50]}...' is DONE → Moving to 'Done' list")
            elif item.status == ActionItemStatus.DOING:
                # Item is actively being worked on
                target_list_name = "Doing"
                item.status = ActionItemStatus.DOING
            elif item.status == ActionItemStatus.PENDING:
                # Same item repeated with no progress
                target_list_name = "To Do"
                item.status = ActionItemStatus.PENDING
            elif item.status == ActionItemStatus.NEW:
                # New item
                target_list_name = "To Do"
                item.status = ActionItemStatus.NEW
            elif matched_item:
                # Item exists - determine status based on progress
                # FIRST: Check if item is completed/done (highest priority)
                description_lower = item.description.lower()
                
                # Check for completion keywords in description
                has_completion_keywords = any(phrase in description_lower for phrase in [
                    "completed", "finished", "is done", "has been completed",
                    "that's been completed", "that task is done", "completed yesterday",
                    "has been finished", "task completed", "is finished", "done",
                    "i completed", "i finished", "completed the", "finished the"
                ])
                
                # Also check if the item status is already set to DONE by LLM
                if item.status == ActionItemStatus.DONE:
                    has_completion_keywords = True
                
                if has_completion_keywords:
                    # Item is completed → DONE
                    item.status = ActionItemStatus.DONE
                    target_list_name = "Done"
                    item.deadline = None
                    print(f"  → Detected completion keywords in '{item.description[:50]}...' → Marking as DONE")
                else:
                    # Check if current item description suggests progress
                    has_progress_indicators = any(phrase in description_lower for phrase in [
                        "working on", "in progress", "doing", "% done", "started", 
                        "implementing", "developing", "building", "60%", "about"
                    ])
                
                    if has_progress_indicators or existing_status == ActionItemStatus.DOING:
                        # Has progress → DOING
                        item.status = ActionItemStatus.DOING
                        target_list_name = "Doing"
                    elif existing_status == ActionItemStatus.PENDING:
                        # Still pending (no progress) → PENDING
                        item.status = ActionItemStatus.PENDING
                        target_list_name = "To Do"
                    elif existing_status == ActionItemStatus.NEW:
                        # Was new, check if there's progress now
                        if has_progress_indicators:
                            item.status = ActionItemStatus.DOING
                            target_list_name = "Doing"
                        else:
                            item.status = ActionItemStatus.PENDING  # Transition from NEW to PENDING
                            target_list_name = "To Do"
                    else:
                        # Default: keep existing status or set to pending
                        if existing_status:
                            item.status = existing_status
                            if existing_status == ActionItemStatus.DOING:
                                target_list_name = "Doing"
                            elif existing_status == ActionItemStatus.DONE:
                                target_list_name = "Done"
                                item.deadline = None
                            else:
                                target_list_name = "To Do"
                        else:
                            item.status = ActionItemStatus.PENDING
                            target_list_name = "To Do"
            else:
                # New item with no match - default to NEW status
                item.status = ActionItemStatus.NEW
                target_list_name = "To Do"
            
            # Check if item is overdue and should be moved to Pending list
            # Only move if it's currently assigned to "To Do" list and deadline has passed
            if target_list_name == "To Do" and item.deadline:
                now = datetime.now()
                # Compare dates (ignore time for deadline comparison)
                deadline_date = item.deadline.date() if hasattr(item.deadline, 'date') else item.deadline
                now_date = now.date() if hasattr(now, 'date') else now
                
                if deadline_date < now_date:
                    # Item is overdue and in To Do → Move to Pending list
                    target_list_name = "Pending"
                    item.status = ActionItemStatus.PENDING
                    print(f"  → Action item '{item.description[:50]}...' is OVERDUE (due: {deadline_date}) → Moving to 'Pending' list")
            
            # Sync to Trello (including done items - they should be in Done list)
            if self.trello_client:
                try:
                    print(f"  Syncing action item '{item.description[:50]}...' (status: {item.status.value}) → {target_list_name} list")
                    if item.external_id:
                        # Card already exists - move it to the correct list
                        # Remove deadline if moving to Done list
                        remove_deadline = (target_list_name == "Done")
                        moved = self._move_trello_card_to_list(
                            item.external_id,
                            board_id,
                            target_list_name,
                            remove_deadline=remove_deadline
                        )
                        if moved:
                            print(f"    ✓ Moved card to {target_list_name} list")
                        else:
                            print(f"    ✗ Warning: Could not move card {item.external_id} to {target_list_name}")
                    else:
                        # Create new card in the appropriate list (including Done list for done items)
                        external_id = self._create_trello_card(
                            item,
                            meeting_title,
                            board_id,
                            target_list_name
                        )
                        if external_id:
                            item.external_id = external_id
                            print(f"    ✓ Created card in {target_list_name} list")
                            # Send assignment reminder for new tasks (not done)
                            if item.status != ActionItemStatus.DONE and Config.REMINDER_ENABLED:
                                self.send_assignment_reminder(item, project_name)
                        else:
                            print(f"    ✗ Warning: Card creation returned None for {target_list_name} list")
                except Exception as e:
                    print(f"    ✗ Warning: Could not sync Trello card: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"  Warning: Trello client not initialized - skipping sync for '{item.description[:50]}...'")
            
            # Always append item to synced_items (even if Trello sync failed)
            synced_items.append(item)
        
        # After syncing all items, check for overdue items in To Do list and move them to Pending
        if self.trello_client:
            moved_count = self.move_overdue_items_to_pending(project_name)
            if moved_count > 0:
                print(f"  → Moved {moved_count} overdue card(s) from 'To Do' to 'Pending' list")
        
        return synced_items
    
    def move_overdue_items_to_pending(self, project_name: str) -> int:
        """
        Check all cards in "To Do" list and move overdue items to "Pending" list.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Number of cards moved to Pending list
        """
        if not self.trello_client:
            return 0
        
        board_id = self._get_or_create_board(project_name)
        if not board_id:
            return 0
        
        # Ensure Pending list exists
        pending_list = self._get_or_create_list(board_id, "Pending")
        if not pending_list:
            return 0
        
        try:
            board = self.trello_client.get_board(board_id)
            todo_list = None
            
            # Find "To Do" list
            for lst in board.list_lists():
                if "todo" in lst.name.lower() or "to do" in lst.name.lower():
                    todo_list = lst
                    break
            
            if not todo_list:
                return 0
            
            # Get all cards in To Do list
            cards = todo_list.list_cards()
            moved_count = 0
            now = datetime.now()
            
            for card in cards:
                try:
                    # Check if card has a due date
                    if card.due_date:
                        due_date = card.due_date
                        if isinstance(due_date, str):
                            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                        
                        # Check if overdue
                        if due_date.date() < now.date():
                            # Move to Pending list
                            card.change_list(pending_list.id)
                            moved_count += 1
                            print(f"  → Moved overdue card '{card.name[:50]}...' to Pending list")
                except Exception as e:
                    print(f"    Warning: Could not check/move card {card.id}: {e}")
            
            return moved_count
        except Exception as e:
            print(f"Warning: Could not move overdue items to pending: {e}")
            return 0
    
    def update_action_item_status(
        self,
        action_item: ActionItem,
        new_status: ActionItemStatus,
        project_name: str
    ) -> ActionItem:
        """
        Update action item status in external system (Trello).
        
        Args:
            action_item: Action item to update
            new_status: New status for the action item
            project_name: Name of the project
            
        Returns:
            Updated action item
        """
        action_item.status = new_status
        action_item.updated_at = datetime.now()
        
        # Update in Trello if synced
        if action_item.external_id and self.trello_client:
            try:
                # Get board ID for the project
                board_id = self._get_or_create_board(project_name)
                if not board_id:
                    return action_item
                
                # Get card using TrelloClient's get_card method
                card = self.trello_client.get_card(action_item.external_id)
                
                # Move to appropriate list based on status
                board = self.trello_client.get_board(board_id)
                
                if new_status == ActionItemStatus.DONE:
                    # Find "Done" list
                    for lst in board.list_lists():
                        if "done" in lst.name.lower() or "completed" in lst.name.lower():
                            card.change_list(lst.id)
                            break
                elif new_status == ActionItemStatus.DOING:
                    # Find "Doing" list
                    for lst in board.list_lists():
                        if "doing" in lst.name.lower() or "progress" in lst.name.lower():
                            card.change_list(lst.id)
                            break
                elif new_status == ActionItemStatus.PENDING:
                    # Check if item is overdue - if so, move to Pending list, otherwise To Do
                    # Check if card has a due date that's passed
                    target_list_name = "To Do"
                    if card.due_date:
                        try:
                            due_date = card.due_date
                            if isinstance(due_date, str):
                                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                            now = datetime.now()
                            if due_date.date() < now.date():
                                target_list_name = "Pending"
                        except Exception:
                            pass
                    
                    # Find appropriate list
                    for lst in board.list_lists():
                        if target_list_name == "Pending" and "pending" in lst.name.lower():
                            card.change_list(lst.id)
                            break
                        elif target_list_name == "To Do" and ("todo" in lst.name.lower() or "to do" in lst.name.lower()):
                            card.change_list(lst.id)
                            break
                elif new_status == ActionItemStatus.NEW:
                    # Find "To Do" list for new items
                    for lst in board.list_lists():
                        if "todo" in lst.name.lower() or "to do" in lst.name.lower():
                            card.change_list(lst.id)
                            break
            except Exception as e:
                print(f"Warning: Could not update Trello card: {e}")
        
        return action_item
    
    # ============================================================================
    # Reminder System
    # ============================================================================
    
    def get_pending_reminders(self) -> List[ActionItem]:
        """
        Get action items that need reminders sent (24 hours before deadline).
        Also checks Trello for manual deadline changes.
        
        Returns:
            List of action items approaching deadlines
        """
        if not Config.REMINDER_ENABLED:
            return []
        
        storage = Storage()
        all_items = []
        
        # Get all pending, doing, and new action items from database (exclude done items)
        for status in [ActionItemStatus.NEW, ActionItemStatus.PENDING, ActionItemStatus.DOING]:
            items = storage.get_action_items_by_owner("", status)  # Empty string gets all
            all_items.extend(items)
        
        # Sync deadlines from Trello (if Trello is enabled)
        if self.trello_client:
            all_items = self._sync_deadlines_from_trello(all_items)
        
        # Filter items that need reminders (within 24 hours)
        now = datetime.now()
        reminder_items = []
        
        for item_data in all_items:
            deadline = item_data.get("deadline")
            if not deadline:
                continue
            
            # Calculate time difference
            time_diff = deadline - now
            hours_until_deadline = time_diff.total_seconds() / 3600
            
            # Send reminder if deadline is within 12-24 hours (not too early, not past)
            if 12 <= hours_until_deadline <= 24:
                # Reconstruct ActionItem from dict
                action_item = ActionItem(
                    id=item_data["id"],
                    description=item_data["description"],
                    owner=item_data["owner"],
                    deadline=deadline,
                    status=item_data["status"],
                    dependencies=item_data.get("dependencies", []),
                    tags=item_data.get("tags", []),
                    external_id=item_data.get("external_id")
                )
                reminder_items.append(action_item)
        
        return reminder_items
    
    def _sync_deadlines_from_trello(self, items: List[Dict]) -> List[Dict]:
        """
        Sync deadlines from Trello cards (detect manual changes).
        
        Args:
            items: List of action item dictionaries from database
            
        Returns:
            Updated list of items with synced deadlines
        """
        if not self.trello_client:
            return items
        
        updated_items = []
        
        for item_data in items:
            external_id = item_data.get("external_id")
            if not external_id:
                updated_items.append(item_data)
                continue
            
            try:
                # Get card from Trello
                card = self.trello_client.get_card(external_id)
                
                # Check if due date exists and is different
                trello_due = card.due_date if hasattr(card, 'due_date') and card.due_date else None
                db_deadline = item_data.get("deadline")
                
                if trello_due:
                    # Parse Trello due date
                    try:
                        if isinstance(trello_due, str):
                            trello_deadline = datetime.fromisoformat(trello_due.replace('Z', '+00:00'))
                        else:
                            trello_deadline = trello_due
                        
                        # Update if different (manual change detected)
                        if not db_deadline or abs((trello_deadline - db_deadline).total_seconds()) > 60:
                            item_data["deadline"] = trello_deadline
                            # Update in database
                            storage = Storage()
                            storage.update_action_item_deadline(item_data["id"], trello_deadline)
                            print(f"✓ Updated deadline in database for card {external_id}: {db_deadline} -> {trello_deadline}")
                    except Exception as e:
                        print(f"Warning: Could not parse Trello due date: {e}")
                
            except Exception as e:
                print(f"Warning: Could not sync deadline from Trello card {external_id}: {e}")
            
            updated_items.append(item_data)
        
        return updated_items
    
    def send_unassigned_items_notification(
        self,
        owner_email: str,
        owner_name: str,
        unassigned_items: List[ActionItem],
        meeting_title: str,
        project_name: str
    ) -> bool:
        """
        Send email notification to project owner about unassigned action items.
        
        Args:
            owner_email: Email address of project owner
            owner_name: Name of project owner
            unassigned_items: List of action items that need assignment
            meeting_title: Title of the meeting
            project_name: Name of the project
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not Config.REMINDER_ENABLED or not Config.SMTP_SERVER:
            return False
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_FROM
            msg['To'] = owner_email
            msg['Subject'] = f"Action Items Requiring Assignment - {meeting_title}"
            
            # Build email body
            items_list = "\n".join([
                f"{i+1}. {item.description}\n   Deadline: {item.deadline.strftime('%Y-%m-%d') if item.deadline else 'Not specified'}"
                for i, item in enumerate(unassigned_items)
            ])
            
            body = f"""
Dear {owner_name},

The following action items from the meeting "{meeting_title}" (Project: {project_name}) 
have been temporarily assigned to you because the original owner could not be determined 
from the meeting transcript.

Please review and assign these items to the appropriate team members:

{items_list}

You can update the assignments in Trello or through the application.

Thank you,
Meeting Transcript Summarizer
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                if Config.SMTP_PORT == 587:
                    server.starttls()
                if Config.SMTP_USERNAME and Config.SMTP_PASSWORD:
                    server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Error sending unassigned items notification: {e}")
            return False
    
    def send_reminder(self, action_item: ActionItem) -> bool:
        """
        Send reminder for an action item (12-24 hours before deadline).
        Uses Trello API if SMTP not configured, otherwise tries email first.
        
        Args:
            action_item: Action item to send reminder for
            
        Returns:
            True if reminder sent successfully
        """
        if not action_item.deadline:
            return False
        
        now = datetime.now()
        time_diff = action_item.deadline - now
        hours_until_deadline = time_diff.total_seconds() / 3600
        
        # Check if deadline is within 12-24 hours (not too early, not past)
        if not (12 <= hours_until_deadline <= 24):
            return False
        
        # Check what email methods are available
        smtp_configured = Config.SMTP_USERNAME and Config.SMTP_PASSWORD and Config.EMAIL_FROM
        graph_api_configured = all([
            Config.MS_GRAPH_TENANT_ID,
            Config.MS_GRAPH_CLIENT_ID,
            Config.MS_GRAPH_CLIENT_SECRET,
            Config.MS_GRAPH_REFRESH_TOKEN,  # Required for delegated permissions
            Config.EMAIL_FROM  # Need a sender mailbox
        ])
        
        owner_email = self._get_owner_email(action_item.owner)
        
        # Priority: SMTP > Graph API > Trello Comments
        if smtp_configured and owner_email:
            try:
                self._send_email_reminder(action_item, owner_email)
                print(f"✓ Email reminder sent via SMTP to {action_item.owner} ({owner_email}) for: {action_item.description}")
                return True
            except Exception as e:
                print(f"Warning: SMTP email reminder failed: {e}. Trying Graph API...")
        
        # Try Microsoft Graph API if SMTP failed or not configured
        if graph_api_configured and owner_email:
            try:
                self._send_email_reminder_via_graph(action_item, owner_email)
                print(f"✓ Email reminder sent via Graph API to {action_item.owner} ({owner_email}) for: {action_item.description}")
                return True
            except Exception as e:
                print(f"Warning: Graph API email reminder failed: {e}. Trying Trello comment fallback...")
        
        # Fallback: Use Trello comment if card exists
        if action_item.external_id and self.trello_client:
            try:
                self._send_trello_reminder(action_item)
                print(f"✓ Trello reminder comment added for {action_item.owner} on card: {action_item.description[:50]}...")
                return True
            except Exception as e:
                print(f"Error sending Trello reminder: {e}")
                return False
        
        # No method available
        if not owner_email:
            print(f"Warning: Cannot send reminder for '{action_item.description[:50]}...' - No email found for owner '{action_item.owner}'")
        else:
            print(f"Warning: Cannot send reminder for '{action_item.description[:50]}...' - All email methods failed and no Trello card")
        return False
    
    def send_all_pending_reminders(self) -> Dict[str, int]:
        """
        Send reminders for all action items due within 24 hours.
        
        Returns:
            Dictionary with counts of reminders sent and failed
        """
        pending_items = self.get_pending_reminders()
        
        results = {
            "total": len(pending_items),
            "sent": 0,
            "failed": 0
        }
        
        for item in pending_items:
            if self.send_reminder(item):
                results["sent"] += 1
            else:
                results["failed"] += 1
        
        return results
    
    # ============================================================================
    # Microsoft Graph API Email Methods
    # ============================================================================
    
    def _get_graph_access_token(self) -> str:
        """
        Get Microsoft Graph API access token for sending emails.
        Uses delegated permissions with refresh token flow (user authentication).
        
        Returns:
            Access token string
            
        Raises:
            ValueError: If Graph API credentials or refresh token are not configured
            Exception: If authentication fails
        """
        # Check if token is still valid (with 5 minute buffer)
        if self._graph_access_token and self._graph_token_expires_at:
            if isinstance(self._graph_token_expires_at, datetime):
                if datetime.now() < self._graph_token_expires_at:
                    return self._graph_access_token
            elif isinstance(self._graph_token_expires_at, (int, float)):
                # Handle timestamp format (backward compatibility)
                if datetime.now().timestamp() < self._graph_token_expires_at:
                    return self._graph_access_token
        
        if not all([Config.MS_GRAPH_TENANT_ID, Config.MS_GRAPH_CLIENT_ID, Config.MS_GRAPH_CLIENT_SECRET]):
            raise ValueError(
                "Microsoft Graph API credentials not configured. "
                "Set MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, and MS_GRAPH_CLIENT_SECRET"
            )
        
        if not Config.MS_GRAPH_REFRESH_TOKEN:
            raise ValueError(
                "Microsoft Graph API refresh token not configured. "
                "Set MS_GRAPH_REFRESH_TOKEN. "
                "To obtain a refresh token, use device code flow (see setup instructions)."
            )
        
        token_url = f"https://login.microsoftonline.com/{Config.MS_GRAPH_TENANT_ID}/oauth2/v2.0/token"
        
        # Use refresh token flow for delegated permissions
        data = {
            "client_id": Config.MS_GRAPH_CLIENT_ID,
            "client_secret": Config.MS_GRAPH_CLIENT_SECRET,
            "refresh_token": Config.MS_GRAPH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
            "scope": "https://graph.microsoft.com/Mail.Send offline_access"  # Delegated permissions
        }
        
        try:
            response = httpx.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._graph_access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            
            # Update refresh token if a new one is provided
            new_refresh_token = token_data.get("refresh_token")
            if new_refresh_token:
                # Note: In production, you might want to update the config/env variable
                # For now, we'll use the new token for subsequent requests
                print("ℹ️  New refresh token received. Update MS_GRAPH_REFRESH_TOKEN in your .env file.")
            
            if not self._graph_access_token:
                raise ValueError("Failed to obtain access token from Microsoft Graph API")
            
            # Calculate expiration time (with 5 minute buffer)
            from datetime import timedelta
            self._graph_token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            
            return self._graph_access_token
            
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            if e.response.status_code == 400:
                raise Exception(
                    f"Failed to refresh access token. The refresh token may be expired or invalid. "
                    f"Please obtain a new refresh token using device code flow. Error: {error_text}"
                )
            raise Exception(f"Failed to authenticate with Microsoft Graph API: {error_text}")
        except Exception as e:
            raise Exception(f"Error getting Graph API access token: {str(e)}")
    
    def _send_email_via_graph_api(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None
    ) -> None:
        """
        Send email using Microsoft Graph API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            from_email: Sender email address (must be a mailbox in your tenant)
            
        Raises:
            ValueError: If Graph API credentials are not configured
            Exception: If email sending fails
        """
        if not all([Config.MS_GRAPH_TENANT_ID, Config.MS_GRAPH_CLIENT_ID, Config.MS_GRAPH_CLIENT_SECRET]):
            raise ValueError("Microsoft Graph API credentials not configured")
        
        # Use configured email or default to a mailbox in the tenant
        sender_email = from_email or Config.EMAIL_FROM
        if not sender_email:
            raise ValueError("EMAIL_FROM not configured. Set EMAIL_FROM to a mailbox in your Microsoft 365 tenant")
        
        access_token = self._get_graph_access_token()
        
        # Graph API endpoint for sending email using delegated permissions
        # With delegated permissions, we use /me/sendMail (sends as the authenticated user)
        graph_url = f"{Config.MS_GRAPH_API_BASE}/me/sendMail"
        
        # Prepare email message
        # With delegated permissions, we can specify the sender explicitly
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ],
                "from": {
                    "emailAddress": {
                        "address": sender_email
                    }
                }
            }
        }
        
        try:
            response = httpx.post(
                graph_url,
                json=message,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_msg = e.response.text
            if e.response.status_code == 403:
                raise Exception(
                    f"Permission denied. Ensure the app has 'Mail.Send' delegated permission "
                    f"and the authenticated user has permission to send emails. Error: {error_msg}"
                )
            elif e.response.status_code == 401:
                raise Exception(
                    f"Authentication failed. The refresh token may be expired. "
                    f"Please obtain a new refresh token. Error: {error_msg}"
                )
            raise Exception(f"Failed to send email via Graph API: {error_msg}")
        except Exception as e:
            raise Exception(f"Error sending email via Graph API: {str(e)}")
    
    # ============================================================================
    # Email Helper Methods
    # ============================================================================
    
    def _get_owner_email(self, owner_name: str) -> Optional[str]:
        """
        Get email address for an owner name.
        Checks extracted emails first, then falls back to config.
        
        Args:
            owner_name: Name of the owner
            
        Returns:
            Email address or None if not found
        """
        # First check extracted emails from database
        storage = Storage()
        email = storage.get_email_mapping(owner_name)
        if email:
            return email
        
        # Fall back to config mapping
        if not Config.OWNER_EMAIL_MAP:
            return None
        
        try:
            email_map = json.loads(Config.OWNER_EMAIL_MAP)
            return email_map.get(owner_name)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def send_assignment_reminder(self, action_item: ActionItem, project_name: str) -> bool:
        """
        Send reminder to owner when a task is assigned to them.
        Uses Trello API if SMTP not configured, otherwise tries email first.
        
        Args:
            action_item: Action item that was just assigned
            project_name: Name of the project
            
        Returns:
            True if reminder sent successfully
        """
        if not Config.REMINDER_ENABLED:
            return False
        
        # Check what email methods are available
        smtp_configured = Config.SMTP_USERNAME and Config.SMTP_PASSWORD and Config.EMAIL_FROM
        graph_api_configured = all([
            Config.MS_GRAPH_TENANT_ID,
            Config.MS_GRAPH_CLIENT_ID,
            Config.MS_GRAPH_CLIENT_SECRET,
            Config.MS_GRAPH_REFRESH_TOKEN,  # Required for delegated permissions
            Config.EMAIL_FROM  # Need a sender mailbox
        ])
        
        owner_email = self._get_owner_email(action_item.owner)
        
        # Priority: SMTP > Graph API > Trello Comments
        if smtp_configured and owner_email:
            try:
                self._send_email_assignment_reminder(action_item, owner_email, project_name)
                print(f"✓ Assignment reminder sent via SMTP to {action_item.owner} ({owner_email}) for: {action_item.description[:50]}...")
                return True
            except Exception as e:
                print(f"Warning: SMTP email assignment reminder failed: {e}. Trying Graph API...")
        
        # Try Microsoft Graph API if SMTP failed or not configured
        if graph_api_configured and owner_email:
            try:
                self._send_email_assignment_reminder_via_graph(action_item, owner_email, project_name)
                print(f"✓ Assignment reminder sent via Graph API to {action_item.owner} ({owner_email}) for: {action_item.description[:50]}...")
                return True
            except Exception as e:
                print(f"Warning: Graph API email assignment reminder failed: {e}. Trying Trello comment fallback...")
        
        # Fallback: Use Trello comment if card exists
        if action_item.external_id and self.trello_client:
            try:
                self._send_trello_assignment_reminder(action_item, project_name)
                print(f"✓ Trello assignment reminder comment added for {action_item.owner} on card: {action_item.description[:50]}...")
                return True
            except Exception as e:
                print(f"Error sending Trello assignment reminder: {e}")
                return False
        
        # No method available
        if not owner_email:
            print(f"Warning: Cannot send assignment reminder - No email found for owner '{action_item.owner}'")
        else:
            print(f"Warning: Cannot send assignment reminder - All email methods failed and no Trello card for: {action_item.description[:50]}...")
        return False
    
    def _send_email_assignment_reminder(self, action_item: ActionItem, recipient_email: str, project_name: str) -> None:
        """
        Send email reminder for task assignment via SMTP.
        
        Args:
            action_item: Action item that was assigned
            recipient_email: Email address of the recipient
            project_name: Name of the project
        """
        if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
            raise ValueError("SMTP credentials not configured")
        
        if not Config.EMAIL_FROM:
            raise ValueError("EMAIL_FROM not configured")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_FROM
        msg['To'] = recipient_email
        msg['Subject'] = f"New Task Assigned: {action_item.description[:50]}"
        
        # Build Trello card link if available
        trello_link = ""
        if action_item.external_id:
            trello_link = f"\n**Trello Card:** https://trello.com/c/{action_item.external_id}\n"
        
        deadline_text = ""
        if action_item.deadline:
            deadline_text = f"**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Create email body
        body = f"""
Hello {action_item.owner},

A new task has been assigned to you:

**Task:** {action_item.description}
**Project:** {project_name}
**Status:** {action_item.status.value.title()}
{deadline_text}{trello_link}
"""
        
        if action_item.dependencies:
            body += "\n**Dependencies:**\n"
            for dep in action_item.dependencies:
                body += f"- {dep}\n"
        
        if action_item.tags:
            body += f"\n**Tags:** {', '.join(action_item.tags)}\n"
        
        body += """
Please review and acknowledge this task assignment. You can update the task status and deadline in Trello if needed.

Best regards,
Meeting Transcript Summarizer
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            text = msg.as_string()
            server.sendmail(Config.EMAIL_FROM, recipient_email, text)
            server.quit()
        except Exception as e:
            raise RuntimeError(f"Failed to send assignment email: {e}") from e
    
    def _send_email_assignment_reminder_via_graph(
        self,
        action_item: ActionItem,
        recipient_email: str,
        project_name: str
    ) -> None:
        """
        Send email reminder for task assignment via Microsoft Graph API.
        
        Args:
            action_item: Action item that was assigned
            recipient_email: Email address of the recipient
            project_name: Name of the project
        """
        # Build Trello card link if available
        trello_link = ""
        if action_item.external_id:
            trello_link = f"\n**Trello Card:** https://trello.com/c/{action_item.external_id}\n"
        
        deadline_text = ""
        if action_item.deadline:
            deadline_text = f"**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Create email subject and body
        subject = f"New Task Assigned: {action_item.description[:50]}"
        
        body = f"""
Hello {action_item.owner},

A new task has been assigned to you:

**Task:** {action_item.description}
**Project:** {project_name}
**Status:** {action_item.status.value.title()}
{deadline_text}{trello_link}
"""
        
        if action_item.dependencies:
            body += "\n**Dependencies:**\n"
            for dep in action_item.dependencies:
                body += f"- {dep}\n"
        
        if action_item.tags:
            body += f"\n**Tags:** {', '.join(action_item.tags)}\n"
        
        body += """
Please review and acknowledge this task assignment. You can update the task status and deadline in Trello if needed.

Best regards,
Meeting Transcript Summarizer
"""
        
        # Send via Graph API
        self._send_email_via_graph_api(recipient_email, subject, body)
    
    def _send_trello_assignment_reminder(self, action_item: ActionItem, project_name: str) -> None:
        """
        Send assignment reminder via Trello comment.
        
        Args:
            action_item: Action item that was assigned
            project_name: Name of the project
        """
        if not self.trello_client:
            raise RuntimeError("Trello client not initialized")
        
        if not action_item.external_id:
            raise RuntimeError("Action item has no Trello card ID")
        
        try:
            card = self.trello_client.get_card(action_item.external_id)
            
            deadline_text = ""
            if action_item.deadline:
                deadline_text = f"**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}\n"
            
            comment_text = f"""🔔 NEW TASK ASSIGNED

**Assigned To:** {action_item.owner}
**Project:** {project_name}
**Status:** {action_item.status.value.title()}
{deadline_text}
**Task Details:**
{action_item.description}

**Card Link:** https://trello.com/c/{action_item.external_id}

Please review and acknowledge this task assignment."""
            
            if action_item.dependencies:
                comment_text += "\n\n**Dependencies:**\n"
                for dep in action_item.dependencies:
                    comment_text += f"- {dep}\n"
            
            if action_item.tags:
                comment_text += f"\n**Tags:** {', '.join(action_item.tags)}"
            
            card.comment(comment_text)
        except Exception as e:
            raise RuntimeError(f"Failed to add Trello assignment comment: {e}") from e
    
    def _send_email_reminder(self, action_item: ActionItem, recipient_email: str) -> None:
        """
        Send email reminder for an action item via SMTP.
        
        Args:
            action_item: Action item to send reminder for
            recipient_email: Email address of the recipient
            
        Raises:
            ValueError: If SMTP credentials or EMAIL_FROM are not configured
            RuntimeError: If email sending fails
        """
        if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
            raise ValueError("SMTP credentials not configured")
        
        if not Config.EMAIL_FROM:
            raise ValueError("EMAIL_FROM not configured")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_FROM
        msg['To'] = recipient_email
        msg['Subject'] = f"Reminder: Action Item Due Soon - {action_item.description[:50]}"
        
        # Calculate time until deadline
        now = datetime.now()
        time_diff = action_item.deadline - now
        hours_left = int(time_diff.total_seconds() / 3600)
        
        # Build Trello card link if available
        trello_link = ""
        if action_item.external_id:
            trello_link = f"\n**Trello Card:** https://trello.com/c/{action_item.external_id}\n"
        
        # Create email body with task details
        body = f"""
Hello {action_item.owner},

This is a reminder that you have an action item due soon:

**Action Item:** {action_item.description}
**Assigned To:** {action_item.owner}
**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}
**Time Remaining:** {hours_left} hours
**Status:** {action_item.status.value.title()}
{trello_link}

**Task Details:**
{action_item.description}
"""
        
        if action_item.dependencies:
            body += "\n**Dependencies:**\n"
            for dep in action_item.dependencies:
                body += f"- {dep}\n"
        
        if action_item.tags:
            body += f"\n**Tags:** {', '.join(action_item.tags)}\n"
        
        body += """
Please ensure this action item is completed before the deadline.

Best regards,
Meeting Transcript Summarizer
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            text = msg.as_string()
            server.sendmail(Config.EMAIL_FROM, recipient_email, text)
            server.quit()
        except Exception as e:
            raise RuntimeError(f"Failed to send email: {e}") from e
    
    def _send_email_reminder_via_graph(self, action_item: ActionItem, recipient_email: str) -> None:
        """
        Send email reminder for an action item via Microsoft Graph API.
        
        Args:
            action_item: Action item to send reminder for
            recipient_email: Email address of the recipient
            
        Raises:
            ValueError: If Graph API credentials or EMAIL_FROM are not configured
            Exception: If email sending fails
        """
        # Calculate time until deadline
        now = datetime.now()
        time_diff = action_item.deadline - now
        hours_left = int(time_diff.total_seconds() / 3600)
        
        # Build Trello card link if available
        trello_link = ""
        if action_item.external_id:
            trello_link = f"\n**Trello Card:** https://trello.com/c/{action_item.external_id}\n"
        
        # Create email subject and body
        subject = f"Reminder: Action Item Due Soon - {action_item.description[:50]}"
        
        body = f"""
Hello {action_item.owner},

This is a reminder that you have an action item due soon:

**Action Item:** {action_item.description}
**Assigned To:** {action_item.owner}
**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}
**Time Remaining:** {hours_left} hours
**Status:** {action_item.status.value.title()}
{trello_link}

**Task Details:**
{action_item.description}
"""
        
        if action_item.dependencies:
            body += "\n**Dependencies:**\n"
            for dep in action_item.dependencies:
                body += f"- {dep}\n"
        
        if action_item.tags:
            body += f"\n**Tags:** {', '.join(action_item.tags)}\n"
        
        body += """
Please ensure this action item is completed before the deadline.

Best regards,
Meeting Transcript Summarizer
"""
        
        # Send via Graph API
        self._send_email_via_graph_api(recipient_email, subject, body)
    
    def _send_trello_reminder(self, action_item: ActionItem) -> None:
        """
        Send reminder via Trello comment (fallback when SMTP not configured).
        Adds a comment to the Trello card with reminder details.
        
        Args:
            action_item: Action item to send reminder for
            
        Raises:
            RuntimeError: If Trello client not initialized or card not found
        """
        if not self.trello_client:
            raise RuntimeError("Trello client not initialized")
        
        if not action_item.external_id:
            raise RuntimeError("Action item has no Trello card ID")
        
        try:
            # Get the Trello card
            card = self.trello_client.get_card(action_item.external_id)
            
            # Calculate time until deadline
            now = datetime.now()
            time_diff = action_item.deadline - now
            hours_left = int(time_diff.total_seconds() / 3600)
            days_left = int(time_diff.total_seconds() / 86400)
            
            # Build reminder message
            trello_card_url = f"https://trello.com/c/{action_item.external_id}"
            
            reminder_text = f"""🔔 REMINDER: Action Item Due Soon

**Assigned To:** {action_item.owner}
**Deadline:** {action_item.deadline.strftime('%Y-%m-%d %H:%M')}
**Time Remaining:** {hours_left} hours ({days_left} days)
**Status:** {action_item.status.value.title()}

**Task Details:**
{action_item.description}

"""
            
            if action_item.dependencies:
                reminder_text += "**Dependencies:**\n"
                for dep in action_item.dependencies:
                    reminder_text += f"- {dep}\n"
                reminder_text += "\n"
            
            if action_item.tags:
                reminder_text += f"**Tags:** {', '.join(action_item.tags)}\n\n"
            
            reminder_text += f"**Card Link:** {trello_card_url}\n\n"
            reminder_text += "Please ensure this action item is completed before the deadline."
            
            # Add comment to card
            card.comment(reminder_text)
            
            # Try to mention the owner if they're a member of the board
            try:
                board = card.get_board()
                members = board.get_members()
                owner_email = self._get_owner_email(action_item.owner)
                
                # Try to find member by email and mention them
                if owner_email:
                    for member in members:
                        try:
                            member_data = member.fetch()
                            if hasattr(member_data, 'email') and member_data.email == owner_email:
                                # Mention the member in a separate comment
                                mention_text = f"@{member.username} - {action_item.owner} - Reminder notification"
                                try:
                                    card.comment(mention_text)
                                except:
                                    # If mention fails, continue without it
                                    pass
                                break
                        except:
                            continue
            except Exception as e:
                # If member lookup fails, continue without mention
                print(f"Warning: Could not mention member in Trello: {e}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to add Trello reminder comment: {e}") from e
    
    # ============================================================================
    # Project Deletion Methods
    # ============================================================================
    
    def delete_project_trello_resources(self, project_name: str) -> Dict[str, int]:
        """
        Archive all Trello resources for a project (board, lists, cards).
        The board is archived (closed) rather than permanently deleted.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary with counts of archived resources
        """
        if not self.trello_client:
            return {'boards': 0, 'lists': 0, 'cards': 0}
        
        archived = {'boards': 0, 'lists': 0, 'cards': 0}
        
        try:
            # Try to find board by name (including closed boards)
            board_id = None
            try:
                all_boards = self.trello_client.list_boards(board_filter='all')  # Include closed boards
                for board in all_boards:
                    if board.name == project_name:
                        board_id = board.id
                        break
            except Exception as e:
                print(f"Warning: Could not list boards: {e}")
            
            # Also check cache
            if not board_id and project_name in self.board_cache:
                board_id = self.board_cache[project_name]
            
            if not board_id:
                print(f"No Trello board found for project: {project_name}")
                return archived
            
            board = self.trello_client.get_board(board_id)
            
            # Archive all cards first
            try:
                all_lists = board.list_lists()
                for lst in all_lists:
                    cards = lst.list_cards()
                    for card in cards:
                        try:
                            if not card.closed:
                                card.set_closed(True)
                                archived['cards'] += 1
                        except Exception:
                            pass
            except Exception as e:
                print(f"Warning: Error archiving cards: {e}")
            
            # Close all lists
            try:
                all_lists = board.list_lists()
                for lst in all_lists:
                    try:
                        if not lst.closed:
                            lst.close()
                            archived['lists'] += 1
                    except Exception:
                        pass
            except Exception as e:
                print(f"Warning: Error closing lists: {e}")
            
            # Archive (close) the board instead of deleting it permanently
            try:
                if not board.closed:
                    print(f"  Archiving Trello board: {project_name}")
                    board.close()
                    archived['boards'] += 1
                    print(f"✓ Successfully archived Trello board: {project_name}")
                else:
                    print(f"  Trello board already archived: {project_name}")
                    archived['boards'] += 1
                    
            except Exception as e:
                import traceback
                print(f"Warning: Error archiving board: {e}")
                traceback.print_exc()
            
            # Remove from cache
            if project_name in self.board_cache:
                del self.board_cache[project_name]
                self._save_board_cache()
            
        except Exception as e:
            print(f"Warning: Error archiving Trello resources for {project_name}: {e}")
            import traceback
            traceback.print_exc()
        
        return archived
    
    def delete_meeting_trello_cards(self, meeting_id: str, project_name: str) -> int:
        """
        Delete all Trello cards associated with a specific meeting.
        
        Args:
            meeting_id: ID of the meeting
            project_name: Name of the project
            
        Returns:
            Number of cards deleted
        """
        if not self.trello_client:
            return 0
        
        board_id = self._get_or_create_board(project_name)
        if not board_id:
            return 0
        
        deleted_count = 0
        
        try:
            # Get all action items for this meeting from database
            storage = Storage()
            action_items = storage.get_action_items_by_owner("", None)
            
            # Filter action items for this meeting
            meeting_action_items = [
                item for item in action_items 
                if item.get("meeting_id") == meeting_id and item.get("external_id")
            ]
            
            # Delete each Trello card
            for item in meeting_action_items:
                card_id = item.get("external_id")
                if card_id:
                    try:
                        card = self.trello_client.get_card(card_id)
                        card.delete()
                        deleted_count += 1
                    except Exception as e:
                        print(f"Warning: Could not delete Trello card {card_id}: {e}")
            
        except Exception as e:
            print(f"Warning: Error deleting meeting Trello cards: {e}")
        
        return deleted_count
    
    def extract_trello_member_emails(self, project_name: str) -> Dict[str, str]:
        """
        Extract member names and emails from Trello board.
        Also includes project owner email from config.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary mapping name -> email
        """
        email_mappings = {}
        
        # Add project owner email from config (if available)
        if Config.PROJECT_OWNER_NAME and Config.PROJECT_OWNER_EMAIL:
            email_mappings[Config.PROJECT_OWNER_NAME] = Config.PROJECT_OWNER_EMAIL
            print(f"Added project owner email: {Config.PROJECT_OWNER_NAME} -> {Config.PROJECT_OWNER_EMAIL}")
        
        if not self.trello_client:
            return email_mappings
        
        try:
            board_id = self._get_or_create_board(project_name)
            if not board_id:
                return email_mappings
            
            board = self.trello_client.get_board(board_id)
            
            # Get all members of the board
            members = board.get_members()
            
            for member in members:
                try:
                    # Get member details
                    member_data = member.fetch()
                    name = member_data.get('fullName') or member_data.get('username', '')
                    email = member_data.get('email', '')
                    
                    if name and email:
                        email_mappings[name] = email
                except Exception as e:
                    print(f"Warning: Could not get member details: {e}")
            
            # Also check card members
            all_lists = board.list_lists()
            for lst in all_lists:
                cards = lst.list_cards()
                for card in cards:
                    try:
                        members = card.get_members()
                        for member in members:
                            try:
                                member_data = member.fetch()
                                name = member_data.get('fullName') or member_data.get('username', '')
                                email = member_data.get('email', '')
                                
                                if name and email:
                                    email_mappings[name] = email
                            except Exception:
                                pass
                    except Exception:
                        pass
            
        except Exception as e:
            print(f"Warning: Error extracting Trello member emails: {e}")
        
        return email_mappings
    
    def update_email_mappings_from_trello(self, project_name: str) -> int:
        """
        Extract emails from Trello and save to database.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Number of mappings saved
        """
        email_mappings = self.extract_trello_member_emails(project_name)
        
        storage = Storage()
        count = 0
        
        for name, email in email_mappings.items():
            storage.save_email_mapping(name, email, 'trello', project_name)
            count += 1
        
        return count

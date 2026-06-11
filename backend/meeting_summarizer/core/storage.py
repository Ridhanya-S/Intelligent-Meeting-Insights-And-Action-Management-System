"""
Storage Module for persisting meeting data
"""
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models import MeetingSummary, ActionItemStatus
from ..config import Config


class Storage:
    """Handle data persistence"""
    
    def __init__(self):
        """Initialize storage"""
        self.db_path = Config.DATABASE_PATH
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create meetings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                meeting_title TEXT NOT NULL,
                meeting_date TEXT NOT NULL,
                meeting_type TEXT,
                participants TEXT,
                duration_minutes REAL,
                overall_summary TEXT,
                tags TEXT,
                transcript_path TEXT,
                summary_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Add meeting_type column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE meetings ADD COLUMN meeting_type TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create action_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_items (
                id TEXT PRIMARY KEY,
                meeting_id TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                deadline TEXT,
                status TEXT NOT NULL,
                dependencies TEXT,
                tags TEXT,
                external_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_meetings_project_date 
            ON meetings(project_name, meeting_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_action_items_owner_status 
            ON action_items(owner, status)
        ''')
        
        # Create processed_files table to track uploaded files
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL UNIQUE,
                original_file_path TEXT NOT NULL,
                project_name TEXT NOT NULL,
                meeting_id TEXT,
                trello_synced INTEGER DEFAULT 0,
                confluence_stored INTEGER DEFAULT 0,
                processed_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_processed_files_hash 
            ON processed_files(file_hash)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_processed_files_project 
            ON processed_files(project_name)
        ''')
        
        # Create email_mappings table to store name->email mappings from Trello/Confluence
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                source TEXT NOT NULL,
                project_name TEXT,
                external_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(name, email, source, project_name)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_email_mappings_name 
            ON email_mappings(name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_email_mappings_project 
            ON email_mappings(project_name)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_summary(self, summary: MeetingSummary, replace_existing: bool = False) -> str:
        """Save meeting summary to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate ID if not present
        if not summary.id:
            summary.id = f"{summary.project_name}_{summary.meeting_date.strftime('%Y%m%d_%H%M%S')}"
        
        # If replacing, delete old action items first
        if replace_existing:
            cursor.execute('DELETE FROM action_items WHERE meeting_id = ?', (summary.id,))
        
        # Save meeting
        cursor.execute('''
            INSERT OR REPLACE INTO meetings 
            (id, project_name, meeting_title, meeting_date, meeting_type, participants, 
             duration_minutes, overall_summary, tags, transcript_path, 
             summary_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            summary.id,
            summary.project_name,
            summary.meeting_title,
            summary.meeting_date.isoformat(),
            summary.meeting_type or "general",
            json.dumps(summary.participants),
            summary.duration_minutes,
            summary.overall_summary,
            json.dumps(summary.tags),
            summary.transcript_path,
            None,  # summary_path will be set after saving JSON
            summary.created_at.isoformat(),
            summary.updated_at.isoformat()
        ))
        
        # Save action items
        for item in summary.all_action_items:
            if not item.id:
                item.id = f"{summary.id}_ai_{len(summary.all_action_items)}"
            
            cursor.execute('''
                INSERT OR REPLACE INTO action_items
                (id, meeting_id, description, owner, deadline, status,
                 dependencies, tags, external_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.id,
                summary.id,
                item.description,
                item.owner,
                item.deadline.isoformat() if item.deadline else None,
                item.status.value,
                json.dumps(item.dependencies),
                json.dumps(item.tags),
                item.external_id,
                item.created_at.isoformat(),
                item.updated_at.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Also save as JSON file
        summary_path = self._save_summary_json(summary)
        
        # Update summary_path in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE meetings SET summary_path = ? WHERE id = ?', (summary_path, summary.id))
        conn.commit()
        conn.close()
        
        return summary.id
    
    def _save_summary_json(self, summary: MeetingSummary) -> str:
        """Save summary as JSON file, organized by project/meetingtime"""
        # Get meeting directory: projectname/meetingtime/
        meeting_dir = Config.get_meeting_dir(summary.project_name, summary.meeting_date)
        
        # Save summary file
        filename = "summary.json"
        file_path = meeting_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary.model_dump(), f, indent=2, default=str)
        
        return str(file_path)
    
    def get_summary(self, summary_id: str) -> Optional[MeetingSummary]:
        """Retrieve meeting summary by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM meetings WHERE id = ?', (summary_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Load from JSON file if available
        summary_path = row[9]  # summary_path column
        if summary_path and Path(summary_path).exists():
            conn.close()
            with open(summary_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migrate old status values to new ones
            data = self._migrate_action_item_statuses(data)
            
            return MeetingSummary(**data)
        
        # Otherwise reconstruct from database
        # (This is a simplified version - full implementation would reconstruct all objects)
        conn.close()
        return None
    
    def _migrate_action_item_statuses(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate old action item status values to new ones.
        
        Old -> New mappings:
        - "completed" -> "done"
        - "in_progress" -> "doing"
        - "pending" -> "pending" (no change)
        - "blocked" -> "blocked" (no change)
        - Missing status -> "new"
        
        Args:
            data: Summary data dictionary
            
        Returns:
            Updated data dictionary with migrated statuses
        """
        if "all_action_items" in data:
            for item in data["all_action_items"]:
                old_status = item.get("status", "pending")
                
                # Map old status values to new ones
                status_mapping = {
                    "completed": "done",
                    "in_progress": "doing",
                    "pending": "pending",
                    "blocked": "blocked",
                    "new": "new",
                    "done": "done",
                    "doing": "doing"
                }
                
                # Convert old status to new status
                new_status = status_mapping.get(old_status, "new")
                item["status"] = new_status
        
        return data
    
    def get_action_items_by_owner(
        self,
        owner: str,
        status: Optional[ActionItemStatus] = None,
        project_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get action items by owner (empty string for all owners).
        
        Args:
            owner: Owner name (empty string for all owners)
            status: Optional status filter
            project_name: Optional project name filter (case-insensitive)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query with JOIN to meetings table for project filtering
        base_query = '''
            SELECT ai.* FROM action_items ai
        '''
        
        conditions = []
        params = []
        
        # Add project filter if specified (using JOIN)
        if project_name:
            base_query += ' INNER JOIN meetings m ON ai.meeting_id = m.id '
            # Use case-insensitive comparison - don't normalize, let SQL handle it
            conditions.append('LOWER(TRIM(m.project_name)) = LOWER(TRIM(?))')
            params.append(project_name.strip())
        
        # Add owner filter
        if owner:
            conditions.append('ai.owner = ?')
            params.append(owner)
        
        # Add status filter
        if status:
            conditions.append('ai.status = ?')
            params.append(status.value)
        
        # Build final query
        if conditions:
            query = base_query + ' WHERE ' + ' AND '.join(conditions) + ' ORDER BY ai.deadline ASC'
        else:
            query = base_query + ' ORDER BY ai.deadline ASC'
        
        # Debug logging (can be removed in production)
        if project_name:
            print(f"DEBUG: Querying action items for project: '{project_name}'")
            print(f"DEBUG: SQL Query: {query}")
            print(f"DEBUG: Params: {params}")
        
        cursor.execute(query, params)
        
        items = []
        for row in cursor.fetchall():
            try:
                items.append({
                    "id": row[0],
                    "meeting_id": row[1],
                    "description": row[2],
                    "owner": row[3],
                    "deadline": datetime.fromisoformat(row[4]) if row[4] else None,
                    "status": ActionItemStatus(row[5]),
                    "dependencies": json.loads(row[6]) if row[6] else [],
                    "tags": json.loads(row[7]) if row[7] else [],
                    "external_id": row[8]
                })
            except (ValueError, IndexError, json.JSONDecodeError) as e:
                # Log error but continue processing other items
                print(f"Warning: Error parsing action item {row[0] if row else 'unknown'}: {e}")
                continue
        
        conn.close()
        return items
    
    def get_project_meetings(
        self,
        project_name: str,
        limit: Optional[int] = None
    ) -> List[str]:
        """Get list of meeting IDs for a project"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT id FROM meetings WHERE project_name = ? ORDER BY meeting_date DESC'
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query, (project_name,))
        ids = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return ids
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            raise ValueError(f"Error calculating file hash: {e}")
    
    def is_file_processed(self, file_path: str, project_name: Optional[str] = None) -> bool:
        """
        Check if a file has been processed before.
        
        Args:
            file_path: Path to the file to check
            project_name: Optional project name - if provided, only checks within that project
            
        Returns:
            True if file has been processed, False otherwise
        """
        try:
            file_hash = self.calculate_file_hash(file_path)
            return self.is_file_hash_processed(file_hash, project_name)
        except Exception:
            # If hash calculation fails, check by file path
            return self.is_file_path_processed(file_path, project_name)
    
    def is_file_hash_processed(self, file_hash: str, project_name: Optional[str] = None) -> bool:
        """
        Check if a file hash has been processed.
        
        Args:
            file_hash: Hash of the file to check
            project_name: Optional project name - if provided, only checks within that project
            
        Returns:
            True if file hash has been processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if project_name:
            # Check only within the specified project
            cursor.execute('SELECT id FROM processed_files WHERE file_hash = ? AND project_name = ?', (file_hash, project_name))
        else:
            # Check across all projects (backward compatibility)
            cursor.execute('SELECT id FROM processed_files WHERE file_hash = ?', (file_hash,))
        
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def is_file_path_processed(self, file_path: str, project_name: Optional[str] = None) -> bool:
        """
        Check if a file path has been processed.
        
        Args:
            file_path: Path to the file to check
            project_name: Optional project name - if provided, only checks within that project
            
        Returns:
            True if file path has been processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if project_name:
            # Check only within the specified project
            cursor.execute('SELECT id FROM processed_files WHERE original_file_path = ? AND project_name = ?', (file_path, project_name))
        else:
            # Check across all projects (backward compatibility)
            cursor.execute('SELECT id FROM processed_files WHERE original_file_path = ?', (file_path,))
        
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def mark_file_processed(
        self,
        file_path: str,
        project_name: str,
        meeting_id: Optional[str] = None,
        trello_synced: bool = False,
        confluence_stored: bool = False
    ) -> int:
        """
        Mark a file as processed
        
        Args:
            file_path: Path to the processed file
            project_name: Name of the project
            meeting_id: ID of the meeting (optional)
            trello_synced: Whether action items were synced to Trello
            confluence_stored: Whether summary was stored in Confluence
        
        Returns:
            ID of the processed file record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            file_hash = self.calculate_file_hash(file_path)
        except Exception:
            # If hash calculation fails, use a placeholder
            file_hash = f"path_{hash(file_path)}"
        
        cursor.execute('''
            INSERT OR IGNORE INTO processed_files
            (file_hash, original_file_path, project_name, meeting_id, 
             trello_synced, confluence_stored, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_hash,
            file_path,
            project_name,
            meeting_id,
            1 if trello_synced else 0,
            1 if confluence_stored else 0,
            datetime.now().isoformat()
        ))
        
        # Get the ID
        cursor.execute('SELECT id FROM processed_files WHERE file_hash = ?', (file_hash,))
        result = cursor.fetchone()
        file_id = result[0] if result else None
        
        conn.commit()
        conn.close()
        
        return file_id
    
    def update_file_processing_status(
        self,
        file_path: str,
        trello_synced: Optional[bool] = None,
        confluence_stored: Optional[bool] = None
    ):
        """Update processing status for a file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if trello_synced is not None:
            updates.append('trello_synced = ?')
            values.append(1 if trello_synced else 0)
        
        if confluence_stored is not None:
            updates.append('confluence_stored = ?')
            values.append(1 if confluence_stored else 0)
        
        if updates:
            values.append(file_path)
            query = f'UPDATE processed_files SET {", ".join(updates)} WHERE original_file_path = ?'
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def get_processed_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get processing information for a file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, file_hash, original_file_path, project_name, meeting_id,
                   trello_synced, confluence_stored, processed_at
            FROM processed_files
            WHERE original_file_path = ?
        ''', (file_path,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "file_hash": row[1],
            "original_file_path": row[2],
            "project_name": row[3],
            "meeting_id": row[4],
            "trello_synced": bool(row[5]),
            "confluence_stored": bool(row[6]),
            "processed_at": row[7]
        }
    
    def update_action_item_deadline(self, action_item_id: str, new_deadline: datetime) -> None:
        """
        Update the deadline of an action item in the database.
        
        Args:
            action_item_id: ID of the action item to update
            new_deadline: New deadline datetime
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE action_items
            SET deadline = ?, updated_at = ?
            WHERE id = ?
        ''', (new_deadline.isoformat(), datetime.now().isoformat(), action_item_id))
        
        conn.commit()
        conn.close()
    
    def save_email_mapping(self, name: str, email: str, source: str, project_name: Optional[str] = None, external_id: Optional[str] = None) -> None:
        """Save or update email mapping"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO email_mappings 
            (name, email, source, project_name, external_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 
                COALESCE((SELECT created_at FROM email_mappings WHERE name = ? AND email = ? AND source = ? AND project_name = ?), ?),
                ?)
        ''', (name, email, source, project_name, external_id, name, email, source, project_name, now, now))
        
        conn.commit()
        conn.close()
    
    def get_email_mapping(self, name: str) -> Optional[str]:
        """Get email address for a name (checks all sources)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email FROM email_mappings 
            WHERE name = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        ''', (name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_all_email_mappings(self, project_name: Optional[str] = None) -> Dict[str, str]:
        """Get all email mappings, optionally filtered by project"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if project_name:
            cursor.execute('''
                SELECT DISTINCT name, email FROM email_mappings 
                WHERE project_name = ?
                ORDER BY updated_at DESC
            ''', (project_name,))
        else:
            cursor.execute('''
                SELECT DISTINCT name, email FROM email_mappings 
                ORDER BY updated_at DESC
            ''')
        
        mappings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return mappings
    
    def delete_project(self, project_name: str) -> Dict[str, int]:
        """Delete all data for a project"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get meeting IDs for this project
        cursor.execute('SELECT id FROM meetings WHERE project_name = ?', (project_name,))
        meeting_ids = [row[0] for row in cursor.fetchall()]
        
        deleted = {
            'meetings': 0,
            'action_items': 0,
            'processed_files': 0,
            'email_mappings': 0
        }
        
        # Delete action items
        if meeting_ids:
            placeholders = ','.join('?' * len(meeting_ids))
            cursor.execute(f'DELETE FROM action_items WHERE meeting_id IN ({placeholders})', meeting_ids)
            deleted['action_items'] = cursor.rowcount
        
        # Delete meetings
        cursor.execute('DELETE FROM meetings WHERE project_name = ?', (project_name,))
        deleted['meetings'] = cursor.rowcount
        
        # Delete processed files
        cursor.execute('DELETE FROM processed_files WHERE project_name = ?', (project_name,))
        deleted['processed_files'] = cursor.rowcount
        
        # Delete email mappings
        cursor.execute('DELETE FROM email_mappings WHERE project_name = ?', (project_name,))
        deleted['email_mappings'] = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_meeting(self, meeting_id: str) -> Dict[str, int]:
        """
        Delete a single meeting and all its associated data.
        
        Args:
            meeting_id: ID of the meeting to delete
            
        Returns:
            Dictionary with counts of deleted records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get meeting info before deletion (for file cleanup)
        cursor.execute('SELECT project_name, summary_path, transcript_path FROM meetings WHERE id = ?', (meeting_id,))
        meeting_row = cursor.fetchone()
        
        if not meeting_row:
            conn.close()
            return {
                'meetings': 0,
                'action_items': 0,
                'processed_files': 0
            }
        
        project_name, summary_path, transcript_path = meeting_row
        
        # Get uploaded file paths from processed_files table
        cursor.execute('SELECT original_file_path FROM processed_files WHERE meeting_id = ?', (meeting_id,))
        uploaded_files = [row[0] for row in cursor.fetchall()]
        
        deleted = {
            'meetings': 0,
            'action_items': 0,
            'processed_files': 0,
            'uploaded_files': 0
        }
        
        # Delete action items
        cursor.execute('DELETE FROM action_items WHERE meeting_id = ?', (meeting_id,))
        deleted['action_items'] = cursor.rowcount
        
        # Delete processed files
        cursor.execute('DELETE FROM processed_files WHERE meeting_id = ?', (meeting_id,))
        deleted['processed_files'] = cursor.rowcount
        
        # Delete meeting
        cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))
        deleted['meetings'] = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Delete files
        try:
            # Delete summary JSON file
            if summary_path and Path(summary_path).exists():
                Path(summary_path).unlink()
            
            # Delete transcript file
            if transcript_path and Path(transcript_path).exists():
                Path(transcript_path).unlink()
            
            # Delete uploaded media files (video/audio files)
            uploaded_files_deleted_count = 0
            for uploaded_file in uploaded_files:
                if uploaded_file and Path(uploaded_file).exists():
                    try:
                        Path(uploaded_file).unlink()
                        uploaded_files_deleted_count += 1
                        print(f"Deleted uploaded file: {uploaded_file}")
                    except Exception as e:
                        print(f"Warning: Could not delete uploaded file {uploaded_file}: {e}")
            
            # Store count in deleted dict for return
            deleted['uploaded_files'] = uploaded_files_deleted_count
            
            # Delete meeting directory and all its contents
            if summary_path:
                meeting_dir = Path(summary_path).parent
                if meeting_dir.exists():
                    try:
                        # Remove all files in directory first
                        for file_path in meeting_dir.iterdir():
                            try:
                                if file_path.is_file():
                                    file_path.unlink()
                                elif file_path.is_dir():
                                    import shutil
                                    shutil.rmtree(file_path)
                            except Exception as e:
                                print(f"Warning: Could not delete {file_path}: {e}")
                        
                        # Now remove the directory itself
                        try:
                            meeting_dir.rmdir()
                            print(f"Deleted meeting directory: {meeting_dir}")
                        except OSError as e:
                            # If directory still not empty, force remove with shutil
                            import shutil
                            try:
                                shutil.rmtree(meeting_dir)
                                print(f"Force deleted meeting directory: {meeting_dir}")
                            except Exception as e2:
                                print(f"Warning: Could not delete meeting directory {meeting_dir}: {e2}")
                    except Exception as e:
                        print(f"Warning: Error deleting meeting directory: {e}")
        except Exception as e:
            print(f"Warning: Error deleting meeting files: {e}")
        
        return deleted


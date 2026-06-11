# Database Documentation

## Database Type
**SQLite** - A lightweight, file-based database that doesn't require a separate server.

## Database Location
- **Path**: `data/meetings.db`
- **Created**: Automatically on first application run
- **Size**: Grows as data is added

## Database Schema

### Tables Overview

#### 1. `meetings`
Stores meeting summaries and metadata.

**Columns:**
- `id` (TEXT, PRIMARY KEY) - Unique meeting identifier
- `project_name` (TEXT, NOT NULL) - Name of the project
- `meeting_title` (TEXT, NOT NULL) - Title of the meeting
- `meeting_date` (TEXT, NOT NULL) - Date/time of the meeting
- `participants` (TEXT) - JSON array of participant names
- `duration_minutes` (REAL) - Meeting duration in minutes
- `overall_summary` (TEXT) - Main summary text
- `tags` (TEXT) - JSON array of tags
- `transcript_path` (TEXT) - Path to transcript file
- `summary_path` (TEXT) - Path to summary JSON file
- `created_at` (TEXT, NOT NULL) - Creation timestamp
- `updated_at` (TEXT, NOT NULL) - Last update timestamp

**Indexes:**
- `idx_meetings_project_date` on `(project_name, meeting_date)`

---

#### 2. `action_items`
Stores action items from meetings.

**Columns:**
- `id` (TEXT, PRIMARY KEY) - Unique action item identifier
- `meeting_id` (TEXT, NOT NULL, FOREIGN KEY) - References `meetings.id`
- `description` (TEXT, NOT NULL) - Action item description
- `owner` (TEXT, NOT NULL) - Person responsible
- `deadline` (TEXT) - Deadline date/time
- `status` (TEXT, NOT NULL) - Status (pending, in_progress, completed, cancelled)
- `dependencies` (TEXT) - JSON array of dependency IDs
- `tags` (TEXT) - JSON array of tags
- `external_id` (TEXT) - Trello card ID (if synced)
- `created_at` (TEXT, NOT NULL) - Creation timestamp
- `updated_at` (TEXT, NOT NULL) - Last update timestamp

**Indexes:**
- `idx_action_items_owner_status` on `(owner, status)`

---

#### 3. `processed_files`
Tracks uploaded files to prevent duplicate processing.

**Columns:**
- `id` (INTEGER, PRIMARY KEY, AUTOINCREMENT) - Unique file record ID
- `file_hash` (TEXT, NOT NULL, UNIQUE) - SHA-256 hash of file content
- `original_file_path` (TEXT, NOT NULL) - Original file path
- `project_name` (TEXT, NOT NULL) - Project name
- `meeting_id` (TEXT, FOREIGN KEY) - References `meetings.id`
- `trello_synced` (INTEGER, DEFAULT 0) - Whether synced to Trello (0/1)
- `confluence_stored` (INTEGER, DEFAULT 0) - Whether stored in Confluence (0/1)
- `processed_at` (TEXT, NOT NULL) - Processing timestamp

**Indexes:**
- `idx_processed_files_hash` on `file_hash`
- `idx_processed_files_project` on `project_name`

---

#### 4. `email_mappings`
Stores email addresses extracted from Trello and Confluence.

**Columns:**
- `id` (INTEGER, PRIMARY KEY, AUTOINCREMENT) - Unique mapping ID
- `name` (TEXT, NOT NULL) - Person's name
- `email` (TEXT, NOT NULL) - Email address
- `source` (TEXT, NOT NULL) - Source: 'trello' or 'confluence'
- `project_name` (TEXT) - Associated project name
- `external_id` (TEXT) - External ID (Trello member ID, Confluence user ID)
- `created_at` (TEXT, NOT NULL) - Creation timestamp
- `updated_at` (TEXT, NOT NULL) - Last update timestamp

**Unique Constraint:**
- `(name, email, source, project_name)` - Prevents duplicates

**Indexes:**
- `idx_email_mappings_name` on `name`
- `idx_email_mappings_project` on `project_name`

---

## How to Visualize the Database

### Method 1: Using the Python Script (Recommended)

```bash
# Run the visualization script
python scripts/view_database.py
```

This will show:
- Database location and size
- All tables with their schemas
- Row counts
- Sample data from each table

### Method 2: Using SQLite Command Line

```bash
# Open database
sqlite3 data/meetings.db

# List all tables
.tables

# View table schema
.schema meetings
.schema action_items
.schema processed_files
.schema email_mappings

# View all data from a table
SELECT * FROM meetings;
SELECT * FROM action_items;
SELECT * FROM processed_files;
SELECT * FROM email_mappings;

# Count rows
SELECT COUNT(*) FROM meetings;
SELECT COUNT(*) FROM action_items;

# Exit
.quit
```

### Method 3: Using DB Browser for SQLite (GUI Tool)

1. **Install DB Browser for SQLite:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install sqlitebrowser
   
   # macOS
   brew install --cask db-browser-for-sqlite
   
   # Windows
   # Download from: https://sqlitebrowser.org/
   ```

2. **Open Database:**
   - Launch DB Browser for SQLite
   - Click "Open Database"
   - Navigate to `data/meetings.db`
   - Browse tables, view data, run queries

### Method 4: Using VS Code Extension

1. Install "SQLite Viewer" extension in VS Code
2. Right-click on `data/meetings.db`
3. Select "Open Database"
4. Browse tables in the sidebar

### Method 5: Using Python Scripts

```python
import sqlite3
from backend.meeting_summarizer.config import Config

db_path = Config.DATABASE_PATH
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all meetings
cursor.execute("SELECT * FROM meetings")
meetings = cursor.fetchall()

# Get all action items
cursor.execute("SELECT * FROM action_items")
action_items = cursor.fetchall()

conn.close()
```

## Common Queries

### Get all meetings for a project
```sql
SELECT * FROM meetings WHERE project_name = 'ProjectName';
```

### Get all action items for a person
```sql
SELECT * FROM action_items WHERE owner = 'John Doe';
```

### Get pending action items
```sql
SELECT * FROM action_items WHERE status = 'pending';
```

### Get email mappings for a project
```sql
SELECT name, email, source FROM email_mappings WHERE project_name = 'ProjectName';
```

### Get meetings with action item counts
```sql
SELECT m.*, COUNT(ai.id) as action_item_count
FROM meetings m
LEFT JOIN action_items ai ON m.id = ai.meeting_id
GROUP BY m.id;
```

## Database Maintenance

### Backup Database
```bash
cp data/meetings.db data/meetings.db.backup
```

### Reset Database (⚠️ Deletes all data)
```bash
rm data/meetings.db
# Database will be recreated on next app run
```

### Vacuum Database (Optimize)
```bash
sqlite3 data/meetings.db "VACUUM;"
```


# Complete Backend Flow Process

This document describes the complete backend flow process for the Meeting Transcript Summarizer application, from API request to final data storage and integration.

## Table of Contents

1. [Application Startup](#application-startup)
2. [Request Flow Overview](#request-flow-overview)
3. [File Upload & Validation](#file-upload--validation)
4. [Duplicate Detection](#duplicate-detection)
5. [File Processing](#file-processing)
6. [GenAI Summarization](#genai-summarization)
7. [Data Storage](#data-storage)
8. [External Integrations](#external-integrations)
9. [Error Handling](#error-handling)
10. [Background Processes](#background-processes)

## Application Startup

### 1. Server Initialization
**Location**: `backend/main.py`

```
1. FastAPI App Creation
   ├── Load configuration from .env
   ├── Initialize CORS middleware
   ├── Add security headers middleware
   └── Register API routers

2. Lifespan Events (Startup)
   ├── Initialize reminder scheduler (if enabled)
   ├── Schedule background jobs
   └── Start scheduler

3. Mount Static Files
   └── Serve frontend files from /static

4. Health Check Endpoint
   └── GET /health → {"status": "healthy"}
```

### 2. Background Scheduler Setup
**Location**: `backend/main.py::lifespan()`

- **Reminder Scheduler**: Runs every hour (configurable)
- **Job**: `send_scheduled_reminders()`
- **Checks**: Action items due within 24 hours
- **Action**: Sends email reminders

## Request Flow Overview

```
HTTP Request → FastAPI Router → Endpoint Handler → Processing → Response
```

### Main Endpoints

1. **POST /api/transcripts/process** - Process uploaded file
2. **POST /api/transcripts/process/confirm** - Confirm duplicate/old meeting
3. **GET /api/transcripts/process/{process_id}/progress** - Get processing progress
4. **GET /api/summaries/{summary_id}** - Get meeting summary
5. **GET /api/summaries/project/{project_name}** - Get project summaries
6. **DELETE /api/summaries/{summary_id}** - Delete meeting
7. **GET /api/action-items/** - Get action items (with filters)
8. **GET /api/projects/** - List projects
9. **DELETE /api/projects/{project_name}** - Delete project

## File Upload & Validation

### Step 1: Request Reception
**Location**: `backend/api/transcripts.py::process_transcript()`

```python
Input Parameters:
- file: UploadFile (required)
- project_name: str (required)
- meeting_title: Optional[str]
- meeting_date: Optional[str]
- participants: Optional[str]
- skip_sync: bool (default: False)
- analyze_project: bool (default: True)
```

### Step 2: Input Sanitization
**Location**: `backend/security.py`

```python
1. Sanitize project_name
   ├── Remove special characters
   ├── Normalize to title case
   └── Validate length

2. Sanitize meeting_title
   ├── Remove HTML tags
   ├── Limit length
   └── Escape special characters

3. Sanitize participants
   ├── Parse comma-separated list
   ├── Trim whitespace
   └── Validate names
```

### Step 3: File Validation
**Location**: `backend/security.py::validate_file_upload()`

```python
Checks Performed:
1. File Extension Validation
   ├── Allowed: .txt, .md, .mp3, .wav, .mp4, .avi, etc.
   └── Reject if not in allowed list

2. MIME Type Validation
   ├── Check Content-Type header
   └── Verify matches extension

3. File Size Check
   ├── Maximum size limit
   └── Reject if too large

4. Content Validation
   ├── Read first bytes
   └── Verify file is readable
```

### Step 4: Temporary File Storage
```python
1. Generate Process ID (UUID)
2. Save file to temporary location
3. Initialize progress tracking
4. Return process_id to frontend
```

## Duplicate Detection

### Step 1: Hash Calculation
**Location**: `backend/meeting_summarizer/core/storage.py::calculate_file_hash()`

```python
1. Read file content
2. Calculate SHA-256 hash
3. Return hex digest
```

### Step 2: Database Check
**Location**: `backend/meeting_summarizer/core/storage.py::is_file_processed()`

```python
Query: SELECT id FROM processed_files 
       WHERE file_hash = ? AND project_name = ?

Result:
- Match found → Duplicate detected
- No match → New file, continue processing
```

### Step 3: Duplicate Handling
**Location**: `backend/api/transcripts.py::process_transcript()`

```python
If duplicate detected:
1. Copy file to permanent location (prevents temp deletion)
2. Query existing meeting info from database
3. Store in pending_confirmations dict
4. Return confirmation request to frontend:
   {
     "requires_confirmation": True,
     "is_duplicate": True,
     "existing_meeting": {...},
     "process_id": "..."
   }
```

### Step 4: User Confirmation
**Location**: `backend/api/transcripts.py::confirm_old_meeting_processing()`

```python
User Response:
- Reprocess → Continue with normal flow
- Skip → Return existing meeting info
```

## File Processing

### Phase 1: File Type Detection
**Location**: `backend/meeting_summarizer/core/transcript_processor.py::_detect_file_type()`

```python
File Extensions:
- Audio: .mp3, .wav, .m4a, .flac, .ogg, .aac, .wma
- Video: .mp4, .avi, .mov, .mkv, .webm, .flv, .wmv
- Transcript: .txt, .json, .srt, .vtt

Detection Logic:
1. Check file extension
2. If unknown, try reading as text
3. Return detected type
```

### Phase 2: Transcript Extraction

#### For Text Files
**Location**: `backend/meeting_summarizer/core/transcript_processor.py::_process_transcript_file()`

```python
1. Read file content
2. Parse format:
   - Plain text → Direct use
   - JSON → Extract text field
   - SRT/VTT → Extract dialogue
3. Extract metadata:
   - Date from filename or content
   - Participants from content
4. Create MeetingTranscript object
```

#### For Audio/Video Files
**Location**: `backend/meeting_summarizer/core/transcript_processor.py::_process_media_file()`

```python
1. Load Whisper model (if not loaded)
2. Transcribe audio/video:
   - Extract audio track (if video)
   - Run Whisper transcription
   - Get segments with timestamps
3. Extract metadata:
   - Duration from file
   - Segments with speaker info
4. Create MeetingTranscript object
```

### Phase 3: Date & Title Extraction
**Location**: `backend/api/transcripts.py::get_meeting_datetime()`

```python
Priority Order:
1. User-provided meeting_date
2. Filename patterns:
   - YYYY-MM-DD or YYYY_MM_DD
   - YYYYMMDD
   - DD-MM-YYYY or DD_MM_YYYY
3. Transcript content:
   - "Date: YYYY-MM-DD"
   - "Meeting Date: ..."
4. File modification time
5. Current timestamp (fallback)
```

**Title Priority**:
```python
1. User-provided meeting_title
2. Default: "YYYY-MM-DD HH:MM - meeting summary"
3. Filename is NOT used (prevents inconsistent formats)
```

## GenAI Summarization

### Step 1: Prompt Creation
**Location**: `backend/meeting_summarizer/core/summarizer.py::_create_summarization_prompt()`

```python
Prompt Structure:
1. System Instructions
   ├── Output format (JSON)
   ├── Field descriptions
   └── Status enumeration

2. Critical Instructions
   ├── Extract ALL action items (including completed)
   ├── Status detection rules
   ├── Owner extraction rules
   └── Tags and dependencies extraction

3. Examples
   ├── Multiple examples
   └── Edge case handling

4. Transcript Content
   ├── Full transcript text
   ├── Participants list
   └── Meeting context
```

### Step 2: API Call
**Location**: `backend/meeting_summarizer/core/summarizer.py::_call_genai()`

```python
Request:
- Endpoint: OPENAI_API_BASE/chat/completions
- Model: OPENAI_MODEL (default: gpt-3.5-turbo)
- Messages: [{"role": "user", "content": prompt}]
- Temperature: 0.7
- Max tokens: 4000

Error Handling:
1. Try OpenAI API
2. If fails → Try HuggingFace (if configured)
3. If both fail → Return error
```

### Step 3: Response Parsing
**Location**: `backend/meeting_summarizer/core/summarizer.py::_parse_genai_response()`

```python
1. Extract JSON from response
   ├── Try direct JSON parsing
   └── Extract from markdown code blocks if needed

2. Validate structure
   ├── Check required fields
   └── Validate data types

3. Handle parsing errors
   └── Return error message
```

### Step 4: Post-Processing
**Location**: `backend/meeting_summarizer/core/summarizer.py::_build_summary()`

```python
For each Action Item:
1. Parse from JSON
   ├── Extract description, owner, deadline, status
   ├── Validate status enum
   └── Check for completion keywords

2. Owner Validation
   ├── Check for date patterns
   ├── Check for placeholders
   └── Set to "Unassigned" if invalid

3. Status Detection
   ├── Check description for completion keywords
   ├── Force to DONE if keywords found
   └── Set deadline to None if DONE

4. Extract Completed Tasks (Post-processing)
   ├── Scan transcript with regex patterns
   ├── Match with existing items
   └── Add if not already present

5. Status Migration
   ├── Convert old status values
   └── Handle missing fields
```

## Data Storage

### Step 1: Database Storage
**Location**: `backend/meeting_summarizer/core/storage.py::save_summary()`

```python
1. Generate Summary ID (UUID)
2. Insert into meetings table:
   ├── id, project_name, meeting_title
   ├── meeting_date, participants
   ├── overall_summary, tags
   ├── transcript_path, summary_path
   └── created_at, updated_at

3. Insert Action Items:
   ├── For each action item
   ├── Insert into action_items table
   ├── Link to meeting (meeting_id)
   └── Store external_id (Trello card ID)

4. Commit transaction
```

### Step 2: File System Storage
**Location**: `backend/meeting_summarizer/core/storage.py::save_summary()`

```python
Directory Structure:
data/
└── {project_name}/
    └── {meeting_date}_{meeting_time}/
        ├── summary.json
        ├── transcript.json
        └── {original_file} (if audio/video)

Files Created:
1. summary.json
   └── Complete MeetingSummary as JSON

2. transcript.json
   └── MeetingTranscript as JSON

3. Original file (copied)
   └── Preserved for reference
```

### Step 3: Processed Files Tracking
**Location**: `backend/meeting_summarizer/core/storage.py::mark_file_processed()`

```python
Insert into processed_files table:
├── file_hash (SHA-256)
├── original_file_path
├── project_name
├── meeting_id
├── trello_synced (0/1)
├── confluence_stored (0/1)
└── processed_at (timestamp)
```

## External Integrations

### Trello Integration Flow
**Location**: `backend/meeting_summarizer/integrations/action_item_manager.py::sync_action_items()`

```python
For each Action Item:
1. Get/Create Board
   ├── Check cache for board_id
   ├── Search by project name
   └── Create if not exists

2. Get/Create Lists
   ├── "To Do" list
   ├── "Doing" list
   ├── "Done" list
   └── "Pending" list

3. Match Existing Card
   ├── Check by external_id
   ├── Fuzzy match by description + owner
   └── Return matched item if found

4. Determine Target List
   ├── DONE → Done list
   ├── DOING → Doing list
   ├── PENDING/NEW → To Do list
   └── Overdue → Pending list

5. Create or Move Card
   ├── If card exists → Move to target list
   ├── If new → Create card in target list
   ├── Set description (owner, deadline, status)
   └── Remove deadline if DONE

6. Store external_id
   └── Update action item with Trello card ID
```

### Confluence Integration Flow
**Location**: `backend/meeting_summarizer/integrations/knowledge_base.py::store_summary()`

```python
1. Generate HTML Content
   ├── Meeting metadata
   ├── Overall summary
   ├── Action items table
   ├── Decisions list
   └── Risks list

2. Get/Create Space
   ├── Check if space exists
   └── Create if not exists

3. Create/Update Page
   ├── Title: "YYYY-MM-DD HH:MM - meeting summary"
   ├── Content: Generated HTML
   ├── Labels: Project name, tags
   └── Return page URL

4. Store URL
   └── Update summary.metadata['confluence_url']
```

## Error Handling

### Error Recovery Strategy

```python
Level 1: Try-Catch Blocks
├── Each operation wrapped in try-except
├── Log errors for debugging
└── Continue processing if non-critical

Level 2: Integration Failures
├── Trello fails → Continue without sync
├── Confluence fails → Continue without storage
└── Email fails → Log, don't crash

Level 3: GenAI Failures
├── Try HuggingFace fallback
└── Return error to user if both fail

Level 4: Database Failures
├── Retry logic for locked database
└── Return error message
```

### Progress Tracking
**Location**: `backend/api/transcripts.py::processing_progress`

```python
Progress States:
- 0%: Starting
- 10%: File validated
- 20%: Duplicate check complete
- 30%: File processing started
- 50%: Transcription complete
- 75%: Summary generated
- 90%: External sync complete
- 100%: Complete

Status Values:
- "processing": In progress
- "completed": Successfully finished
- "error": Processing failed
```

## Background Processes

### Reminder Scheduler
**Location**: `backend/main.py::send_scheduled_reminders()`

```python
Schedule: Every hour (configurable)

Process:
1. Query Action Items
   ├── Status: NEW, PENDING, DOING
   ├── Deadline within REMINDER_DAYS_BEFORE days
   └── Not blocked

2. Get Owner Email
   ├── Check email_mappings table
   └── Fallback to config

3. Send Email
   ├── SMTP connection
   ├── Format email body
   └── Send reminder

4. Log Results
   └── Track sent/failed counts
```

### Overdue Task Detection
**Location**: `backend/meeting_summarizer/integrations/action_item_manager.py::move_overdue_items_to_pending()`

```python
Process:
1. Query Trello board
2. Get all cards in "To Do" list
3. Check due dates
4. If overdue → Move to "Pending" list
5. Update status in database
```

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Request Received                    │
│              POST /api/transcripts/process                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Input Validation                          │
│  ├── Sanitize project_name, meeting_title, participants     │
│  ├── Validate file extension, MIME type, size              │
│  └── Generate process_id, initialize progress tracking      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Duplicate Detection                         │
│  ├── Calculate SHA-256 hash                                 │
│  ├── Check processed_files table (project-scoped)          │
│  └── If duplicate → Return confirmation request             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    File Processing                           │
│  ├── Detect file type (audio/video/text)                    │
│  ├── If audio/video → Whisper transcription                │
│  ├── If text → Read and parse                              │
│  └── Extract metadata (date, participants, duration)       │
└───────────────────────┬─────────────────────────────────────┘
                        │ MeetingTranscript
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  GenAI Summarization                         │
│  ├── Create prompt with instructions                        │
│  ├── Call OpenAI API                                        │
│  ├── Parse JSON response                                    │
│  ├── Post-process action items                             │
│  ├── Validate owners, statuses                              │
│  └── Extract completed tasks (fallback)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ MeetingSummary
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Handle Missing Owners                     │
│  ├── Check for unassigned items                            │
│  ├── Assign to project owner                                │
│  └── Send notification email                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              External Integrations (if not skip_sync)        │
│  ├── Trello Sync                                            │
│  │   ├── Get/create board                                  │
│  │   ├── Match existing cards                              │
│  │   ├── Create/move cards                                 │
│  │   └── Store external_id                                 │
│  └── Confluence Sync                                        │
│      ├── Generate HTML content                              │
│      ├── Create/update page                                 │
│      └── Store page URL                                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Storage                             │
│  ├── Save to database (meetings, action_items)              │
│  ├── Save JSON files (summary.json, transcript.json)        │
│  ├── Copy original file to project directory                │
│  └── Mark file as processed                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Meeting Analysis                     │
│  ├── Analyze patterns across meetings                       │
│  ├── Identify trends                                        │
│  └── Generate insights                                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      Response Returned                        │
│  ├── Summary ID                                             │
│  ├── Meeting title, date                                    │
│  ├── Action items count                                     │
│  ├── Trello board URL                                       │
│  └── Confluence page URL                                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Storage Layer (`storage.py`)
- Database operations (SQLite)
- File system management
- Hash calculation
- Duplicate detection

### 2. Transcript Processor (`transcript_processor.py`)
- File type detection
- Whisper transcription
- Metadata extraction
- Format parsing

### 3. Summarizer (`summarizer.py`)
- Prompt engineering
- GenAI API calls
- Response parsing
- Post-processing validation

### 4. Action Item Manager (`action_item_manager.py`)
- Trello integration
- Card creation/movement
- Status synchronization
- Email reminders

### 5. Knowledge Base (`knowledge_base.py`)
- Confluence integration
- HTML generation
- Page creation/updates
- Space management

## Error Recovery Points

1. **File Validation**: Reject invalid files early
2. **Duplicate Detection**: Prevent reprocessing
3. **Transcription**: Handle Whisper failures gracefully
4. **GenAI API**: Fallback to HuggingFace
5. **Trello Sync**: Continue if sync fails
6. **Confluence Sync**: Continue if storage fails
7. **Database**: Retry on lock errors
8. **Email**: Log failures, don't crash

## Performance Considerations

1. **Async Processing**: Long operations run asynchronously
2. **Progress Tracking**: Real-time updates via polling
3. **Caching**: Trello board IDs cached
4. **Batch Operations**: Multiple action items processed together
5. **Connection Pooling**: Database connections reused

This complete flow ensures robust, reliable processing of meeting transcripts with comprehensive error handling and integration support.


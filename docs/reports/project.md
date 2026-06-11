# Complete Project Flow

This document describes the complete flow of the Meeting Transcript Summarizer application, from file upload to final output.

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [File Upload Flow](#file-upload-flow)
3. [Processing Pipeline](#processing-pipeline)
4. [GenAI Summarization Flow](#genai-summarization-flow)
5. [Action Item Sync Flow](#action-item-sync-flow)
6. [Integration Flows](#integration-flows)
7. [Data Flow Diagram](#data-flow-diagram)

## High-Level Architecture

```
┌─────────────┐
│   Frontend  │ (Web UI)
│  (HTML/JS)  │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐
│   FastAPI   │ (REST API)
│   Backend   │
└──────┬──────┘
       │
       ├──► Storage (SQLite)
       ├──► GenAI (OpenAI/GPT)
       ├──► Trello API
       ├──► Confluence API
       └──► Email (SMTP)
```

## File Upload Flow

### Step 1: User Uploads File
```
User → Frontend → Upload Form
├── File Selection (audio/video/text)
├── Project Name Input
├── Meeting Title (optional)
├── Meeting Date (optional)
└── Participants (optional)
```

### Step 2: Frontend Validation
- File type validation
- File size check
- Required fields validation
- Show progress indicator

### Step 3: API Request
```javascript
POST /api/transcripts/process
FormData:
  - file: File object
  - project_name: string
  - meeting_title: string (optional)
  - meeting_date: string (optional)
  - participants: string (optional)
  - skip_sync: boolean
```

### Step 4: Backend Receives Request
**Location**: `backend/api/transcripts.py::process_transcript()`

1. **Duplicate Detection**:
   - Calculate SHA-256 hash
   - Check `processed_files` table (project-scoped)
   - If duplicate: Store in `pending_confirmations` and return confirmation request

2. **File Validation**:
   - Check file extension and MIME type
   - Validate file size
   - Security checks

3. **Store Temporary File**:
   - Save to temporary location
   - If duplicate detected, copy to permanent location immediately

## Processing Pipeline

### Phase 1: File Processing
**Location**: `backend/meeting_summarizer/core/transcript_processor.py`

```
Uploaded File
    │
    ├──► Text File? ──► Read directly
    │
    └──► Audio/Video? ──► Whisper Transcription
                          │
                          └──► Transcript Text
```

**Process**:
1. Detect file type
2. If audio/video: Use Whisper to transcribe
3. Extract metadata (duration, segments)
4. Create `MeetingTranscript` object

### Phase 2: Date and Title Extraction
**Location**: `backend/api/transcripts.py`

```
Input Priority:
1. User-provided meeting_title
2. Auto-detected from filename
3. Default: "YYYY-MM-DD HH:MM - meeting summary"

Date Priority:
1. User-provided meeting_date
2. Extracted from filename
3. Current timestamp
```

### Phase 3: GenAI Summarization
**Location**: `backend/meeting_summarizer/core/summarizer.py`

See [GenAI Summarization Flow](#genai-summarization-flow) below.

### Phase 4: Storage
**Location**: `backend/meeting_summarizer/core/storage.py`

```
MeetingSummary Object
    │
    ├──► Save to Database (meetings table)
    ├──► Save JSON to File (data/project/meeting/summary.json)
    ├──► Copy Transcript File (data/project/meeting/transcript.json)
    └──► Record in processed_files table
```

### Phase 5: Integration Sync
**Location**: `backend/api/transcripts.py`

```
If skip_sync == False:
    ├──► Trello Sync (action_item_manager.py)
    └──► Confluence Sync (knowledge_base.py)
```

## GenAI Summarization Flow

### Step 1: Prompt Creation
**Location**: `backend/meeting_summarizer/core/summarizer.py::_create_summarization_prompt()`

**Prompt Structure**:
```
1. System Instructions
   - Output format (JSON)
   - Field descriptions
   - Status values explanation

2. Critical Instructions
   - Extract ALL action items (including completed)
   - Status detection rules
   - Owner extraction rules
   - Tags and dependencies extraction

3. Examples
   - Multiple examples showing desired output
   - Edge case handling examples

4. Transcript Content
   - Full transcript text
   - Participants list
   - Meeting context
```

### Step 2: API Call
**Location**: `backend/meeting_summarizer/core/summarizer.py::_call_genai()`

```
Prompt → OpenAI API (GPT-3.5-turbo/GPT-4)
    │
    └──► JSON Response
```

**Error Handling**:
- Try OpenAI API first
- Fallback to HuggingFace if configured
- Return error if both fail

### Step 3: Response Parsing
**Location**: `backend/meeting_summarizer/core/summarizer.py::_parse_genai_response()`

```
JSON Response
    │
    ├──► Parse JSON
    ├──► Extract JSON from markdown (if needed)
    └──► Validate structure
```

### Step 4: Post-Processing
**Location**: `backend/meeting_summarizer/core/summarizer.py::_build_summary()`

**Actions**:
1. **Parse Action Items**:
   - Validate status values
   - Check for completion keywords
   - Validate owner field
   - Set deadline to None for done items

2. **Extract Completed Tasks**:
   - Scan transcript for missed completions
   - Use regex patterns
   - Match with existing action items
   - Add if not already present

3. **Status Migration**:
   - Convert old status values to new ones
   - Handle missing fields

4. **Create MeetingSummary Object**:
   - Combine all extracted data
   - Set metadata
   - Calculate duration

## Action Item Sync Flow

### Step 1: Action Item Processing
**Location**: `backend/meeting_summarizer/integrations/action_item_manager.py::sync_action_items()`

```
For each ActionItem:
    │
    ├──► Check for Completion Keywords
    │   └──► Force status to DONE if found
    │
    ├──► Match with Existing Items
    │   ├──► By external_id (Trello card ID)
    │   └──► By description + owner (fuzzy match)
    │
    ├──► Determine Status
    │   ├──► DONE → Done list, remove deadline
    │   ├──► DOING → Doing list
    │   ├──► PENDING → To Do list
    │   └──► NEW → To Do list
    │
    └──► Check for Overdue
        └──► Move to Pending list if overdue
```

### Step 2: Trello Sync
**Location**: `backend/meeting_summarizer/integrations/action_item_manager.py`

```
Action Item
    │
    ├──► Get/Create Board (by project name)
    ├──► Get/Create Lists (To Do, Doing, Done, Pending)
    │
    ├──► Card Exists? (external_id present)
    │   ├──► Yes → Move to appropriate list
    │   │   └──► Remove deadline if moving to Done
    │   │
    │   └──► No → Create new card
    │       ├──► Set name (description)
    │       ├──► Set description (owner, deadline, status)
    │       ├──► Add to appropriate list
    │       └──► Store card ID (external_id)
    │
    └──► Update Database
        └──► Save external_id for future matching
```

### Step 3: Database Update
**Location**: `backend/meeting_summarizer/core/storage.py`

```
Action Item
    │
    ├──► Save to action_items table
    ├──► Link to meeting (meeting_id)
    ├──► Store external_id (Trello card ID)
    └──► Update timestamps
```

## Integration Flows

### Confluence Integration Flow
**Location**: `backend/meeting_summarizer/integrations/knowledge_base.py`

```
MeetingSummary
    │
    ├──► Generate HTML Content
    │   ├──► Meeting metadata
    │   ├──► Overall summary
    │   ├──► Action items table
    │   ├──► Decisions list
    │   └──► Risks list
    │
    ├──► Get/Create Confluence Space
    ├──► Create/Update Page
    │   ├──► Title: "YYYY-MM-DD HH:MM - meeting summary"
    │   ├──► Content: Generated HTML
    │   └──► Labels: Project name, tags
    │
    └──► Store Page URL
        └──► Update summary.confluence_url
```

### Email Reminder Flow
**Location**: `backend/meeting_summarizer/integrations/action_item_manager.py`

```
Background Scheduler (every hour)
    │
    ├──► Query Action Items
    │   ├──► Status: NEW, PENDING, DOING
    │   ├──► Deadline within 24 hours
    │   └──► Not blocked
    │
    ├──► Get Owner Email
    │   ├──► Check email_mappings table
    │   └──► Fallback to config
    │
    └──► Send Email
        ├──► Subject: "Action Item Reminder"
        ├──► Body: Task details, deadline
        └──► SMTP via configured server
```

## Data Flow Diagram

```
┌──────────────┐
│   User       │
│   Uploads    │
│   File       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Frontend    │──► Validate & Show Progress
│  (app.js)    │
└──────┬───────┘
       │ POST /api/transcripts/process
       ▼
┌──────────────┐
│  FastAPI     │──► Check Duplicates
│  Backend     │──► Validate File
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Transcript   │──► Whisper (if audio/video)
│ Processor    │──► Extract Metadata
└──────┬───────┘
       │ MeetingTranscript
       ▼
┌──────────────┐
│  Summarizer  │──► Create Prompt
│  (GenAI)     │──► Call OpenAI API
└──────┬───────┘──► Parse Response
       │          └──► Post-process
       │ MeetingSummary
       ▼
┌──────────────┐
│   Storage    │──► Save to Database
│              │──► Save JSON Files
└──────┬───────┘──► Record Processed File
       │
       ├──► Action Item Manager ──► Trello Sync
       │
       └──► Knowledge Base ──► Confluence Sync
```

## Detailed Component Flows

### 1. Duplicate Detection Flow
```
File Upload
    │
    ├──► Calculate SHA-256 Hash
    │
    ├──► Query processed_files WHERE hash = ? AND project_name = ?
    │
    ├──► Match Found?
    │   ├──► Yes → Copy to permanent location
    │   │   └──► Return confirmation request
    │   │
    │   └──► No → Continue processing
    │
    └──► User Confirms
        ├──► Reprocess → Continue with processing
        └──► Skip → Return existing meeting info
```

### 2. Status Detection Flow
```
Action Item Description
    │
    ├──► LLM Extraction (Primary)
    │   └──► Status from prompt analysis
    │
    ├──► Keyword Detection (Secondary)
    │   ├──► "completed", "finished", "done" → DONE
    │   ├──► "working on", "in progress" → DOING
    │   └──► No progress mentioned → PENDING/NEW
    │
    ├──► Post-Processing (Tertiary)
    │   └──► Regex patterns for missed completions
    │
    └──► Validation (Final)
        ├──► Check status enum
        └──► Set deadline to None if DONE
```

### 3. Owner Extraction Flow
```
Transcript Text
    │
    ├──► LLM Extraction
    │   └──► Extract owner from context
    │
    ├──► Speaker Identification
    │   ├──► Match text position to transcript segments
    │   └──► Extract speaker name
    │
    ├──► Validation
    │   ├──► Check for date patterns
    │   ├──► Check for placeholders
    │   └──► Correct to "Unassigned" if invalid
    │
    └──► Fallback
        └──► "Unassigned" if not found
```

### 4. Project Deletion Flow
```
Delete Project Request
    │
    ├──► Normalize Project Name
    │
    ├──► Delete Trello Resources
    │   ├──► Archive all cards
    │   ├──► Close all lists
    │   └──► Delete board
    │
    ├──► Delete Confluence Resources
    │   └──► Delete all pages in space
    │
    ├──► Delete Database Records
    │   ├──► Delete meetings
    │   ├──► Delete action_items
    │   ├──► Delete processed_files
    │   └──► Delete email_mappings
    │
    └──► Delete Project Directory
        └──► Remove all files recursively
```

## Error Recovery Flow

```
Error Occurs
    │
    ├──► Try-Catch Block
    │   ├──► Log Error
    │   └──► Continue if Non-Critical
    │
    ├──► Integration Failures
    │   ├──► Trello fails → Continue without sync
    │   ├──► Confluence fails → Continue without storage
    │   └──► Email fails → Log, don't crash
    │
    ├──► GenAI Failures
    │   ├──► Try HuggingFace fallback
    │   └──► Return error to user
    │
    └──► Database Failures
        ├──► Retry logic
        └──► Return error message
```

## Summary

The complete flow ensures:
1. **Robust Processing**: Multiple fallback mechanisms at each stage
2. **Data Integrity**: Validation and migration at every step
3. **Error Recovery**: Graceful handling of failures
4. **User Experience**: Clear feedback and progress tracking
5. **Integration**: Seamless sync with external services

Each component is designed to handle edge cases and failures gracefully, ensuring the system remains operational even when individual components fail.


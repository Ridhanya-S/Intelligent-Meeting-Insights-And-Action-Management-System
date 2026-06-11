# Technical Reference — Meeting Transcript Summarizer

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture Overview](#architecture-overview)
3. [Processing Pipeline](#processing-pipeline)
4. [API Reference](#api-reference)
5. [Database Schema](#database-schema)
6. [Configuration & Environment Variables](#configuration--environment-variables)
7. [Integrations](#integrations)
8. [Security Model](#security-model)
9. [Running & Deployment](#running--deployment)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python 3.8+) |
| ASGI server | Uvicorn |
| Database | SQLite (via `sqlite3` stdlib) |
| AI / Summarization | OpenAI GPT-3.5-turbo / GPT-4 (configurable) |
| Audio transcription | OpenAI Whisper (`whisper` Python package) |
| Task scheduling | APScheduler (background reminder jobs) |
| Frontend | Vanilla HTML + CSS + JavaScript (no build step) |
| Input validation | Pydantic v2 |
| Auth | HTTP Bearer Token (optional, env-configured) |
| External integrations | Trello REST API, Atlassian Confluence REST API, Microsoft Graph API |
| Email | SMTP (smtplib) or Microsoft Graph delegated mail |
| Duplicate detection | SHA-256 file hashing |
| Linting / formatting | Ruff, Flake8, Black |
| Pre-commit hooks | pre-commit framework |
| Testing | pytest + pytest-cov |
| Containerisation | Docker + Docker Compose |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Clients                          │
│          Browser (Frontend)  /  REST API consumers      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Application                   │
│  backend/main.py                                        │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌─────────┐  │
│  │transcripts│ │summaries │ │action_items│ │projects │  │
│  │   /api   │ │   /api   │ │    /api    │ │  /api   │  │
│  └────┬─────┘ └────┬─────┘ └─────┬──────┘ └────┬────┘  │
└───────┼────────────┼─────────────┼──────────────┼───────┘
        │            │             │              │
┌───────▼────────────▼─────────────▼──────────────▼───────┐
│              meeting_summarizer package                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │    core/     │  │ integrations/│  │   analysis/   │  │
│  │  storage.py  │  │ trello sync  │  │ multi-meeting │  │
│  │summarizer.py │  │ confluence   │  │   analyzer    │  │
│  │transcript_   │  │ email remind │  │               │  │
│  │processor.py  │  │ teams / SP   │  └───────────────┘  │
│  └──────┬───────┘  └──────┬───────┘                     │
└─────────┼────────────────┼─────────────────────────────┘
          │                │
    ┌─────▼──────┐   ┌─────▼──────────────────────────┐
    │  SQLite DB │   │   External Services             │
    │data/       │   │  OpenAI API  /  Whisper (local) │
    │meetings.db │   │  Trello API                     │
    └────────────┘   │  Confluence API                 │
                     │  Microsoft Graph API            │
                     │  SMTP / MS Graph Mail           │
                     └────────────────────────────────┘
```

### Key source files

| File | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app, CORS, security headers, lifespan/scheduler |
| `backend/api/transcripts.py` | File upload, Teams URL, SharePoint URL processing |
| `backend/api/summaries.py` | Summary CRUD |
| `backend/api/action_items.py` | Action item queries and reminder trigger |
| `backend/api/projects.py` | Project management, email extraction |
| `backend/security.py` | Bearer token dependency, input sanitization |
| `backend/middleware/rate_limit.py` | Request rate limiting |
| `backend/meeting_summarizer/config.py` | All configuration from env vars |
| `backend/meeting_summarizer/models.py` | Internal domain models (`MeetingSummary`, `ActionItem`, …) |
| `backend/meeting_summarizer/core/storage.py` | SQLite read/write for all entities |
| `backend/meeting_summarizer/core/summarizer.py` | LLM prompt construction and GPT call |
| `backend/meeting_summarizer/core/transcript_processor.py` | File type handling, Whisper transcription |
| `backend/meeting_summarizer/integrations/action_item_manager.py` | Trello sync and email reminders |
| `backend/meeting_summarizer/integrations/knowledge_base.py` | Confluence page creation |
| `backend/meeting_summarizer/integrations/teams_integration.py` | Microsoft Graph / Teams meeting fetch |
| `backend/meeting_summarizer/integrations/sharepoint_download.py` | SharePoint recording download |
| `backend/meeting_summarizer/analysis/multi_meeting_analyzer.py` | Cross-meeting trend analysis |
| `backend/models/schemas.py` | Pydantic request/response schemas |

---

## Processing Pipeline

A file upload (`POST /api/transcripts/process`) passes through these stages in order:

```
1. Input Validation
   └─ Sanitize project_name, meeting_title, participants (security.py)

2. File Save & Hash
   └─ Write upload to temp path → compute SHA-256

3. Duplicate Check
   └─ Query processed_files table by hash
   └─ If match: return requires_confirmation=true → client calls /confirm

4. File Type Detection
   ├─ .txt / .md / .json  → read as plain text
   ├─ .mp3 / .mp4 / .wav  → Whisper transcription → text
   └─ Teams URL           → Graph API fetch → transcript text

5. AI Summarization (summarizer.py)
   └─ Build structured prompt with extracted text
   └─ Call LLM (OpenAI / Elsai / HuggingFace)
   └─ Parse JSON response into MeetingSummary model

6. Post-Processing
   ├─ Validate owner fields (reject date-like strings → "Unassigned")
   ├─ Keyword-based status correction (done/completed keywords)
   └─ Status value migration (old → canonical: new/pending/doing/done/blocked)

7. Persistence
   ├─ Write summary.json and transcript.json to data/<project>/<datetime>/
   └─ INSERT into meetings + action_items tables

8. External Sync (unless skip_sync=true)
   ├─ Trello: create board (if new project) + cards per action item
   └─ Confluence: create formatted page for meeting summary

9. Multi-Meeting Analysis (if analyze_project=true)
   └─ Run trend analysis across all project meetings

10. Response
    └─ Return ProcessTranscriptResponse with summary_id and integration URLs
```

### Status values for action items

| Value | Meaning |
|---|---|
| `new` | Just extracted, not yet acted on |
| `pending` | Acknowledged, waiting to start |
| `doing` | In progress |
| `done` | Completed |
| `blocked` | Blocked by dependency or issue |

---

## API Reference

Base URL: `http://localhost:8000`

### Authentication

Endpoints marked **[auth]** require `Authorization: Bearer <token>` when `API_BEARER_TOKEN` is set in env. Unauthenticated requests return `401`. Wrong token returns `403`. If `API_BEARER_TOKEN` is unset, all endpoints are open (development mode).

### Transcripts

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/transcripts/process` | No | Upload and process a meeting file |
| `POST` | `/api/transcripts/process/confirm` | No | Confirm processing of a flagged old/duplicate meeting |
| `GET` | `/api/transcripts/process/{process_id}/progress` | No | Poll processing progress |
| `POST` | `/api/transcripts/process/{process_id}/skip` | No | Skip a file during multi-file processing |
| `POST` | `/api/transcripts/process-teams-url` | No | Process a Teams meeting URL |
| `POST` | `/api/transcripts/process-sharepoint-url` | No | Process recordings from a SharePoint URL |

**POST /api/transcripts/process — form fields**

| Field | Type | Required | Default |
|---|---|---|---|
| `file` | `UploadFile` | Yes | — |
| `project_name` | `string` | Yes | — |
| `meeting_title` | `string` | No | Derived from filename |
| `meeting_date` | `string` (YYYY-MM-DD) | No | Current date |
| `participants` | `string` (comma-separated) | No | `[]` |
| `skip_sync` | `bool` | No | `false` |
| `analyze_project` | `bool` | No | `false` |

**Accepted file types:** `.txt`, `.md`, `.json`, `.mp3`, `.mp4`, `.wav`, `.m4a`, `.webm`

### Summaries

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/summaries/{summary_id}` | **[auth]** | Get a single meeting summary |
| `GET` | `/api/summaries/project/{project_name}` | **[auth]** | List all summaries for a project |
| `DELETE` | `/api/summaries/{summary_id}` | **[auth]** | Delete a meeting and its data |

`GET /api/summaries/{summary_id}` accepts query param `full_details=true` to include action items, decisions, and risks inline.

### Action Items

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/action-items/` | **[auth]** | List action items with optional filters |
| `POST` | `/api/action-items/send-reminders` | **[auth]** | Manually trigger reminder emails |
| `GET` | `/api/action-items/reminder-status` | **[auth]** | Check reminder system status |

**GET /api/action-items/ — query params**

| Param | Type | Description |
|---|---|---|
| `owner` | string | Filter by owner name |
| `status` | string | Filter by status value |
| `project_name` | string | Filter by project |
| `due_within_days` | int | Filter items due within N days |

### Projects

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/projects` | **[auth]** | List all projects |
| `POST` | `/api/projects` | **[auth]** | Create a project |
| `DELETE` | `/api/projects/{project_name}` | **[auth]** | Delete project and all meetings |
| `POST` | `/api/projects/{project_name}/extract-emails` | **[auth]** | Pull member emails from Trello/Confluence |
| `POST` | `/api/projects/{project_name}/sync-confluence` | **[auth]** | Re-sync all meetings to Confluence |
| `GET` | `/api/projects/{project_name}/email-mappings` | **[auth]** | List stored name→email mappings |

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | No | Health check — `{"status":"healthy","version":"1.0.0"}` |
| `GET` | `/` | No | Serve frontend HTML |
| `GET` | `/docs` | No | Swagger UI (interactive API docs) |

---

## Database Schema

SQLite file: `data/meetings.db` — created automatically on first run.

### `meetings`

```sql
CREATE TABLE meetings (
    id               TEXT PRIMARY KEY,
    project_name     TEXT NOT NULL,
    meeting_title    TEXT NOT NULL,
    meeting_date     TEXT NOT NULL,
    participants     TEXT,              -- JSON array
    duration_minutes REAL,
    overall_summary  TEXT,
    tags             TEXT,              -- JSON array
    transcript_path  TEXT,
    summary_path     TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX idx_meetings_project_date ON meetings (project_name, meeting_date);
```

### `action_items`

```sql
CREATE TABLE action_items (
    id          TEXT PRIMARY KEY,
    meeting_id  TEXT NOT NULL REFERENCES meetings(id),
    description TEXT NOT NULL,
    owner       TEXT NOT NULL,
    deadline    TEXT,
    status      TEXT NOT NULL,         -- new | pending | doing | done | blocked
    dependencies TEXT,                 -- JSON array of action_item ids
    tags        TEXT,                  -- JSON array
    external_id TEXT,                  -- Trello card ID
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX idx_action_items_owner_status ON action_items (owner, status);
```

### `processed_files`

```sql
CREATE TABLE processed_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash           TEXT NOT NULL UNIQUE,   -- SHA-256
    original_file_path  TEXT NOT NULL,
    project_name        TEXT NOT NULL,
    meeting_id          TEXT REFERENCES meetings(id),
    trello_synced       INTEGER DEFAULT 0,
    confluence_stored   INTEGER DEFAULT 0,
    processed_at        TEXT NOT NULL
);
CREATE INDEX idx_processed_files_hash    ON processed_files (file_hash);
CREATE INDEX idx_processed_files_project ON processed_files (project_name);
```

### `email_mappings`

```sql
CREATE TABLE email_mappings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    source      TEXT NOT NULL,          -- 'trello' | 'confluence'
    project_name TEXT,
    external_id TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (name, email, source, project_name)
);
CREATE INDEX idx_email_mappings_name    ON email_mappings (name);
CREATE INDEX idx_email_mappings_project ON email_mappings (project_name);
```

---

## Configuration & Environment Variables

All config is loaded in `backend/meeting_summarizer/config.py` via `python-dotenv`. Copy `.env.example` to `.env` and fill in values. **Never commit `.env`.**

### Core

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `RELOAD` | `true` | Uvicorn hot-reload (disable in prod) |
| `ENVIRONMENT` | — | Set to `production` to tighten CORS |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |
| `API_BEARER_TOKEN` | — | Bearer token for protected endpoints; unset = auth disabled |

### AI / LLM

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` \| `elsai` \| `huggingface` |
| `OPENAI_API_KEY` | — | **Required for summarization** |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | Override for compatible APIs (Elsai, Azure OpenAI) |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Model name |
| `HUGGINGFACE_API_KEY` | — | Alternative to OpenAI |
| `ELSAI_IMPLEMENTATION` | `native` | `native` \| `langchain` |
| `ELSAI_TEMPERATURE` | `0.1` | Temperature for Elsai requests |

### Transcription

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | `tiny` \| `base` \| `small` \| `medium` \| `large` |
| `TRANSCRIPTION_LANGUAGE` | `en` | Language hint; omit for auto-detect |

### Trello

| Variable | Description |
|---|---|
| `TRELLO_API_KEY` | Trello API key |
| `TRELLO_API_TOKEN` | Trello OAuth token |

### Confluence

| Variable | Description |
|---|---|
| `CONFLUENCE_URL` | Confluence base URL (e.g. `https://your-org.atlassian.net/wiki`) |
| `CONFLUENCE_USERNAME` | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | Atlassian API token |

### Microsoft Graph / Teams

| Variable | Description |
|---|---|
| `MS_GRAPH_TENANT_ID` | Azure AD tenant ID |
| `MS_GRAPH_CLIENT_ID` | App registration client ID |
| `MS_GRAPH_CLIENT_SECRET` | App registration client secret |
| `MS_GRAPH_API_BASE` | Graph API base URL (default: `https://graph.microsoft.com/v1.0`) |
| `MS_GRAPH_REFRESH_TOKEN` | Delegated refresh token (device code flow) |
| `SHAREPOINT_SITE_URL` | SharePoint site URL |
| `SHAREPOINT_CLIENT_ID` | SharePoint app client ID |
| `SHAREPOINT_CLIENT_SECRET` | SharePoint app client secret |

### Email / Reminders

| Variable | Default | Description |
|---|---|---|
| `REMINDER_ENABLED` | `true` | Enable/disable all reminders |
| `REMINDER_AUTO_SEND` | `true` | Auto-send in background; set `false` for manual-only |
| `REMINDER_CHECK_INTERVAL_MINUTES` | `60` | How often the scheduler checks |
| `REMINDER_DAYS_BEFORE` | `1` | Days before deadline to send reminder |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP host |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` | — | SMTP auth username |
| `SMTP_PASSWORD` | — | SMTP auth password |
| `EMAIL_FROM` | — | Sender address |
| `PROJECT_OWNER_EMAIL` | — | Fallback recipient for unassigned items |
| `PROJECT_OWNER_NAME` | — | Display name for fallback recipient |
| `OWNER_EMAIL_MAP` | — | JSON object mapping owner names to emails: `{"Alice": "alice@example.com"}` |

---

## Integrations

### Trello

- On first meeting in a project: creates a Trello board with lists `To Do`, `Doing`, `Done`, `Pending`.
- Each action item → one Trello card placed in the list matching its status.
- Board URL stored in `summary.json` and returned in API responses.
- `external_id` on `action_items` stores the Trello card ID.
- Project deletion triggers Trello board deletion.
- Requires: `TRELLO_API_KEY`, `TRELLO_API_TOKEN`

### Confluence

- Creates one page per meeting under the project space.
- Page content is formatted Markdown converted to Confluence storage format.
- Sync can be re-triggered via `POST /api/projects/{project_name}/sync-confluence`.
- Requires: `CONFLUENCE_URL`, `CONFLUENCE_USERNAME`, `CONFLUENCE_API_TOKEN`

### Microsoft Teams / Graph API

- Fetches meeting transcripts and recordings via Microsoft Graph API.
- Uses app-only credentials (`MS_GRAPH_CLIENT_ID` + `MS_GRAPH_CLIENT_SECRET`) for recording access.
- Uses delegated credentials (`MS_GRAPH_REFRESH_TOKEN`) for sending email via Graph Mail API.
- Required Graph permissions:
  - `OnlineMeetingRecording.Read.All`
  - `OnlineMeetingTranscript.Read.All`
  - `Files.Read.All`

### SharePoint

- Downloads `.mp4` recordings from SharePoint document libraries.
- Passes downloaded file through the same Whisper → summarization pipeline.
- Requires: `SHAREPOINT_SITE_URL`, `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`

### Email Reminders

- Sends reminders 24 hours before action item deadlines (configurable via `REMINDER_DAYS_BEFORE`).
- Name → email resolution order: `email_mappings` table → `OWNER_EMAIL_MAP` env var → `PROJECT_OWNER_EMAIL` fallback.
- Transport: SMTP (Gmail/other) or Microsoft Graph delegated mail if `MS_GRAPH_REFRESH_TOKEN` is set.

---

## Security Model

### API Authentication

- `API_BEARER_TOKEN` env var enables Bearer token auth.
- Implemented as a FastAPI dependency (`BearerTokenAuth`) applied per-router.
- Transcript upload endpoints are intentionally public to allow file submission without auth.
- In development (token unset), all endpoints are open.

### Input Sanitization

`backend/security.py` sanitizes all user-controlled string inputs:
- Strips HTML tags
- Removes shell-injection characters from filenames and project names
- Normalizes project names to title case
- Enforces field length limits

### Security Headers

Every response includes:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### File Handling

- Uploaded files are written to a temp path then moved; not executed.
- Only allowed MIME types are processed; others return `400`.
- SHA-256 hash-based duplicate detection prevents reprocessing.

### CORS

- Default: `*` (development). Set `ENVIRONMENT=production` and `ALLOWED_ORIGINS=https://yourdomain.com` for production.

> **Note:** `config.py` currently contains hardcoded fallback values for several integration credentials (Trello, MS Graph, Confluence). These should be removed and the credentials rotated — they are not needed as fallbacks since the integrations silently skip when credentials are absent.

---

## Running & Deployment

### Development

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY

# Start server (hot-reload enabled by default)
python start_server.py
```

Endpoints after startup:

| URL | Content |
|---|---|
| `http://localhost:8000` | Web UI |
| `http://localhost:8000/docs` | Swagger / OpenAPI |
| `http://localhost:8000/health` | Health check |

### Docker

```bash
cp .env.example .env   # fill in credentials
docker-compose up -d
```

The `docker-compose.yml` mounts `./data` so the database and processed files persist across container restarts.

### Tests

```bash
# All tests
pytest tests/

# With coverage (requires pytest-cov)
python run_tests.py

# Fast subset (skip AI-dependent tests)
pytest -m "not slow"
```

### Utility scripts

| Script | Purpose |
|---|---|
| `python scripts/view_database.py` | Print all DB tables and row counts |
| `python scripts/clear_database.py` | Wipe all data (irreversible) |
| `bash kill_port.sh` | Kill whatever is listening on port 8000 |

### Sample input files

Located in `samples/`:

```
samples/
├── sample_transcript.txt          — plain-text meeting transcript
├── sample_transcript_followup.txt — follow-up meeting transcript
└── meeting_recordings/            — MP4 recordings for testing audio pipeline
```

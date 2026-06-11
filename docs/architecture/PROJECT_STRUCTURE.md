# Project Structure

This document describes the folder structure of the Meeting Transcript Summarizer project.

## Directory Layout

```
testcase_obs_v3(working)/
├── backend/                    # Backend API (self-contained)
│   ├── main.py                # FastAPI application
│   ├── api/                   # API endpoints
│   │   ├── transcripts.py
│   │   ├── summaries.py
│   │   ├── action_items.py
│   │   └── projects.py
│   ├── models/                # API schemas
│   │   └── schemas.py
│   └── meeting_summarizer/    # Self-contained package copy
│       ├── config.py
│       ├── models.py
│       ├── core/
│       ├── integrations/
│       └── analysis/
│
├── frontend/                   # Web frontend
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── style.css
│       └── app.js
│
├── scripts/                    # CLI scripts
│   ├── main.py                # Main CLI entry point
│   └── send_reminders.py     # Reminder sender
│
├── tests/                      # Test files
│   └── test_meeting_summarizer.py
│
├── meeting_summarizer/         # Symlink to backend/meeting_summarizer (for scripts)
│
├── data/                       # Data directory
│   ├── meetings.db            # SQLite database
│   ├── trello_boards.json    # Trello board cache
│   └── [ProjectName]/        # Project-specific data
│       └── [MeetingDate]/    # Meeting-specific files
│           ├── transcript.json
│           ├── summary.json
│           └── [uploaded files]
│
├── requirements.txt            # Python dependencies
├── setup.py                   # Package setup
├── start_server.py            # Server startup script
└── README.md                  # Main documentation
```

## Package Organization

### `backend/`
Self-contained FastAPI backend with all dependencies.

- **`main.py`**: FastAPI application entry point
- **`api/`**: REST API endpoints
- **`models/`**: API request/response schemas
- **`meeting_summarizer/`**: Self-contained package copy

### `frontend/`
Web interface files.

- **`templates/index.html`**: Main HTML page
- **`static/style.css`**: Stylesheet
- **`static/app.js`**: JavaScript application

### `scripts/`
Command-line scripts for processing meetings.

- **`main.py`**: CLI entry point
- **`send_reminders.py`**: Standalone reminder script

### `meeting_summarizer/` (symlink)
Symlink to `backend/meeting_summarizer/` for CLI scripts compatibility.

### `data/`
Data storage directory (shared between backend and CLI).

- **`meetings.db`**: SQLite database
- **`trello_boards.json`**: Trello board cache
- **`[ProjectName]/[MeetingDate]/`**: Organized meeting data

## Usage

### Running the Web Application

```bash
python start_server.py
# or
python backend/main.py
```

### Running CLI Scripts

```bash
python scripts/main.py "ProjectName" "/path/to/transcript.txt"
```

### Running Tests

```bash
python -m pytest tests/
```

## Import Examples

### Backend
```python
from backend.meeting_summarizer.config import Config
from backend.meeting_summarizer.core.storage import Storage
from backend.models.schemas import SummaryResponse
```

### CLI Scripts
```python
from meeting_summarizer.config import Config
from meeting_summarizer.core.storage import Storage
```

## Notes

- Backend is self-contained in `backend/` folder
- Frontend is separate in `frontend/` folder
- CLI scripts use symlinked `meeting_summarizer/` package
- All components share the same `data/` directory
- Configuration paths are automatically adjusted

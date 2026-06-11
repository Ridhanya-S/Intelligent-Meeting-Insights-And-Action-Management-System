# Backend API

FastAPI-based REST API for Meeting Transcript Summarizer.

## Structure

The backend is self-contained with all required dependencies:

```
backend/
├── main.py                    # FastAPI application entry point
├── api/                       # API endpoints
│   ├── transcripts.py        # Process transcripts
│   ├── summaries.py          # Get summaries
│   ├── action_items.py       # Manage action items
│   └── projects.py           # List projects
├── models/                    # API schemas
│   └── schemas.py            # Request/response models
└── meeting_summarizer/       # Self-contained package copy
    ├── config.py             # Configuration
    ├── models.py             # Data models
    ├── core/                 # Core functionality
    ├── integrations/         # External integrations
    └── analysis/             # Analysis modules
```

## Running the Backend

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python backend/main.py
```

Or using uvicorn directly:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the startup script from project root:

```bash
python start_server.py
```

The API will be available at:
- **Frontend**: http://localhost:8000
- **API**: http://localhost:8000/api
- **API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### Transcripts
- `POST /api/transcripts/process` - Process an uploaded transcript file

### Summaries
- `GET /api/summaries/{summary_id}` - Get a specific summary
- `GET /api/summaries/project/{project_name}` - Get all summaries for a project

### Action Items
- `GET /api/action-items/` - Get action items (with optional filters: owner, status, project_name)
- `POST /api/action-items/send-reminders` - Send reminders for due items

### Projects
- `GET /api/projects/` - Get list of all projects

### Health
- `GET /health` - Health check endpoint
- `GET /` - Frontend page

## Self-Contained Design

The backend includes its own copy of the `meeting_summarizer` package, making it:
- **Independent**: Can be deployed separately
- **Self-contained**: All dependencies are within the backend folder
- **Easy to track**: All backend-related code is in one place

The data directory (`data/`) remains at the project root level and is shared between CLI scripts and the backend API.

## API Documentation

Interactive API documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

# Meeting Transcript Summarizer

A FastAPI application that processes Teams meeting recordings and transcripts to generate structured summaries, extract action items, and sync them to Trello and Confluence.

For full technical details see [TECH.md](TECH.md). For docs navigation see [docs/INDEX.md](docs/INDEX.md).

---

## Features

- Upload audio, video, or text transcripts for AI-powered summarization
- Extracts action items (with owner, deadline, status), decisions, and risks
- Syncs action items to **Trello** and summaries to **Confluence**
- Fetches recordings directly from **Microsoft Teams / SharePoint**
- Sends automated email reminders before deadlines
- Duplicate file detection (SHA-256 hashing)
- Multi-meeting trend analysis per project
- Bearer token authentication (optional)

---

## Project Structure

```
poc_testcase/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry point, CORS, scheduler
│   ├── api/                    # Route handlers
│   ├── models/                 # Pydantic schemas
│   ├── middleware/             # Rate limiting
│   ├── security.py             # Auth dependency, input sanitization
│   └── meeting_summarizer/     # Core package
│       ├── config.py           # All configuration (env vars)
│       ├── models.py           # Domain models
│       ├── core/               # Storage, summarizer, transcript processor
│       ├── integrations/       # Trello, Confluence, Teams, SharePoint, email
│       └── analysis/           # Multi-meeting analyzer
├── frontend/                   # HTML + CSS + JS (no build step)
├── scripts/                    # CLI utilities (view_database, clear_database)
├── tests/                      # pytest test suite
├── data/                       # Runtime data (DB + processed meetings)
├── samples/                    # Sample input files for testing
│   ├── sample_transcript.txt
│   ├── sample_transcript_followup.txt
│   └── meeting_recordings/
├── docs/                       # Documentation
│   ├── INDEX.md
│   ├── architecture/
│   ├── api/
│   ├── integrations/
│   ├── development/
│   └── reports/
├── start_server.py             # Server startup script
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Setup

### Prerequisites

- Python 3.8+
- FFmpeg (for audio/video processing)

```bash
sudo apt-get install ffmpeg   # Ubuntu/Debian
```

### Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env — minimum required: OPENAI_API_KEY
```

See [TECH.md — Configuration](TECH.md#configuration--environment-variables) for the full variable reference.

### Start

```bash
python start_server.py
```

| URL | Content |
|---|---|
| `http://localhost:8000` | Web UI |
| `http://localhost:8000/docs` | Swagger / OpenAPI |
| `http://localhost:8000/health` | Health check |

### Docker

```bash
cp .env.example .env
docker-compose up -d
```

---

## Usage

### Web UI

Open `http://localhost:8000`, upload a meeting file (`.txt`, `.mp3`, `.mp4`, etc.), enter a project name, and submit.

### API

```bash
curl -X POST "http://localhost:8000/api/transcripts/process" \
  -F "file=@samples/sample_transcript.txt" \
  -F "project_name=MyProject" \
  -F "meeting_title=Weekly Standup"
```

See [TECH.md — API Reference](TECH.md#api-reference) for all endpoints.

### Utility scripts

```bash
python scripts/view_database.py    # inspect DB contents
python scripts/clear_database.py   # wipe all data
bash kill_port.sh                  # kill process on port 8000
```

---

## Development

### Tests

```bash
pytest tests/                      # run all tests
python run_tests.py                # with coverage report
pytest -m "not slow"               # skip AI-dependent tests
```

### Linting

```bash
ruff check .
black .
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`. See [docs/development/PRE_COMMIT.md](docs/development/PRE_COMMIT.md).

---

## License

Provided as-is for educational and internal use.

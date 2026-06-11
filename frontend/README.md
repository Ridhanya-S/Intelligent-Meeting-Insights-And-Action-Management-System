# Frontend - Meeting Transcript Summarizer

A simple, modern web interface for the Meeting Transcript Summarizer application.

## Features

- **File Upload**: Upload audio, video, or text transcript files
- **Project Management**: View all projects and their meeting summaries
- **Action Items**: Browse and filter action items by project and status
- **Real-time Processing**: See processing status and results in real-time
- **Responsive Design**: Works on desktop and mobile devices

## Structure

```
frontend/
├── templates/
│   └── index.html      # Main HTML page
├── static/
│   ├── style.css       # Styling
│   └── app.js          # JavaScript for API interactions
└── README.md           # This file
```

## Usage

The frontend is automatically served by the FastAPI backend when you start the server:

```bash
python start_server.py
# or
uvicorn backend.main:app --reload
```

Then open your browser to:
- **Frontend**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs

## API Endpoints Used

- `POST /api/transcripts/process` - Upload and process transcript
- `GET /api/projects/` - Get list of all projects
- `GET /api/summaries/project/{project_name}` - Get summaries for a project
- `GET /api/action-items/` - Get action items with filters

## Features Details

### Upload Form
- Supports audio (MP3, WAV), video (MP4), and text (TXT, MD) files
- Optional fields: meeting title, date, participants
- Options to skip Trello sync or run multi-meeting analysis

### Projects Section
- Displays all projects with meeting counts
- Click on a project to view its summaries
- Refresh button to reload projects

### Action Items Section
- Filter by project and status
- Shows owner, deadline, tags, and dependencies
- Indicates if synced to Trello

## Styling

The frontend uses a modern gradient design with:
- Purple gradient theme (#667eea to #764ba2)
- Card-based layout
- Responsive grid system
- Smooth transitions and hover effects

## Browser Support

Works in all modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)


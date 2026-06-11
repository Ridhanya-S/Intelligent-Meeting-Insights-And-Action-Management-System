# Database to Frontend Data Flow

This document explains how content from the database flows to the frontend UI.

## Overview

The data flow follows this path:
```
SQLite Database → Storage Class → API Endpoint → Pydantic Schema → JSON Response → Frontend Fetch → UI Display
```

## Step-by-Step Flow

### 1. **Database Layer (SQLite)**

Data is stored in SQLite database (`data/meetings.db`) with these main tables:
- `meetings` - Meeting summaries metadata
- `action_items` - Action items associated with meetings
- `processed_files` - Track processed files to prevent duplicates

**Example Query:**
```sql
SELECT * FROM meetings WHERE id = 'meeting-123'
```

### 2. **Storage Class (`backend/meeting_summarizer/core/storage.py`)**

The `Storage` class provides methods to retrieve data from the database:

```python
def get_summary(self, summary_id: str) -> Optional[MeetingSummary]:
    """Retrieve meeting summary by ID"""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM meetings WHERE id = ?', (summary_id,))
    row = cursor.fetchone()
    
    # Load full data from JSON file
    summary_path = row[9]  # summary_path column
    if summary_path and Path(summary_path).exists():
        with open(summary_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return MeetingSummary(**data)
```

**Key Methods:**
- `get_summary(summary_id)` - Get single meeting summary
- `get_action_items_by_owner()` - Get action items with filters
- `get_project_meetings()` - Get all meetings for a project

### 3. **API Endpoint (`backend/api/summaries.py`, `backend/api/action_items.py`)**

API endpoints retrieve data using Storage and convert to response format:

```python
@router.get("/{summary_id}", response_model=SummaryResponse, dependencies=[BearerTokenAuth])
async def get_summary(summary_id: str, full_details: bool = False):
    storage = Storage()
    summary = storage.get_summary(summary_id)  # ← Database query
    
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    # Convert MeetingSummary model to SummaryResponse schema
    return SummaryResponse(
        id=summary.id,
        project_name=summary.project_name,
        meeting_title=summary.meeting_title,
        # ... more fields
    )
```

**Protected Endpoints** (require Bearer Token):
- `GET /api/summaries/{summary_id}` - Get single summary
- `GET /api/summaries/project/{project_name}` - Get all summaries for project
- `GET /api/action-items/` - Get action items (with filters)
- `GET /api/projects` - Get all projects

### 4. **Pydantic Schema (`backend/models/schemas.py`)**

Pydantic models define the response structure and validate data:

```python
class SummaryResponse(BaseModel):
    """Response model for meeting summary"""
    id: Optional[str] = None
    project_name: str
    meeting_title: str
    meeting_date: datetime
    participants: List[str]
    overall_summary: str
    action_items_count: int
    # ... more fields
```

**Benefits:**
- Type validation
- Automatic JSON serialization
- API documentation (OpenAPI/Swagger)

### 5. **JSON Response**

FastAPI automatically converts Pydantic models to JSON:

```json
{
  "id": "meeting-123",
  "project_name": "Project Alpha",
  "meeting_title": "Sprint Planning",
  "meeting_date": "2024-01-15T10:00:00",
  "participants": ["Alice", "Bob"],
  "overall_summary": "Discussed sprint goals...",
  "action_items_count": 5
}
```

### 6. **Frontend Fetch (`frontend/static/app.js`)**

JavaScript fetches data from API endpoints:

```javascript
async function loadFullSummary(summaryId, targetElement = null) {
    // Fetch from API with Bearer Token
    const response = await fetch(`${API_BASE}/api/summaries/${summaryId}?full_details=true`, {
        headers: {
            'Authorization': `Bearer ${API_BEARER_TOKEN}`
        }
    });
    
    // Parse JSON response
    const summary = await response.json();
    
    // Render to UI
    renderSummaryCard(summary, date, true, targetElement);
}
```

**Key Frontend Functions:**
- `loadFullSummary(summaryId)` - Load single summary details
- `loadActionItems()` - Load action items list
- `loadProjects()` - Load projects list
- `loadProjectSummaries(projectName)` - Load all summaries for a project

### 7. **UI Display**

Data is rendered into HTML elements:

```javascript
function renderSummaryCard(summary, date, isExpanded = false) {
    const content = `
        <div class="summary-card">
            <div class="summary-title">${escapeHtml(summary.meeting_title)}</div>
            <div class="summary-meta">
                <span>📁 ${escapeHtml(summary.project_name)}</span>
                <span>📅 ${date}</span>
            </div>
            <p>${escapeHtml(summary.overall_summary)}</p>
            <!-- More content -->
        </div>
    `;
    resultsContent.innerHTML = content;
}
```

## Complete Example: Loading a Summary

### Backend Flow:

1. **Frontend Request:**
   ```javascript
   fetch('/api/summaries/abc123?full_details=true', {
       headers: { 'Authorization': 'Bearer token123' }
   })
   ```

2. **API Endpoint (`backend/api/summaries.py`):**
   ```python
   @router.get("/{summary_id}")
   async def get_summary(summary_id: str):
       storage = Storage()
       summary = storage.get_summary(summary_id)  # ← DB query
       return SummaryResponse(...)  # ← Convert to schema
   ```

3. **Storage Query (`backend/meeting_summarizer/core/storage.py`):**
   ```python
   def get_summary(self, summary_id: str):
       conn = sqlite3.connect(self.db_path)
       cursor.execute('SELECT * FROM meetings WHERE id = ?', (summary_id,))
       row = cursor.fetchone()
       # Load JSON file with full data
       with open(summary_path, 'r') as f:
           data = json.load(f)
       return MeetingSummary(**data)
   ```

4. **Database Query:**
   ```sql
   SELECT * FROM meetings WHERE id = 'abc123'
   ```

5. **JSON File Load:**
   ```json
   {
     "id": "abc123",
     "project_name": "Project Alpha",
     "meeting_title": "Sprint Planning",
     "overall_summary": "...",
     "all_action_items": [...]
   }
   ```

6. **Response:**
   ```json
   {
     "id": "abc123",
     "project_name": "Project Alpha",
     "meeting_title": "Sprint Planning",
     "overall_summary": "...",
     "action_items_count": 5
   }
   ```

### Frontend Flow:

1. **Receive JSON:**
   ```javascript
   const summary = await response.json();
   ```

2. **Render to UI:**
   ```javascript
   renderSummaryCard(summary, date, true);
   ```

3. **Display:**
   ```html
   <div class="summary-card">
     <div class="summary-title">Sprint Planning</div>
     <div class="summary-meta">📁 Project Alpha</div>
     <p>Meeting summary text...</p>
   </div>
   ```

## Authentication Flow

All database-exposing endpoints require Bearer Token authentication:

1. **Token Check (`backend/security.py`):**
   ```python
   async def verify_bearer_token(credentials):
       if credentials.credentials != Config.API_BEARER_TOKEN:
           raise HTTPException(status_code=403)
   ```

2. **Frontend Includes Token:**
   ```javascript
   fetch('/api/summaries/123', {
       headers: {
           'Authorization': `Bearer ${API_BEARER_TOKEN}`
       }
   })
   ```

## Data Storage Strategy

The system uses a **hybrid storage approach**:

1. **Database (SQLite):** Stores metadata and relationships
   - Meeting IDs, titles, dates, project names
   - Action item references
   - File processing history

2. **JSON Files:** Store complete meeting data
   - Full summary text
   - All action items with details
   - Decisions and risks
   - Metadata

**Why this approach?**
- Database: Fast queries, relationships, indexing
- JSON Files: Complete data, easy backup, version control friendly

## Key Files

- **Database Access:** `backend/meeting_summarizer/core/storage.py`
- **API Endpoints:** `backend/api/summaries.py`, `backend/api/action_items.py`, `backend/api/projects.py`
- **Response Schemas:** `backend/models/schemas.py`
- **Frontend Fetch:** `frontend/static/app.js`
- **Authentication:** `backend/security.py`

## Summary

The data flow is:
1. **SQLite DB** stores metadata
2. **JSON files** store complete data
3. **Storage class** retrieves and combines both
4. **API endpoints** convert to Pydantic schemas
5. **FastAPI** serializes to JSON
6. **Frontend** fetches and renders to HTML

This architecture provides:
- ✅ Type safety (Pydantic)
- ✅ Security (Bearer tokens)
- ✅ Performance (indexed database queries)
- ✅ Completeness (JSON file storage)
- ✅ API documentation (OpenAPI)


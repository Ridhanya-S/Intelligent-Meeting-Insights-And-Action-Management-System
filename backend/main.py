"""
FastAPI Backend Server

REST API for Meeting Transcript Summarizer
"""
import sys
from pathlib import Path

# Add backend directory to Python path
_backend_root = Path(__file__).parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import os
from contextlib import asynccontextmanager

from backend.api import transcripts, summaries, action_items, projects
from backend.meeting_summarizer.config import Config


def send_scheduled_reminders():
    """Background task to send reminders automatically"""
    if not Config.REMINDER_ENABLED:
        return
    
    try:
        from backend.meeting_summarizer.integrations.action_item_manager import ActionItemManager
        manager = ActionItemManager()
        results = manager.send_all_pending_reminders()
        
        if results["total"] > 0:
            print(f"[Reminder Scheduler] Sent {results['sent']} reminders, {results['failed']} failed")
    except Exception as e:
        print(f"[Reminder Scheduler] Error sending reminders: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Initialize background scheduler
    if Config.REMINDER_ENABLED and Config.REMINDER_AUTO_SEND:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            
            scheduler = BackgroundScheduler()
            
            # Schedule reminders to run every hour
            reminder_interval = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "60"))
            scheduler.add_job(
                send_scheduled_reminders,
                trigger=IntervalTrigger(minutes=reminder_interval),
                id='send_reminders',
                name='Send action item reminders',
                replace_existing=True
            )
            
            scheduler.start()
            print(f"[Reminder Scheduler] Started - checking every {reminder_interval} minutes")
            
            # Store scheduler in app state
            app.state.scheduler = scheduler
        except ImportError:
            print("[Reminder Scheduler] APScheduler not installed. Install with: pip install APScheduler")
        except Exception as e:
            print(f"[Reminder Scheduler] Failed to start: {e}")
    
    yield
    
    # Shutdown: Stop scheduler
    if hasattr(app.state, 'scheduler'):
        scheduler = app.state.scheduler
        if scheduler.running:
            scheduler.shutdown()
            print("[Reminder Scheduler] Stopped")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Meeting Transcript Summarizer API",
    description="API for processing meeting transcripts and managing action items",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS with security improvements
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if "*" in allowed_origins and os.getenv("ENVIRONMENT") == "production":
    # In production, don't allow all origins
    allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Include routers
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["transcripts"])
app.include_router(summaries.router, prefix="/api/summaries", tags=["summaries"])
app.include_router(action_items.router, prefix="/api/action-items", tags=["action-items"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])

# Note: Request size limiting is handled by FastAPI's built-in limits
# For production, configure uvicorn with --limit-max-requests and --limit-concurrency

# Mount static files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    static_path = frontend_path / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page"""
    frontend_file = Path(__file__).parent.parent / "frontend" / "templates" / "index.html"
    if frontend_file.exists():
        return frontend_file.read_text(encoding="utf-8")
    return """
    <html>
        <head><title>Meeting Summarizer API</title></head>
        <body>
            <h1>Meeting Transcript Summarizer API</h1>
            <p>API is running. Frontend files not found.</p>
            <p>API docs: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


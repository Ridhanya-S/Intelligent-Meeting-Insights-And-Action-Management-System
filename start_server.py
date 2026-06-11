#!/usr/bin/env python3
"""
Startup script for Meeting Transcript Summarizer Web Application

This script starts the FastAPI backend server with the frontend.
"""
import sys
from pathlib import Path

# Add project root to Python path
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import uvicorn

if __name__ == "__main__":
    import os
    from backend.meeting_summarizer.config import Config
    
    # Get host and port from environment variables (for Docker)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    # Get API Bearer Token from Config (which loads from .env file)
    # If not set, authentication will be disabled (development mode)
    api_bearer_token = Config.API_BEARER_TOKEN
    if api_bearer_token:
        os.environ["API_BEARER_TOKEN"] = api_bearer_token
        print("=" * 60)
        print("Starting Meeting Transcript Summarizer Web Application")
        print("=" * 60)
        print(f"\nServer will be available at:")
        print(f"  - Frontend: http://{host}:{port}")
        print(f"  - API Docs: http://{host}:{port}/docs")
        print(f"  - API: http://{host}:{port}/api")
        print(f"\nHost: {host}, Port: {port}, Reload: {reload}")
        print("\n✓ API Bearer Token authentication: ENABLED")
        print("  Protected endpoints require: Authorization: Bearer <token>")
        print("\nPress Ctrl+C to stop the server")
        print("=" * 60)
        print()
    else:
        print("=" * 60)
        print("Starting Meeting Transcript Summarizer Web Application")
        print("=" * 60)
        print(f"\nServer will be available at:")
        print(f"  - Frontend: http://{host}:{port}")
        print(f"  - API Docs: http://{host}:{port}/docs")
        print(f"  - API: http://{host}:{port}/api")
        print(f"\nHost: {host}, Port: {port}, Reload: {reload}")
        print("\n⚠ API Bearer Token authentication: DISABLED (development mode)")
        print("  Set API_BEARER_TOKEN in .env file or environment variable to enable authentication")
        print("  Example: Add to .env file: API_BEARER_TOKEN=your-secret-token-here")
        print("  Or: export API_BEARER_TOKEN='your-secret-token-here'")
        print("\nPress Ctrl+C to stop the server")
        print("=" * 60)
        print()
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


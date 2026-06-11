"""
Configuration Management Module

Manages application configuration from environment variables and provides
default values for all settings.
"""

# Standard library imports
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Third-party imports
from dotenv import load_dotenv

# Load environment variables (ignore errors if .env file has issues)
try:
    load_dotenv()
except Exception:
    # If .env file has parsing issues, continue without it
    pass


class Config:
    """
    Application configuration class.
    
    All configuration values are loaded from environment variables with
    sensible defaults. Configuration is validated on startup.
    """
    
    # ============================================================================
    # Project Settings
    # ============================================================================
    
    # PROJECT_ROOT is the project root (3 levels up: backend/meeting_summarizer/config.py -> project root)
    # This allows backend to be self-contained while accessing project data directory
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    
    # Create directories if they don't exist
    DATA_DIR.mkdir(exist_ok=True)
    
    @staticmethod
    def get_meeting_dir(project_name: str, meeting_date: datetime) -> Path:
        """
        Get directory path for a meeting: projectname/meetingtime/.
        
        Args:
            project_name: Name of the project
            meeting_date: Date and time of the meeting
            
        Returns:
            Path to the meeting directory
        """
        date_str = meeting_date.strftime("%Y-%m-%d_%H%M%S")
        meeting_dir = Config.DATA_DIR / project_name / date_str
        meeting_dir.mkdir(parents=True, exist_ok=True)
        return meeting_dir
    
    # ============================================================================
    # GenAI Configuration (OpenAI or compatible API)
    # ============================================================================
    
    # LLM Provider Selection: "elsai", "openai", or "huggingface"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
    
    OPENAI_API_KEY: Optional[str] = os.getenv(
        "OPENAI_API_KEY",
        ""
    )
    OPENAI_API_BASE: Optional[str] = os.getenv(
        "OPENAI_API_BASE",
        "https://api.openai.com/v1"
    )
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # Alternative: Hugging Face (free tier)
    HUGGINGFACE_API_KEY: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
    
    # Elsai Model Configuration
    ELSAI_IMPLEMENTATION: str = os.getenv("ELSAI_IMPLEMENTATION", "native")  # "native" or "langchain"
    ELSAI_TEMPERATURE: float = float(os.getenv("ELSAI_TEMPERATURE", "0.1"))
    
    # ============================================================================
    # Transcription Settings
    # ============================================================================
    
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large
    TRANSCRIPTION_LANGUAGE: Optional[str] = os.getenv("TRANSCRIPTION_LANGUAGE", "en")  # None = auto-detect
    
    # ============================================================================
    # Trello Configuration
    # ============================================================================
    
    TRELLO_API_KEY: Optional[str] = os.getenv("TRELLO_API_KEY")
    TRELLO_API_TOKEN: Optional[str] = os.getenv("TRELLO_API_TOKEN")
    
    # ============================================================================
    # SharePoint Configuration
    # ============================================================================
    
    SHAREPOINT_SITE_URL: Optional[str] = os.getenv("SHAREPOINT_SITE_URL")
    SHAREPOINT_CLIENT_ID: Optional[str] = os.getenv("SHAREPOINT_CLIENT_ID")
    SHAREPOINT_CLIENT_SECRET: Optional[str] = os.getenv("SHAREPOINT_CLIENT_SECRET")
    
    # ============================================================================
    # Microsoft Graph API / Teams Configuration
    # ============================================================================
    
    MS_GRAPH_TENANT_ID: Optional[str] = os.getenv("MS_GRAPH_TENANT_ID")
    MS_GRAPH_CLIENT_ID: Optional[str] = os.getenv("MS_GRAPH_CLIENT_ID")
    MS_GRAPH_CLIENT_SECRET: Optional[str] = os.getenv("MS_GRAPH_CLIENT_SECRET")
    MS_GRAPH_API_BASE: str = os.getenv(
        "MS_GRAPH_API_BASE",
        "https://graph.microsoft.com/v1.0"
    )
    
    # Microsoft Graph API Delegated Permissions (for email sending)
    # Refresh token for delegated permissions (obtained via device code flow)
    MS_GRAPH_REFRESH_TOKEN: Optional[str] = os.getenv("MS_GRAPH_REFRESH_TOKEN")
    
    # ============================================================================
    # Confluence Configuration
    # ============================================================================
    
    CONFLUENCE_URL: Optional[str] = os.getenv("CONFLUENCE_URL")
    CONFLUENCE_USERNAME: Optional[str] = os.getenv("CONFLUENCE_USERNAME")
    CONFLUENCE_API_TOKEN: Optional[str] = os.getenv("CONFLUENCE_API_TOKEN")
    
    # ============================================================================
    # Reminder Settings
    # ============================================================================
    
    REMINDER_DAYS_BEFORE: int = int(os.getenv("REMINDER_DAYS_BEFORE", "1"))
    REMINDER_ENABLED: bool = os.getenv("REMINDER_ENABLED", "true").lower() == "true"
    REMINDER_AUTO_SEND: bool = os.getenv("REMINDER_AUTO_SEND", "true").lower() == "true"  # Auto-send reminders in background
    REMINDER_CHECK_INTERVAL_MINUTES: int = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "60"))  # Check every hour by default
    
    # Project Owner Settings (for unassigned action items)
    PROJECT_OWNER_EMAIL: Optional[str] = os.getenv("PROJECT_OWNER_EMAIL")
    PROJECT_OWNER_NAME: Optional[str] = os.getenv("PROJECT_OWNER_NAME")
    
    # ============================================================================
    # Email Configuration for Reminders
    # ============================================================================
    
    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")

    # Email mapping: owner name -> email address (JSON format)
    OWNER_EMAIL_MAP: Optional[str] = os.getenv("OWNER_EMAIL_MAP")
    
    # ============================================================================
    # Database Configuration
    # ============================================================================
    
    DATABASE_PATH: Path = DATA_DIR / "meetings.db"
    
    # ============================================================================
    # API Security Configuration
    # ============================================================================
    
    API_BEARER_TOKEN: Optional[str] = os.getenv("API_BEARER_TOKEN")
    # If no token is set, authentication is disabled (for development)
    # In production, always set API_BEARER_TOKEN
    
    # ============================================================================
    # Validation
    # ============================================================================
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate that required configuration is present.
        
        Returns:
            True if configuration is valid (warnings may be printed)
        """
        # Validate LLM provider configuration
        valid_providers = ["elsai", "openai", "huggingface"]
        if cls.LLM_PROVIDER.lower() not in valid_providers:
            print(f"Warning: Invalid LLM_PROVIDER '{cls.LLM_PROVIDER}'. Must be one of: {', '.join(valid_providers)}")
        
        # Validate provider-specific configuration
        if cls.LLM_PROVIDER.lower() == "elsai":
            if not cls.OPENAI_API_KEY:
                print("Warning: LLM_PROVIDER is 'elsai' but OPENAI_API_KEY is not configured")
        elif cls.LLM_PROVIDER.lower() == "openai":
            if not cls.OPENAI_API_KEY:
                print("Warning: LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not configured")
        elif cls.LLM_PROVIDER.lower() == "huggingface":
            if not cls.HUGGINGFACE_API_KEY:
                print("Warning: LLM_PROVIDER is 'huggingface' but HUGGINGFACE_API_KEY is not configured")
        
        # At minimum, we need either OpenAI or HuggingFace for GenAI
        has_genai = bool(cls.OPENAI_API_KEY) or bool(cls.HUGGINGFACE_API_KEY)
        if not has_genai:
            print("Warning: No GenAI API key found. Set OPENAI_API_KEY or HUGGINGFACE_API_KEY")
        return True

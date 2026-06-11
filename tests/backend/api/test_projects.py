"""
Tests for projects API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app
from pathlib import Path


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


class TestProjectsAPI:
    """Test projects API endpoints"""
    
    @patch('backend.api.projects.Config')
    def test_get_projects(self, mock_config, client, temp_data_dir):
        """Test getting list of projects"""
        mock_config.DATA_DIR = temp_data_dir
        
        # Create a test project directory
        project_dir = temp_data_dir / "TestProject"
        project_dir.mkdir()
        meeting_dir = project_dir / "2024-01-01_000000"
        meeting_dir.mkdir()
        summary_file = meeting_dir / "summary.json"
        summary_file.write_text('{"meeting_date": "2024-01-01T00:00:00"}')
        
        response = client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('backend.api.projects.Config')
    def test_get_projects_empty(self, mock_config, client, temp_data_dir):
        """Test getting projects when none exist"""
        mock_config.DATA_DIR = temp_data_dir
        
        response = client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


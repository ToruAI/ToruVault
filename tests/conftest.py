import os
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    original_environ = os.environ.copy()
    os.environ["BWS_TOKEN"] = "test_token"
    os.environ["ORGANIZATION_ID"] = "test_org_id"
    os.environ["STATE_FILE"] = "test_state_file"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_environ)

@pytest.fixture
def mock_keyring():
    """Mock keyring for testing"""
    with patch("keyring.get_password") as mock_get, patch("keyring.set_password") as mock_set:
        mock_get.return_value = None  # Default to None, tests can override if needed
        mock_set.return_value = None
        yield mock_get, mock_set

@pytest.fixture
def mock_bitwarden_client():
    """Create a mock Bitwarden client for testing"""
    client = MagicMock()
    
    # Mock secrets service
    secrets_service = MagicMock()
    
    # Mock successful sync response
    sync_response = MagicMock()
    sync_response.success = True
    secrets_service.sync.return_value = sync_response
    
    # Mock secrets list response
    secrets_list = MagicMock()
    secrets_list.data = MagicMock()
    secrets_list.data.data = [
        MagicMock(id="secret1"),
        MagicMock(id="secret2"),
    ]
    secrets_service.list.return_value = secrets_list
    
    # Mock get_by_ids response with test secrets
    secrets_detailed = MagicMock()
    secrets_detailed.data = MagicMock()
    secret1 = MagicMock(key="TEST_SECRET1", value="test_value1", project_id="project1")
    secret2 = MagicMock(key="TEST_SECRET2", value="test_value2", project_id="project1")
    secrets_detailed.data.data = [secret1, secret2]
    secrets_service.get_by_ids.return_value = secrets_detailed
    
    # Attach secrets service to client
    client.secrets.return_value = secrets_service
    
    # Mock projects service
    projects_service = MagicMock()
    projects_list = MagicMock()
    projects_list.data = MagicMock()
    project1 = MagicMock(id="project1", name="Test Project")
    projects_list.data.data = [project1]
    projects_service.list.return_value = projects_list
    
    # Attach projects service to client
    client.projects.return_value = projects_service
    
    # Mock auth service
    auth_service = MagicMock()
    login_response = MagicMock()
    login_response.success = True
    auth_service.login_access_token.return_value = login_response
    
    # Attach auth service to client
    client.auth.return_value = auth_service
    
    return client

@pytest.fixture
def mock_initialize_client(mock_bitwarden_client):
    """Mock the _initialize_client function to return our mock client"""
    with patch("toru_vault.vault._initialize_client") as mock_init:
        mock_init.return_value = mock_bitwarden_client
        yield mock_init

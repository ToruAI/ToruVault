import os
import pytest
from unittest.mock import patch, MagicMock

from toru_vault.vault import env_load, env_load_all

class TestEnvLoad:
    
    def test_env_load_single_project(self, mock_env_vars, mock_initialize_client, mock_bitwarden_client):
        """Test loading secrets from a single project into environment variables"""
        # Clear any existing test environment variables
        if "TEST_SECRET1" in os.environ:
            del os.environ["TEST_SECRET1"]
        if "TEST_SECRET2" in os.environ:
            del os.environ["TEST_SECRET2"]
            
        # Call the function with a specific project
        env_load(project_id="project1")
        
        # Verify Bitwarden client was initialized
        mock_initialize_client.assert_called_once()
        
        # Verify secrets synchronization was performed
        mock_bitwarden_client.secrets().sync.assert_called_once()
        
        # Verify environment variables were set
        assert os.environ["TEST_SECRET1"] == "test_value1"
        assert os.environ["TEST_SECRET2"] == "test_value2"
        
        # Test overriding
        os.environ["TEST_SECRET1"] = "existing_value"
        
        # Call with override=False, shouldn't change existing value
        env_load(project_id="project1", override=False)
        assert os.environ["TEST_SECRET1"] == "existing_value"
        
        # Call with override=True, should change existing value
        env_load(project_id="project1", override=True)
        assert os.environ["TEST_SECRET1"] == "test_value1"
    
    def test_env_load_all(self, mock_env_vars, mock_initialize_client, mock_bitwarden_client):
        """Test loading secrets from all projects into environment variables"""
        # Clear any existing test environment variables
        if "TEST_SECRET1" in os.environ:
            del os.environ["TEST_SECRET1"]
        if "TEST_SECRET2" in os.environ:
            del os.environ["TEST_SECRET2"]
        
        # Call the function to load all secrets
        env_load_all()
        
        # Verify Bitwarden client was initialized
        mock_initialize_client.assert_called_once()
        
        # Verify secrets synchronization was performed
        mock_bitwarden_client.secrets().sync.assert_called_once()
        
        # Verify secrets were fetched with list and get_by_ids
        mock_bitwarden_client.secrets().list.assert_called_once()
        mock_bitwarden_client.secrets().get_by_ids.assert_called_once()
        
        # Verify environment variables were set
        assert os.environ["TEST_SECRET1"] == "test_value1"
        assert os.environ["TEST_SECRET2"] == "test_value2"
        
        # Test overriding
        os.environ["TEST_SECRET1"] = "existing_value"
        
        # Call with override=False, shouldn't change existing value
        env_load_all(override=False)
        assert os.environ["TEST_SECRET1"] == "existing_value"
        
        # Call with override=True, should change existing value
        env_load_all(override=True)
        assert os.environ["TEST_SECRET1"] == "test_value1"
    
    def test_env_load_missing_organization_id(self, mock_env_vars):
        """Test env_load behavior when organization_id is missing"""
        # Remove organization ID from environment
        if "ORGANIZATION_ID" in os.environ:
            del os.environ["ORGANIZATION_ID"]
        
        # Should not raise exception, just return without doing anything
        env_load(project_id="project1")
        
        # Verify no environment variables were set
        assert "TEST_SECRET1" not in os.environ
        assert "TEST_SECRET2" not in os.environ
    
    def test_env_load_all_missing_organization_id(self, mock_env_vars):
        """Test env_load_all behavior when organization_id is missing"""
        # Remove organization ID from environment
        if "ORGANIZATION_ID" in os.environ:
            del os.environ["ORGANIZATION_ID"]
        
        # Should not raise exception, just return without doing anything
        env_load_all()
        
        # Verify no environment variables were set
        assert "TEST_SECRET1" not in os.environ
        assert "TEST_SECRET2" not in os.environ

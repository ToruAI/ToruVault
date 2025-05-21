import pytest
import os
from unittest.mock import patch, MagicMock

class TestVaultDecryption:
    """Test encryption/decryption with vault API functions"""
    
    def test_get_in_memory(self, mock_initialize_client, mock_env_vars):
        """Test retrieval with get() using in-memory mode"""
        from toru_vault import vault
        
        # Get secrets with in-memory storage (no keyring)
        secrets = vault.get("project1", use_keyring=False)
        
        # Verify we got the expected keys
        assert "TEST_SECRET1" in secrets
        assert "TEST_SECRET2" in secrets
        
        # Access secrets and verify values 
        assert secrets["TEST_SECRET1"] == "test_value1"
        assert secrets["TEST_SECRET2"] == "test_value2"
        

    
    @patch("keyring.get_password")
    @patch("keyring.set_password")
    def test_get_with_keyring(self, mock_set, mock_get, mock_initialize_client, mock_env_vars):
        """Test decryption with get() using keyring"""
        from toru_vault import vault
        from toru_vault.in_memory import _encrypt_secret, _decrypt_secret
        
        # Setup keyring mock to simulate stored encrypted values
        def mock_get_side_effect(service_name, key):
            if key == "TEST_SECRET1":
                return _encrypt_secret("test_value1")
            elif key == "TEST_SECRET2":
                return _encrypt_secret("test_value2")
            return None
            
        mock_get.side_effect = mock_get_side_effect
        
        # Get secrets using keyring
        secrets = vault.get("project1", use_keyring=True)
        
        # Access both secrets sequentially to test individual decryption
        value1 = secrets["TEST_SECRET1"]
        assert value1 == "test_value1"
        
        value2 = secrets["TEST_SECRET2"]
        assert value2 == "test_value2"
        
        # Verify we called get_password at least twice, plus once for org_id lookup
        # Expected number: 2 secret lookups + 1 for ORGANIZATION_ID
        assert mock_get.call_count >= 3
        
    # Tests for env_load and env_load_all removed as they already exist in TestEnvLoad
            
    def test_get_all(self, mock_initialize_client, mock_env_vars):
        """Test decryption with get_all()"""
        with patch("toru_vault.vault.get") as mock_get:
            from toru_vault import vault
            
            # Setup mock get to return test secrets
            mock_get.return_value = {
                "TEST_SECRET1": "test_value1",
                "TEST_SECRET2": "test_value2"
            }
            
            # Call get_all
            all_secrets = vault.get_all(use_keyring=False)
            
            # Verify get was called for the project
            mock_get.assert_called_once_with("project1", use_keyring=False)
            
            # Verify expected secrets are in result
            assert "TEST_SECRET1" in all_secrets
            assert all_secrets["TEST_SECRET1"] == "test_value1"
            assert "TEST_SECRET2" in all_secrets
            assert all_secrets["TEST_SECRET2"] == "test_value2"

"""
Tests for the vault package.
"""
import os
import time
from unittest.mock import patch, MagicMock

import toru_vault as vault

class TestVaultCore:
    """Test core functionality of the vault package."""
    
    def test_env_load(self, mock_bitwarden_client, mock_env_vars):
        """Test loading secrets into environment variables."""
        # Call the function
        vault.env_load(project_id="project1")
        
        # Verify secrets were loaded into environment variables
        assert os.environ.get("SECRET1") == "value1"
        assert os.environ.get("SECRET2") == "value2"
        assert os.environ.get("SECRET3") is None  # Not from project1
        assert os.environ.get("SECRET4") is None  # Not from project1
        
        # No need to verify client calls since we're mocking _load_secrets directly
    
    def test_env_load_override(self, mock_bitwarden_client, mock_env_vars):
        """Test loading secrets with override parameter."""
        # Set existing environment variable
        os.environ["SECRET1"] = "original_value"
        
        # Without override
        vault.env_load(project_id="project1", override=False)
        assert os.environ.get("SECRET1") == "original_value"  # Not overridden
        
        # With override
        vault.env_load(project_id="project1", override=True)
        assert os.environ.get("SECRET1") == "value1"  # Overridden
    
    @patch("os.environ", new_callable=dict)
    def test_env_load_all(self, mock_environ, mock_bitwarden_client, mock_env_vars):
        """Test loading secrets from all projects."""
        # Set up the initial environment
        mock_environ["ORGANIZATION_ID"] = "test-org-id"
        mock_environ["BWS_TOKEN"] = "test-token"
        
        # Create a response structure that matches what our real function expects
        project1 = MagicMock()
        project1.id = "project1"
        project1.name = "Test Project 1"
        
        project2 = MagicMock()
        project2.id = "project2"
        project2.name = "Test Project 2"
        
        # Create the data structure
        mock_data = MagicMock()
        mock_data.data = [project1, project2]
        
        mock_response = MagicMock()
        mock_response.data = mock_data
        
        # Set up the projects client to return our mock data
        mock_bitwarden_client.projects().list.return_value = mock_response
        
        # Allow the _get_from_keyring_or_env function to return our test organization ID
        with patch("vault.vault._get_from_keyring_or_env", return_value="test-org-id"):
            # Create a simple implementation of env_load that sets the right env vars
            def simple_env_load(project_id=None, override=False):
                if project_id == "project1":
                    mock_environ["SECRET1"] = "value1"
                    mock_environ["SECRET2"] = "value2"
                elif project_id == "project2":
                    mock_environ["SECRET3"] = "value3"
                    mock_environ["SECRET4"] = "value4"
            
            # Patch the env_load function that our test subject will call
            with patch("vault.vault.env_load", side_effect=simple_env_load):
                # Call the function under test
                vault.env_load_all()
                
                # Verify secrets are loaded correctly
                assert mock_environ.get("SECRET1") == "value1"
                assert mock_environ.get("SECRET2") == "value2"
                assert mock_environ.get("SECRET3") == "value3"
                assert mock_environ.get("SECRET4") == "value4"
                
                # Verify projects list was called
                mock_bitwarden_client.projects().list.assert_called_once()
    
    def test_get_with_keyring(self, mock_bitwarden_client, mock_keyring, mock_env_vars):
        """Test getting secrets with keyring enabled."""
        # Call the function
        secrets = vault.get(project_id="project1", use_keyring=True)
        
        # Verify secrets are accessible
        assert secrets["SECRET1"] == "value1"
        assert secrets["SECRET2"] == "value2"
        assert "SECRET3" not in secrets
        assert "SECRET4" not in secrets
        
        # Verify keys were stored in keyring
        assert mock_keyring.get_password("vault_test-org-id", "SECRET1") == "value1"
        assert mock_keyring.get_password("vault_test-org-id", "SECRET2") == "value2"
    
    def test_get_without_keyring(self, mock_bitwarden_client, mock_env_vars):
        """Test getting secrets with keyring disabled."""
        with patch("vault.vault._KEYRING_AVAILABLE", False):
            # Call the function
            secrets = vault.get(project_id="project1")
            
            # Verify secrets are accessible
            assert secrets["SECRET1"] == "value1"
            assert secrets["SECRET2"] == "value2"
            assert "SECRET3" not in secrets
            assert "SECRET4" not in secrets
    
    def test_get_refresh(self, mock_bitwarden_client, mock_env_vars):
        """Test refreshing the cache."""
        # First call to populate cache
        secrets1 = vault.get(project_id="project1")
        assert secrets1["SECRET1"] == "value1"
        
        # Create a patched version of _load_secrets that returns updated values
        def updated_load_secrets(project_id=None):
            if project_id == "project1":
                return {"SECRET1": "updated_value1", "SECRET2": "updated_value2"}
            return {}
            
        # Apply the patch for the second call
        with patch("vault.vault._load_secrets", side_effect=updated_load_secrets):
            # Call with refresh should get new values
            secrets3 = vault.get(project_id="project1", refresh=True)
            assert secrets3["SECRET1"] == "updated_value1"  # Updated value
    
    def test_get_use_keyring_parameter(self, mock_bitwarden_client, mock_keyring, mock_env_vars):
        """Test the use_keyring parameter."""
        # With keyring
        secrets = vault.get(project_id="project1", use_keyring=True)
        assert mock_keyring.get_password("vault_test-org-id", "SECRET1") == "value1"
        
        # Without keyring (should use in-memory encryption)
        secrets = vault.get(project_id="project1", use_keyring=False)
        # We can't directly test the in-memory encryption, but we can verify
        # the secret is still accessible
        assert secrets["SECRET1"] == "value1"


class TestVaultEncryption:
    """Test encryption and decryption functionality."""
    
    def test_encrypt_decrypt_secrets(self):
        """Test encryption and decryption of secrets."""
        # Access private functions for testing
        encrypt_secrets = vault.vault._encrypt_secrets
        decrypt_secrets = vault.vault._decrypt_secrets
        
        # Test data
        test_secrets = {"key1": "value1", "key2": "value2"}
        
        # Encrypt
        encrypted = encrypt_secrets(test_secrets)
        assert encrypted is not None
        assert ":" in encrypted  # Format is "salt:encrypted_data"
        
        # Decrypt
        decrypted = decrypt_secrets(encrypted)
        assert decrypted is not None
        assert decrypted["key1"] == "value1"
        assert decrypted["key2"] == "value2"
        
    def test_cache_expiration(self, mock_bitwarden_client, mock_env_vars):
        """Test cache expiration."""
        # Set up call counter
        load_secrets_call_count = 0
        
        # Create a patched version of _load_secrets that counts calls
        def counting_load_secrets(project_id=None):
            nonlocal load_secrets_call_count
            load_secrets_call_count += 1
            if project_id == "project1":
                return {"SECRET1": "value1", "SECRET2": "value2"}
            return {}
        
        # Patch the cache timeout to a small value for testing
        with patch("vault.vault._SECRET_CACHE_TIMEOUT", 0.1):
            with patch("vault.vault._load_secrets", side_effect=counting_load_secrets):
                # First call to populate cache
                vault.get(project_id="project1")
                assert load_secrets_call_count == 1
                
                # Wait for cache to expire
                time.sleep(0.2)
                
                # Next call should refresh from source
                vault.get(project_id="project1")
                assert load_secrets_call_count == 2  # Should be called again after expiration

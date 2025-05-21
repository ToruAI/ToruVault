import pytest
import os
from unittest.mock import patch, MagicMock

from toru_vault.in_memory import (
    _encrypt_secret,
    _decrypt_secret,
    _encrypt_secrets,
    _decrypt_secrets,
    create_secrets_dict
)

class TestEncryption:
    """Tests for encryption/decryption implementation"""
    
    def test_single_secret_encryption_decryption(self):
        """Test individual secret encryption and decryption"""
        secret_value = "super-sensitive-value"
        
        # Encrypt the secret
        encrypted = _encrypt_secret(secret_value)
        assert encrypted is not None
        assert ":" in encrypted  # Should contain salt and encrypted data
        
        # Should not be the same as original
        assert encrypted != secret_value
        
        # Decrypt the secret
        decrypted = _decrypt_secret(encrypted)
        assert decrypted == secret_value

    def test_multiple_secrets_encryption_decryption(self):
        """Test encryption and decryption of multiple secrets"""
        secrets = {
            "API_KEY": "secret-api-key",
            "PASSWORD": "secret-password",
            "TOKEN": "secret-token"
        }
        
        # Encrypt dictionary of secrets
        encrypted_secrets = _encrypt_secrets(secrets)
        assert encrypted_secrets is not None
        
        # Ensure each value is encrypted
        for key, value in encrypted_secrets.items():
            assert ":" in value  # Should contain salt and encrypted data
            assert value != secrets[key]  # Should not match original value
        
        # Decrypt all secrets
        decrypted_secrets = _decrypt_secrets(encrypted_secrets)
        assert decrypted_secrets is not None
        
        # Ensure decrypted values match original
        for key, value in secrets.items():
            assert decrypted_secrets[key] == value

    def test_decryption_in_memory(self):
        """Test decryption in non-keyring mode"""
        # Create test secrets
        test_secrets = {
            "API_KEY": "test-api-key",
            "DB_PASSWORD": "test-db-password" 
        }
        
        # Create secret keys set
        secret_keys = set(test_secrets.keys())
        
        # Create LazySecretsDict with in-memory decryption
        secrets_dict = create_secrets_dict(
            secret_keys,
            "test_org_id",
            "test_project_id",
            test_secrets,  # Direct use of secrets
            False         # No keyring
        )
        
        # Access each secret and verify correct values
        for key, expected_value in test_secrets.items():
            assert secrets_dict[key] == expected_value

    @patch("keyring.get_password")
    @patch("keyring.set_password")
    def test_decryption_with_keyring(self, mock_set_password, mock_get_password):
        """Test decryption with keyring enabled"""
        # Create test secrets
        test_secrets = {
            "API_KEY": "test-api-key",
            "DB_PASSWORD": "test-db-password" 
        }
        
        # Mock keyring to return encrypted values
        def mock_get_side_effect(service_name, key):
            # Return encrypted version of the test secret
            if key in test_secrets:
                return _encrypt_secret(test_secrets[key])
            return None
            
        mock_get_password.side_effect = mock_get_side_effect
        
        # Create secret keys set
        secret_keys = set(test_secrets.keys())
        organization_id = "test_org_id"
        project_id = "test_project_id"
        
        # Create LazySecretsDict with keyring decryption
        secrets_dict = create_secrets_dict(
            secret_keys,
            organization_id,
            project_id,
            test_secrets,  # Used to initialize keyring
            True           # Use keyring
        )
        
        # Verify secrets were encrypted and stored in keyring
        assert mock_set_password.call_count == len(test_secrets)
        
        # Access each secret and verify decryption
        for key, expected_value in test_secrets.items():
            # Value should be decrypted from keyring when accessed
            assert secrets_dict[key] == expected_value
            

    


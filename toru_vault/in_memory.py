#!/usr/bin/env python3
import os
import logging
import tempfile
import stat
import secrets as pysecrets
from typing import Dict, Optional, Tuple, Set
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from .lazy_dict import LazySecretsDict

# Try importing keyring - it might not be available in container environments
try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

# Setup minimal logging
logger = logging.getLogger(__name__)

# Constants for keyring storage
_KEYRING_SERVICE_NAME = "bitwarden_vault"
_KEYRING_BWS_TOKEN_KEY = "bws_token"
_KEYRING_ORG_ID_KEY = "organization_id"

# No caching - encryption and decryption only happens JIT

def _generate_encryption_key(salt: bytes = None) -> Tuple[bytes, bytes]:
    """
    Generate an encryption key for securing the cache
    
    Args:
        salt (bytes, optional): Salt for key derivation
        
    Returns:
        Tuple[bytes, bytes]: Key and salt
    """
    if salt is None:
        salt = os.urandom(16)
    
    # Generate a key from the machine-specific information and random salt
    machine_id = _get_machine_id()
    password = machine_id.encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key, salt

def _get_machine_id() -> str:
    """Get a unique identifier for the current machine"""
    machine_id = ""
    # MacOS and Linux
    if os.path.exists('/etc/machine-id'):
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    elif os.path.exists('/var/lib/dbus/machine-id'):
        with open('/var/lib/dbus/machine-id', 'r') as f:
            machine_id = f.read().strip()
    elif os.name == 'nt':  # Windows
        import subprocess
        try:
            result = subprocess.run(['wmic', 'csproduct', 'get', 'UUID'], capture_output=True, text=True)
            if result.returncode == 0:
                machine_id = result.stdout.strip().split('\n')[-1].strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    if not machine_id:
        # Some systems truncate nodename to 8 characters or to the leading component;
        # a better way to get the hostname is socket.gethostname()
        import socket
        hostname = socket.gethostname()
        
        # Create a persistent random ID
        id_file = os.path.join(tempfile.gettempdir(), '.vault_machine_id')
        if os.path.exists(id_file):
            try:
                with open(id_file, 'r') as f:
                    random_id = f.read().strip()
            except Exception:
                random_id = pysecrets.token_hex(16)
        else:
            random_id = pysecrets.token_hex(16)
            try:
                # Try to save it with restricted permissions
                with open(id_file, 'w') as f:
                    f.write(random_id)
                os.chmod(id_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600 permissions
            except Exception:
                pass
                
        machine_id = f"{hostname}-{random_id}"
    
    return machine_id

def _encrypt_secret(secret_value: str) -> Optional[str]:
    """
    Encrypt a single secret value
    
    Args:
        secret_value (str): Secret value to encrypt
        
    Returns:
        Optional[str]: Encrypted data or None if encryption fails
    """
    try:
        key, salt = _generate_encryption_key()
        if not key:
            return None
            
        # Encrypt the secret value
        f = Fernet(key)
        encrypted_data = f.encrypt(secret_value.encode())
        
        # Store along with the salt
        return base64.urlsafe_b64encode(salt).decode() + ":" + encrypted_data.decode()
    except Exception as e:
        logger.warning(f"Failed to encrypt secret: {e}")
        return None

def _encrypt_secrets(secrets_dict: Dict[str, str]) -> Optional[Dict[str, str]]:
    """
    Encrypt secrets dictionary with per-secret encryption
    
    Args:
        secrets_dict (Dict[str, str]): Dictionary of secrets
        
    Returns:
        Optional[Dict[str, str]]: Dictionary of encrypted secrets or None if encryption fails
    """
    try:
        encrypted_secrets = {}
        for key, value in secrets_dict.items():
            encrypted_value = _encrypt_secret(value)
            if encrypted_value:
                encrypted_secrets[key] = encrypted_value
            else:
                logger.warning(f"Failed to encrypt secret '{key}'")
                
        return encrypted_secrets if encrypted_secrets else None
    except Exception as e:
        logger.warning(f"Failed to encrypt secrets: {e}")
        return None

def _decrypt_secret(encrypted_value: str) -> Optional[str]:
    """
    Decrypt a single secret value
    
    Args:
        encrypted_value (str): Encrypted secret value
        
    Returns:
        Optional[str]: Decrypted secret value or None if decryption fails
    """
    try:
        # Split salt and encrypted data
        salt_b64, encrypted = encrypted_value.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_b64)
        
        # Regenerate the key with the same salt
        key, _ = _generate_encryption_key(salt)
        if not key:
            return None
            
        # Decrypt the data
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted.encode())
        
        return decrypted_data.decode()
    except Exception as e:
        logger.warning(f"Failed to decrypt secret: {e}")
        return None

def _decrypt_secrets(encrypted_dict: Dict[str, str]) -> Optional[Dict[str, str]]:
    """
    Decrypt a dictionary of encrypted secrets
    
    Args:
        encrypted_dict (Dict[str, str]): Dictionary of encrypted secrets
        
    Returns:
        Optional[Dict[str, str]]: Decrypted secrets dictionary or None if decryption fails
    """
    try:
        decrypted_secrets = {}
        for key, encrypted_value in encrypted_dict.items():
            decrypted_value = _decrypt_secret(encrypted_value)
            if decrypted_value is not None:
                decrypted_secrets[key] = decrypted_value
                
        return decrypted_secrets if decrypted_secrets else None
    except Exception as e:
        logger.warning(f"Failed to decrypt secrets dictionary: {e}")
        return None

def create_secrets_dict(secrets_keys: Set[str], organization_id: str, project_id: str, 
                       all_secrets: Dict[str, str], use_keyring: bool) -> LazySecretsDict:
    """
    Create a LazySecretsDict with appropriate getter, setter, and deleter functions
    
    Args:
        secrets_keys: Set of keys available in the dictionary
        organization_id: Organization ID
        project_id: Project ID
        all_secrets: Dictionary of all preloaded secrets
        refresh: Whether to force refresh
        use_keyring: Whether to use keyring
        
    Returns:
        LazySecretsDict: Dictionary of secrets with lazy loading
    """
    # Build the service name for keyring storage
    service_name = f"vault_{organization_id or 'default'}"
    
    # When keyring is unavailable or not requested (likely in container)
    keyring_usable = _KEYRING_AVAILABLE and use_keyring
    
    if keyring_usable:
        # Store encrypted secrets in keyring if available and requested
        for key, value in all_secrets.items():
            encrypted_value = _encrypt_secret(value)
            if encrypted_value:
                keyring.set_password(service_name, key, encrypted_value)
        
        # Create getter function for keyring mode that decrypts JIT
        def _keyring_getter(key):
            encrypted_value = keyring.get_password(service_name, key)
            if encrypted_value:
                return _decrypt_secret(encrypted_value)
            return None
            
        # Create setter function for keyring mode
        def _keyring_setter(key, value):
            encrypted_value = _encrypt_secret(value)
            if encrypted_value:
                keyring.set_password(service_name, key, encrypted_value)
            
        # Create deleter function for keyring mode
        def _keyring_deleter(key):
            keyring.delete_password(service_name, key)
        
        # Create the lazy dictionary with keyring functions
        return LazySecretsDict(secrets_keys, _keyring_getter, _keyring_setter, _keyring_deleter)
    else:
        # Container or non-keyring mode implementation
        # No caching - always work with encrypted provided secrets
        
        # Function to load secrets from Bitwarden - defined as forward reference
        # This will be passed in by the vault.py module when calling this function
        _load_secrets = None
            
        # Create getter function for container mode with JIT decryption
        def _container_getter(key):
            nonlocal _load_secrets
            
            # If value exists in memory (either plaintext or encrypted)
            if all_secrets and key in all_secrets:
                value = all_secrets[key]
                
                # Check if the value is encrypted (has the salt:encrypted format)
                if isinstance(value, str) and ":" in value:
                    # Decrypt the value but don't store decrypted version
                    decrypted = _decrypt_secret(value)
                    if decrypted is not None:
                        return decrypted
                    # If decryption fails, return the original value (might be plaintext)
                    return value
                # Return plaintext value if not encrypted
                return value
            
            # If all else fails, load from API
            if _load_secrets:
                fresh_secrets = _load_secrets(project_id)
                if key in fresh_secrets:
                    # Don't save in container_secrets to avoid storing plaintext
                    # Just return the value
                    return fresh_secrets[key]
                
            return None
        
        # Create the lazy dictionary with container getter
        return LazySecretsDict(secrets_keys, _container_getter)

# No caching functionality

def load_secrets_memory(client, organization_id, project_id=None):
    """
    Load secrets from Bitwarden specifically for in-memory usage
    
    Args:
        client: Initialized Bitwarden client
        organization_id: Organization ID
        project_id: Optional project ID to filter secrets
        
    Returns:
        dict: Dictionary of secrets with their names as keys (encrypted in memory)
    """
    try:
        client.secrets().sync(organization_id, None)
        
        secrets = {}
        encrypted_secrets = {}
        
        # Retrieve all secrets details (no values)
        all_secrets = client.secrets().list(organization_id)
        
        if not hasattr(all_secrets, 'data') or not hasattr(all_secrets.data, 'data'):
            return {}
        
        secret_ids = []
        for secret in all_secrets.data.data:
            secret_ids.append(secret.id)
        
        if secret_ids:
            # Fetch value for each secret
            secrets_detailed = client.secrets().get_by_ids(secret_ids)
            
            if not hasattr(secrets_detailed, 'data') or not hasattr(secrets_detailed.data, 'data'):
                return {}
            
            # Process each secret
            for secret in secrets_detailed.data.data:
                # Extract the project ID
                secret_project_id = getattr(secret, 'project_id', None)
                
                # Check if this secret belongs to the specified project
                if project_id and secret_project_id is not None and project_id != str(secret_project_id):
                    continue
                
                # Add the secret to our dictionary (plaintext)
                secrets[secret.key] = secret.value
                
                # Also encrypt the value for in-memory storage
                encrypted_value = _encrypt_secret(secret.value)
                if encrypted_value:
                    encrypted_secrets[secret.key] = encrypted_value
                else:
                    # Fallback if encryption fails
                    encrypted_secrets[secret.key] = secret.value
        
        # Return the encrypted secrets for secure in-memory storage
        # Values will be decrypted JIT when accessed
        return encrypted_secrets
    except Exception as e:
        logger.error(f"Error loading secrets for memory storage: {e}")
        return {}

def decrypt_cached_secrets(organization_id: str, project_id: str):
    """
    Function retained for API compatibility but always returns None as caching is disabled
    
    Args:
        organization_id: Organization ID
        project_id: Project ID

    Returns:
        None: Always returns None as caching is disabled
    """
    return None

def update_secrets_cache(organization_id: str, project_id: str, secrets: Dict[str, str]) -> None:
    """
    Function retained for API compatibility but does nothing as caching is disabled
    
    Args:
        organization_id: Organization ID
        project_id: Project ID
        secrets: Dictionary of secrets
    """
    # No-op since caching is disabled
    return

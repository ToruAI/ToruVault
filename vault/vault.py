#!/usr/bin/env python3
import os
import logging
import time
import json
import tempfile
import stat
import atexit
import secrets as pysecrets
from typing import Dict, Optional, Tuple
from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Setup minimal logging
logger = logging.getLogger(__name__)

# Secure cache configuration
_SECRET_CACHE_TIMEOUT = 300  # 5 minutes
_secrets_cache: Dict[str, Tuple[float, Dict[str, str]]] = {}

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
    # Try platform-specific methods to get a machine ID
    machine_id = ""
    
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
    
    # Fallback if we couldn't get a machine ID
    if not machine_id:
        # Use a combination of hostname and a persisted random value
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

def _encrypt_secrets(secrets_dict: Dict[str, str]) -> Optional[str]:
    """
    Encrypt secrets dictionary
    
    Args:
        secrets_dict (Dict[str, str]): Dictionary of secrets
        
    Returns:
        Optional[str]: Encrypted data or None if encryption fails
    """
    try:
        key, salt = _generate_encryption_key()
        if not key:
            return None
            
        # Encrypt the serialized secrets
        f = Fernet(key)
        encrypted_data = f.encrypt(json.dumps(secrets_dict).encode())
        
        # Store along with the salt
        return base64.urlsafe_b64encode(salt).decode() + ":" + encrypted_data.decode()
    except Exception as e:
        logger.warning(f"Failed to encrypt secrets: {e}")
        return None

def _decrypt_secrets(encrypted_data: str) -> Optional[Dict[str, str]]:
    """
    Decrypt secrets
    
    Args:
        encrypted_data (str): Encrypted data
        
    Returns:
        Optional[Dict[str, str]]: Decrypted secrets dictionary or None if decryption fails
    """
    try:
        # Split salt and encrypted data
        salt_b64, encrypted = encrypted_data.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_b64)
        
        # Regenerate the key with the same salt
        key, _ = _generate_encryption_key(salt)
        if not key:
            return None
            
        # Decrypt the data
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted.encode())
        
        return json.loads(decrypted_data.decode())
    except Exception as e:
        logger.warning(f"Failed to decrypt secrets: {e}")
        return None

def _secure_state_file(state_path: str) -> None:
    """
    Ensure the state file has secure permissions
    
    Args:
        state_path (str): Path to the state file
    """
    try:
        if os.path.exists(state_path):
            if os.name == 'posix':  # Linux/Mac
                os.chmod(state_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 permissions
            elif os.name == 'nt':  # Windows
                import subprocess
                subprocess.run(['icacls', state_path, '/inheritance:r', '/grant:r', f'{os.getlogin()}:(F)'], 
                               capture_output=True)
    except Exception as e:
        logger.warning(f"Could not set secure permissions on state file: {e}")

def _clear_cache() -> None:
    """Clear the secrets cache on exit"""
    global _secrets_cache
    _secrets_cache = {}
    
# Register the cache clearing function to run on exit
atexit.register(_clear_cache)

def _initialize_client():
    """
    Initialize the Bitwarden client
    """
    # Get environment variables with defaults
    api_url = os.getenv("API_URL", "https://api.bitwarden.com")
    identity_url = os.getenv("IDENTITY_URL", "https://identity.bitwarden.com")
    bws_token = os.getenv("BWS_TOKEN")
    state_path = os.getenv("STATE_FILE")
    
    # Validate required environment variables
    if not bws_token:
        raise ValueError("BWS_TOKEN environment variable is required")
    if not state_path:
        raise ValueError("STATE_FILE environment variable is required")
        
    # Ensure state file directory exists
    state_dir = os.path.dirname(state_path)
    if state_dir and not os.path.exists(state_dir):
        try:
            os.makedirs(state_dir, exist_ok=True)
            # Secure the directory if possible
            if os.name == 'posix':  # Linux/Mac
                os.chmod(state_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)  # 0700 permissions
        except Exception as e:
            logger.warning(f"Could not create state directory with secure permissions: {e}")
    
    # Secure the state file
    _secure_state_file(state_path)
    
    # Create and initialize the client
    client = BitwardenClient(
        client_settings_from_dict({
            "apiUrl": api_url,
            "deviceType": DeviceType.SDK,
            "identityUrl": identity_url,
            "userAgent": "Python",
        })
    )
    
    # Authenticate with the Secrets Manager Access Token
    client.auth().login_access_token(bws_token, state_path)
    
    return client

def _load_secrets(organization_id=None, project_id=None):
    """
    Load secrets from Bitwarden
    
    Args:
        organization_id (str): Organization ID
        project_id (str): Project ID to filter secrets
    
    Returns:
        dict: Dictionary of secrets with their names as keys
    """
    global _secrets_cache
    
    # Validate organization ID
    if not organization_id:
        organization_id = os.getenv("ORGANIZATION_ID")
        if not organization_id:
            raise ValueError("ORGANIZATION_ID environment variable is required")
    
    # Check if we have valid cached secrets for this combination
    cache_key = f"{organization_id}:{project_id or ''}"
    current_time = time.time()
    
    if cache_key in _secrets_cache:
        timestamp, encrypted_secrets = _secrets_cache[cache_key]
        
        # If cache hasn't expired
        if current_time - timestamp < _SECRET_CACHE_TIMEOUT:
            # If we have encryption, try to decrypt
            if encrypted_secrets:
                decrypted_secrets = _decrypt_secrets(encrypted_secrets)
                if decrypted_secrets:
                    return decrypted_secrets
            # Otherwise return the unencrypted data (backward compatibility)
            elif isinstance(encrypted_secrets, dict):
                return encrypted_secrets.copy()
    
    try:
        client = _initialize_client()
        
        # Sync secrets to ensure we have the latest
        client.secrets().sync(organization_id, None)
        
        # Initialize empty secrets dictionary
        secrets = {}
        
        # Retrieve all secrets
        all_secrets = client.secrets().list(organization_id)
        
        # Validate response format
        if not hasattr(all_secrets, 'data') or not hasattr(all_secrets.data, 'data'):
            return {}
        
        # We need to collect all secret IDs first
        secret_ids = []
        for secret in all_secrets.data.data:
            secret_ids.append(secret.id)
        
        # If we have secret IDs, fetch their values
        if secret_ids:
            # Get detailed information for all secrets by their IDs
            secrets_detailed = client.secrets().get_by_ids(secret_ids)
            
            # Validate response format
            if not hasattr(secrets_detailed, 'data') or not hasattr(secrets_detailed.data, 'data'):
                return {}
            
            # Process each secret
            for secret in secrets_detailed.data.data:
                # Extract the project ID
                secret_project_id = getattr(secret, 'project_id', None)
                
                # Check if this secret belongs to the specified project
                if project_id and secret_project_id is not None and project_id != str(secret_project_id):
                    continue
                
                # Add the secret to our dictionary
                secrets[secret.key] = secret.value
        
        # Update the cache with encryption
        encrypted_data = _encrypt_secrets(secrets)
        if encrypted_data:
            _secrets_cache[cache_key] = (current_time, encrypted_data)
        else:
            _secrets_cache[cache_key] = (current_time, secrets.copy())
        
        return secrets
    except Exception as e:
        logger.error(f"Error loading secrets: {e}")
        raise

def env_load(organization_id=None, project_id=None, override=False):
    """
    Load all secrets related to the project into environmental variables.
    
    Args:
        organization_id (str, optional): Organization ID
        project_id (str, optional): Project ID to filter secrets
        override (bool, optional): Whether to override existing environment variables
    """
    secrets = _load_secrets(organization_id, project_id)
    
    # Add each secret to environment variables
    for key, value in secrets.items():
        # Only set if the environment variable doesn't exist or override is True
        if override or key not in os.environ:
            os.environ[key] = value

def get(organization_id=None, project_id=None, refresh=False):
    """
    Return a dictionary of all project secrets
    
    Args:
        organization_id (str, optional): Organization ID
        project_id (str, optional): Project ID to filter secrets
        refresh (bool, optional): Force refresh the secrets cache
        
    Returns:
        dict: Dictionary of secrets with their names as keys
    """
    # Check if we need to force a refresh
    if refresh:
        return _load_secrets(organization_id, project_id)
    
    # Otherwise try to use cached values first
    cache_key = f"{organization_id}:{project_id or ''}"
    current_time = time.time()
    
    if cache_key in _secrets_cache:
        timestamp, encrypted_secrets = _secrets_cache[cache_key]
        
        # If cache hasn't expired
        if current_time - timestamp < _SECRET_CACHE_TIMEOUT:
            # If we have encryption, try to decrypt
            if encrypted_secrets:
                decrypted_secrets = _decrypt_secrets(encrypted_secrets)
                if decrypted_secrets:
                    return decrypted_secrets
            # Otherwise return the unencrypted data (backward compatibility)
            elif isinstance(encrypted_secrets, dict):
                return encrypted_secrets.copy()
    
    # If we couldn't get from cache, load fresh
    return _load_secrets(organization_id, project_id)

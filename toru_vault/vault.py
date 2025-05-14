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
_KEYRING_STATE_FILE_KEY = "state_file"

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

def _get_from_keyring_or_env(key, env_var):
    """
    Get a value from keyring or environment variable
    
    Args:
        key (str): Key in keyring
        env_var (str): Environment variable name
    
    Returns:
        str: Value from keyring or environment variable
    """
    value = None
    
    # Try keyring first if available
    if _KEYRING_AVAILABLE:
        try:
            value = keyring.get_password(_KEYRING_SERVICE_NAME, key)
        except Exception as e:
            logger.warning(f"Failed to get {key} from keyring: {e}")
    
    # Fall back to environment variable
    if not value:
        value = os.getenv(env_var)
    
    return value

def set_to_keyring(key, value):
    """
    Set a value to keyring
    
    Args:
        key (str): Key in keyring
        value (str): Value to store
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not _KEYRING_AVAILABLE:
        return False
    
    try:
        keyring.set_password(_KEYRING_SERVICE_NAME, key, value)
        return True
    except Exception as e:
        logger.warning(f"Failed to set {key} to keyring: {e}")
        return False

def _initialize_client():
    """
    Initialize the Bitwarden client
    """
    # Get environment variables with defaults
    api_url = os.getenv("API_URL", "https://api.bitwarden.com")
    identity_url = os.getenv("IDENTITY_URL", "https://identity.bitwarden.com")
    
    # Get BWS_TOKEN from keyring or environment variable
    bws_token = _get_from_keyring_or_env(_KEYRING_BWS_TOKEN_KEY, "BWS_TOKEN")
    
    # Get STATE_FILE from keyring or environment variable
    state_path = _get_from_keyring_or_env(_KEYRING_STATE_FILE_KEY, "STATE_FILE")
    
    # Validate required environment variables
    if not bws_token:
        raise ValueError("BWS_TOKEN not found in keyring or environment variable")
    if not state_path:
        raise ValueError("STATE_FILE not found in keyring or environment variable")
        
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

def _load_secrets(project_id=None):
    """
    Load secrets from Bitwarden
    
    Args:
        project_id (str): Project ID to filter secrets
    
    Returns:
        dict: Dictionary of secrets with their names as keys
    """
    # Initialize client with credentials from environment or keyring
    try:
        client = _initialize_client()
    except Exception as e:
        logger.error(f"Failed to initialize Bitwarden client: {e}")
        return {}
    
    # Get ORGANIZATION_ID from keyring or environment variable
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if not organization_id:
        logger.error("ORGANIZATION_ID not found in keyring or environment variable")
        return {}
    
    # Get secrets from BitWarden
    try:
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
            _secrets_cache[f"{organization_id}:{project_id or ''}"] = (time.time(), encrypted_data)
        else:
            _secrets_cache[f"{organization_id}:{project_id or ''}"] = (time.time(), secrets.copy())
        
        return secrets
    except Exception as e:
        logger.error(f"Error loading secrets: {e}")
        raise

def env_load(project_id=None, override=False):
    """
    Load all secrets related to the project into environmental variables.
    
    Args:
        project_id (str, optional): Project ID to filter secrets
        override (bool, optional): Whether to override existing environment variables
    """
    # Get all secrets from BWS
    secrets = _load_secrets(project_id)
    
    # Set environment variables
    for key, value in secrets.items():
        if override or key not in os.environ:
            os.environ[key] = value

def env_load_all(override=False):
    """
    Load all secrets from all projects that user has access to into environment variables
    
    Args:
        override (bool, optional): Whether to override existing environment variables
    """
    # Get ORGANIZATION_ID from keyring or environment variable
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    
    # Initialize Bitwarden client
    try:
        client = _initialize_client()
    except Exception as e:
        logger.error(f"Failed to initialize Bitwarden client: {e}")
        return
    
    try:
        # Sync to ensure we have the latest data
        client.secrets().sync(organization_id, None)
        
        # Get all projects
        projects_response = client.projects().list(organization_id)
        
        # Validate response format
        if not hasattr(projects_response, 'data') or not hasattr(projects_response.data, 'data'):
            logger.warning(f"No projects found in organization {organization_id}")
            return
        
        # Process each project
        for project in projects_response.data.data:
            if hasattr(project, 'id'):
                project_id = str(project.id)
                
                # Load environment variables for this project
                try:
                    # Get the secrets for this project and set them as environment variables
                    env_load(project_id=project_id, override=override)
                    logger.info(f"Loaded secrets from project: {getattr(project, 'name', project_id)}")
                except Exception as e:
                    logger.warning(f"Failed to load secrets from project {project_id}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to load all secrets into environment variables: {e}")

def get(project_id=None, refresh=False, use_keyring=True):
    """
    Return a dictionary of all project secrets
    
    Args:
        project_id (str, optional): Project ID to filter secrets
        refresh (bool, optional): Force refresh the secrets cache
        use_keyring (bool, optional): Whether to use system keyring (True) or in-memory encryption (False)
        
    Returns:
        dict: Dictionary of secrets with their names as keys, using lazy loading
    """
    # Get ORGANIZATION_ID from keyring or environment variable
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    
    # Build the service name for keyring storage
    service_name = f"vault_{organization_id or 'default'}"
    
    # Function to either fetch from keyring or decrypt from cache based on container flag
    def _load_decrypted_secrets():
        # Check if we need to force a refresh
        if refresh:
            return _load_secrets(project_id)
        
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
        return _load_secrets(project_id)
    
    # Get all secrets and their keys
    all_secrets = _load_decrypted_secrets()
    secret_keys = set(all_secrets.keys())
    
    # Store secrets in keyring if available and requested
    keyring_usable = _KEYRING_AVAILABLE and use_keyring
    if keyring_usable:
        for key, value in all_secrets.items():
            keyring.set_password(service_name, key, value)
    
    # When keyring is unavailable or not requested (likely in container)
    if not keyring_usable:
        # Create a dictionary of cached secrets for container mode
        container_secrets = {}
        encrypted_data = None
        cache_key = f"{organization_id}:{project_id or ''}"
        
        # If we have a cached encrypted version, use that
        if cache_key in _secrets_cache:
            _, encrypted_data = _secrets_cache[cache_key]
            
        # Create getter function for container mode
        def _container_getter(key):
            if key in container_secrets:
                return container_secrets[key]
            
            # If not in memory cache, check if we have pre-loaded decrypted secrets
            if all_secrets and key in all_secrets:
                container_secrets[key] = all_secrets[key]
                return container_secrets[key]
                
            # Otherwise, try to decrypt from cache
            if encrypted_data and not isinstance(encrypted_data, dict):
                decrypted = _decrypt_secrets(encrypted_data)
                if decrypted and key in decrypted:
                    container_secrets[key] = decrypted[key]
                    return container_secrets[key]
                
            # If all else fails, load from API
            fresh_secrets = _load_secrets(project_id)
            if key in fresh_secrets:
                container_secrets[key] = fresh_secrets[key]
                return container_secrets[key]
                
            return None
        
        # Create the lazy dictionary with container getter
        return LazySecretsDict(secret_keys, _container_getter)
    else:
        # Create getter function for keyring mode
        def _keyring_getter(key):
            return keyring.get_password(service_name, key)
            
        # Create setter function for keyring mode
        def _keyring_setter(key, value):
            keyring.set_password(service_name, key, value)
            
        # Create deleter function for keyring mode
        def _keyring_deleter(key):
            keyring.delete_password(service_name, key)
        
        # Create the lazy dictionary with keyring getter/setter/deleter
        return LazySecretsDict(secret_keys, _keyring_getter, _keyring_setter, _keyring_deleter)

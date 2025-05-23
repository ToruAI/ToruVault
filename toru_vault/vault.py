#!/usr/bin/env python3
import os
import logging
import stat
from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict

from .in_memory import (
    _KEYRING_AVAILABLE,
    create_secrets_dict
)
from .in_env import (
    set_env_vars,
    load_secrets_env
)

logger = logging.getLogger(__name__)

# Constants for keyring storage
_KEYRING_SERVICE_NAME = "bitwarden_vault"
_KEYRING_BWS_TOKEN_KEY = "bws_token"
_KEYRING_ORG_ID_KEY = "organization_id"
_KEYRING_STATE_FILE_KEY = "state_file"
_KEYRING_PROJECT_ID_KEY = "project_id"

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
            import keyring
            value = keyring.get_password(_KEYRING_SERVICE_NAME, key)
        except Exception as e:
            logger.warning(f"Failed to get {key} from keyring: {e}")
    
    if not value:
        value = os.getenv(env_var)
    
    return value



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
                # /inheritance:r - Removes all inherited ACEs (Access Control Entries).
                # /grant:r - Grants specified user rights, replacing any previous explicit ACEs for that user.
                # <os.getlogin()>:(F) - Grants the current user (F)ull control.
                result = subprocess.run(['icacls', state_path, '/inheritance:r', '/grant:r', f'{os.getlogin()}:(F)'], 
                               capture_output=True)
                if result.returncode != 0:
                    raise Exception(f"Could not set secure permissions on state file: {result.stderr.decode()}")
        
    except Exception as e:
        logger.warning(f"Could not set secure permissions on state file: {e}")

def _initialize_client():
    """
    Initialize the Bitwarden client
    """
    api_url = os.getenv("API_URL", "https://api.bitwarden.com")
    identity_url = os.getenv("IDENTITY_URL", "https://identity.bitwarden.com")
    
    bws_token = _get_from_keyring_or_env(_KEYRING_BWS_TOKEN_KEY, "BWS_TOKEN")
    state_path = _get_from_keyring_or_env(_KEYRING_STATE_FILE_KEY, "STATE_FILE")
    org_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    
    if not bws_token:
        raise ValueError("BWS_TOKEN not found in keyring or environment variable")
    if not state_path:
        raise ValueError("STATE_FILE not found in keyring or environment variable")
    if not org_id:
        raise ValueError("ORGANIZATION_ID not found in keyring or environment variable")
        
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
    
    _secure_state_file(state_path)
    
    client = BitwardenClient(
        client_settings_from_dict({
            "apiUrl": api_url,
            "deviceType": DeviceType.SDK,
            "identityUrl": identity_url,
            "userAgent": "Python",
        })
    )
    
    client.auth().login_access_token(bws_token, state_path)
    
    del bws_token
    del org_id
    
    return client

def env_load(project_id=None, override=False):
    """
    Load all secrets related to the project into environmental variables.
    
    Args:
        project_id (str, optional): Project ID to filter secrets. If None, will try to get from keyring or PROJECT_ID environment variable
        override (bool, optional): Whether to override existing environment variables
    """
    try:
        client = _initialize_client()
    except Exception as e:
        logger.error(f"Failed to initialize Bitwarden client: {e}")
        return
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if not organization_id:
        logger.error("ORGANIZATION_ID not found in keyring or environment variable")
        return
    
    # If project_id is not provided, try to get it from keyring or environment variable
    if project_id is None:
        project_id = _get_from_keyring_or_env(_KEYRING_PROJECT_ID_KEY, "PROJECT_ID")
    
    secrets = load_secrets_env(client, organization_id, project_id)

    set_env_vars(secrets, override)

    del secrets

def env_load_all(override=False):
    """
    Load all secrets from all projects that user has access to into environment variables
    
    Args:
        override (bool, optional): Whether to override existing environment variables
    """
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if not organization_id:
        logger.error("ORGANIZATION_ID not found in keyring or environment variable")
        return
    
    try:
        client = _initialize_client()
        from .in_env import load_secrets_env_all
        secrets = load_secrets_env_all(client, organization_id)
        set_env_vars(secrets, override)
        del secrets
    except Exception as e:
        logger.error(f"Failed to load all secrets: {e}")
        return

def get(project_id=None, use_keyring=True):
    """
    Return a dictionary of all project secrets with JIT decryption
    
    Args:
        project_id (str, optional): Project ID to filter secrets. If None, will try to get from keyring or PROJECT_ID environment variable
        use_keyring (bool, optional): Whether to use system keyring (True) or in-memory encryption (False)
        
    Returns:
        dict: Dictionary of secrets with their names as keys, using lazy loading with JIT decryption
    """
    try:
        client = _initialize_client()
    except Exception as e:
        logger.error(f"Failed to initialize Bitwarden client: {e}")
        return {}
        
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if not organization_id:
        logger.error("ORGANIZATION_ID not found in keyring or environment variable")
        return {}
    
    # If project_id is not provided, try to get it from keyring or environment variable
    if project_id is None:
        project_id = _get_from_keyring_or_env(_KEYRING_PROJECT_ID_KEY, "PROJECT_ID")
    
    from .in_memory import load_secrets_memory
    all_secrets = load_secrets_memory(client, organization_id, project_id)
    
    # Get all secret keys - values will be decrypted JIT when accessed
    secret_keys = set(all_secrets.keys())
    
    return create_secrets_dict(
        secret_keys, 
        organization_id, 
        project_id or "", 
        all_secrets,
        use_keyring
    )

def get_all(use_keyring=True):
    """
    Return a combined dictionary of secrets from all projects that user has access to with JIT decryption
    
    Args:
        use_keyring (bool, optional): Whether to use system keyring (True) or in-memory encryption (False)
        
    Returns:
        dict: Dictionary of secrets with their names as keys, using lazy loading with JIT decryption
    """
    try:
        client = _initialize_client()
    except Exception as e:
        logger.error(f"Failed to initialize Bitwarden client: {e}")
        return {}
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if not organization_id:
        logger.error("Organization ID not found in keyring or environment variables")
        return {}

    try:
        projects_response = client.projects().list(organization_id)
        
        # Validate response format
        if not hasattr(projects_response, 'data') or not hasattr(projects_response.data, 'data'):
            logger.warning(f"No projects found in organization {organization_id}")
            return {}

        # Create a combined dictionary with all secrets
        all_secrets = {}
        project_ids = []
        
        # First collect all project IDs
        for project in projects_response.data.data:
            if hasattr(project, 'id'):
                project_ids.append(str(project.id))
        
        # Create merged dictionary of all secrets with JIT decryption
        for project_id in project_ids:
            # Get secrets for this project
            project_secrets = get(project_id, use_keyring=use_keyring)
            # Update the combined dictionary (this will overwrite duplicate keys)
            all_secrets.update(project_secrets)

        return all_secrets
    except Exception as e:
        logger.error(f"Error retrieving projects: {str(e)}")
        return {}

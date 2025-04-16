#!/usr/bin/env python3
import os
import logging
from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict

# Setup minimal logging
logger = logging.getLogger(__name__)

# Dictionary to store secrets
_secrets_cache = {}

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
        
        # Update the cache
        _secrets_cache = secrets
        
        return secrets
    except Exception as e:
        logger.error(f"Error loading secrets: {e}")
        raise

def env_load(organization_id=None, project_id=None):
    """
    Load all secrets related to the project into environmental variables.
    
    Args:
        organization_id (str, optional): Organization ID
        project_id (str, optional): Project ID to filter secrets
    """
    secrets = _load_secrets(organization_id, project_id)
    
    # Add each secret to environment variables
    for key, value in secrets.items():
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
    global _secrets_cache
    
    # If cache is empty or refresh is requested, reload secrets
    if not _secrets_cache or refresh:
        return _load_secrets(organization_id, project_id)
    
    return _secrets_cache.copy()  # Return a copy to prevent modification

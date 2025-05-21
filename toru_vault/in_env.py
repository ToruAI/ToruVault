#!/usr/bin/env python3
import os
import logging
from typing import Dict

# Setup minimal logging
logger = logging.getLogger(__name__)

def set_env_vars(secrets: Dict[str, str], override: bool = False) -> None:
    """
    Set environment variables based on secrets dictionary
    
    Args:
        secrets: Dictionary of secrets
        override: Whether to override existing environment variables
    """
    # Set environment variables
    for key, value in secrets.items():
        if override or key not in os.environ:
            os.environ[key] = value

def process_env_project(project_id: str, project_name: str, override: bool, load_project_secrets) -> None:
    """
    Process a project and load its secrets into environment variables
    
    Args:
        project_id: Project ID
        project_name: Project name (for logging)
        override: Whether to override existing environment variables
        load_project_secrets: Function that loads secrets for a specific project
    """
    try:
        # Get the secrets for this project and set them as environment variables
        secrets = load_project_secrets(project_id)
        set_env_vars(secrets, override)
        logger.info(f"Loaded secrets from project: {project_name}")
    except Exception as e:
        logger.warning(f"Failed to load secrets from project {project_id}: {e}")

def load_secrets_env(client, organization_id, project_id=None):
    """
    Load secrets from Bitwarden specifically for environment variable usage
    
    Args:
        client: Initialized Bitwarden client
        organization_id: Organization ID
        project_id: Optional project ID to filter secrets
        
    Returns:
        dict: Dictionary of secrets with their names as keys
    """
    try:
        client.secrets().sync(organization_id, None)
        
        secrets = {}
        
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
                
                # Add the secret to our dictionary
                secrets[secret.key] = secret.value
        
        return secrets
    except Exception as e:
        logger.error(f"Error loading secrets for environment: {e}")
        return {}

def load_secrets_env_all(client, organization_id):
    """
    Load all secrets from all projects in the organization
    
    Args:
        client: Bitwarden client instance
        organization_id: Organization ID
        
    Returns:
        dict: Dictionary of all secrets from all projects
    """
    try:
        # Sync secrets with server
        client.secrets().sync(organization_id, None)
        
        # Get all secrets directly
        all_secrets_list = client.secrets().list(organization_id)
        if not hasattr(all_secrets_list, 'data') or not hasattr(all_secrets_list.data, 'data'):
            return {}

        # Extract secret IDs
        secret_ids = [secret.id for secret in all_secrets_list.data.data]
        
        if not secret_ids:
            return {}
            
        # Fetch values for all secrets
        secrets_detailed = client.secrets().get_by_ids(secret_ids)
        if not hasattr(secrets_detailed, 'data') or not hasattr(secrets_detailed.data, 'data'):
            return {}
            
        # Process all secrets
        all_secrets = {}
        for secret in secrets_detailed.data.data:
            all_secrets[secret.key] = secret.value
            
        return all_secrets
    except Exception as e:
        logger.error(f"Error loading secrets from all projects: {e}")
        return {}


def process_all_projects(organization_id: str, override: bool, 
                        initialize_client, load_project_secrets) -> None:
    """
    Process all projects and load their secrets into environment variables
    
    Args:
        organization_id: Organization ID
        override: Whether to override existing environment variables
        initialize_client: Function that initializes the Bitwarden client
        load_project_secrets: Function that loads secrets for a specific project
    """
    # Initialize Bitwarden client
    try:
        client = initialize_client()
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
                project_name = getattr(project, 'name', project_id)
                
                # Load environment variables for this project
                process_env_project(project_id, project_name, override, load_project_secrets)
                
    except Exception as e:
        logger.error(f"Failed to load all secrets into environment variables: {e}")

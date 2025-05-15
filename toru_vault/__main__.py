#!/usr/bin/env python3
"""
Command-line interface for the ToruVault package.
"""
import argparse
import os
import sys
import getpass

from .vault import (_initialize_client, set_to_keyring, _get_from_keyring_or_env,
                   _KEYRING_BWS_TOKEN_KEY, _KEYRING_ORG_ID_KEY, _KEYRING_STATE_FILE_KEY, 
                   _KEYRING_AVAILABLE)


def list_projects(organization_id=None):
    """
    List all projects and their IDs for the given organization.
    
    Args:
        organization_id (str, optional): Organization ID
    
    Returns:
        list: List of projects
    """
    # Check for organization ID
    if not organization_id:
        organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
        if not organization_id:
            print("Error: ORGANIZATION_ID not found in keyring or environment variable")
            sys.exit(1)
    
    try:
        # Initialize client
        client = _initialize_client()
        
        # Get all projects
        projects = client.projects().list(organization_id)
        
        if not hasattr(projects, 'data') or not hasattr(projects.data, 'data'):
            print("No projects found or invalid response format")
            return []
        
        return projects.data.data
    except Exception as e:
        print(f"Error listing projects: {e}")
        sys.exit(1)


def init_vault():
    """
    Initialize ToruVault by storing BWS_TOKEN, ORGANIZATION_ID, and STATE_FILE in keyring.
    
    Returns:
        bool: True if initialization was successful
    """
    # Check if keyring is available
    if not _KEYRING_AVAILABLE:
        print("Error: keyring package is not available. Cannot securely store credentials.")
        return False

    # Get existing values
    existing_token = _get_from_keyring_or_env(_KEYRING_BWS_TOKEN_KEY, "BWS_TOKEN")
    existing_org_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    existing_state_file = _get_from_keyring_or_env(_KEYRING_STATE_FILE_KEY, "STATE_FILE")
    
    # Suggest current directory for STATE_FILE if not set
    current_dir = os.getcwd()
    suggested_state_file = os.path.join(current_dir, "state")
    
    # Ask for BWS_TOKEN or use existing
    if existing_token:
        print(f"Found existing BWS_TOKEN {'in keyring' if _KEYRING_AVAILABLE else 'in environment'}")
        new_token = getpass.getpass("Enter new BWS_TOKEN (leave empty to keep existing): ")
        token = new_token if new_token else existing_token
    else:
        token = getpass.getpass("Enter BWS_TOKEN: ")
        if not token:
            print("Error: BWS_TOKEN is required")
            return False
    
    # Ask for ORGANIZATION_ID or use existing
    if existing_org_id:
        print(f"Found existing ORGANIZATION_ID {'in keyring' if _KEYRING_AVAILABLE else 'in environment'}")
        new_org_id = input("Enter new ORGANIZATION_ID (leave empty to keep existing): ")
        org_id = new_org_id if new_org_id else existing_org_id
    else:
        org_id = input("Enter ORGANIZATION_ID: ")
        if not org_id:
            print("Error: ORGANIZATION_ID is required")
            return False
    
    # Ask for STATE_FILE or use existing
    if existing_state_file:
        print(f"Found existing STATE_FILE {'in keyring' if _KEYRING_AVAILABLE else 'in environment'}: {existing_state_file}")
        new_state_file = input(f"Enter new STATE_FILE path (leave empty to keep existing, default: {suggested_state_file}): ")
        state_file = new_state_file if new_state_file else existing_state_file
    else:
        state_file = input(f"Enter STATE_FILE path (default: {suggested_state_file}): ")
        if not state_file:
            state_file = suggested_state_file
            print(f"Using default STATE_FILE path: {state_file}")
    
    # Store in keyring
    if _KEYRING_AVAILABLE:
        if existing_token != token or not existing_token:
            if set_to_keyring(_KEYRING_BWS_TOKEN_KEY, token):
                print("BWS_TOKEN stored in keyring")
            else:
                print("Failed to store BWS_TOKEN in keyring")
                return False
        
        if existing_org_id != org_id or not existing_org_id:
            if set_to_keyring(_KEYRING_ORG_ID_KEY, org_id):
                print("ORGANIZATION_ID stored in keyring")
            else:
                print("Failed to store ORGANIZATION_ID in keyring")
                return False
        
        if existing_state_file != state_file or not existing_state_file:
            if set_to_keyring(_KEYRING_STATE_FILE_KEY, state_file):
                print("STATE_FILE stored in keyring")
            else:
                print("Failed to store STATE_FILE in keyring")
                return False
    else:
        # Store in environment variables if keyring is not available
        os.environ["BWS_TOKEN"] = token
        os.environ["ORGANIZATION_ID"] = org_id
        os.environ["STATE_FILE"] = state_file
        print("Credentials stored in environment variables (not persistent)")
    
    # Ensure state file directory exists
    state_dir = os.path.dirname(state_file)
    if state_dir and not os.path.exists(state_dir):
        try:
            os.makedirs(state_dir, exist_ok=True)
            print(f"Created directory for STATE_FILE: {state_dir}")
        except Exception as e:
            print(f"Warning: Could not create state directory: {e}")
    
    print("\nToruVault initialization completed successfully")
    return True


def main():
    """
    Main entry point for the command-line interface.
    """
    parser = argparse.ArgumentParser(description="ToruVault: Bitwarden Secret Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List projects")
    list_parser.add_argument("--org-id", "-o", help="Organization ID")
    
    # Init command
    subparsers.add_parser("init", help="Initialize ToruVault with BWS_TOKEN and ORGANIZATION_ID")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if args.command == "list":
        projects = list_projects(args.org_id)
        if projects:
            print("\nAvailable Projects:")
            print("===================")
            for project in projects:
                print(f"ID: {project.id}")
                print(f"Name: {project.name}")
                print(f"Created: {project.creation_date}")
                print("-" * 50)
        else:
            print("No projects found")
    elif args.command == "init":
        init_vault()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

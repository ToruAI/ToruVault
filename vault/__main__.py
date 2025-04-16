#!/usr/bin/env python3
"""
Command-line interface for the vault package.
"""
import argparse
import os
import sys

from .vault import _initialize_client


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
        organization_id = os.getenv("ORGANIZATION_ID")
        if not organization_id:
            print("Error: ORGANIZATION_ID environment variable is required")
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


def main():
    """
    Main entry point for the command-line interface.
    """
    parser = argparse.ArgumentParser(description="Bitwarden Secret Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List projects")
    list_parser.add_argument("--org-id", "-o", help="Organization ID")
    
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

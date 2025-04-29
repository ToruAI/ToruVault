#!/usr/bin/env python3
"""
Example wrapper script that runs the usage example using keyring values
"""
import os
import sys
import subprocess

# Import vault to use keyring helper functions
try:
    from vault.vault import _get_from_keyring_or_env, _KEYRING_STATE_FILE_KEY, _KEYRING_ORG_ID_KEY
    
    # Get STATE_FILE from keyring or environment
    state_file = _get_from_keyring_or_env(_KEYRING_STATE_FILE_KEY, "STATE_FILE")
    if state_file:
        os.environ["STATE_FILE"] = state_file
        print(f"Using STATE_FILE from keyring: {state_file}")
    else:
        print("STATE_FILE not found in keyring or environment")
        print("Please run 'python -m vault init' to set up vault configuration")
        sys.exit(1)
    
    # Get ORGANIZATION_ID from keyring or environment
    organization_id = _get_from_keyring_or_env(_KEYRING_ORG_ID_KEY, "ORGANIZATION_ID")
    if organization_id:
        os.environ["ORGANIZATION_ID"] = organization_id
        print(f"Using ORGANIZATION_ID from keyring: {organization_id}")
    else:
        print("ORGANIZATION_ID not found in keyring or environment")
        print("Please run 'python -m vault init' to set up vault configuration")
        sys.exit(1)
except ImportError:
    print("Error: Unable to import vault module")
    sys.exit(1)

# Run the usage example
subprocess.run([sys.executable, "usage_example.py"], check=False)

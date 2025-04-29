#!/usr/bin/env python3
"""
Example showing how to use the vault package
"""
import os
import vault

# Method 1: Load all secrets into environment variables
print("Loading secrets into environment variables...")
vault.env_load(project_id='b40bd93f-ff8e-407b-ab95-b2ba013ed760')

# Access the secrets as environment variables
print("\nAccessing secrets from environment variables:")
print(f"TEST_SECRET = {os.environ.get('TEST_SECRET', 'Not found')}")

# Method 2: Get all secrets as a dictionary
print("\nGetting secrets as a dictionary...")
secrets = vault.get(project_id='b40bd93f-ff8e-407b-ab95-b2ba013ed760')

# Access the secrets from the dictionary
print("\nAccessing secrets from dictionary:")
print(f"TEST_SECRET = {secrets.get('TEST_SECRET', 'Not found')}")

# Show all available secret keys (without exposing values)
print("\nAvailable secret keys:")
for key in secrets:
    print(f"- {key}")

# Method 3: Load all secrets from all projects
print("\nLoading all secrets from all projects...")
vault.env_load_all()

# Method 4: Use in-memory encryption instead of keyring
print("\nGetting secrets with in-memory encryption...")
secrets = vault.get(project_id='b40bd93f-ff8e-407b-ab95-b2ba013ed760', use_keyring=False)

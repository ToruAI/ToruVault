#!/usr/bin/env python3
"""
Example showing how to use the vault package
"""
import os
import vault

# Method 1: Load all secrets into environment variables
print("Loading secrets into environment variables...")
vault.env_load(organization_id='770031ca-3bc6-4468-b958-b2b301304812', project_id='b40bd93f-ff8e-407b-ab95-b2ba013ed760')

# Access the secrets as environment variables
print("\nAccessing secrets from environment variables:")
print(f"TEST_SECRET = {os.environ.get('TEST_SECRET', 'Not found')}")

# Method 2: Get all secrets as a dictionary
print("\nGetting secrets as a dictionary...")
secrets = vault.get(organization_id='770031ca-3bc6-4468-b958-b2b301304812', project_id='b40bd93f-ff8e-407b-ab95-b2ba013ed760')

# Access the secrets from the dictionary
print("\nAccessing secrets from dictionary:")
print(f"TEST_SECRET = {secrets.get('TEST_SECRET', 'Not found')}")

# Show all available secret keys (without exposing values)
print("\nAvailable secret keys:")
for key, value in secrets.items():
    print(f"- {key} = {value}")

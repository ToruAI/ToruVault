# Vault

A simple Python package for managing Bitwarden secrets with enhanced security.

## Features

- Load secrets from Bitwarden Secret Manager into environment variables
- Get secrets as a Python dictionary
- Filter secrets by project ID
- Secure in-memory caching with encryption
- Automatic cache expiration (5 minutes)
- Secure file permissions for state storage
- Machine-specific secret protection

## Installation

```bash
pip install vault
```

### From Source

```bash
# Clone the repository
git clone https://github.com/ToruAI/vault.git
cd vault

# Install in development mode
pip install -e .
```

## Environment Variables

The following environment variables are required:

- `BWS_TOKEN`: Your Bitwarden access token
- `ORGANIZATION_ID`: Your Bitwarden organization ID
- `STATE_FILE`: Path to the state file (must be in an existing directory)
- `API_URL` (optional): Defaults to "https://api.bitwarden.com"
- `IDENTITY_URL` (optional): Defaults to "https://identity.bitwarden.com"

## Usage

### Listing Available Projects

```bash
# List all projects in your organization
python -m vault list 

# With a specific organization ID
python -m vault list --org-id YOUR_ORGANIZATION_ID
```

### Loading secrets into environment variables

```python
import vault

# Load all secrets into environment variables
vault.env_load()

# Now you can access secrets as environment variables
import os
print(os.environ.get("SECRET_NAME"))

# Load secrets for a specific organization
vault.env_load(organization_id="your-org-id")

# Load secrets for a specific project
vault.env_load(project_id="your-project-id")

# Override existing environment variables (default: False)
vault.env_load(override=True)
```

### Getting secrets as a dictionary

```python
import vault

# Get all secrets as a dictionary
secrets = vault.get()
print(secrets["SECRET_NAME"])

# Force refresh the cache
secrets = vault.get(refresh=True)

# Get secrets for a specific project
secrets = vault.get(project_id="your-project-id")
```

## Security Features

The vault package includes several security enhancements:

1. **Memory Protection**: Secrets are encrypted in memory using Fernet encryption (AES-128)
2. **Cache Expiration**: Cached secrets expire after 5 minutes by default
3. **Secure File Permissions**: Sets secure permissions on state files
4. **Machine-Specific Encryption**: Uses machine-specific identifiers for encryption keys
5. **Cache Clearing**: Automatically clears secret cache on program exit
6. **Environment Variable Protection**: Doesn't override existing environment variables by default

## Building and Publishing

Build the package:

```bash
python -m build
```

Publish to PyPI:

```bash
python -m twine upload dist/*
```

## License

MIT

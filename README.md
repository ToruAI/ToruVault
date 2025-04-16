# Vault

A simple Python package for managing Bitwarden secrets.

## Features

- Load secrets from Bitwarden Secret Manager into environment variables
- Get secrets as a Python dictionary
- Filter secrets by project ID
- Cache secrets for performance

## Installation

### From PyPI (when published)

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

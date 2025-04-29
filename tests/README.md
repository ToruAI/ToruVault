# Vault Test Suite

This directory contains tests for the vault package using pytest.

## Overview

The test suite includes:

- `test_vault.py`: Tests core functionality (env_load, get, encryption)
- `test_lazy_dict.py`: Tests the LazySecretsDict class for lazy loading
- `test_cli.py`: Tests command line interface functionality
- `conftest.py`: Contains test fixtures and mocking utilities

## Running Tests

### Installation

First, install the development dependencies:

```bash
# Using UV (recommended)
cd tests
uv pip install -r requirements-dev.txt

# Or using pip
cd tests
pip install -r requirements-dev.txt
```

### Basic Usage

Run all tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=vault
```

Generate an HTML coverage report:

```bash
pytest --cov=vault --cov-report=html
```

### Specific Tests

Run a specific test file:

```bash
pytest tests/test_vault.py
```

Run a specific test class:

```bash
pytest tests/test_vault.py::TestVaultCore
```

Run a specific test:

```bash
pytest tests/test_vault.py::TestVaultCore::test_env_load
```

## Test Structure

### Fixtures

- `mock_keyring`: Mocks the keyring module with in-memory storage
- `mock_env_vars`: Sets up test environment variables
- `mock_bitwarden_client`: Mocks the Bitwarden client with test data

### Test Categories

1. **Core Functionality Tests**:
   - `env_load()` functionality with and without overriding
   - `env_load_all()` across multiple projects
   - `get()` with various parameter combinations
   - Cache refreshing and expiration

2. **Encryption Tests**:
   - Encryption and decryption functionality
   - Cache expiration mechanism

3. **Lazy Loading Tests**:
   - LazySecretsDict behavior
   - On-demand value loading

4. **CLI Tests**:
   - Command line interface functionality
   - Input/output handling

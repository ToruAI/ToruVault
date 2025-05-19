# Development Ideas for Vault Package

This document tracks potential future enhancements and feature ideas for the `vault` package.

## Security Enhancements

- Investigate and potentially implement per-secret just-in-time (JIT) decryption. This involves encrypting each secret individually in any local cache and only decrypting a specific secret upon access via `LazySecretsDict`, thereby minimizing the exposure time of plaintext secrets in memory.

## Feature Ideas

- 

## Refactoring & Improvements

- Investigate options to optimize secret fetching for single projects (e.g., in `env_load`). Currently, the SDK (`bitwarden-sdk.py`) appears to necessitate listing all organization secret identifiers before local filtering by `project_id`. 
  - **Goal**: Enhance both **security** (by adhering to the principle of least privilege and reducing the in-memory exposure of non-relevant secrets) and **efficiency** by fetching only project-specific secrets directly from the server.
  - **Action**: Determine if the underlying Bitwarden API (and the `bitwarden_py` library) supports server-side filtering of secrets by `project_id`. If so, modify the local `bitwarden-sdk.py` (specifically `SecretsClient.list()` or add a new method) to leverage this. If not, document this as a current limitation.
- 

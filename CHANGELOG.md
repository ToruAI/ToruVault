# Changelog

All notable changes to the toru-vault package will be documented in this file.

## [0.2.0] - 2025-05-21

### Security
- Implemented true Just-In-Time (JIT) decryption for all secrets
- Removed all caching functionality to prevent secrets persisting in memory
- Each secret is now individually encrypted in memory
- Decryption happens only when a specific value is accessed and is never stored

### Changed
- LazySecretsDict no longer maintains an internal cache of decrypted values
- Modified container_getter to perform decryption on every access
- load_secrets_memory now returns encrypted values
- Removed refresh parameter from get() and get_all() functions
- Simplified API by removing cache-related parameters

### Breaking Changes
- Changed function signatures for get() and get_all()
- Removed no_cache parameter (caching is now permanently disabled)

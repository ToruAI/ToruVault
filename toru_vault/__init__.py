#!/usr/bin/env python3
# Import functions from the core module
from .vault import env_load, env_load_all, get, get_all

__version__ = "0.2.0"
__all__ = ["env_load", "env_load_all", "get", "get_all"]

from collections.abc import MutableMapping
from typing import Optional, Callable, Set, Iterator, Tuple

class LazySecretsDict(MutableMapping):
    """
    A dictionary-like class that only loads/decrypts secrets when they are accessed.
    The specific mechanisms for fetching and storing secrets (e.g., using OS keyring
    or other encryption methods) are determined by the functions provided during
    its instantiation.
    """
    
    def __init__(self, 
                 secret_keys: Set[str], 
                 getter_func: Callable[[str], str],
                 setter_func: Optional[Callable[[str, str], None]] = None,
                 deleter_func: Optional[Callable[[str], None]] = None):
        """
        Initialize the lazy dictionary with a list of available keys and functions to retrieve/set/delete values.
        
        Args:
            secret_keys: Set of keys that are available in this dictionary
            getter_func: Function that takes a key and returns the secret value
            setter_func: Optional function to set a value for a key
            deleter_func: Optional function to delete a key
        """
        self._keys = secret_keys
        self._getter = getter_func
        self._setter = setter_func
        self._deleter = deleter_func
    
    def __getitem__(self, key: str) -> str:
        """Get an item from the dictionary, fetching/decrypting it on each access."""
        if key not in self._keys:
            raise KeyError(key)
            
        # Always fetch and decrypt fresh to avoid keeping decrypted values in memory
        value = self._getter(key)
        if value is None:
            raise KeyError(f"Failed to retrieve value for key: {key}")
            
        return value
    
    def __setitem__(self, key: str, value: str) -> None:
        """Set an item in the dictionary."""
        if self._setter is None:
            raise NotImplementedError("This dictionary does not support item assignment")
        
        self._setter(key, value)
        self._cache[key] = value
        self._keys.add(key)
    
    def __delitem__(self, key: str) -> None:
        """Delete an item from the dictionary."""
        if self._deleter is None:
            raise NotImplementedError("This dictionary does not support item deletion")
            
        if key not in self._keys:
            raise KeyError(key)
            
        self._deleter(key)
        if key in self._cache:
            del self._cache[key]
        self._keys.remove(key)
    
    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys."""
        return iter(self._keys)
    
    def __len__(self) -> int:
        """Return the number of keys."""
        return len(self._keys)
    
    def items(self) -> Iterator[Tuple[str, str]]:
        for key in self._keys:
            yield (key, self[key])
            
    def keys(self) -> Set[str]:
        return self._keys.copy()
    
    def values(self) -> Iterator[str]:
        for key in self._keys:
            yield self[key]

"""
Tests for the lazy dictionary implementation in the vault package.
"""
from unittest.mock import MagicMock

class TestLazySecretsDict:
    """Test the LazySecretsDict class."""
    
    def test_lazy_loading(self):
        """Test that values are only loaded when accessed."""
        # Mock getter function
        mock_getter = MagicMock(return_value="secret_value")
        
        # Create dictionary with known keys
        keys = {"KEY1", "KEY2", "KEY3"}
        lazy_dict = LazySecretsDict(keys, mock_getter)
        
        # Getter should not be called yet
        mock_getter.assert_not_called()
        
        # Access a key
        value = lazy_dict["KEY1"]
        
        # Getter should be called exactly once with the right key
        assert mock_getter.call_count == 1
        mock_getter.assert_called_with("KEY1")
        assert value == "secret_value"
        
        # Access the same key again
        value = lazy_dict["KEY1"]
        
        # Getter should not be called again
        assert mock_getter.call_count == 1
    
    def test_iteration(self):
        """Test iterating through the dictionary."""
        # Mock getter that returns different values based on key
        def mock_getter(key):
            return f"value_for_{key}"
            
        # Create dictionary with known keys
        keys = {"KEY1", "KEY2", "KEY3"}
        lazy_dict = LazySecretsDict(keys, mock_getter)
        
        # Test iteration
        iterated_keys = []
        for key in lazy_dict:
            iterated_keys.append(key)
            
        # Should have all keys
        assert sorted(iterated_keys) == sorted(keys)
        
        # Test items method
        items = list(lazy_dict.items())
        assert len(items) == 3
        assert ("KEY1", "value_for_KEY1") in items
        assert ("KEY2", "value_for_KEY2") in items
        assert ("KEY3", "value_for_KEY3") in items
    
    def test_setter(self):
        """Test setter functionality if provided."""
        # Mock getter and setter
        mock_getter = MagicMock(return_value="original_value")
        mock_setter = MagicMock()
        
        # Create dictionary with setter
        keys = {"KEY1"}
        lazy_dict = LazySecretsDict(keys, mock_getter, mock_setter)
        
        # Set a value
        lazy_dict["KEY1"] = "new_value"
        
        # Setter should be called with the key and new value
        mock_setter.assert_called_once_with("KEY1", "new_value")
        
        # The value should be updated in the cache
        assert lazy_dict["KEY1"] == "new_value"
    
    def test_deleter(self):
        """Test deleter functionality if provided."""
        # Mock getter and deleter
        mock_getter = MagicMock(return_value="value")
        mock_deleter = MagicMock()
        
        # Create dictionary with deleter
        keys = {"KEY1", "KEY2"}
        lazy_dict = LazySecretsDict(keys, mock_getter, None, mock_deleter)
        
        # Delete a key
        del lazy_dict["KEY1"]
        
        # Deleter should be called with the key
        mock_deleter.assert_called_once_with("KEY1")
        
        # Key should be removed from the keys set
        assert "KEY1" not in lazy_dict
        assert "KEY2" in lazy_dict
    
    def test_contains(self):
        """Test the contains method."""
        # Create dictionary
        keys = {"KEY1", "KEY2"}
        lazy_dict = LazySecretsDict(keys, lambda k: "value")
        
        # Test contains
        assert "KEY1" in lazy_dict
        assert "KEY2" in lazy_dict
        assert "KEY3" not in lazy_dict
    
    def test_get_with_default(self):
        """Test the get method with default value."""
        # Mock getter that returns None for certain keys
        def mock_getter(key):
            if key == "MISSING":
                return None
            return f"value_for_{key}"
            
        # Create dictionary
        keys = {"KEY1", "MISSING"}
        lazy_dict = LazySecretsDict(keys, mock_getter)
        
        # Test get with default
        assert lazy_dict.get("KEY1") == "value_for_KEY1"
        assert lazy_dict.get("MISSING", "default") == "default"
        assert lazy_dict.get("NOT_A_KEY", "default") == "default"

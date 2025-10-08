#!/usr/bin/env python3
"""
Safe data access utilities - prevent KeyError and AttributeError
DRAFT - awaiting approval for integration
"""
from typing import Any, Optional, Union


def safe_get(obj: Any, path: str, default: Any = None) -> Any:
    """
    Safely access nested dict/object attributes using dot notation.
    
    Examples:
        safe_get(data, 'meta.audio.duration', 0.0)
        safe_get(info, 'samplerate', 44100)
    
    Args:
        obj: The object to access (dict or object with attributes)
        path: Dot-separated path to the value
        default: Default value if path doesn't exist
    
    Returns:
        The value at the path, or default if not found
    """
    if obj is None:
        return default
    
    keys = path.split('.')
    current = obj
    
    for key in keys:
        if current is None:
            return default
        
        # Try dict access first
        if isinstance(current, dict):
            current = current.get(key)
        # Then object attribute
        else:
            current = getattr(current, key, None)
        
        # If we got None at any point, return default
        if current is None:
            return default
    
    # If we still have None at the end, use default
    return current if current is not None else default


def safe_get_dict(d: dict, key: str, default: Any = None) -> Any:
    """Safely get from dict with default"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def safe_get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get object attribute with default"""
    return getattr(obj, attr, default)


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.
    
    Examples:
        safe_float("1.5")  # 1.5
        safe_float(None, 0.0)  # 0.0
        safe_float("invalid", 0.0)  # 0.0
    """
    if value is None:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int.
    
    Examples:
        safe_int("42")  # 42
        safe_int(None, 0)  # 0
        safe_int("invalid", 0)  # 0
    """
    if value is None:
        return default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """
    Safely convert value to string.
    
    Examples:
        safe_str(42)  # "42"
        safe_str(None, "")  # ""
    """
    if value is None:
        return default
    
    try:
        return str(value)
    except Exception:
        return default


def safe_list(value: Any, default: list = None) -> list:
    """
    Safely ensure value is a list.
    
    Examples:
        safe_list([1, 2, 3])  # [1, 2, 3]
        safe_list(None, [])  # []
        safe_list("single", [])  # ["single"]
    """
    if default is None:
        default = []
    
    if value is None:
        return default
    
    if isinstance(value, list):
        return value
    
    # Wrap single value in list
    return [value]


def safe_dict(value: Any, default: dict = None) -> dict:
    """
    Safely ensure value is a dict.
    
    Examples:
        safe_dict({'a': 1})  # {'a': 1}
        safe_dict(None, {})  # {}
    """
    if default is None:
        default = {}
    
    if value is None:
        return default
    
    if isinstance(value, dict):
        return value
    
    return default


def ensure_not_none(value: Any, default: Any, value_name: str = "value") -> Any:
    """
    Ensure value is not None, log warning if it is.
    
    Args:
        value: The value to check
        default: Default value if None
        value_name: Name of the value for logging
    
    Returns:
        The value or default
    """
    if value is None:
        import logging
        logging.warning(f"{value_name} is None, using default: {default}")
        return default
    return value


def extract_metadata(obj: Any, fields: dict) -> dict:
    """
    Extract multiple fields from object with defaults.
    
    Args:
        obj: The object to extract from
        fields: Dict of {output_key: (path, default)}
    
    Example:
        metadata = extract_metadata(audio_info, {
            'duration': ('duration', 0.0),
            'sample_rate': ('samplerate', 44100),
            'channels': ('channels', 2)
        })
    
    Returns:
        Dict with extracted values
    """
    result = {}
    
    for key, (path, default) in fields.items():
        result[key] = safe_get(obj, path, default)
    
    return result


# Convenience decorator for safe function execution
def returns_default_on_error(default_value: Any = None):
    """
    Decorator that returns default value if function raises exception.
    
    Example:
        @returns_default_on_error(default_value={})
        def risky_function():
            return potentially_failing_operation()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                import logging
                logging.error(f"{func.__name__} failed: {e}", exc_info=True)
                return default_value
        return wrapper
    return decorator


if __name__ == "__main__":
    # Tests
    print("Testing safe_access utilities...")
    
    # Test data
    data = {
        'meta': {
            'audio': {
                'duration': 10.5,
                'channels': 2
            }
        },
        'name': 'test'
    }
    
    class AudioInfo:
        duration = 42.0
        samplerate = 44100
    
    audio = AudioInfo()
    
    # Test safe_get
    assert safe_get(data, 'meta.audio.duration', 0.0) == 10.5
    assert safe_get(data, 'meta.audio.missing', 0.0) == 0.0
    assert safe_get(data, 'completely.wrong.path', 'default') == 'default'
    assert safe_get(audio, 'duration', 0.0) == 42.0
    assert safe_get(audio, 'missing', 0.0) == 0.0
    
    # Test conversions
    assert safe_float("1.5", 0.0) == 1.5
    assert safe_float(None, 0.0) == 0.0
    assert safe_int("42", 0) == 42
    assert safe_int(None, 0) == 0
    
    # Test extract_metadata
    metadata = extract_metadata(audio, {
        'duration_sec': ('duration', 0.0),
        'sample_rate': ('samplerate', 44100),
        'missing_field': ('doesnotexist', 'default')
    })
    
    assert metadata['duration_sec'] == 42.0
    assert metadata['sample_rate'] == 44100
    assert metadata['missing_field'] == 'default'
    
    print("✅ All tests passed!")

"""Credential transport checks only. Never alter, display or persist key values."""


def key_format_issue(key):
    if not isinstance(key,str) or not key:
        return None  # Missing configuration is handled separately.
    if any(ord(char)<32 or ord(char)==127 for char in key):
        return 'control_characters'
    if key!=key.strip():
        return 'surrounding_whitespace'
    return None

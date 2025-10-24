"""
Centralized text normalization utility for consistent matching across all clients.

This module provides standardized text normalization functions that handle:
- Apostrophe variations (\u2018, \u2019 -> ')
- Quote variations (\u201c, \u201d -> ")
- Dash variations (\u2010, \u2012, \u2013, \u2014 -> -)
- Other punctuation removal
"""

import re
from typing import Optional


def normalize_text(text: Optional[str]) -> str:
    """
    Normalize text for consistent matching across all clients.
    
    Normalizes common punctuation variations to their standard equivalents:
    - Apostrophes: \u2018 ('), \u2019 (') -> ' (straight apostrophe)
    - Quotes: \u201c ("), \u201d (") -> " (straight quote)
    - Dashes: \u2010 (‐), \u2012 (‒), \u2013 (–), \u2014 (—) -> - (hyphen-minus)
    - Removes other punctuation except spaces, apostrophes, and hyphens
    
    Args:
        text: The text to normalize (can be None)
        
    Returns:
        Normalized text string, or empty string if input is None/empty
    """
    if not text:
        return ""
    
    # Convert to lowercase and strip whitespace
    text = text.lower().strip()
    
    # Normalize apostrophes (use Unicode escapes to ensure correct characters)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    
    # Normalize quotes (use Unicode escapes to ensure correct characters)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    
    # Normalize dashes (use Unicode escapes to ensure correct characters)
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2012", "-").replace("\u2010", "-")
    
    # Remove other punctuation except spaces and apostrophes
    text = re.sub(r'[^\w\s\'-]', '', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    return text


def normalize_for_search(text: Optional[str]) -> str:
    """
    Normalize text specifically for search operations.
    
    This is an alias for normalize_text() but makes the intent clearer
    when used in search contexts.
    
    Args:
        text: The text to normalize for search
        
    Returns:
        Normalized text string suitable for search operations
    """
    return normalize_text(text)


def normalize_for_indexing(text: Optional[str]) -> str:
    """
    Normalize text specifically for indexing operations.
    
    This is an alias for normalize_text() but makes the intent clearer
    when used in indexing contexts.
    
    Args:
        text: The text to normalize for indexing
        
    Returns:
        Normalized text string suitable for indexing operations
    """
    return normalize_text(text)

"""
Internationalization (i18n) module for Real-time Subtitles.

Provides multi-language support for the UI.
"""

from typing import Dict, Optional
from realtime_subtitles.settings_manager import get_settings_manager

# Import translation modules
from . import zh_TW
from . import zh_CN
from . import en

# Available languages
LANGUAGES = {
    "zh_TW": ("繁體中文", zh_TW.TRANSLATIONS),
    "zh_CN": ("简体中文", zh_CN.TRANSLATIONS),
    "en": ("English", en.TRANSLATIONS),
}

# Default language
DEFAULT_LANGUAGE = "zh_TW"

# Current language cache
_current_language: Optional[str] = None
_translations: Dict[str, str] = {}


def get_current_language() -> str:
    """Get the current UI language code."""
    global _current_language
    if _current_language is None:
        settings = get_settings_manager()
        _current_language = settings.get("ui_language", DEFAULT_LANGUAGE)
    return _current_language


def set_language(lang_code: str) -> None:
    """
    Set the UI language.
    
    Args:
        lang_code: Language code (zh_TW, zh_CN, en)
    """
    global _current_language, _translations
    
    if lang_code not in LANGUAGES:
        lang_code = DEFAULT_LANGUAGE
    
    _current_language = lang_code
    _translations = LANGUAGES[lang_code][1]
    
    # Save to settings
    settings = get_settings_manager()
    settings.set("ui_language", lang_code)
    settings.save()


def get_text(key: str, **kwargs) -> str:
    """
    Get translated text for a key.
    
    Args:
        key: Translation key
        **kwargs: Format arguments for string interpolation
        
    Returns:
        Translated string, or key if not found
    """
    global _translations
    
    # Initialize translations if not loaded
    if not _translations:
        lang = get_current_language()
        _translations = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE])[1]
    
    text = _translations.get(key, key)
    
    # Apply format arguments if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    
    return text


def get_language_options() -> list:
    """
    Get list of available languages for UI dropdown.
    
    Returns:
        List of (display_name, code) tuples
    """
    return [(name, code) for code, (name, _) in LANGUAGES.items()]


# Convenience alias
t = get_text

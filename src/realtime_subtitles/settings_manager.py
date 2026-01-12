"""
Settings persistence for Real-time Subtitles.

Saves and loads user settings to a JSON file.
"""

import json
from pathlib import Path
from typing import Optional


class SettingsManager:
    """Manages saving and loading user settings."""
    
    DEFAULT_SETTINGS = {
        "mode": "實時",
        "model": "Sherpa-ONNX",
        "language": "英文",
        "vad_enabled": False,
        "vad_silence_ms": 100,
        "min_duration": 100,
    }
    
    def __init__(self):
        """Initialize settings manager."""
        self._config_dir = Path.home() / ".config" / "realtime-subtitles"
        self._config_file = self._config_dir / "settings.json"
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._load()
    
    def _load(self) -> None:
        """Load settings from file."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge with defaults (in case new settings were added)
                self._settings = {**self.DEFAULT_SETTINGS, **saved}
                print(f"[Settings] Loaded from {self._config_file}")
            except Exception as e:
                print(f"[Settings] Failed to load: {e}")
                self._settings = self.DEFAULT_SETTINGS.copy()
        else:
            print("[Settings] Using defaults (no saved settings)")
    
    def save(self) -> None:
        """Save settings to file."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            print(f"[Settings] Saved to {self._config_file}")
        except Exception as e:
            print(f"[Settings] Failed to save: {e}")
    
    def get(self, key: str, default=None):
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value) -> None:
        """Set a setting value."""
        self._settings[key] = value
    
    def update(self, settings: dict) -> None:
        """Update multiple settings at once."""
        self._settings.update(settings)
    
    def get_all(self) -> dict:
        """Get all settings."""
        return self._settings.copy()


# Global instance
_instance: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    global _instance
    if _instance is None:
        _instance = SettingsManager()
    return _instance

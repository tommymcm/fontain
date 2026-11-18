"""Filesystem locations, following the XDG base directory spec."""

import os
import sys
from pathlib import Path


def _xdg(var: str, default: str) -> Path:
    value = os.environ.get(var)
    if value and os.path.isabs(value):
        return Path(value)
    return Path.home() / default


def font_root() -> Path:
    """Directory that fontain installs fonts into (one subdir per font)."""
    if override := os.environ.get("FONTAIN_FONT_DIR"):
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Fonts" / "fontain"
    return _xdg("XDG_DATA_HOME", ".local/share") / "fonts" / "fontain"


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache") / "fontain"


def state_file() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / "fontain" / "installed.json"


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "fontain"


def config_file() -> Path:
    """User repositories."""
    return config_dir() / "repos.json"


def settings_file() -> Path:
    """General preferences, e.g. the preferred source."""
    return config_dir() / "config.json"

"""Small helpers for the JSON files fontain keeps (manifest, config, caches)."""

import json
import os
from pathlib import Path
from typing import Any


def read(path: Path, default: Any) -> Any:
    """Parse ``path``, or return ``default`` if it doesn't exist.

    Invalid JSON raises ``json.JSONDecodeError`` (a ``ValueError``); callers
    turn that into an error message that names the file's purpose.
    """
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def write(path: Path, data: Any, *, indent: int | None = 2, sort_keys: bool = False) -> None:
    """Write ``data`` atomically, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    text = json.dumps(data, indent=indent, sort_keys=sort_keys)
    tmp.write_text(text + "\n" if indent is not None else text)
    os.replace(tmp, path)

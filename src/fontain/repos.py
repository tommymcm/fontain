"""User-added repositories, stored in $XDG_CONFIG_HOME/fontain/repos.json."""

import json
import os
import re
from pathlib import Path
from typing import Any

from fontain import paths

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$")
GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?/?(?:[/#?].*)?$"
)


class RepoError(Exception):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise RepoError(f"invalid config {path}: {e}") from e
    if not isinstance(data, dict):
        raise RepoError(f"invalid config {path}: expected an object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def load() -> dict[str, dict[str, Any]]:
    return _read_json(paths.config_file())


def save(repos: dict[str, dict[str, Any]]) -> None:
    _write_json(paths.config_file(), repos)


def preferred() -> str | None:
    """The source to try first for bare font names (``FONTAIN_PREFER`` overrides)."""
    if env := os.environ.get("FONTAIN_PREFER"):
        return env
    value = _read_json(paths.settings_file()).get("prefer")
    return value if isinstance(value, str) and value else None


def set_preferred(name: str | None) -> None:
    settings = _read_json(paths.settings_file())
    if name:
        settings["prefer"] = name
    else:
        settings.pop("prefer", None)
    _write_json(paths.settings_file(), settings)


def parse_spec(spec: str) -> dict[str, str]:
    """Parse ``github:owner/repo``, a github.com URL, or a local directory."""
    if spec.startswith("github:"):
        repo = spec[len("github:") :].strip("/")
    elif m := GITHUB_URL_RE.match(spec):
        repo = m.group(1)
    else:
        path = Path(spec).expanduser()
        if not path.is_dir():
            raise RepoError(f"{spec!r} is not a directory (for GitHub use github:OWNER/REPO)")
        return {"type": "local", "target": str(path.resolve())}
    if not GITHUB_REPO_RE.match(repo):
        raise RepoError(f"invalid GitHub repository {repo!r} (expected OWNER/REPO)")
    return {"type": "github", "target": repo}


def check_name(name: str, builtin: set[str], existing: dict[str, Any]) -> None:
    if not NAME_RE.match(name):
        raise RepoError(f"invalid name {name!r}: use lowercase letters, digits, '-' or '_'")
    if name in builtin:
        raise RepoError(f"{name!r} is a built-in source")
    if name in existing:
        raise RepoError(f"repository {name!r} already exists (remove it first)")

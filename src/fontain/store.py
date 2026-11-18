"""Installed-font bookkeeping: where files live and what fontain owns."""

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fontain import paths
from fontain.sources.base import FontEntry, Selection, Source


class StoreError(Exception):
    pass


def load_manifest() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(paths.state_file().read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise StoreError(f"corrupt manifest {paths.state_file()}: {e}") from e


def save_manifest(manifest: dict[str, dict[str, Any]]) -> None:
    path = paths.state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def font_dir(source: str, font_id: str) -> Path:
    root = paths.font_root().resolve()
    target = (root / source / font_id).resolve()
    if root not in target.parents:
        raise StoreError(f"refusing to use path outside font root: {target}")
    return target


def is_installed(key: str) -> bool:
    return key in load_manifest()


def install(entry: FontEntry, source: Source, sel: Selection, force: bool = False) -> dict[str, Any] | None:
    """Install ``entry``; returns its manifest record, or None if already installed."""
    manifest = load_manifest()
    if entry.key in manifest and not force:
        return None
    target = font_dir(entry.source, entry.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{entry.id}-"))
    try:
        files = source.install_files(entry, staging, sel)
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    record = {
        "source": entry.source,
        "id": entry.id,
        "family": entry.family,
        "dir": str(target),
        "files": sorted(f.name for f in files),
        "weights": sorted(sel.weights),
        "styles": sorted(sel.styles),
        "installed": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    manifest[entry.key] = record
    save_manifest(manifest)
    return record


def remove(key: str) -> bool:
    manifest = load_manifest()
    record = manifest.pop(key, None)
    if record is None:
        return False
    target = font_dir(record["source"], record["id"])
    if target.exists():
        shutil.rmtree(target)
    try:
        target.parent.rmdir()  # drop the source dir once it is empty
    except OSError:
        pass
    save_manifest(manifest)
    return True

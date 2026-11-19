"""Installed-font bookkeeping: where files live and what fontain owns."""

import contextlib
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fontain import jsonfile, paths
from fontain.sources.base import FontEntry, Selection, Source


class StoreError(Exception):
    pass


def load_manifest() -> dict[str, dict[str, Any]]:
    try:
        manifest: dict[str, dict[str, Any]] = jsonfile.read(paths.state_file(), {})
    except ValueError as e:
        raise StoreError(f"corrupt manifest {paths.state_file()}: {e}") from e
    return manifest


def save_manifest(manifest: dict[str, dict[str, Any]]) -> None:
    jsonfile.write(paths.state_file(), manifest, sort_keys=True)


def font_dir(source: str, font_id: str) -> Path:
    root = paths.font_root().resolve()
    target = (root / source / font_id).resolve()
    if root not in target.parents:
        raise StoreError(f"refusing to use path outside font root: {target}")
    return target


def find_installed(spec: str, manifest: dict[str, dict[str, Any]]) -> str:
    """Resolve what the user typed (``id``, family, or ``source:id``) to a manifest key.

    Matching ignores case and spaces. This is the single definition of which
    names ``fontain remove`` accepts; tab completion is derived from it.
    """
    source, sep, name = spec.partition(":")
    if not sep:
        source, name = "", spec
    name = name.lower().replace(" ", "")
    matches = [
        key
        for key, rec in manifest.items()
        if (not source or rec["source"] == source)
        and name in (rec["id"].lower().replace(" ", ""), rec["family"].lower().replace(" ", ""))
    ]
    if not matches:
        raise StoreError(f"{spec!r} is not installed")
    if len(matches) > 1:
        raise StoreError(f"{spec!r} is ambiguous: {', '.join(sorted(matches))}")
    return matches[0]


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
    with contextlib.suppress(OSError):  # drop the source dir once it is empty
        target.parent.rmdir()
    save_manifest(manifest)
    return True

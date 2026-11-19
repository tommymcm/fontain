"""Refresh the system font cache after fonts change."""

import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_pending: dict[Path, None] | None = None  # roots waiting for a deferred refresh


@contextmanager
def deferred() -> Iterator[None]:
    """Collect refreshes inside the block and run each one once at the end."""
    global _pending
    if _pending is not None:  # already deferring
        yield
        return
    _pending = {}
    try:
        yield
    finally:
        roots, _pending = list(_pending), None
        for root in roots:
            _rebuild(root)


def refresh(root: Path, quiet: bool = False) -> bool:
    """Run ``fc-cache`` on ``root`` (later, if inside ``deferred()``)."""
    if _pending is not None:
        _pending[root] = None
        return True
    return _rebuild(root, quiet)


def _rebuild(root: Path, quiet: bool = False) -> bool:
    """Run ``fc-cache`` on ``root``. Returns False if it could not run."""
    if sys.platform == "darwin":
        return True  # CoreText watches ~/Library/Fonts itself
    exe = shutil.which("fc-cache")
    if not exe:
        print(
            "warning: fc-cache not found; install fontconfig "
            "(e.g. `apt install fontconfig` / `dnf install fontconfig`) to refresh the cache",
            file=sys.stderr,
        )
        return False
    root.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print("Updating font cache...", flush=True)
    result = subprocess.run([exe, "-f", str(root)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: fc-cache failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True

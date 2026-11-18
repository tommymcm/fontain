"""Refresh the system font cache after fonts change."""

import shutil
import subprocess
import sys
from pathlib import Path


def refresh(root: Path, quiet: bool = False) -> bool:
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
        print("Updating font cache...", file=sys.stderr)
    result = subprocess.run([exe, "-f", str(root)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"warning: fc-cache failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True

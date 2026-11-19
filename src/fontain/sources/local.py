"""User-added local directories.

Each subdirectory is one font (font files may be nested inside it). Font
files sitting directly in the top-level directory are grouped by the part of
their name before the first ``-`` (``Acme-Bold.otf`` -> ``Acme``).
"""

import os
import shutil
from collections import defaultdict
from pathlib import Path

from fontain.sources.archives import FORMAT_PREFERENCE, pick_fonts
from fontain.sources.base import FontEntry, Selection, SourceError
from fontain.sources.filenames import basename, variants_of


def _font_files(root: Path, base: Path) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for f in sorted(filenames):
            if f.lower().endswith(FORMAT_PREFERENCE) and not f.startswith("."):
                out.append(str((Path(dirpath) / f).relative_to(base)))
    return out


def scan(source: str, root: Path) -> list[FontEntry]:
    groups: dict[str, list[str]] = defaultdict(list)
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            groups[child.name].extend(_font_files(child, root))
        elif child.name.lower().endswith(FORMAT_PREFERENCE):
            groups[child.name.split("-", 1)[0].rsplit(".", 1)[0]].append(child.name)
    entries = []
    for font_id, files in sorted(groups.items()):
        picked = pick_fonts(files)
        if not picked:
            continue
        weights, styles = variants_of(picked)
        entries.append(
            FontEntry(
                source=source,
                id=font_id,
                family=font_id,
                weights=weights,
                styles=styles,
                extra={"paths": picked},
            )
        )
    return entries


class LocalDirSource:
    kind = "local"
    cacheable = False  # scanning is cheap; always reflect the directory as it is

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = Path(path)

    def _root(self) -> Path:
        if not self.path.is_dir():
            raise SourceError(f"repository {self.name!r}: directory {self.path} not found")
        return self.path

    def fetch_index(self) -> list[FontEntry]:
        return scan(self.name, self._root())

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        root = self._root()
        files = [
            Path(shutil.copy2(root / p, dest / basename(p))) for p in pick_fonts(entry.extra["paths"], sel)
        ]
        if not files:
            raise SourceError(f"no font files of {entry.key} match the requested weights/styles")
        return files

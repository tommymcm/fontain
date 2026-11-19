"""Pick font files out of archives and file listings."""

import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from fontain.sources.base import ALL_VARIANTS, Selection
from fontain.sources.filenames import basename, parse_filename

# Only one format is installed per font so fontconfig doesn't see duplicates.
FORMAT_PREFERENCE = (".ttf", ".otf", ".ttc")


def pick_fonts(paths: Iterable[str], sel: Selection = ALL_VARIANTS) -> list[str]:
    """Choose which of ``paths`` to install.

    Keeps the most preferred font format present, honours ``sel``, skips
    hidden/macOS metadata files and drops duplicate basenames (first wins).
    """
    candidates = [
        p
        for p in paths
        if not any(part.startswith(".") or part == "__MACOSX" for part in PurePosixPath(p).parts)
    ]
    for ext in FORMAT_PREFERENCE:
        of_type = [p for p in candidates if p.lower().endswith(ext)]
        if of_type:
            break
    else:
        return []
    seen: set[str] = set()
    out = []
    for p in of_type:
        name = basename(p)
        if name in seen or not sel.wants(*parse_filename(name)):
            continue
        seen.add(name)
        out.append(p)
    return out


def extract_fonts(archive: Path, dest: Path, sel: Selection = ALL_VARIANTS) -> list[Path]:
    """Extract font files from a zip or tar archive into ``dest``.

    Members are flattened to their basename, so nothing can escape ``dest``,
    and only regular files are read (no links or devices).
    """
    written = []
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = {i.filename: i for i in zf.infolist() if not i.is_dir() and not _zip_symlink(i)}
            for name in pick_fonts(infos, sel):
                target = dest / basename(name)
                with zf.open(infos[name]) as src, target.open("wb") as out:
                    out.write(src.read())
                written.append(target)
        return written
    with tarfile.open(archive, "r:*") as tar:
        members = {m.name: m for m in tar.getmembers() if m.isfile()}
        for name in pick_fonts(members, sel):
            member = tar.extractfile(members[name])
            if member is None:
                continue
            target = dest / basename(name)
            with member, target.open("wb") as out:
                out.write(member.read())
            written.append(target)
    return written


def _zip_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000

"""Nerd Fonts (https://www.nerdfonts.com), from GitHub release tarballs."""

import hashlib
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from fontain import net
from fontain.sources.base import FontEntry, Selection, SourceError
from fontain.sources.google import parse_filename

RELEASE = "https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest"
SUFFIX = ".tar.xz"
FONT_EXTS = (".ttf", ".otf")


def parse_index(release: dict[str, Any]) -> list[FontEntry]:
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    checksums = assets.get("SHA-256.txt")
    out = []
    for name, url in sorted(assets.items()):
        if not name.endswith(SUFFIX):
            continue
        font_id = name[: -len(SUFFIX)]
        out.append(
            FontEntry(
                source=NerdFontsSource.name,
                id=font_id,
                family=f"{font_id} Nerd Font",
                category="monospace",
                license="see archive",
                extra={"url": url, "checksums": checksums, "version": release.get("tag_name", "")},
            )
        )
    return out


def parse_checksums(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1].lstrip("*")] = parts[0].lower()
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_fonts(archive: Path, dest: Path, sel: Selection) -> list[Path]:
    """Extract only regular font files, flattened to their basename.

    Flattening means no member path can escape ``dest``.
    """
    written = []
    with tarfile.open(archive, "r:xz") as tar:
        for member in tar:
            base = PurePosixPath(member.name).name
            if not member.isfile() or not base.lower().endswith(FONT_EXTS) or base.startswith("."):
                continue
            if not sel.wants(*parse_filename(base)):
                continue
            src = tar.extractfile(member)
            if src is None:
                continue
            target = dest / base
            with src, target.open("wb") as out:
                out.write(src.read())
            written.append(target)
    return written


class NerdFontsSource:
    name = "nerd"

    def fetch_index(self) -> list[FontEntry]:
        return parse_index(net.get_json(RELEASE))

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        url = entry.extra.get("url")
        if not url:
            raise SourceError(f"no download URL for {entry.key}; try `fontain refresh`")
        with tempfile.TemporaryDirectory(prefix="fontain-") as tmp:
            archive = net.download(url, Path(tmp) / f"{entry.id}{SUFFIX}")
            if checksums_url := entry.extra.get("checksums"):
                expected = parse_checksums(net.get_text(checksums_url)).get(archive.name)
                if expected and sha256(archive) != expected:
                    raise SourceError(f"checksum mismatch for {archive.name}")
            files = extract_fonts(archive, dest, sel)
        if not files:
            raise SourceError(f"no font files of {entry.key} match the requested weights/styles")
        return files

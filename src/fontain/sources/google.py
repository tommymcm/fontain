"""Google Fonts, fetched directly from the google/fonts GitHub repository."""

import re
from pathlib import Path
from typing import Any

from fontain import net
from fontain.sources.base import FontEntry, Selection, SourceError
from fontain.sources.filenames import parse_filename

METADATA = "https://fonts.google.com/metadata/fonts"
CONTENTS = "https://api.github.com/repos/google/fonts/contents/{}"
LICENSE_DIRS = ("ofl", "apache", "ufl")
LICENSE_NAMES = {"ofl": "OFL-1.1", "apache": "Apache-2.0", "ufl": "UFL-1.0"}


def slugify(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def _variant(key: str) -> tuple[int, str]:
    """Metadata variant keys look like ``400`` or ``700i``."""
    return int(key.rstrip("i")), "italic" if key.endswith("i") else "normal"


def parse_index(data: dict[str, Any]) -> list[FontEntry]:
    out = []
    for f in data.get("familyMetadataList", []):
        variants = [_variant(k) for k in f.get("fonts", {})]
        out.append(
            FontEntry(
                source=GoogleSource.name,
                id=slugify(f["family"]),
                family=f["family"],
                category=f.get("category", "").lower().replace(" ", "-"),
                weights=tuple(sorted({w for w, _ in variants})),
                styles=tuple(s for s in ("normal", "italic") if any(v[1] == s for v in variants)),
                extra={"variable": bool(f.get("axes"))},
            )
        )
    return out


def select_files(listing: list[dict[str, Any]], sel: Selection) -> list[tuple[str, str]]:
    fonts = [f for f in listing if f.get("type") == "file" and f["name"].endswith(".ttf")]
    picked = [f for f in fonts if sel.wants(*parse_filename(f["name"]))]
    licenses = [
        f for f in listing if f.get("type") == "file" and f["name"] in ("OFL.txt", "LICENSE.txt", "UFL.txt")
    ]
    return [(f["name"], f["download_url"]) for f in picked + (licenses if picked else [])]


class GoogleSource:
    name = "google"

    def fetch_index(self) -> list[FontEntry]:
        return parse_index(net.get_json(METADATA))

    def _listing(self, entry: FontEntry) -> tuple[str, list[dict[str, Any]]]:
        for lic in LICENSE_DIRS:
            try:
                return lic, net.get_json(CONTENTS.format(f"{lic}/{entry.id}"))
            except net.NetError as e:
                if e.status != 404:
                    raise
        raise SourceError(f"could not find {entry.family} in the google/fonts repository")

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        _, listing = self._listing(entry)
        files = select_files(listing, sel)
        if not files:
            raise SourceError(f"no files of {entry.key} match the requested weights/styles")
        return [net.download(url, dest / name) for name, url in files]

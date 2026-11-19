"""Fontsource (https://fontsource.org): Google Fonts plus other open fonts."""

from pathlib import Path
from typing import Any

from fontain import net
from fontain.sources.base import FontEntry, Selection, SourceError

API = "https://api.fontsource.org/v1/fonts"


def parse_index(data: list[dict[str, Any]]) -> list[FontEntry]:
    return [
        FontEntry(
            source=FontsourceSource.name,
            id=f["id"],
            family=f["family"],
            category=f.get("category", ""),
            license=f.get("license", ""),
            weights=tuple(f.get("weights", ())),
            styles=tuple(f.get("styles", ())),
            version=f.get("lastModified", ""),
        )
        for f in data
    ]


def select_files(font: dict[str, Any], sel: Selection) -> list[tuple[str, str]]:
    """Return ``(filename, url)`` pairs for the requested variants."""
    preferred = font.get("defSubset") or "latin"
    out = []
    for weight, styles in font.get("variants", {}).items():
        for style, subsets in styles.items():
            if not sel.wants(int(weight), style):
                continue
            subset = preferred if preferred in subsets else next(iter(subsets), None)
            url = subsets.get(subset, {}).get("url", {}).get("ttf") if subset else None
            if url:
                out.append((f"{font['id']}-{weight}-{style}.ttf", url))
    return out


class FontsourceSource:
    name = "fontsource"

    def fetch_index(self) -> list[FontEntry]:
        return parse_index(net.get_json(API))

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        font = net.get_json(f"{API}/{entry.id}")
        files = select_files(font, sel)
        if not files:
            raise SourceError(f"no variants of {entry.key} match the requested weights/styles")
        return [net.download(url, dest / name) for name, url in files]

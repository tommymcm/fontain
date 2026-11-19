"""Shared test doubles. Importable from tests as `helpers` (pytest puts tests/ on sys.path)."""

from fontain import store
from fontain.sources.base import FontEntry


def entry(font_id: str, family: str | None = None, source: str = "fake", **kw) -> FontEntry:
    return FontEntry(source=source, id=font_id, family=family or font_id.title(), **kw)


class FakeSource:
    """An offline source: `install` writes one `<id>-Regular.ttf` per font."""

    name = "fake"

    def __init__(self, *entries: FontEntry):
        self.entries = list(entries) or [entry("mono")]

    def fetch_index(self) -> list[FontEntry]:
        return list(self.entries)

    def install_files(self, entry, dest, sel):
        f = dest / f"{entry.id}-Regular.ttf"
        f.write_bytes(b"x")
        return [f]


def write_manifest(*keys: str) -> None:
    """Pretend fontain installed these `source:id` fonts (family = id)."""
    store.save_manifest(
        {
            key: {
                "source": key.split(":", 1)[0],
                "id": key.split(":", 1)[1],
                "family": key.split(":", 1)[1],
                "files": [],
                "installed": "",
            }
            for key in keys
        }
    )

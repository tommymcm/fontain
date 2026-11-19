"""Common types shared by all font sources."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


class SourceError(Exception):
    pass


@dataclass(frozen=True)
class FontEntry:
    source: str
    id: str
    family: str
    category: str = ""
    license: str = ""
    weights: tuple[int, ...] = ()
    styles: tuple[str, ...] = ()
    # Changes whenever the source publishes different files for this font (a
    # release tag, a modification date, a content fingerprint). "" = unknown.
    version: str = ""
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    def variants_summary(self) -> str:
        parts = []
        if self.weights:
            parts.append(",".join(str(w) for w in self.weights))
        if self.styles:
            parts.append("/".join(self.styles))
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FontEntry":
        d = dict(d)
        d["weights"] = tuple(d.get("weights") or ())
        d["styles"] = tuple(d.get("styles") or ())
        return cls(**d)


@dataclass(frozen=True)
class Selection:
    """User filter on which variants to install; empty means everything."""

    weights: frozenset[int] = frozenset()
    styles: frozenset[str] = frozenset()

    def wants(self, weight: int | None, style: str | None) -> bool:
        """Unknown weights/styles (None) are always wanted, e.g. variable fonts."""
        if self.weights and weight is not None and weight not in self.weights:
            return False
        return not (self.styles and style is not None and style not in self.styles)


ALL_VARIANTS = Selection()


class Source(Protocol):
    name: str

    def fetch_index(self) -> list[FontEntry]:
        """Download the full list of fonts this source offers."""
        ...

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        """Download the font files for ``entry`` into ``dest``; return written paths."""
        ...

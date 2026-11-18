"""Registry of font sources, in bare-name resolution priority order.

Built-in sources come first, followed by user repositories in the order
they were added.
"""

from typing import Any

from fontain.sources.base import FontEntry, Selection, Source, SourceError
from fontain.sources.fontsource import FontsourceSource
from fontain.sources.github import GitHubRepoSource
from fontain.sources.google import GoogleSource
from fontain.sources.local import LocalDirSource
from fontain.sources.nerdfonts import NerdFontsSource

SOURCES: dict[str, Source] = {
    s.name: s for s in (FontsourceSource(), GoogleSource(), NerdFontsSource())
}


def make_source(name: str, cfg: dict[str, Any]) -> Source:
    match cfg.get("type"):
        case "github":
            return GitHubRepoSource(name, cfg["target"])
        case "local":
            return LocalDirSource(name, cfg["target"])
    raise SourceError(f"repository {name!r} has unknown type {cfg.get('type')!r}")


def registry() -> dict[str, Source]:
    """All sources: built-ins plus the user's configured repositories."""
    from fontain import repos

    out: dict[str, Source] = dict(SOURCES)
    for name, cfg in repos.load().items():
        if name not in out:
            out[name] = make_source(name, cfg)
    return out


__all__ = ["SOURCES", "FontEntry", "Selection", "Source", "SourceError", "make_source", "registry"]

"""Registry of available font sources, in bare-id resolution priority order."""

from fontain.sources.base import FontEntry, Selection, Source, SourceError
from fontain.sources.fontsource import FontsourceSource
from fontain.sources.google import GoogleSource
from fontain.sources.nerdfonts import NerdFontsSource

SOURCES: dict[str, Source] = {
    s.name: s for s in (FontsourceSource(), GoogleSource(), NerdFontsSource())
}

__all__ = ["SOURCES", "FontEntry", "Selection", "Source", "SourceError"]

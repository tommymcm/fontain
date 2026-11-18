"""Per-source font indexes, cached on disk, plus search and name resolution."""

import json
import os
import sys
import time
from dataclasses import dataclass

from fontain import net, paths
from fontain.sources import SOURCES, FontEntry

TTL_SECONDS = 24 * 3600


def _cache_path(source: str):
    return paths.cache_dir() / f"{source}.json"


def refresh(source: str) -> list[FontEntry]:
    entries = SOURCES[source].fetch_index()
    path = _cache_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps([e.to_dict() for e in entries]))
    os.replace(tmp, path)
    return entries


def load(source: str, max_age: float = TTL_SECONDS) -> list[FontEntry]:
    """Return the index for ``source``, re-fetching it when stale.

    If fetching fails but an old cache exists, the stale copy is used.
    """
    path = _cache_path(source)
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age
    if not fresh:
        try:
            print(f"Fetching {source} index...", file=sys.stderr)
            return refresh(source)
        except (net.NetError, ValueError, KeyError) as e:
            if not path.exists():
                raise
            print(f"warning: {e}; using cached {source} index", file=sys.stderr)
    return [FontEntry.from_dict(d) for d in json.loads(path.read_text())]


def load_many(sources: list[str]) -> dict[str, list[FontEntry]]:
    """Load several indexes, warning about (and skipping) any that fail."""
    out = {}
    for name in sources:
        try:
            out[name] = load(name)
        except (net.NetError, ValueError, KeyError) as e:
            print(f"warning: skipping {name}: {e}", file=sys.stderr)
    return out


def search(entries: list[FontEntry], query: str) -> list[FontEntry]:
    q = query.lower().replace(" ", "")

    def rank(e: FontEntry) -> int | None:
        names = (e.id.lower(), e.family.lower().replace(" ", ""))
        if q in names:
            return 0
        if any(n.startswith(q) for n in names):
            return 1
        if any(q in n for n in names):
            return 2
        return None

    scored = [(r, e) for e in entries if (r := rank(e)) is not None]
    scored.sort(key=lambda t: (t[0], len(t[1].id), t[1].id.lower()))
    return [e for _, e in scored]


class ResolveError(Exception):
    pass


@dataclass
class Resolved:
    entry: FontEntry
    alternatives: list[FontEntry]


def _match(entries: list[FontEntry], name: str) -> FontEntry | None:
    n = name.lower().replace(" ", "")
    for e in entries:
        if e.id.lower() == n or e.family.lower().replace(" ", "") == n:
            return e
    return None


def resolve(spec: str, indexes: dict[str, list[FontEntry]]) -> Resolved:
    """Turn ``source:id`` or a bare id/family into a FontEntry."""
    source, sep, name = spec.partition(":")
    if sep:
        if source not in SOURCES:
            raise ResolveError(f"unknown source {source!r} (choose from {', '.join(SOURCES)})")
        if source not in indexes:
            raise ResolveError(f"{source} index is unavailable")
        if entry := _match(indexes[source], name):
            return Resolved(entry, [])
        raise ResolveError(f"no font {name!r} in {source}; try `fontain search {name}`")

    hits = [e for src in SOURCES if src in indexes and (e := _match(indexes[src], spec))]
    if not hits:
        raise ResolveError(f"no font named {spec!r}; try `fontain search {spec}`")
    return Resolved(hits[0], hits[1:])

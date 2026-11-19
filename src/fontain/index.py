"""Per-source font indexes, cached on disk, plus search and name resolution."""

import json
import sys
import time
from dataclasses import dataclass

from fontain import jsonfile, net, paths, sources
from fontain.sources import FontEntry, SourceError

TTL_SECONDS = 24 * 3600


def _cache_path(source: str):
    return paths.cache_dir() / f"{source}.json"


def write_cache(source: str, entries: list[FontEntry]) -> None:
    jsonfile.write(_cache_path(source), [e.to_dict() for e in entries], indent=None)


def drop_cache(source: str) -> None:
    _cache_path(source).unlink(missing_ok=True)


def refresh(source: str) -> list[FontEntry]:
    src = sources.registry()[source]
    entries = src.fetch_index()
    if getattr(src, "cacheable", True):
        write_cache(source, entries)
    return entries


def load(source: str, max_age: float = TTL_SECONDS) -> list[FontEntry]:
    """Return the index for ``source``, re-fetching it when stale.

    If fetching fails but an old cache exists, the stale copy is used.
    """
    src = sources.registry()[source]
    if not getattr(src, "cacheable", True):
        return src.fetch_index()
    path = _cache_path(source)
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age
    if not fresh:
        try:
            print(f"Fetching {source} index...", file=sys.stderr)
            return refresh(source)
        except (net.NetError, SourceError, ValueError, KeyError) as e:
            if not path.exists():
                raise
            print(f"warning: {e}; using cached {source} index", file=sys.stderr)
    return [FontEntry.from_dict(d) for d in json.loads(path.read_text())]


def load_many(names: list[str]) -> dict[str, list[FontEntry]]:
    """Load several indexes, warning about (and skipping) any that fail."""
    out = {}
    for name in names:
        try:
            out[name] = load(name)
        except (net.NetError, SourceError, OSError, ValueError, KeyError) as e:
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

    priority = {name: i for i, name in enumerate(sources.registry())}
    scored = [(r, e) for e in entries if (r := rank(e)) is not None]
    # Same family from different sources sorts together, in source priority order.
    scored.sort(key=lambda t: (t[0], len(t[1].family), t[1].family.lower(), priority.get(t[1].source, 99)))
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
    known = sources.registry()
    source, sep, name = spec.partition(":")
    if sep:
        if source not in known:
            raise ResolveError(f"unknown source {source!r} (choose from {', '.join(known)})")
        if source not in indexes:
            raise ResolveError(f"{source} index is unavailable")
        if entry := _match(indexes[source], name):
            return Resolved(entry, [])
        raise ResolveError(f"no font {name!r} in {source}; try `fontain search {name}`")

    hits = [e for src in known if src in indexes and (e := _match(indexes[src], spec))]
    if not hits:
        raise ResolveError(f"no font named {spec!r}; try `fontain search {spec}`")
    return Resolved(hits[0], hits[1:])


def cached_ids(source: str) -> list[str]:
    """Font ids from the on-disk cache only (never fetches); for completion."""
    try:
        return [d["id"] for d in json.loads(_cache_path(source).read_text())]
    except (OSError, ValueError, KeyError, TypeError):
        return []

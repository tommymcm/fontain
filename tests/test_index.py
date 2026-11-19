import json
import os

import pytest

from fontain import index, net, paths, sources
from fontain.sources.base import FontEntry


def E(source, id, family=None):
    return FontEntry(source=source, id=id, family=family or id)


INDEXES = {
    "fontsource": [
        E("fontsource", "roboto", "Roboto"),
        E("fontsource", "roboto-mono", "Roboto Mono"),
        E("fontsource", "inter", "Inter"),
    ],
    "google": [E("google", "roboto", "Roboto"), E("google", "notoserifroboto", "Noto Serif Roboto")],
    "nerd": [E("nerd", "JetBrainsMono", "JetBrainsMono Nerd Font")],
}


def test_search_ranking():
    entries = [e for es in INDEXES.values() for e in es]
    keys = [e.key for e in index.search(entries, "roboto")]
    assert keys[:2] == ["fontsource:roboto", "google:roboto"]
    assert keys.index("fontsource:roboto-mono") < keys.index("google:notoserifroboto")
    assert index.search(entries, "zzz") == []
    assert [e.key for e in index.search(entries, "roboto mono")] == ["fontsource:roboto-mono"]


def test_resolve_bare_prefers_fontsource():
    r = index.resolve("roboto", INDEXES)
    assert r.entry.key == "fontsource:roboto"
    assert [a.key for a in r.alternatives] == ["google:roboto"]


def test_resolve_qualified_and_case():
    assert index.resolve("google:roboto", INDEXES).entry.key == "google:roboto"
    assert index.resolve("nerd:jetbrainsmono", INDEXES).entry.key == "nerd:JetBrainsMono"
    assert index.resolve("Roboto Mono", INDEXES).entry.key == "fontsource:roboto-mono"


@pytest.mark.parametrize("spec", ["nope", "bogus:roboto", "nerd:roboto"])
def test_resolve_errors(spec):
    with pytest.raises(index.ResolveError):
        index.resolve(spec, INDEXES)


def test_load_uses_cache_and_stale_fallback(monkeypatch):
    calls = []

    class Src:
        name = "fontsource"

        def fetch_index(self):
            calls.append(1)
            if len(calls) > 1:
                raise net.NetError("offline")
            return [E("fontsource", "inter")]

    monkeypatch.setattr(sources, "registry", lambda: {"fontsource": Src()})
    assert [e.id for e in index.load("fontsource")] == ["inter"]
    assert [e.id for e in index.load("fontsource")] == ["inter"]
    assert len(calls) == 1  # second load came from cache

    cache = paths.cache_dir() / "fontsource.json"
    os.utime(cache, (0, 0))  # make it stale
    assert [e.id for e in index.load("fontsource")] == ["inter"]  # stale fallback
    assert len(calls) == 2
    assert json.loads(cache.read_text())[0]["id"] == "inter"

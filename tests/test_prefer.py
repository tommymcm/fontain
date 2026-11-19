import pytest

from fontain import cli, index, repos, sources
from fontain.sources.base import FontEntry


class Src:
    def __init__(self, name):
        self.name = name

    def fetch_index(self):
        return [FontEntry(source=self.name, id="roboto", family="Roboto")]


@pytest.fixture
def fake(monkeypatch):
    builtins = {n: Src(n) for n in ("fontsource", "google", "nerd")}
    monkeypatch.setattr(sources, "SOURCES", builtins)
    monkeypatch.setattr(cli, "SOURCES", builtins)
    monkeypatch.setattr(sources, "make_source", lambda name, cfg: Src(name))
    repos.save({"mine": {"type": "local", "target": "/x"}})
    monkeypatch.delenv("FONTAIN_PREFER", raising=False)


def _resolve():
    reg = sources.registry()
    indexes = {n: s.fetch_index() for n, s in reg.items()}
    r = index.resolve("roboto", indexes)
    return r.entry.source, [a.source for a in r.alternatives]


def test_default_order(fake):
    assert list(sources.registry()) == ["fontsource", "google", "nerd", "mine"]
    assert _resolve() == ("fontsource", ["google", "nerd", "mine"])


@pytest.mark.parametrize("pref", ["mine", "google"])
def test_preferred_first(fake, pref, capsys):
    assert cli.main(["repo", "prefer", pref]) == 0
    assert next(iter(sources.registry())) == pref
    assert _resolve()[0] == pref
    assert cli.main(["repo", "prefer"]) == 0
    assert capsys.readouterr().out.strip().endswith(pref)
    cli.main(["repo"])
    assert f"* {pref}" in capsys.readouterr().out


def test_env_override(fake, monkeypatch):
    repos.set_preferred("google")
    monkeypatch.setenv("FONTAIN_PREFER", "nerd")
    assert _resolve()[0] == "nerd"


def test_unknown_and_clear(fake):
    assert cli.main(["repo", "prefer", "nope"]) == 2
    assert repos.preferred() is None
    cli.main(["repo", "prefer", "google"])
    assert cli.main(["repo", "prefer", "--clear"]) == 0
    assert repos.preferred() is None


def test_removing_preferred_repo_clears(fake):
    cli.main(["repo", "prefer", "mine"])
    assert cli.main(["repo", "rm", "mine"]) == 0
    assert repos.preferred() is None


def test_stale_preference_ignored(fake):
    repos.set_preferred("gone")
    assert next(iter(sources.registry())) == "fontsource"

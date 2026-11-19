import pytest
from helpers import FakeSource, entry

from fontain import cli, fontcache, sources, store

FONT = entry("mono", "Fake Mono", category="monospace", weights=(400, 700), styles=("normal",))


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(sources, "registry", lambda: {"fake": FakeSource(FONT)})
    calls = []
    monkeypatch.setattr(fontcache, "refresh", lambda root, quiet=False: calls.append(root) or True)
    return calls


def test_full_flow(fake, capsys):
    assert cli.main(["search", "mono"]) == 0
    assert "fake:mono" in capsys.readouterr().out

    assert cli.main(["install", "mono"]) == 0
    assert len(fake) == 1
    assert store.is_installed("fake:mono")

    assert cli.main(["install", "fake:mono"]) == 0  # no-op
    assert len(fake) == 1

    assert cli.main(["search", "mono"]) == 0
    assert "* fake:mono" in capsys.readouterr().out

    assert cli.main(["list"]) == 0
    assert "Fake Mono" in capsys.readouterr().out

    assert cli.main(["info", "Fake Mono"]) == 0
    assert "Installed:" in capsys.readouterr().out

    assert cli.main(["remove", "fakemono"]) == 0
    assert len(fake) == 2
    assert not store.is_installed("fake:mono")


def test_errors(fake, capsys):
    assert cli.main(["install", "nope", "--no-cache"]) == 1
    assert cli.main(["remove", "mono"]) == 1
    assert cli.main(["search", "zzz"]) == 1
    assert fake == []


def test_bad_args():
    with pytest.raises(SystemExit):
        cli.main(["install", "x", "--weights", "bold"])
    with pytest.raises(SystemExit):
        cli.main(["install", "x", "--styles", "oblique"])

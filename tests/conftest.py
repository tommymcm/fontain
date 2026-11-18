import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    """Never touch the real font, cache or state directories."""
    monkeypatch.setenv("FONTAIN_FONT_DIR", str(tmp_path / "fonts"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never reach the internet."""
    from fontain import net

    def blocked(url):
        raise net.NetError(f"network disabled in tests: {url}")

    monkeypatch.setattr(net, "_open", blocked)

import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    """Never touch the real font, cache or state directories."""
    monkeypatch.setenv("FONTAIN_FONT_DIR", str(tmp_path / "fonts"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path

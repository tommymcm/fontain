import sys

import pytest

from fontain import paths


@pytest.mark.skipif(sys.platform == "darwin", reason="linux layout")
def test_xdg_overrides(monkeypatch, tmp_path):
    monkeypatch.delenv("FONTAIN_FONT_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert paths.font_root() == tmp_path / "data" / "fonts" / "fontain"
    assert paths.cache_dir() == tmp_path / "cache" / "fontain"
    assert paths.state_file() == tmp_path / "state" / "fontain" / "installed.json"


def test_relative_xdg_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/dir")
    assert paths.cache_dir() == tmp_path / ".cache" / "fontain"

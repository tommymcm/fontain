import pytest

from fontain import paths, store
from fontain.sources.base import FontEntry, Selection, SourceError

ENTRY = FontEntry(source="fake", id="mono", family="Mono")


class FakeSource:
    name = "fake"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def install_files(self, entry, dest, sel):
        self.calls += 1
        f = dest / "Mono-Regular.ttf"
        f.write_bytes(b"font")
        if self.fail:
            raise SourceError("boom")
        return [f]


def test_install_and_remove():
    src = FakeSource()
    rec = store.install(ENTRY, src, Selection())
    target = paths.font_root() / "fake" / "mono"
    assert rec["files"] == ["Mono-Regular.ttf"]
    assert (target / "Mono-Regular.ttf").read_bytes() == b"font"
    assert store.is_installed("fake:mono")

    assert store.install(ENTRY, src, Selection()) is None  # already installed
    assert src.calls == 1
    assert store.install(ENTRY, src, Selection(), force=True) is not None
    assert src.calls == 2

    assert store.remove("fake:mono")
    assert not target.exists()
    assert not store.is_installed("fake:mono")
    assert not store.remove("fake:mono")


def test_failed_install_leaves_nothing():
    with pytest.raises(SourceError):
        store.install(ENTRY, FakeSource(fail=True), Selection())
    assert list((paths.font_root() / "fake").iterdir()) == []
    assert store.load_manifest() == {}


def test_path_traversal_rejected():
    with pytest.raises(store.StoreError):
        store.font_dir("fake", "../../etc")

import pytest

from fontain.sources.base import Selection, SourceError
from fontain.sources.local import LocalDirSource, scan


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "myfonts"
    (root / "Acme Sans" / "otf").mkdir(parents=True)
    (root / "Acme Sans" / "ttf").mkdir()
    (root / "Acme Sans" / "otf" / "AcmeSans-Regular.otf").write_bytes(b"o")
    (root / "Acme Sans" / "ttf" / "AcmeSans-Regular.ttf").write_bytes(b"r")
    (root / "Acme Sans" / "ttf" / "AcmeSans-Bold.ttf").write_bytes(b"b")
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("hi")
    (root / ".git").mkdir()
    (root / ".git" / "Junk-Regular.ttf").write_bytes(b"j")
    (root / "Loose-Regular.otf").write_bytes(b"l")
    (root / "Loose-Italic.otf").write_bytes(b"i")
    return root


def test_scan(repo):
    entries = {e.id: e for e in scan("mine", repo)}
    assert sorted(entries) == ["Acme Sans", "Loose"]
    assert entries["Acme Sans"].extra["paths"] == [
        "Acme Sans/ttf/AcmeSans-Bold.ttf",
        "Acme Sans/ttf/AcmeSans-Regular.ttf",
    ]
    assert entries["Acme Sans"].weights == (400, 700)
    assert entries["Loose"].styles == ("normal", "italic")


def test_install_copies(repo, tmp_path):
    src = LocalDirSource("mine", str(repo))
    entry = next(e for e in src.fetch_index() if e.id == "Acme Sans")
    dest = tmp_path / "dest"
    dest.mkdir()
    files = src.install_files(entry, dest, Selection(weights=frozenset({700})))
    assert [f.name for f in files] == ["AcmeSans-Bold.ttf"]
    assert (dest / "AcmeSans-Bold.ttf").read_bytes() == b"b"


def test_missing_dir(tmp_path):
    with pytest.raises(SourceError):
        LocalDirSource("mine", str(tmp_path / "gone")).fetch_index()


def test_version_changes_when_files_change(repo):
    def version():
        return next(e.version for e in scan("mine", repo) if e.id == "Acme Sans")

    before = version()
    assert before and version() == before  # stable while nothing changes
    bold = repo / "Acme Sans" / "ttf" / "AcmeSans-Bold.ttf"
    bold.write_bytes(b"bold v2")  # new content (and size)
    assert version() != before
    changed = version()
    (repo / "Acme Sans" / "ttf" / "AcmeSans-Black.ttf").write_bytes(b"k")  # a file added
    assert version() != changed

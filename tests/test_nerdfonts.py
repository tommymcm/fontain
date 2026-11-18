import io
import tarfile

from fontain.sources.base import Selection
from fontain.sources.nerdfonts import extract_fonts, parse_checksums, parse_index


def test_parse_index():
    release = {"tag_name": "v3.5.1", "assets": [
        {"name": "JetBrainsMono.tar.xz", "browser_download_url": "https://dl/JetBrainsMono.tar.xz"},
        {"name": "JetBrainsMono.zip", "browser_download_url": "https://dl/JetBrainsMono.zip"},
        {"name": "SHA-256.txt", "browser_download_url": "https://dl/SHA-256.txt"},
    ]}
    (e,) = parse_index(release)
    assert e.key == "nerd:JetBrainsMono"
    assert e.extra["checksums"] == "https://dl/SHA-256.txt"


def test_parse_checksums():
    assert parse_checksums("ABC  a.tar.xz\nbad line here x\n") == {"a.tar.xz": "abc"}


def _archive(path, members):
    with tarfile.open(path, "w:xz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("Evil-Link.ttf")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tar.addfile(link)


def test_extract_only_fonts_and_flatten(tmp_path):
    arc = tmp_path / "f.tar.xz"
    _archive(arc, {
        "Mono-Regular.ttf": b"r",
        "sub/Mono-Bold.otf": b"b",
        "../../escape-Regular.ttf": b"x",
        "README.md": b"readme",
        "LICENSE": b"l",
    })
    dest = tmp_path / "out"
    dest.mkdir()
    written = extract_fonts(arc, dest, Selection())
    assert sorted(p.name for p in written) == ["Mono-Bold.otf", "Mono-Regular.ttf", "escape-Regular.ttf"]
    assert sorted(p.name for p in dest.iterdir()) == sorted(p.name for p in written)
    assert not (tmp_path.parent / "escape-Regular.ttf").exists()


def test_extract_filtered(tmp_path):
    arc = tmp_path / "f.tar.xz"
    _archive(arc, {"Mono-Regular.ttf": b"r", "Mono-Bold.ttf": b"b"})
    dest = tmp_path / "out"
    dest.mkdir()
    written = extract_fonts(arc, dest, Selection(weights=frozenset({700})))
    assert [p.name for p in written] == ["Mono-Bold.ttf"]

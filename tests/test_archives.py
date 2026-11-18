import io
import stat
import tarfile
import zipfile

import pytest

from fontain.sources.archives import extract_fonts, pick_fonts
from fontain.sources.base import Selection


def test_pick_prefers_ttf_and_dedupes():
    paths = ["otf/A-Regular.otf", "ttf/A-Regular.ttf", "variable/A-Regular.ttf", "A.ttc",
             "__MACOSX/._A-Bold.ttf", ".hidden/A-Bold.ttf", "README.md"]
    assert pick_fonts(paths) == ["ttf/A-Regular.ttf"]
    assert pick_fonts(["x/A-Regular.otf", "A.ttc"]) == ["x/A-Regular.otf"]
    assert pick_fonts(["A.ttc"]) == ["A.ttc"]
    assert pick_fonts(["README.md"]) == []


def test_pick_filters_selection():
    paths = ["A-Regular.ttf", "A-Bold.ttf", "A-BoldItalic.ttf"]
    sel = Selection(weights=frozenset({700}), styles=frozenset({"normal"}))
    assert pick_fonts(paths, sel) == ["A-Bold.ttf"]


def _tar(path, members):
    with tarfile.open(path, "w:xz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("Evil-Link.ttf")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tar.addfile(link)


def _zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        link = zipfile.ZipInfo("Evil-Link.ttf")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "/etc/passwd")


@pytest.mark.parametrize("make,suffix", [(_tar, ".tar.xz"), (_zip, ".zip")])
def test_extract_only_fonts_and_flatten(tmp_path, make, suffix):
    arc = tmp_path / f"f{suffix}"
    make(arc, {
        "Mono-Regular.ttf": b"r",
        "sub/Mono-Bold.ttf": b"b",
        "otf/Mono-Bold.otf": b"o",
        "../../escape-Regular.ttf": b"x",
        "README.md": b"readme",
    })
    dest = tmp_path / "out"
    dest.mkdir()
    written = extract_fonts(arc, dest)
    assert sorted(p.name for p in written) == ["Mono-Bold.ttf", "Mono-Regular.ttf"]  # "../" paths skipped
    assert sorted(p.name for p in dest.iterdir()) == sorted(p.name for p in written)
    assert (dest / "Mono-Bold.ttf").read_bytes() == b"b"
    assert not (tmp_path.parent / "escape-Regular.ttf").exists()


def test_extract_filtered(tmp_path):
    arc = tmp_path / "f.zip"
    _zip(arc, {"Mono-Regular.ttf": b"r", "Mono-Bold.ttf": b"b"})
    dest = tmp_path / "out"
    dest.mkdir()
    assert [p.name for p in extract_fonts(arc, dest, Selection(weights=frozenset({700})))] == ["Mono-Bold.ttf"]

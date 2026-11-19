import base64
import webbrowser

import pytest
from helpers import FakeSource, entry, write_manifest

from fontain import cli, preview, sources, store


def make(tmp_path, *names):
    out = []
    for name in names:
        f = tmp_path / name
        f.write_bytes(name.encode())
        out.append(f)
    return out


def test_faces_order_labels_and_skips(tmp_path):
    files = make(
        tmp_path,
        "X-BoldItalic.ttf",
        "X-Regular.ttf",
        "X[wght].ttf",
        "X-Italic.otf",
        "X-Bold.ttf",
        "OFL.txt",
        "X.ttc",
        "Plain.ttf",
    )
    labels = [(f.path.name, f.label) for f in preview.faces(files)]
    assert labels == [
        ("Plain.ttf", "Regular"),  # no weight in the name: treated as Regular
        ("X-Regular.ttf", "Regular"),
        ("X-Bold.ttf", "Bold"),
        ("X-Italic.otf", "Italic"),
        ("X-BoldItalic.ttf", "Bold Italic"),
        ("X[wght].ttf", "Variable"),
    ]  # licence text and .ttc (unsupported by browsers) are skipped


def test_build_html_embeds_fonts_and_escapes(tmp_path):
    files = make(tmp_path, "X-Regular.ttf", "X[wght].ttf")
    page = preview.build_html("<Evil> Sans", "fake:x · installed", files)
    assert f"url(data:font/ttf;base64,{base64.b64encode(b'X-Regular.ttf').decode()})" in page
    assert "font-weight: 1 1000" in page  # the variable font covers every weight
    assert "&lt;Evil&gt; Sans" in page and "<Evil>" not in page
    for name in ("title", "subtitle", "font_faces", "cards", "count", "samples"):
        assert f"${name}" not in page  # every template placeholder was filled
    assert 'class="sample icons"' not in page
    assert 'class="sample icons"' in preview.build_html("N", "n", files, icons=True)


def test_build_html_needs_a_browser_font(tmp_path):
    with pytest.raises(ValueError):
        preview.build_html("X", "x", make(tmp_path, "OFL.txt", "X.ttc"))


def test_page_path_is_safe():
    path = preview.page_path("work:Acme Sans/../x")
    assert path.parent.name == "previews" and "/" not in path.name and " " not in path.name


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(webbrowser, "open", lambda url: urls.append(url) or True)
    return urls


def test_preview_installed_font_uses_its_files(tmp_path, opened, capsys):
    write_manifest("fake:mono")
    folder = store.font_dir("fake", "mono")
    folder.mkdir(parents=True)
    for name in ("Mono-Regular.ttf", "Mono-Bold.ttf"):
        (folder / name).write_bytes(name.encode())
    manifest = store.load_manifest()
    manifest["fake:mono"]["files"] = ["Mono-Bold.ttf", "Mono-Regular.ttf"]
    store.save_manifest(manifest)

    assert cli.main(["preview", "mono", "-w", "700"]) == 0
    page = preview.page_path("fake:mono")
    assert opened == [page.as_uri()]
    html = page.read_text()
    assert "Mono-Bold.ttf" in html and "Mono-Regular.ttf" not in html  # -w 700 applied
    assert "fake:mono · installed" in html


def test_preview_downloads_fonts_that_are_not_installed(monkeypatch, opened, capsys):
    source = FakeSource(entry("serif", "Fake Serif"))
    monkeypatch.setattr(sources, "registry", lambda: {"fake": source})
    assert cli.main(["preview", "fake:serif"]) == 0
    html = preview.page_path("fake:serif").read_text()
    assert "Fake Serif" in html and "not installed" in html and "serif-Regular.ttf" in html
    assert store.load_manifest() == {}  # previewing never installs


def test_no_open_and_browser_failures(monkeypatch, opened, capsys):
    monkeypatch.setattr(sources, "registry", lambda: {"fake": FakeSource()})
    assert cli.main(["preview", "--no-open", "fake:mono"]) == 0
    assert opened == []
    assert f"Preview: {preview.page_path('fake:mono')}" in capsys.readouterr().out
    monkeypatch.setattr(webbrowser, "open", lambda url: False)
    assert cli.main(["preview", "fake:mono"]) == 0
    assert "couldn't open a browser" in capsys.readouterr().out


def test_unknown_font(monkeypatch, opened, capsys):
    monkeypatch.setattr(sources, "registry", lambda: {"fake": FakeSource()})
    assert cli.main(["preview", "nope"]) == 1
    assert "no font named 'nope'" in capsys.readouterr().err
    assert opened == []

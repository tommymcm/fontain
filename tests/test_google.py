from fontain.sources.base import Selection
from fontain.sources.google import parse_index, select_files, slugify


def test_slugify():
    assert slugify("Roboto Mono") == "robotomono"
    assert slugify("M PLUS 1p") == "mplus1p"


def test_parse_index():
    data = {
        "familyMetadataList": [
            {
                "family": "Lato",
                "category": "Sans Serif",
                "fonts": {"400": {}, "400i": {}, "700": {}},
                "axes": [],
                "lastModified": "2025-09-08",
            },
        ]
    }
    (e,) = parse_index(data)
    assert e.key == "google:lato"
    assert e.category == "sans-serif"
    assert e.weights == (400, 700)
    assert e.styles == ("normal", "italic")
    assert e.version == "2025-09-08"


def _f(name):
    return {"name": name, "type": "file", "download_url": f"https://raw/{name}"}


LISTING = [
    _f(n) for n in ("Lato-Regular.ttf", "Lato-Bold.ttf", "Lato-BoldItalic.ttf", "OFL.txt", "METADATA.pb")
]


def test_select_all_includes_license():
    names = [n for n, _ in select_files(LISTING, Selection())]
    assert names == ["Lato-Regular.ttf", "Lato-Bold.ttf", "Lato-BoldItalic.ttf", "OFL.txt"]


def test_select_filtered():
    sel = Selection(weights=frozenset({700}), styles=frozenset({"normal"}))
    assert [n for n, _ in select_files(LISTING, sel)] == ["Lato-Bold.ttf", "OFL.txt"]


def test_select_nothing_skips_license():
    assert select_files(LISTING, Selection(weights=frozenset({100}))) == []

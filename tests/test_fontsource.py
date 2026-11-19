from fontain.sources.base import Selection
from fontain.sources.fontsource import parse_index, select_files

INDEX = [
    {
        "id": "inter",
        "family": "Inter",
        "category": "sans-serif",
        "license": "OFL-1.1",
        "weights": [400, 700],
        "styles": ["normal", "italic"],
        "type": "google",
    },
]

FONT = {
    "id": "inter",
    "defSubset": "latin",
    "variants": {
        "400": {
            "normal": {
                "cyrillic": {"url": {"ttf": "https://x/cyr-400-normal.ttf"}},
                "latin": {"url": {"ttf": "https://x/latin-400-normal.ttf"}},
            },
            "italic": {"greek": {"url": {"ttf": "https://x/greek-400-italic.ttf"}}},
        },
        "700": {"normal": {"latin": {"url": {"ttf": "https://x/latin-700-normal.ttf"}}}},
    },
}


def test_parse_index():
    (e,) = parse_index(INDEX)
    assert e.key == "fontsource:inter"
    assert e.weights == (400, 700)
    assert e.variants_summary() == "400,700 normal/italic"


def test_select_all_prefers_default_subset():
    files = dict(select_files(FONT, Selection()))
    assert files == {
        "inter-400-normal.ttf": "https://x/latin-400-normal.ttf",
        "inter-400-italic.ttf": "https://x/greek-400-italic.ttf",
        "inter-700-normal.ttf": "https://x/latin-700-normal.ttf",
    }


def test_select_filtered():
    sel = Selection(weights=frozenset({700}), styles=frozenset({"normal"}))
    assert [n for n, _ in select_files(FONT, sel)] == ["inter-700-normal.ttf"]

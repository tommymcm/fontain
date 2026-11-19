import pytest

from fontain.sources.filenames import basename, parse_filename, variants_of


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Lato-Regular.ttf", (400, "normal")),
        ("Lato-Italic.ttf", (400, "italic")),
        ("Lato-ExtraBoldItalic.ttf", (800, "italic")),
        ("Lato-Thin.ttf", (100, "normal")),
        ("Inter[opsz,wght].ttf", (None, "normal")),
        ("MonaspaceNeon-SemiWideBold.otf", (700, "normal")),
        ("MonaspaceNeon-SemiWideSemiBold.otf", (600, "normal")),
        ("MonaspaceNeon-WideExtraLightItalic.otf", (200, "italic")),
        ("Foo-Condensed.ttf", (None, "normal")),
        ("Inter-Italic[opsz,wght].ttf", (None, "italic")),
    ],
)
def test_parse_filename(name, expected):
    assert parse_filename(name) == expected


def test_basename():
    assert basename("fonts/ttf/X-Regular.ttf") == "X-Regular.ttf"
    assert basename("dir\\X-Bold.ttf") == "X-Bold.ttf"


def test_variants_of():
    names = ["a/X-Regular.ttf", "X-BoldItalic.ttf", "X[wght].ttf"]
    assert variants_of(names) == ((400, 700), ("normal", "italic"))

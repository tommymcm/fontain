"""Reading weight and style from font file names, shared by all sources."""

from pathlib import PurePosixPath

WEIGHT_NAMES = {
    "thin": 100,
    "hairline": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "regular": 400,
    "": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}


def basename(path: str) -> str:
    """The file name part of an archive member or repository path."""
    return PurePosixPath(path.replace("\\", "/")).name


def parse_filename(name: str) -> tuple[int | None, str]:
    """Infer ``(weight, style)`` from a font file name like ``Lato-BoldItalic.ttf``.

    Variable fonts (``Family[wght].ttf``) cover every weight, so weight is None.
    """
    stem = name.rsplit(".", 1)[0]
    variable = "[" in stem
    stem = stem.split("[", 1)[0]
    suffix = stem.split("-", 1)[1] if "-" in stem else ""
    italic = suffix.lower().endswith("italic")
    if italic:
        suffix = suffix[: -len("italic")]
    style = "italic" if italic else "normal"
    if variable:
        return None, style
    return _weight(suffix.lower()), style


def _weight(suffix: str) -> int | None:
    """Map a style suffix to a weight, tolerating prefixes like ``SemiWide``."""
    if suffix in WEIGHT_NAMES:
        return WEIGHT_NAMES[suffix]
    for name in sorted(WEIGHT_NAMES, key=len, reverse=True):
        if name and suffix.endswith(name):
            return WEIGHT_NAMES[name]
    return None


def variants_of(names: list[str]) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """The sorted weights and styles a set of font files covers."""
    parsed = [parse_filename(basename(n)) for n in names]
    weights = tuple(sorted({w for w, _ in parsed if w is not None}))
    styles = tuple(s for s in ("normal", "italic") if any(p[1] == s for p in parsed))
    return weights, styles

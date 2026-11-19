"""Build a self-contained HTML page that previews a font's files in a browser.

Fonts are embedded as data: URIs. Linking to them with file:// URLs is
unreliable: Chrome blocks fonts loaded from file:// pages and Firefox only
allows the page's own directory.
"""

import base64
import html
import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from string import Template

from fontain import paths
from fontain.sources.filenames import parse_filename

FORMATS = {
    ".ttf": ("font/ttf", "truetype"),
    ".otf": ("font/otf", "opentype"),
    ".woff2": ("font/woff2", "woff2"),
}
WEIGHT_LABELS = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
}

SAMPLES = [
    ("pangram", "The quick brown fox jumps over the lazy dog"),
    ("alphabet", "ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz"),
    ("figures", "0123456789 !?&@#$%*()[]{}<>/\\|\"'.,;:-\u2013\u2014"),
    (
        "paragraph",
        "Typography is the craft of arranging type to make written language legible, readable "
        "and appealing when displayed. Good type disappears; you only notice the words.",
    ),
    ("code", 'fn main() { let x = [1, 2, 3]; println!("{x:?} != 0O1lI"); } // -> => != <='),
]
# A few Nerd Fonts icons (Powerline, devicons, Font Awesome) to show the patched glyphs.
NERD_ICONS = "\ue0b0 \ue0b2 \ue0a0 \uf09b \ue7a8 \ue73c \ue718 \uf120 \uf07b \uf013 \uf0e7 \uf487"


@dataclass(frozen=True)
class Face:
    """One font file, described for the page."""

    path: Path
    weight: int | None  # None for variable fonts (every weight)
    style: str

    @property
    def label(self) -> str:
        style = " Italic" if self.style == "italic" else ""
        if self.weight is None:
            return f"Variable{style}"
        return f"{WEIGHT_LABELS.get(self.weight, str(self.weight))}{style}".replace(
            "Regular Italic", "Italic"
        )


def faces(files: list[Path]) -> list[Face]:
    """The previewable files, ordered by style then weight (variable fonts last)."""
    out = []
    for f in files:
        if f.suffix.lower() not in FORMATS:
            continue  # licence texts, .ttc collections (browsers can't load those), ...
        weight, style = parse_filename(f.name)
        if weight is None and "[" not in f.name:
            weight = 400  # no weight in the name: most likely Regular
        out.append(Face(f, weight, style))
    return sorted(out, key=lambda x: (x.weight is None, x.style != "normal", x.weight or 0, x.path.name))


def _font_face(n: int, face: Face) -> str:
    mime, fmt = FORMATS[face.path.suffix.lower()]
    data = base64.b64encode(face.path.read_bytes()).decode("ascii")
    weight = "1 1000" if face.weight is None else str(face.weight)
    return (
        f"@font-face {{ font-family: 'face{n}'; src: url(data:{mime};base64,{data}) format('{fmt}'); "
        f"font-weight: {weight}; font-style: {face.style}; }}"
    )


def build_html(title: str, subtitle: str, files: list[Path], icons: bool = False) -> str:
    """The preview page for ``files``, from the assets/preview.html template.

    Raises ValueError if none of the files can be shown in a browser.
    """
    shown = faces(files)
    if not shown:
        raise ValueError("no previewable font files (.ttf, .otf or .woff2)")
    samples = [*SAMPLES, ("icons", NERD_ICONS)] if icons else SAMPLES
    cards = []
    for n, face in enumerate(shown):
        rows = "".join(
            f'<p class="sample {kind}" data-kind="{kind}">{html.escape(text)}</p>' for kind, text in samples
        )
        weight = "normal" if face.weight is None else face.weight
        cards.append(
            f'<section class="card" style="font-family: \'face{n}\'; font-weight: {weight}; '
            f'font-style: {face.style}">'
            f"<h2><span>{html.escape(face.label)}</span><code>{html.escape(face.path.name)}</code></h2>"
            f"{rows}</section>"
        )
    font_faces = "\n".join(_font_face(n, face) for n, face in enumerate(shown))
    page = resources.files("fontain").joinpath("assets/preview.html").read_text(encoding="utf-8")
    return Template(page).substitute(
        title=html.escape(title),
        subtitle=html.escape(subtitle),
        font_faces=font_faces,
        cards="\n".join(cards),
        count=len(shown),
        samples=json.dumps(dict(samples)),
    )


def page_path(key: str) -> Path:
    """Where the preview for a font (``source:id``) is written."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", key.replace(":", "__"))
    return paths.cache_dir() / "previews" / f"{safe}.html"

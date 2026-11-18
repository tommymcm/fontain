"""The fontain logo as coloured terminal pixel art, decoded from assets/logo.png
(a copy of docs/images/fontain-text-small.png).

Two image pixels share one character cell using half blocks (▀/▄), with the
top pixel as the foreground colour and the bottom one as the background.
The image's white background is made transparent so the terminal's own
background shows through.
"""

import os
import struct
import zlib
from importlib import resources

Pixel = tuple[int, int, int, int]
Image = list[list[Pixel]]

BACKGROUND = (255, 255, 255)  # treated as transparent


# --- minimal PNG decoding (8-bit RGBA, non-interlaced) ---------------------------


def decode_png(data: bytes) -> Image:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, header = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("missing IHDR")
    width, height, depth, color, _, _, interlace = header
    if (depth, color, interlace) != (8, 6, 0):
        raise ValueError("only 8-bit RGBA, non-interlaced PNGs are supported")

    raw, bpp, stride = zlib.decompress(idat), 4, width * 4
    rows: list[bytearray] = []
    prev = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + b) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        rows.append(line)
        prev = line
    return [[tuple(row[x * 4 : x * 4 + 4]) for x in range(width)] for row in rows]


# --- rendering ------------------------------------------------------------------------


def _to_256(r: int, g: int, b: int) -> int:
    """Nearest colour in the xterm 256-colour palette (cube or grey ramp)."""
    def level(v: int) -> int:
        return 0 if v < 48 else 1 if v < 115 else (v - 35) // 40

    steps = (0, 95, 135, 175, 215, 255)
    ri, gi, bi = level(r), level(g), level(b)
    cube = (steps[ri], steps[gi], steps[bi])
    grey_i = max(0, min(23, round(((r + g + b) / 3 - 8) / 10)))
    grey = 8 + grey_i * 10
    dist = lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2  # noqa: E731
    if dist((grey, grey, grey)) < dist(cube):
        return 232 + grey_i
    return 16 + 36 * ri + 6 * gi + bi


def _sgr(rgb: Pixel, ground: int, truecolor: bool) -> str:
    """ground is 38 (foreground) or 48 (background)."""
    if truecolor:
        return f"\x1b[{ground};2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    return f"\x1b[{ground};5;{_to_256(*rgb[:3])}m"


def render(img: Image, truecolor: bool = True) -> str:
    if len(img) % 2:
        img = img + [[(0, 0, 0, 0)] * len(img[0])]
    lines = []
    for top, bottom in zip(img[::2], img[1::2]):
        # trim fully transparent columns on the right
        width = len(top)
        while width and top[width - 1][3] < 128 and bottom[width - 1][3] < 128:
            width -= 1
        cells = []
        for t, b in zip(top[:width], bottom[:width]):
            t_on, b_on = t[3] >= 128, b[3] >= 128
            if t_on and b_on:
                cells.append(_sgr(t, 38, truecolor) + _sgr(b, 48, truecolor) + "▀")
            elif t_on:
                cells.append("\x1b[49m" + _sgr(t, 38, truecolor) + "▀")
            elif b_on:
                cells.append("\x1b[49m" + _sgr(b, 38, truecolor) + "▄")
            else:
                cells.append("\x1b[0m ")
        lines.append("".join(cells) + "\x1b[0m")
    return "\n".join(lines)


# --- choosing what to show -----------------------------------------------------------


def color_mode(env: dict[str, str] | None = None) -> str | None:
    """``truecolor``, ``256`` or None (no colour: show no logo)."""
    env = os.environ if env is None else env
    term = env.get("TERM", "")
    if "NO_COLOR" in env or term in ("", "dumb"):
        return None
    if env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "truecolor"
    if "256color" in term or "kitty" in term or "alacritty" in term:
        return "256"
    return None


def load() -> Image:
    data = resources.files("fontain").joinpath("assets/logo.png").read_bytes()
    return [[(0, 0, 0, 0) if p[:3] == BACKGROUND else p for p in row] for row in decode_png(data)]


def banner(columns: int, env: dict[str, str] | None = None) -> str | None:
    """The logo for a terminal ``columns`` wide, or None if it won't fit or there's no colour."""
    mode = color_mode(env)
    if mode is None:
        return None
    try:
        img = load()
    except (OSError, ValueError, zlib.error):
        return None
    if columns < len(img[0]):
        return None
    return render(img, truecolor=mode == "truecolor")

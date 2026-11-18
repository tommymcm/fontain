import struct
import zlib

import pytest

from fontain import logo

TRUE = {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
BLUE = (115, 179, 211, 255)
CLEAR = (0, 0, 0, 0)

# docs/images/fontain-text-small.png, with its white background removed
SHAPE = """\
...###...................................##............
..#.##.....................#.............##............
.##.......................##...........................
.##.......................##...........................
#####....###....##..##...#####....###....##...##..##...
.##.....#.####.#########..##.....#..###.####.#########.
.##....##..##....##..##...##....##..##...##....##..##..
.##....##..##....##..##...##....##..##...##....##..##..
.##....##..##....##..##...##....##..##...##....##..##..
.##....##..##....##..##...##....##..##...##....##..##..
####..######....####.###.#####.########.####..####.###.
.##.....##.......##...#....##....##.##...##....##...#..
"""


def test_asset_is_blue_text_on_clear_background():
    img = logo.load()
    assert "\n".join("".join("#" if p == BLUE else "." for p in row) for row in img) + "\n" == SHAPE
    assert {p for row in img for p in row} == {BLUE, CLEAR}  # the white background is gone


def _png(rows, filter_type):
    raw = b"".join(bytes([filter_type]) + bytes(sum(row, ())) for row in rows)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    ihdr = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_decoder_filter_none():
    rows = [[(1, 2, 3, 255), (4, 5, 6, 0)], [(7, 8, 9, 255), (10, 11, 12, 128)]]
    assert logo.decode_png(_png(rows, 0)) == rows


def test_decoder_rejects_other_formats():
    with pytest.raises(ValueError):
        logo.decode_png(b"GIF89a")


def test_render_cells():
    red, blue = (255, 0, 0, 255), (0, 0, 255, 255)
    out = logo.render([[red, red, CLEAR, CLEAR], [blue, CLEAR, blue, CLEAR]])
    assert "\x1b[38;2;255;0;0m\x1b[48;2;0;0;255m▀" in out  # top red over bottom blue
    assert "\x1b[49m\x1b[38;2;255;0;0m▀" in out            # top only
    assert "\x1b[49m\x1b[38;2;0;0;255m▄" in out            # bottom only
    assert out.endswith("\x1b[0m") and "\n" not in out     # transparent right edge trimmed


def test_render_256():
    out = logo.render([[(255, 0, 0, 255)], [(128, 128, 128, 255)]], truecolor=False)
    assert "\x1b[38;5;196m\x1b[48;5;244m▀" in out


@pytest.mark.parametrize("columns,lines", [(200, 6), (55, 6), (54, None)])
def test_banner_fits_terminal(columns, lines):
    out = logo.banner(columns, TRUE)
    assert (None if out is None else len(out.splitlines())) == lines


@pytest.mark.parametrize("env,mode", [
    (TRUE, "truecolor"),
    ({"TERM": "xterm-256color"}, "256"),
    ({"TERM": "xterm"}, None),
    ({"TERM": "dumb", "COLORTERM": "truecolor"}, None),
    ({**TRUE, "NO_COLOR": "1"}, None),
])
def test_color_mode(env, mode):
    assert logo.color_mode(env) == mode
    assert (logo.banner(200, env) is None) == (mode is None)

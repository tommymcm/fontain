"""Plain-text output helpers shared by commands and the shell."""

import sys


def err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def table(rows: list[list[str]], header: list[str]) -> None:
    rows = [header, *rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())

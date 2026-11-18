"""Command-line interface for fontain."""

import argparse
import sys
from collections.abc import Sequence

from fontain import __version__, fontcache, index, net, paths, store
from fontain.sources import SOURCES, Selection, SourceError


def err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def table(rows: list[list[str]], header: list[str]) -> None:
    rows = [header, *rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())


def _sources_for(specs: Sequence[str]) -> list[str]:
    needed = []
    for spec in specs:
        src, sep, _ = spec.partition(":")
        if not sep:
            return list(SOURCES)
        if src in SOURCES and src not in needed:
            needed.append(src)
    return needed


def _int_list(value: str) -> frozenset[int]:
    try:
        return frozenset(int(v) for v in value.split(",") if v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected comma-separated numbers, got {value!r}")


def _style_list(value: str) -> frozenset[str]:
    styles = frozenset(v.strip().lower() for v in value.split(",") if v.strip())
    if bad := styles - {"normal", "italic"}:
        raise argparse.ArgumentTypeError(f"unknown style(s): {', '.join(sorted(bad))}")
    return styles


# --- commands ---------------------------------------------------------------


def cmd_search(args) -> int:
    sources = [args.source] if args.source else list(SOURCES)
    indexes = index.load_many(sources)
    if not indexes:
        return 1
    entries = [e for name in sources for e in indexes.get(name, [])]
    hits = index.search(entries, args.query)
    if not hits:
        print(f"No fonts match {args.query!r}.")
        return 1
    installed = store.load_manifest()
    shown = hits[: args.limit] if args.limit > 0 else hits
    table(
        [[("* " if e.key in installed else "  ") + e.key, e.family, e.category, e.variants_summary()]
         for e in shown],
        ["  FONT", "FAMILY", "CATEGORY", "VARIANTS"],
    )
    if len(hits) > len(shown):
        print(f"... {len(hits) - len(shown)} more (use --limit 0 to show all)")
    return 0


def cmd_info(args) -> int:
    indexes = index.load_many(_sources_for([args.font]))
    try:
        resolved = index.resolve(args.font, indexes)
    except index.ResolveError as e:
        err(str(e))
        return 1
    e = resolved.entry
    record = store.load_manifest().get(e.key)
    fields = [
        ("Font", e.key),
        ("Family", e.family),
        ("Category", e.category),
        ("License", e.license),
        ("Weights", ", ".join(map(str, e.weights))),
        ("Styles", ", ".join(e.styles)),
        ("Version", e.extra.get("version", "")),
        ("Installed", record["dir"] if record else "no"),
    ]
    for label, value in fields:
        if value:
            print(f"{label + ':':<11}{value}")
    if resolved.alternatives:
        print(f"{'Also in:':<11}{', '.join(a.key for a in resolved.alternatives)}")
    return 0


def cmd_install(args) -> int:
    indexes = index.load_many(_sources_for(args.fonts))
    sel = Selection(weights=args.weights or frozenset(), styles=args.styles or frozenset())
    failures = changed = 0
    for spec in args.fonts:
        try:
            resolved = index.resolve(spec, indexes)
            e = resolved.entry
            if resolved.alternatives:
                alts = ", ".join(a.key for a in resolved.alternatives)
                print(f"note: {spec!r} resolved to {e.key} (also available: {alts})", file=sys.stderr)
            print(f"Installing {e.key} ({e.family})...")
            record = store.install(e, SOURCES[e.source], sel, force=args.force)
            if record is None:
                print("  already installed; use --force to reinstall")
                continue
            changed += 1
            print(f"  {len(record['files'])} file(s) -> {record['dir']}")
        except (index.ResolveError, SourceError, net.NetError, store.StoreError, OSError) as ex:
            failures += 1
            err(f"{spec}: {ex}")
    if changed and not args.no_cache:
        fontcache.refresh(paths.font_root())
    return 1 if failures else 0


def _installed_key(spec: str, manifest: dict) -> str:
    source, sep, name = spec.partition(":")
    if not sep:
        source, name = "", spec
    name = name.lower().replace(" ", "")
    matches = [
        key for key, rec in manifest.items()
        if (not source or rec["source"] == source)
        and name in (rec["id"].lower(), rec["family"].lower().replace(" ", ""))
    ]
    if not matches:
        raise store.StoreError(f"{spec!r} is not installed")
    if len(matches) > 1:
        raise store.StoreError(f"{spec!r} is ambiguous: {', '.join(sorted(matches))}")
    return matches[0]


def cmd_remove(args) -> int:
    failures = changed = 0
    for spec in args.fonts:
        try:
            key = _installed_key(spec, store.load_manifest())
            store.remove(key)
            changed += 1
            print(f"Removed {key}")
        except (store.StoreError, OSError) as ex:
            failures += 1
            err(str(ex))
    if changed and not args.no_cache:
        fontcache.refresh(paths.font_root())
    return 1 if failures else 0


def cmd_list(args) -> int:
    manifest = store.load_manifest()
    if not manifest:
        print("No fonts installed. Try `fontain search <name>`.")
        return 0
    rows = [
        [key, rec["family"], str(len(rec["files"])), rec["installed"][:10]]
        for key, rec in sorted(manifest.items(), key=lambda kv: kv[0].lower())
    ]
    table(rows, ["FONT", "FAMILY", "FILES", "INSTALLED"])
    if args.paths:
        print(f"\nFont directory: {paths.font_root()}")
    return 0


def cmd_refresh(args) -> int:
    if unknown := [n for n in args.sources if n not in SOURCES]:
        err(f"unknown source(s): {', '.join(unknown)} (choose from {', '.join(SOURCES)})")
        return 2
    failures = 0
    for name in args.sources or list(SOURCES):
        try:
            print(f"{name}: {len(index.refresh(name))} fonts")
        except (net.NetError, ValueError, KeyError) as e:
            failures += 1
            err(f"{name}: {e}")
    return 1 if failures else 0


def cmd_cache(args) -> int:
    return 0 if fontcache.refresh(paths.font_root()) else 1


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fontain",
        description="Install and manage fonts from public repositories.",
        epilog=f"Sources: {', '.join(SOURCES)}. Refer to fonts as NAME or SOURCE:NAME.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    s = sub.add_parser("search", help="search for fonts")
    s.add_argument("query")
    s.add_argument("-s", "--source", choices=list(SOURCES))
    s.add_argument("-n", "--limit", type=int, default=25, help="max results (0 = all, default 25)")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("info", help="show details about a font")
    s.add_argument("font")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("install", aliases=["add"], help="install fonts")
    s.add_argument("fonts", nargs="+", metavar="font")
    s.add_argument("-w", "--weights", type=_int_list, help="only these weights, e.g. 400,700")
    s.add_argument("-S", "--styles", type=_style_list, help="only these styles: normal,italic")
    s.add_argument("-f", "--force", action="store_true", help="reinstall if already installed")
    s.add_argument("--no-cache", action="store_true", help="don't run fc-cache afterwards")
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("remove", aliases=["uninstall", "rm"], help="remove installed fonts")
    s.add_argument("fonts", nargs="+", metavar="font")
    s.add_argument("--no-cache", action="store_true", help="don't run fc-cache afterwards")
    s.set_defaults(func=cmd_remove)

    s = sub.add_parser("list", aliases=["ls"], help="list installed fonts")
    s.add_argument("-p", "--paths", action="store_true", help="also show the font directory")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("refresh", help="re-download source indexes")
    s.add_argument("sources", nargs="*", metavar="source", help=f"one of: {', '.join(SOURCES)}")
    s.set_defaults(func=cmd_refresh)

    s = sub.add_parser("cache", help="rebuild the font cache (fc-cache)")
    s.set_defaults(func=cmd_cache)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except store.StoreError as e:
        err(str(e))
        return 1

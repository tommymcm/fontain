"""Command-line interface for fontain."""

import argparse
import sys
from collections.abc import Sequence

from fontain import __version__, fontcache, index, net, paths, repos, sources, store
from fontain.sources import SOURCES, Selection, SourceError


def err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def table(rows: list[list[str]], header: list[str]) -> None:
    rows = [header, *rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())


def _sources_for(specs: Sequence[str]) -> list[str]:
    known = sources.registry()
    needed = []
    for spec in specs:
        src, sep, _ = spec.partition(":")
        if not sep:
            return list(known)
        if src in known and src not in needed:
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
    known = sources.registry()
    if args.source and args.source not in known:
        err(f"unknown source {args.source!r} (choose from {', '.join(known)})")
        return 2
    names = [args.source] if args.source else list(known)
    indexes = index.load_many(names)
    if not indexes:
        return 1
    entries = [e for name in names for e in indexes.get(name, [])]
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
    known = sources.registry()
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
            record = store.install(e, known[e.source], sel, force=args.force)
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
    known = sources.registry()
    if unknown := [n for n in args.sources if n not in known]:
        err(f"unknown source(s): {', '.join(unknown)} (choose from {', '.join(known)})")
        return 2
    failures = 0
    for name in args.sources or list(known):
        try:
            print(f"{name}: {len(index.refresh(name))} fonts")
        except (net.NetError, SourceError, OSError, ValueError, KeyError) as e:
            failures += 1
            err(f"{name}: {e}")
    return 1 if failures else 0


def cmd_cache(args) -> int:
    return 0 if fontcache.refresh(paths.font_root()) else 1


def cmd_repo_list(args) -> int:
    rows = [[name, "built-in", ""] for name in SOURCES]
    rows += [[name, cfg.get("type", "?"), cfg.get("target", "")] for name, cfg in repos.load().items()]
    table(rows, ["NAME", "TYPE", "LOCATION"])
    return 0


def cmd_repo_add(args) -> int:
    existing = repos.load()
    repos.check_name(args.name, set(SOURCES), existing)
    cfg = repos.parse_spec(args.spec)
    source = sources.make_source(args.name, cfg)
    if not args.no_check:
        print(f"Checking {cfg['target']}...", flush=True)
        try:
            entries = source.fetch_index()
        except (net.NetError, SourceError, OSError, ValueError, KeyError) as e:
            if isinstance(e, net.NetError) and e.status == 404:
                e = f"GitHub repository {cfg['target']} not found (or private)"
            err(f"could not read repository: {e}")
            return 1
        if not entries:
            err(f"no fonts found in {cfg['target']} (use --no-check to add it anyway)")
            return 1
        if getattr(source, "cacheable", True):
            index.write_cache(args.name, entries)
    existing[args.name] = cfg
    repos.save(existing)
    found = "" if args.no_check else f" with {len(entries)} font(s)"
    print(f"Added {cfg['type']} repository {args.name!r}{found}. Install with `fontain install {args.name}:<font>`.")
    return 0


def cmd_repo_remove(args) -> int:
    existing = repos.load()
    if existing.pop(args.name, None) is None:
        err(f"no user repository named {args.name!r}")
        return 1
    repos.save(existing)
    index.drop_cache(args.name)
    print(f"Removed repository {args.name!r}")
    if left := [k for k, rec in store.load_manifest().items() if rec["source"] == args.name]:
        print(f"note: {len(left)} font(s) installed from it remain: {', '.join(left)}")
        print("      remove them with `fontain remove <font>`")
    return 0


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fontain",
        description="Install and manage fonts from public repositories.",
        epilog=f"Built-in sources: {', '.join(SOURCES)}; add your own with `fontain repo add`. "
        "Refer to fonts as NAME or SOURCE:NAME.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    s = sub.add_parser("search", help="search for fonts")
    s.add_argument("query")
    s.add_argument("-s", "--source", help="only search this source or repository")
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
    s.add_argument("sources", nargs="*", metavar="source", help="sources to refresh (default: all)")
    s.set_defaults(func=cmd_refresh)

    s = sub.add_parser("cache", help="rebuild the font cache (fc-cache)")
    s.set_defaults(func=cmd_cache)

    repo = sub.add_parser("repo", help="manage your own font repositories")
    repo.set_defaults(func=cmd_repo_list)
    rsub = repo.add_subparsers(dest="repo_command", metavar="ACTION")

    s = rsub.add_parser("list", aliases=["ls"], help="list repositories")
    s.set_defaults(func=cmd_repo_list)

    s = rsub.add_parser(
        "add", help="add a repository",
        description="Add a GitHub repository (github:OWNER/REPO or a github.com URL) "
        "or a local directory as a font source.",
    )
    s.add_argument("name", help="short name used as SOURCE in SOURCE:FONT")
    s.add_argument("spec", help="github:OWNER/REPO, https://github.com/OWNER/REPO, or a directory")
    s.add_argument("--no-check", action="store_true", help="don't verify the repository has fonts")
    s.set_defaults(func=cmd_repo_add)

    s = rsub.add_parser("remove", aliases=["rm"], help="remove a repository (installed fonts are kept)")
    s.add_argument("name")
    s.set_defaults(func=cmd_repo_remove)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except (store.StoreError, repos.RepoError, SourceError) as e:
        err(str(e))
        return 1

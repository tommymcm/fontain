"""Handlers for each fontain subcommand. Each takes parsed ``args`` and returns an exit code."""

import argparse
import contextlib
import sys
from collections.abc import Sequence

from fontain import completion, fontcache, index, net, paths, repos, sources, store
from fontain.output import err, table
from fontain.sources import FETCH_ERRORS, SOURCES, Selection, SourceError


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


def cmd_search(args: argparse.Namespace) -> int:
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
        [
            [("* " if e.key in installed else "  ") + e.key, e.family, e.category, e.variants_summary()]
            for e in shown
        ],
        ["  FONT", "FAMILY", "CATEGORY", "VARIANTS"],
    )
    if len(hits) > len(shown):
        print(f"... {len(hits) - len(shown)} more (use --limit 0 to show all)")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    indexes = index.load_many(_sources_for([args.font]))
    try:
        resolved = index.resolve(args.font, indexes)
    except index.ResolveError as e:
        err(str(e))
        return 1
    entry = resolved.entry
    record = store.load_manifest().get(entry.key)
    fields = [
        ("Font", entry.key),
        ("Family", entry.family),
        ("Category", entry.category),
        ("License", entry.license),
        ("Weights", ", ".join(map(str, entry.weights))),
        ("Styles", ", ".join(entry.styles)),
        ("Version", entry.extra.get("version", "")),
        ("Installed", record["dir"] if record else "no"),
    ]
    for label, value in fields:
        if value:
            print(f"{label + ':':<11}{value}")
    if resolved.alternatives:
        print(f"{'Also in:':<11}{', '.join(a.key for a in resolved.alternatives)}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
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


def cmd_remove(args: argparse.Namespace) -> int:
    failures = changed = 0
    for spec in args.fonts:
        try:
            key = store.find_installed(spec, store.load_manifest())
            store.remove(key)
            changed += 1
            print(f"Removed {key}")
        except (store.StoreError, OSError) as ex:
            failures += 1
            err(str(ex))
    if changed and not args.no_cache:
        fontcache.refresh(paths.font_root())
    return 1 if failures else 0


def cmd_list(args: argparse.Namespace) -> int:
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


def cmd_refresh(args: argparse.Namespace) -> int:
    known = sources.registry()
    if unknown := [n for n in args.sources if n not in known]:
        err(f"unknown source(s): {', '.join(unknown)} (choose from {', '.join(known)})")
        return 2
    failures = 0
    for name in args.sources or list(known):
        try:
            print(f"{name}: {len(index.refresh(name))} fonts")
        except FETCH_ERRORS as e:
            failures += 1
            err(f"{name}: {e}")
    return 1 if failures else 0


def cmd_cache(args: argparse.Namespace) -> int:
    return 0 if fontcache.refresh(paths.font_root()) else 1


def cmd_repo_list(args: argparse.Namespace) -> int:
    pref = repos.preferred()
    rows = [[name, "built-in", ""] for name in SOURCES]
    rows += [[name, cfg.get("type", "?"), cfg.get("target", "")] for name, cfg in repos.load().items()]
    for row in rows:
        row[0] = ("* " if row[0] == pref else "  ") + row[0]
    table(rows, ["  NAME", "TYPE", "LOCATION"])
    if pref:
        print("\n* preferred for bare font names")
    return 0


def cmd_repo_prefer(args: argparse.Namespace) -> int:
    if args.clear:
        repos.set_preferred(None)
        print("Cleared preferred source; bare names use the default order.")
        return 0
    if not args.name:
        pref = repos.preferred()
        print(pref or f"(none; default order: {', '.join(SOURCES)}, then your repos)")
        return 0
    known = sources.registry()
    if args.name not in known:
        err(f"unknown source {args.name!r} (choose from {', '.join(known)})")
        return 1
    repos.set_preferred(args.name)
    print(f"Bare font names now resolve from {args.name!r} first.")
    return 0


def cmd_repo_add(args: argparse.Namespace) -> int:
    existing = repos.load()
    repos.check_name(args.name, set(SOURCES), existing)
    cfg = repos.parse_spec(args.spec)
    source = sources.make_source(args.name, cfg)
    if not args.no_check:
        print(f"Checking {cfg['target']}...", flush=True)
        try:
            entries = source.fetch_index()
        except FETCH_ERRORS as e:
            reason = str(e)
            if isinstance(e, net.NetError) and e.status == 404:
                reason = f"GitHub repository {cfg['target']} not found (or private)"
            err(f"could not read repository: {reason}")
            return 1
        if not entries:
            err(f"no fonts found in {cfg['target']} (use --no-check to add it anyway)")
            return 1
        if getattr(source, "cacheable", True):
            index.write_cache(args.name, entries)
    existing[args.name] = cfg
    repos.save(existing)
    found = "" if args.no_check else f" with {len(entries)} font(s)"
    print(
        f"Added {cfg['type']} repository {args.name!r}{found}. "
        f"Install with `fontain install {args.name}:<font>`."
    )
    return 0


def cmd_repo_remove(args: argparse.Namespace) -> int:
    existing = repos.load()
    if existing.pop(args.name, None) is None:
        err(f"no user repository named {args.name!r}")
        return 1
    repos.save(existing)
    index.drop_cache(args.name)
    print(f"Removed repository {args.name!r}")
    if repos.preferred() == args.name:
        repos.set_preferred(None)
        print("note: it was your preferred source; preference cleared")
    if left := [k for k, rec in store.load_manifest().items() if rec["source"] == args.name]:
        print(f"note: {len(left)} font(s) installed from it remain: {', '.join(left)}")
        print("      remove them with `fontain remove <font>`")
    return 0


def cmd_completion(args: argparse.Namespace) -> int:
    parser = args.parser  # the top-level FontainParser, which records its subcommands
    commands = [(c.name, c.help) for c in parser.commands if not c.hidden]
    remove_names = list(parser.find("remove").names)
    if args.reset:
        completion.set_consent(None)
        for name in completion.AUTOLOAD_SHELLS:
            with contextlib.suppress(completion.CompletionError):  # not ours; leave it alone
                completion.uninstall(name)
        print("Reset: you'll be asked about tab completion the next time you press Tab after `fontain`.")
        return 0
    if args.install or args.uninstall:
        shell: str | None = args.shell or completion.detect_shell()
        if not shell:
            err("couldn't detect your shell from $SHELL; pass it explicitly, e.g. `--install bash`")
            return 2
        if args.install and shell == "bash" and (loader := completion.tab_loader_path()) and loader.exists():
            completion.set_consent("yes")
            print("Enabled bash tab completion. It takes effect in new shells.")
        elif args.install:
            path = completion.install(shell)
            completion.set_consent("yes")
            print(f"Installed {shell} completion: {path}")
            print("It takes effect in new shells.")
            if shell == "bash" and not completion.bash_completion_available():
                print(
                    "note: this needs the bash-completion package "
                    "(e.g. `dnf install bash-completion` / `apt install bash-completion`)"
                )
        else:
            removed = completion.uninstall(shell)
            completion.set_consent("no")
            print(f"Removed {removed}." if removed else f"Disabled {shell} tab completion.")
            print("It takes effect in new shells; you won't be asked again.")
        return 0
    if not args.shell:
        err("specify a shell (bash, zsh, fish), or use --install")
        return 2
    print(completion.script(args.shell, commands, remove_names), end="")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    match args.what:
        case "consent":
            print(completion.get_consent())
        case "accept":
            completion.set_consent("yes")
        case "decline":
            completion.set_consent("no")
        case _:
            for name in completion.installed_candidates(qualified=args.what == "installed-keys"):
                print(name)
    return 0

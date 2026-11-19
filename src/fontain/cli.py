"""Command-line interface for fontain."""

import argparse
import shutil
import sys
from collections.abc import Sequence

from fontain import __version__, completion, fontcache, index, logo, net, paths, repl, repos, sources, store
from fontain.sources import FETCH_ERRORS, SOURCES, Selection, SourceError


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
        [
            [("* " if e.key in installed else "  ") + e.key, e.family, e.category, e.variants_summary()]
            for e in shown
        ],
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


def cmd_remove(args) -> int:
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
        except FETCH_ERRORS as e:
            failures += 1
            err(f"{name}: {e}")
    return 1 if failures else 0


def cmd_cache(args) -> int:
    return 0 if fontcache.refresh(paths.font_root()) else 1


def cmd_repo_list(args) -> int:
    pref = repos.preferred()
    rows = [[name, "built-in", ""] for name in SOURCES]
    rows += [[name, cfg.get("type", "?"), cfg.get("target", "")] for name, cfg in repos.load().items()]
    for row in rows:
        row[0] = ("* " if row[0] == pref else "  ") + row[0]
    table(rows, ["  NAME", "TYPE", "LOCATION"])
    if pref:
        print("\n* preferred for bare font names")
    return 0


def cmd_repo_prefer(args) -> int:
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


def cmd_repo_add(args) -> int:
    existing = repos.load()
    repos.check_name(args.name, set(SOURCES), existing)
    cfg = repos.parse_spec(args.spec)
    source = sources.make_source(args.name, cfg)
    if not args.no_check:
        print(f"Checking {cfg['target']}...", flush=True)
        try:
            entries = source.fetch_index()
        except FETCH_ERRORS as e:
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
    print(
        f"Added {cfg['type']} repository {args.name!r}{found}. Install with `fontain install {args.name}:<font>`."
    )
    return 0


def cmd_repo_remove(args) -> int:
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


def cmd_completion(args) -> int:
    sub = args.parser._subparsers._group_actions[0]
    commands = [(a.dest, a.help or "") for a in sub._choices_actions]
    remove = sub.choices["remove"]
    remove_names = [name for name, parser in sub.choices.items() if parser is remove]
    if args.reset:
        completion.set_consent(None)
        for shell in completion.AUTOLOAD_SHELLS:
            try:
                completion.uninstall(shell)
            except completion.CompletionError:
                pass  # not ours; leave it alone
        print("Reset: you'll be asked about tab completion the next time you press Tab after `fontain`.")
        return 0
    if args.install or args.uninstall:
        shell = args.shell or completion.detect_shell()
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
            path = completion.uninstall(shell)
            completion.set_consent("no")
            print(f"Removed {path}." if path else f"Disabled {shell} tab completion.")
            print("It takes effect in new shells; you won't be asked again.")
        return 0
    if not args.shell:
        err("specify a shell (bash, zsh, fish), or use --install")
        return 2
    print(completion.script(args.shell, commands, remove_names), end="")
    return 0


def cmd_complete(args) -> int:
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
        "add",
        help="add a repository",
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

    s = rsub.add_parser(
        "prefer",
        help="set the source bare font names resolve from first",
        description="Choose which source `fontain install NAME` tries first. "
        "With no NAME, print the current preference.",
    )
    s.add_argument("name", nargs="?", help="a built-in source or one of your repositories")
    s.add_argument("--clear", action="store_true", help="go back to the default order")
    s.set_defaults(func=cmd_repo_prefer)

    s = sub.add_parser(
        "completion",
        help="set up shell tab completion",
        description="In bash, fontain asks the first time you press Tab after `fontain`. "
        "Use --install/--uninstall to change your answer (or set it up for fish), "
        "--reset to be asked again, or print the script for SHELL "
        '(for zsh: add eval "$(fontain completion zsh)" to ~/.zshrc).',
    )
    s.add_argument("shell", nargs="?", choices=completion.SHELLS, help="default for --install: from $SHELL")
    mode = s.add_mutually_exclusive_group()
    mode.add_argument(
        "--install", action="store_true", help="install into the shell's completion directory (bash, fish)"
    )
    mode.add_argument("--uninstall", action="store_true", help="disable completion and don't ask again")
    mode.add_argument("--reset", action="store_true", help="forget your answer; ask again on the next Tab")
    s.set_defaults(func=cmd_completion, parser=p)

    s = sub.add_parser("shell", help="interactive shell (also: run `fontain` with no arguments)")
    s.set_defaults(func=cmd_shell)

    s = sub.add_parser(
        "run",
        help="run commands from a script file or stdin",
        description="Run one fontain command per line, as typed in the shell: shell-style quoting, "
        "blank lines and # comments are ignored. Stops at the first failing command. The font "
        "cache is rebuilt once at the end. Make a script executable with the first line "
        "`#!/usr/bin/env -S fontain run`. Piping into `fontain` with no arguments also runs a script.",
    )
    s.add_argument("script", nargs="?", default="-", help="script file (default or `-`: stdin)")
    s.add_argument(
        "-k",
        "--keep-going",
        action="store_true",
        help="run every line even if one fails (still exits non-zero)",
    )
    s.set_defaults(func=cmd_run)

    # Hidden helper used by the completion scripts (no help= keeps it out of --help).
    s = sub.add_parser("__complete")
    s.add_argument("what", choices=["installed", "installed-keys", "consent", "accept", "decline"])
    s.set_defaults(func=cmd_complete)
    return p


def cmd_shell(args) -> int:
    return start_shell()


def _shell_context():
    """Command names, sub-actions and a `help` printer, shared by the shell and scripts."""
    parser = build_parser()
    sub = parser._subparsers._group_actions[0]
    commands = [name for name in sub.choices if name not in repl.HIDDEN]
    repo_sub = sub.choices["repo"]._subparsers._group_actions[0]
    subcommands = {"repo": list(repo_sub.choices)}

    def help_text(cmd: str | None) -> None:
        if cmd is None:
            rows = [[a.dest, a.help or ""] for a in sub._choices_actions if a.dest not in repl.HIDDEN]
            rows += [["help [command]", "show commands, or a command's options"], ["exit", "leave the shell"]]
            table(rows, ["COMMAND", "DESCRIPTION"])
        elif cmd in sub.choices and cmd not in repl.HIDDEN:
            sub.choices[cmd].print_help()
        else:
            err(f"unknown command {cmd!r}")

    return commands, subcommands, help_text


def start_shell() -> int:
    commands, subcommands, help_text = _shell_context()
    art = logo.banner(shutil.get_terminal_size().columns)
    return repl.repl(run, help_text, repl.Completer(commands, subcommands), logo=art)


def run_script(source: str, keep_going: bool = False) -> int:
    """Run a script file, or stdin when ``source`` is ``-``."""
    if source == "-":
        name, lines = "<stdin>", sys.stdin
    else:
        try:
            with open(source, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            err(f"can't read script {source}: {e}")
            return 1
        name = source
    commands, _, help_text = _shell_context()
    return repl.run_script(lines, name, run, help_text, commands, keep_going=keep_going)


def cmd_run(args) -> int:
    return run_script(args.script, keep_going=args.keep_going)


def main(argv: Sequence[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        if not sys.stdin.isatty():  # `fontain < fonts.txt`, `cat fonts.txt | fontain`
            return run_script("-")
        if sys.stdout.isatty():
            return start_shell()
    return run(argv)


def run(argv: Sequence[str]) -> int:
    """Run one command line. argparse errors raise SystemExit (callers decide)."""
    args = build_parser().parse_args(argv)
    try:
        rc = args.func(args)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except (store.StoreError, repos.RepoError, SourceError, completion.CompletionError) as e:
        err(str(e))
        return 1
    completion.ensure_tab_loader()
    return rc

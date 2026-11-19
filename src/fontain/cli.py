"""Command-line entry point: the argument parser, `main`, and the shell/script glue."""

import argparse
import shutil
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from fontain import __version__, completion, logo, repl, repos, store
from fontain.commands import (
    cmd_cache,
    cmd_complete,
    cmd_completion,
    cmd_info,
    cmd_install,
    cmd_list,
    cmd_preview,
    cmd_refresh,
    cmd_remove,
    cmd_repo_add,
    cmd_repo_list,
    cmd_repo_prefer,
    cmd_repo_remove,
    cmd_search,
    cmd_update,
)
from fontain.output import err, table
from fontain.sources import SOURCES, SourceError


@dataclass(frozen=True)
class Command:
    """A subcommand as registered with the parser."""

    name: str
    aliases: tuple[str, ...]
    help: str
    parser: argparse.ArgumentParser

    @property
    def hidden(self) -> bool:
        """Internal commands are registered without help text, which keeps them out of --help."""
        return not self.help

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


class FontainParser(argparse.ArgumentParser):
    """An ArgumentParser that remembers its subcommands, so nothing needs argparse internals."""

    commands: list[Command]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    def command(
        self, subparsers, name: str, func: Callable, help: str = "", aliases: Sequence[str] = (), **kw
    ):
        """Add a subcommand that runs ``func``; leave ``help`` empty to hide it."""
        if help:  # argparse lists any subcommand given a `help` argument, even None
            kw["help"] = help
        p = subparsers.add_parser(name, aliases=list(aliases), **kw)
        p.set_defaults(func=func)
        self.commands.append(Command(name, tuple(aliases), help, p))
        return p

    def find(self, name: str) -> Command | None:
        return next((c for c in self.commands if name in c.names), None)


def _int_list(value: str) -> frozenset[int]:
    try:
        return frozenset(int(v) for v in value.split(",") if v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected comma-separated numbers, got {value!r}") from None


def _style_list(value: str) -> frozenset[str]:
    styles = frozenset(v.strip().lower() for v in value.split(",") if v.strip())
    if bad := styles - {"normal", "italic"}:
        raise argparse.ArgumentTypeError(f"unknown style(s): {', '.join(sorted(bad))}")
    return styles


# --- parser -----------------------------------------------------------------


def build_parser() -> FontainParser:
    p = FontainParser(
        prog="fontain",
        description="Install and manage fonts from public repositories.",
        epilog=f"Built-in sources: {', '.join(SOURCES)}; add your own with `fontain repo add`. "
        "Refer to fonts as NAME or SOURCE:NAME.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    s = p.command(sub, "search", cmd_search, help="search for fonts")
    s.add_argument("query")
    s.add_argument("-s", "--source", help="only search this source or repository")
    s.add_argument("-n", "--limit", type=int, default=25, help="max results (0 = all, default 25)")

    s = p.command(sub, "info", cmd_info, help="show details about a font")
    s.add_argument("font")

    s = p.command(sub, "install", cmd_install, help="install fonts", aliases=["add"])
    s.add_argument("fonts", nargs="+", metavar="font")
    s.add_argument("-w", "--weights", type=_int_list, help="only these weights, e.g. 400,700")
    s.add_argument("-S", "--styles", type=_style_list, help="only these styles: normal,italic")
    s.add_argument("-f", "--force", action="store_true", help="reinstall if already installed")
    s.add_argument("--no-cache", action="store_true", help="don't run fc-cache afterwards")

    s = p.command(sub, "remove", cmd_remove, help="remove installed fonts", aliases=["uninstall", "rm"])
    s.add_argument("fonts", nargs="+", metavar="font")
    s.add_argument("--no-cache", action="store_true", help="don't run fc-cache afterwards")

    s = p.command(
        sub,
        "preview",
        cmd_preview,
        help="preview a font in your web browser",
        description="Write an HTML page showing every style of FONT and open it in the default browser. "
        "Works for installed fonts and, by downloading them temporarily, for fonts you haven't installed.",
    )
    s.add_argument("font")
    s.add_argument("-w", "--weights", type=_int_list, help="only these weights, e.g. 400,700")
    s.add_argument("-S", "--styles", type=_style_list, help="only these styles: normal,italic")
    s.add_argument("--no-open", action="store_true", help="just write the page and print its path")

    s = p.command(
        sub,
        "update",
        cmd_update,
        help="update installed fonts whose source has changed",
        aliases=["upgrade"],
        description="Fetch each source again and reinstall installed fonts whose files changed there, "
        "keeping the weights and styles you chose. With no FONT, checks every installed font.",
    )
    s.add_argument("fonts", nargs="*", metavar="font", help="installed fonts to update (default: all)")
    s.add_argument("-n", "--dry-run", action="store_true", help="only show what would be updated")
    s.add_argument("-f", "--force", action="store_true", help="reinstall even if nothing changed")
    s.add_argument("--no-cache", action="store_true", help="don't run fc-cache afterwards")

    s = p.command(sub, "list", cmd_list, help="list installed fonts", aliases=["ls"])
    s.add_argument("-p", "--paths", action="store_true", help="also show the font directory")

    s = p.command(sub, "refresh", cmd_refresh, help="re-download source indexes")
    s.add_argument("sources", nargs="*", metavar="source", help="sources to refresh (default: all)")

    p.command(sub, "cache", cmd_cache, help="rebuild the font cache (fc-cache)")

    repo = p.command(sub, "repo", cmd_repo_list, help="manage your own font repositories")
    assert isinstance(repo, FontainParser)  # subparsers are created with the parent's class
    rsub = repo.add_subparsers(dest="repo_command", metavar="ACTION")

    repo.command(rsub, "list", cmd_repo_list, help="list repositories", aliases=["ls"])

    s = repo.command(
        rsub,
        "add",
        cmd_repo_add,
        help="add a repository",
        description="Add a GitHub repository (github:OWNER/REPO or a github.com URL) "
        "or a local directory as a font source.",
    )
    s.add_argument("name", help="short name used as SOURCE in SOURCE:FONT")
    s.add_argument("spec", help="github:OWNER/REPO, https://github.com/OWNER/REPO, or a directory")
    s.add_argument("--no-check", action="store_true", help="don't verify the repository has fonts")

    s = repo.command(
        rsub, "remove", cmd_repo_remove, help="remove a repository (installed fonts are kept)", aliases=["rm"]
    )
    s.add_argument("name")

    s = repo.command(
        rsub,
        "prefer",
        cmd_repo_prefer,
        help="set the source bare font names resolve from first",
        description="Choose which source `fontain install NAME` tries first. "
        "With no NAME, print the current preference.",
    )
    s.add_argument("name", nargs="?", help="a built-in source or one of your repositories")
    s.add_argument("--clear", action="store_true", help="go back to the default order")

    s = p.command(
        sub,
        "completion",
        cmd_completion,
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
    s.set_defaults(parser=p)

    p.command(sub, "shell", cmd_shell, help="interactive shell (also: run `fontain` with no arguments)")

    s = p.command(
        sub,
        "run",
        cmd_run,
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

    # Hidden helper used by the completion scripts.
    s = p.command(sub, "__complete", cmd_complete)
    s.add_argument("what", choices=["installed", "installed-keys", "consent", "accept", "decline"])
    return p


# --- shell and scripts ---------------------------------------------------------


def shell_context() -> tuple[list[str], dict[str, list[str]], Callable[[str | None], None]]:
    """Command names, sub-actions and a `help` printer, shared by the shell and scripts."""
    parser = build_parser()
    visible = [c for c in parser.commands if not c.hidden and c.name not in repl.HIDDEN]
    commands = [name for c in visible for name in c.names]
    repo = parser.find("repo")
    assert repo is not None and isinstance(repo.parser, FontainParser)
    subcommands = {"repo": [name for c in repo.parser.commands for name in c.names]}

    def help_text(cmd: str | None) -> None:
        if cmd is None:
            rows = [[c.name, c.help] for c in visible]
            rows += [["help [command]", "show commands, or a command's options"], ["exit", "leave the shell"]]
            table(rows, ["COMMAND", "DESCRIPTION"])
        elif cmd in commands and (found := parser.find(cmd)):
            found.parser.print_help()
        else:
            err(f"unknown command {cmd!r}")

    return commands, subcommands, help_text


def start_shell() -> int:
    commands, subcommands, help_text = shell_context()
    art = logo.banner(shutil.get_terminal_size().columns)
    return repl.repl(run, help_text, repl.Completer(commands, subcommands), logo=art)


def run_script(source: str, keep_going: bool = False) -> int:
    """Run a script file, or stdin when ``source`` is ``-``."""
    lines: Iterable[str]
    if source == "-":
        name, lines = "<stdin>", sys.stdin  # read lazily: each line runs as it arrives
    else:
        try:
            with open(source, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            err(f"can't read script {source}: {e}")
            return 1
        name = source
    commands, _, help_text = shell_context()
    return repl.run_script(lines, name, run, help_text, commands, keep_going=keep_going)


def cmd_shell(args: argparse.Namespace) -> int:
    return start_shell()


def cmd_run(args: argparse.Namespace) -> int:
    return run_script(args.script, keep_going=args.keep_going)


# --- entry points ------------------------------------------------------------------


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
    parser = build_parser()
    if argv and not argv[0].startswith("-") and parser.find(argv[0]) is None:
        # argparse would list every choice, including internal ones; keep it short
        err(f"unknown command {argv[0]!r} (see `fontain --help`)")
        return 2
    args = parser.parse_args(argv)
    try:
        rc: int = args.func(args)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except (store.StoreError, repos.RepoError, SourceError, completion.CompletionError) as e:
        err(str(e))
        return 1
    completion.ensure_tab_loader()
    return rc

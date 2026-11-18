"""Interactive shell: each line is one fontain command, e.g. ``search roboto``."""

import shlex
import sys
from collections.abc import Callable

from fontain import __version__, completion, index, paths, repos, sources

try:
    import readline
except ImportError:  # e.g. some minimal Python builds
    readline = None

PROMPT = "fontain> "
EXIT_WORDS = {"exit", "quit", "q"}
HELP_WORDS = {"help", "?"}
HIDDEN = {"__complete", "shell"}

BANNER = f"""fontain {__version__}: type a command without the `fontain` prefix, e.g. `search roboto`.
`help` lists commands, `help <command>` shows its options, `exit` or Ctrl-D quits."""


def history_file():
    return paths.state_file().parent / "history"


# --- completion ----------------------------------------------------------------


class Completer:
    def __init__(self, commands: list[str], subcommands: dict[str, list[str]]):
        self.commands = commands
        self.subcommands = subcommands  # e.g. {"repo": ["add", "list", ...]}

    def candidates(self, line: str) -> list[str]:
        """Completions for the last word of ``line`` (the text before the cursor)."""
        words = line.split()
        if not line or line[-1].isspace():
            words.append("")
        if words and words[0] == "fontain":
            words = words[1:] or [""]
        cur, before = words[-1], words[:-1]
        if not before:
            options = self.commands + sorted(EXIT_WORDS | HELP_WORDS - {"q", "?"})
        else:
            options = self.arguments(before)
        if cur.startswith("-"):
            return []
        return sorted({o.replace(" ", "\\ ") for o in options if o.startswith(cur)}, key=str.lower)

    def arguments(self, before: list[str]) -> list[str]:
        cmd = before[0]
        if cmd in HELP_WORDS and len(before) == 1:
            return self.commands
        if cmd in self.subcommands and len(before) == 1:
            return self.subcommands[cmd]
        if cmd in ("remove", "uninstall", "rm"):
            return completion.installed_candidates() + completion.installed_candidates(qualified=True)
        if cmd == "repo" and len(before) == 2 and before[1] in ("remove", "rm", "prefer"):
            names = list(repos.load()) if before[1] != "prefer" else list(sources.registry())
            return names
        if cmd in ("install", "add", "info"):
            out = []
            for name in sources.registry():
                ids = index.cached_ids(name)
                out += ids + [f"{name}:{i}" for i in ids]
            return out
        return []

    def complete(self, text: str, state: int) -> str | None:
        """readline completer hook."""
        if state == 0:
            line = readline.get_line_buffer()[: readline.get_endidx()]
            try:
                # Python's readline adds no space after a unique match; add it ourselves
                # (it isn't part of the common prefix when several candidates match).
                self._matches = [m + " " for m in self.candidates(line)]
            except Exception:  # completion must never crash the shell
                self._matches = []
        return self._matches[state] if state < len(self._matches) else None


def _setup_readline(completer: Completer) -> None:
    if readline is None:
        return
    readline.set_completer(completer.complete)
    readline.set_completer_delims(" \t\n")  # keep "source:id" and "a-b" as one word
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    try:
        readline.read_history_file(history_file())
    except (OSError, ValueError):
        pass
    readline.set_history_length(1000)


def _save_history() -> None:
    if readline is None:
        return
    try:
        history_file().parent.mkdir(parents=True, exist_ok=True)
        readline.write_history_file(history_file())
    except OSError:
        pass


# --- the loop -----------------------------------------------------------------


def run_line(
    line: str,
    run: Callable[[list[str]], int],
    help_text: Callable[[str | None], None],
    commands: list[str] | None = None,
) -> bool:
    """Run one line. Returns False when the user asked to leave."""
    try:
        words = shlex.split(line)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return True
    if words and words[0] == "fontain":  # tolerate habit
        words = words[1:]
    if not words:
        return True
    cmd = words[0]
    if cmd in EXIT_WORDS:
        return False
    if cmd in HELP_WORDS:
        help_text(words[1] if len(words) > 1 else None)
        return True
    if cmd == "shell":
        print("Already in the fontain shell.")
        return True
    if commands is not None and cmd not in commands and not cmd.startswith("-"):
        print(f"error: unknown command {cmd!r} (type `help` for a list)", file=sys.stderr)
        return True
    try:
        run(words)
    except SystemExit:
        pass  # argparse already printed usage/--help; stay in the shell
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
    return True


def repl(
    run: Callable[[list[str]], int],
    help_text: Callable[[str | None], None],
    completer: Completer,
    read: Callable[[str], str] = input,
    logo: str | None = None,
) -> int:
    _setup_readline(completer)
    if logo:
        print(logo)
    print(BANNER)
    try:
        while True:
            try:
                line = read(PROMPT)
            except KeyboardInterrupt:
                print()  # Ctrl-C clears the line, like a shell
                continue
            except EOFError:
                print()
                break
            if not run_line(line, run, help_text, completer.commands):
                break
            sys.stdout.flush()
    finally:
        _save_history()
    return 0

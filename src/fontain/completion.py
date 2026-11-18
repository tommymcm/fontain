"""Shell tab-completion scripts.

The scripts complete subcommand names statically and ask
``fontain __complete installed`` for the fonts that ``remove`` accepts.
That command only reads the installed-font manifest, so it is fast and
never touches the network.
"""

import os
import shlex
import sys
from pathlib import Path

from fontain import paths, store

SHELLS = ("bash", "zsh", "fish")
# Shells that autoload completion files from a per-user directory.
AUTOLOAD_SHELLS = ("bash", "fish")
MARKER = "# Installed by fontain"
BASH_COMPLETION_SCRIPTS = (
    "/usr/share/bash-completion/bash_completion",
    "/usr/local/share/bash-completion/bash_completion",
    "/etc/bash_completion",
    "/opt/homebrew/etc/profile.d/bash_completion.sh",
    "/usr/local/etc/profile.d/bash_completion.sh",
)


class CompletionError(Exception):
    pass


def _removable(name: str, key: str, manifest: dict) -> bool:
    try:
        return store.find_installed(name, manifest) == key
    except store.StoreError:
        return False


def installed_candidates(qualified: bool = False) -> list[str]:
    """One name per font installed by fontain, each guaranteed to work with ``remove``.

    The bare id is offered when it identifies the font on its own, otherwise
    ``source:id``. With ``qualified``, always ``source:id``.
    """
    manifest = store.load_manifest()
    out = []
    for key, rec in manifest.items():
        if not qualified and _removable(rec["id"], key, manifest):
            out.append(rec["id"])
        elif _removable(key, key, manifest):
            out.append(key)
    return sorted(out, key=str.lower)


def helper_command() -> str:
    """How the scripts call back into fontain: this exact interpreter, so it
    works whether or not a ``fontain`` executable is on PATH."""
    return f"{shlex.quote(sys.executable)} -m fontain"


BASH = r"""# fontain bash completion. Enable with:  eval "$(fontain completion bash)"
_fontain() {
    local line=${COMP_LINE:0:COMP_POINT}
    local -a words
    # Split the line ourselves so "source:id" stays one word ("\ " escapes kept).
    read -a words <<< "$line"
    [[ $line == *[[:space:]] ]] && words+=("")
    local cur=${words[${#words[@]}-1]}
    COMPREPLY=()

    if (( ${#words[@]} <= 2 )); then
        COMPREPLY=($(compgen -W "__COMMANDS__" -- "$cur"))
        return
    fi
    case ${words[1]} in
        __REMOVE_PIPE__)
            if [[ $cur == -* ]]; then
                COMPREPLY=($(compgen -W "--no-cache --help" -- "$cur"))
                return
            fi
            local IFS=$'\n' font kind=installed
            [[ $cur == *:* ]] && kind=installed-keys
            for font in $(__HELPER__ __complete $kind 2>/dev/null); do
                [[ $font == "$cur"* ]] && COMPREPLY+=("$(printf '%q' "$font")")
            done
            # Bash only replaces the text after the last ':' (a word-break
            # character), so drop that prefix from each candidate.
            if [[ $cur == *:* && $COMP_WORDBREAKS == *:* ]]; then
                local prefix=${cur%"${cur##*:}"}
                COMPREPLY=("${COMPREPLY[@]#"$prefix"}")
            fi
            ;;
    esac
}
complete -F _fontain fontain
"""

ZSH = r"""#compdef fontain
# fontain zsh completion. Enable with:  eval "$(fontain completion zsh)"
_fontain() {
    local -a commands fonts
    commands=(__ZSH_COMMANDS__)
    if (( CURRENT == 2 )); then
        _describe -t commands 'fontain command' commands
        return
    fi
    case $words[2] in
        __REMOVE_PIPE__)
            if [[ $PREFIX == *:* ]]; then
                fonts=("${(@f)$(__HELPER__ __complete installed-keys 2>/dev/null)}")
            else
                fonts=("${(@f)$(__HELPER__ __complete installed 2>/dev/null)}")
            fi
            _arguments \
                "--no-cache[don't run fc-cache afterwards]" \
                '*:installed font:{compadd -a fonts}'
            ;;
    esac
}
if (( $+functions[compdef] )); then
    compdef _fontain fontain
fi
"""

FISH = r"""# fontain fish completion. Enable with:  fontain completion fish | source
complete -c fontain -f
__FISH_COMMANDS__
set -l __fontain_remove __REMOVE_SPACE__
complete -c fontain -n "__fish_seen_subcommand_from $__fontain_remove" -a '(__HELPER__ __complete installed 2>/dev/null)' -d 'installed font'
complete -c fontain -n "__fish_seen_subcommand_from $__fontain_remove" -l no-cache -d "don't run fc-cache afterwards"
"""


def _quote_single(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def script(shell: str, commands: list[tuple[str, str]], remove_names: list[str]) -> str:
    """Render the completion script for ``shell``.

    ``commands`` is ``(name, help)`` for each subcommand; ``remove_names`` is
    ``remove`` plus its aliases.
    """
    names = " ".join(n for n, _ in commands)
    if shell == "bash":
        return (BASH.replace("__COMMANDS__", names).replace("__HELPER__", helper_command())
                .replace("__REMOVE_PIPE__", "|".join(remove_names)))
    if shell == "zsh":
        described = " ".join(_quote_single(f"{n}:{h}") for n, h in commands)
        return (ZSH.replace("__ZSH_COMMANDS__", described).replace("__HELPER__", helper_command())
                .replace("__REMOVE_PIPE__", "|".join(remove_names)))
    if shell == "fish":
        lines = "\n".join(
            f"complete -c fontain -n __fish_use_subcommand -a {n} -d {_quote_single(h)}" for n, h in commands
        )
        return (FISH.replace("__FISH_COMMANDS__", lines).replace("__HELPER__", helper_command())
                .replace("__REMOVE_SPACE__", " ".join(remove_names)))
    raise ValueError(f"unsupported shell {shell!r}")


# --- installing into the shell's autoload directory --------------------------


def detect_shell() -> str | None:
    name = Path(os.environ.get("SHELL", "")).name
    return name if name in SHELLS else None


def bash_completion_available() -> bool:
    return any(Path(p).exists() for p in BASH_COMPLETION_SCRIPTS)


def install_path(shell: str) -> Path:
    if shell == "bash":
        if user_dir := os.environ.get("BASH_COMPLETION_USER_DIR"):
            return Path(user_dir) / "completions" / "fontain"
        return paths.xdg("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions" / "fontain"
    if shell == "fish":
        return paths.xdg("XDG_CONFIG_HOME", ".config") / "fish" / "completions" / "fontain.fish"
    raise CompletionError(
        f"{shell} has no per-user completion directory; add "
        f'`eval "$(fontain completion {shell})"` to your ~/.{shell}rc instead'
    )


def loader(shell: str) -> str:
    """A tiny file that regenerates the full script when the shell loads it,
    so upgrades to fontain are picked up automatically."""
    cmd = f"{helper_command()} completion {shell} 2>/dev/null"
    note = f"{MARKER}; remove with `fontain completion --uninstall {shell}`.\n"
    if shell == "bash":
        return note + f'eval "$({cmd})"\n'
    return note + f"{cmd} | source\n"


def is_installed(shell: str) -> bool:
    path = install_path(shell)
    return path.exists() and path.read_text().startswith(MARKER)


def install(shell: str) -> Path:
    path = install_path(shell)
    if path.exists() and not path.read_text().startswith(MARKER):
        raise CompletionError(f"{path} exists and wasn't created by fontain; not overwriting it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(loader(shell))
    return path


def uninstall(shell: str) -> Path | None:
    path = install_path(shell)
    if not path.exists():
        return None
    if not path.read_text().startswith(MARKER):
        raise CompletionError(f"{path} wasn't created by fontain; not removing it")
    path.unlink()
    return path


def _setup_marker() -> Path:
    return paths.state_file().parent / "completion-setup"


def _interactive() -> bool:
    return sys.stderr.isatty()


def auto_setup() -> None:
    """On the first interactive run, enable completion for the user's shell.

    Only ever writes into the shell's own autoload directory (never rc files),
    runs once, and is skipped when FONTAIN_NO_COMPLETION_SETUP is set.
    """
    if os.environ.get("FONTAIN_NO_COMPLETION_SETUP") or not _interactive():
        return
    marker = _setup_marker()
    if marker.exists():
        return
    shell = detect_shell()
    try:
        if shell in AUTOLOAD_SHELLS and not is_installed(shell):
            path = install(shell)
            msg = f"fontain: enabled {shell} tab completion ({path}); it takes effect in new shells."
            if shell == "bash" and not bash_completion_available():
                msg += " It needs the bash-completion package."
            print(msg + " Undo with `fontain completion --uninstall`.", file=sys.stderr)
        elif shell == "zsh":
            print('fontain: for tab completion, add `eval "$(fontain completion zsh)"` to ~/.zshrc',
                  file=sys.stderr)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{shell or 'unknown'}\n")
    except (OSError, CompletionError):
        pass  # never let completion setup get in the way of the actual command

"""Shell tab-completion scripts.

The scripts complete subcommand names statically and ask
``fontain __complete installed`` for the installed fonts that ``remove`` and
``update`` accept.
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
        __FONT_CMDS_PIPE__)
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
        __FONT_CMDS_PIPE__)
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
set -l __fontain_font_cmds __FONT_CMDS_SPACE__
complete -c fontain -n "__fish_seen_subcommand_from $__fontain_font_cmds" -a '(__HELPER__ __complete installed 2>/dev/null)' -d 'installed font'
complete -c fontain -n "__fish_seen_subcommand_from $__fontain_font_cmds" -l no-cache -d "don't run fc-cache afterwards"
"""


def _quote_single(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def script(shell: str, commands: list[tuple[str, str]], font_commands: list[str]) -> str:
    """Render the completion script for ``shell``.

    ``commands`` is ``(name, help)`` for each subcommand; ``font_commands`` are
    the names (with aliases) of commands whose arguments are installed fonts.
    """
    names = " ".join(n for n, _ in commands)
    if shell == "bash":
        return (
            BASH.replace("__COMMANDS__", names)
            .replace("__HELPER__", helper_command())
            .replace("__FONT_CMDS_PIPE__", "|".join(font_commands))
        )
    if shell == "zsh":
        described = " ".join(_quote_single(f"{n}:{h}") for n, h in commands)
        return (
            ZSH.replace("__ZSH_COMMANDS__", described)
            .replace("__HELPER__", helper_command())
            .replace("__FONT_CMDS_PIPE__", "|".join(font_commands))
        )
    if shell == "fish":
        lines = "\n".join(
            f"complete -c fontain -n __fish_use_subcommand -a {n} -d {_quote_single(h)}" for n, h in commands
        )
        return (
            FISH.replace("__FISH_COMMANDS__", lines)
            .replace("__HELPER__", helper_command())
            .replace("__FONT_CMDS_SPACE__", " ".join(font_commands))
        )
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


# --- ask-on-first-Tab (bash) -------------------------------------------------
#
# bash-completion looks for a completion file next to the command's real path
# (<prefix>/share/bash-completion/completions/<cmd>) the first time you press
# Tab. fontain ships TAB_LOADER there. It enables nothing by itself: on that
# first Tab it asks, remembers the answer, and only then loads completion.

TAB_LOADER_RELPATH = Path("share/bash-completion/completions/fontain")

TAB_LOADER = r"""# fontain: bash completion loader, shipped with the fontain package.
# bash-completion sources this on the first <Tab> after `fontain`. Nothing is
# enabled until you say yes; the answer is remembered (change it with
# `fontain completion --install`, `--uninstall` or `--reset`).

_fontain_py=${BASH_SOURCE[0]%/share/bash-completion/completions/*}/bin/python

_fontain_off() { :; }  # declined: no suggestions, fall back to filenames

_fontain_ask() {
    local reply ps tty=${_FONTAIN_TTY:-/dev/tty}
    {
        printf '\nfontain: enable tab completion for fontain? [Y/n] '
        read -r -n 1 reply
        printf '%s\n' "${reply//[$'\r\n']/}"
    } <"$tty" >>"$tty" 2>&1
    if [[ $reply == [nN] ]]; then
        "$_fontain_py" -m fontain __complete decline >/dev/null 2>&1
        printf 'fontain: OK, not asking again. Enable later with `fontain completion --install`.\n' >>"$tty"
        complete -o bashdefault -o default -F _fontain_off fontain
    else
        "$_fontain_py" -m fontain __complete accept >/dev/null 2>&1
        eval "$("$_fontain_py" -m fontain completion bash 2>/dev/null)"
    fi
    # Readline still thinks the cursor is on the original line: redraw it.
    ps=${PS1@P}
    printf '%s%s' "${ps##*$'\n'}" "$COMP_LINE" >>"$tty"
    COMPREPLY=()
    if declare -F _fontain >/dev/null; then
        _fontain "$@"
    fi
}

case $("$_fontain_py" -m fontain __complete consent 2>/dev/null) in
    yes) eval "$("$_fontain_py" -m fontain completion bash 2>/dev/null)" ;;
    no) complete -o bashdefault -o default -F _fontain_off fontain ;;
    *) complete -F _fontain_ask fontain ;;
esac
"""


def _consent_file() -> Path:
    return paths.state_file().parent / "completion"


def get_consent() -> str:
    """``yes``, ``no`` or ``ask`` (never answered)."""
    try:
        value = _consent_file().read_text().strip()
    except FileNotFoundError:
        return "ask"
    return value if value in ("yes", "no") else "ask"


def set_consent(value: str | None) -> None:
    path = _consent_file()
    if value is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n")


def tab_loader_path() -> Path | None:
    """Where bash-completion will look for fontain's loader, if we're in a venv."""
    if sys.prefix == sys.base_prefix:
        return None  # system/user site install: don't write into a shared prefix
    return Path(sys.prefix) / TAB_LOADER_RELPATH


def ensure_tab_loader() -> None:
    """Make sure the loader exists in fontain's own install prefix.

    Normal installs ship it as package data; editable installs don't, so put
    it there ourselves. Never touches the user's own config or rc files.
    """
    path = tab_loader_path()
    if path is None:
        return
    try:
        if path.exists() and path.read_text() == TAB_LOADER:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TAB_LOADER)
    except OSError:
        pass

"""Shell tab-completion scripts.

The scripts complete subcommand names statically and ask
``fontain __complete installed`` for the fonts that ``remove`` accepts.
That command only reads the installed-font manifest, so it is fast and
never touches the network.
"""

from collections import Counter

from fontain import store

SHELLS = ("bash", "zsh", "fish")


def installed_candidates() -> list[str]:
    """Names ``fontain remove`` accepts: every ``source:id``, plus bare ids that are unique."""
    manifest = store.load_manifest()
    ids = Counter(rec["id"] for rec in manifest.values())
    keys = sorted(manifest, key=str.lower)
    bare = sorted((i for i, n in ids.items() if n == 1), key=str.lower)
    return bare + keys


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
            local IFS=$'\n' font
            for font in $(command fontain __complete installed 2>/dev/null); do
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
            fonts=("${(@f)$(command fontain __complete installed 2>/dev/null)}")
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
complete -c fontain -n "__fish_seen_subcommand_from $__fontain_remove" -a '(command fontain __complete installed 2>/dev/null)' -d 'installed font'
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
        return (BASH.replace("__COMMANDS__", names)
                .replace("__REMOVE_PIPE__", "|".join(remove_names)))
    if shell == "zsh":
        described = " ".join(_quote_single(f"{n}:{h}") for n, h in commands)
        return (ZSH.replace("__ZSH_COMMANDS__", described)
                .replace("__REMOVE_PIPE__", "|".join(remove_names)))
    if shell == "fish":
        lines = "\n".join(
            f"complete -c fontain -n __fish_use_subcommand -a {n} -d {_quote_single(h)}" for n, h in commands
        )
        return (FISH.replace("__FISH_COMMANDS__", lines)
                .replace("__REMOVE_SPACE__", " ".join(remove_names)))
    raise ValueError(f"unsupported shell {shell!r}")

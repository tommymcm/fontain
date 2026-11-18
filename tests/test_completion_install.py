import os
import subprocess
import sys
from pathlib import Path

import pytest

from fontain import cli, completion, paths, store


def _bash_file():
    return paths.xdg("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions" / "fontain"


def test_install_uninstall_bash(capsys):
    assert cli.main(["completion", "--install", "bash"]) == 0
    text = _bash_file().read_text()
    assert text.startswith(completion.MARKER)
    assert f'eval "$({sys.executable} -m fontain completion bash 2>/dev/null)"' in text
    assert cli.main(["completion", "--uninstall", "bash"]) == 0
    assert not _bash_file().exists()
    assert cli.main(["completion", "--uninstall", "bash"]) == 0
    assert "No fontain bash completion" in capsys.readouterr().out


def test_install_fish_path():
    assert cli.main(["completion", "--install", "fish"]) == 0
    path = paths.xdg("XDG_CONFIG_HOME", ".config") / "fish" / "completions" / "fontain.fish"
    assert path.read_text().rstrip().endswith("completion fish 2>/dev/null | source")


def test_bash_completion_user_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BASH_COMPLETION_USER_DIR", str(tmp_path / "bc"))
    assert completion.install_path("bash") == tmp_path / "bc" / "completions" / "fontain"


def test_install_detects_shell(monkeypatch):
    monkeypatch.setenv("SHELL", "/usr/bin/bash")
    assert cli.main(["completion", "--install"]) == 0
    assert _bash_file().exists()
    monkeypatch.setenv("SHELL", "/bin/tcsh")
    assert cli.main(["completion", "--install"]) == 2


def test_zsh_install_explains(capsys):
    assert cli.main(["completion", "--install", "zsh"]) == 1
    assert "~/.zshrc" in capsys.readouterr().err


def test_never_touches_foreign_files():
    _bash_file().parent.mkdir(parents=True)
    _bash_file().write_text("# my own completion\n")
    assert cli.main(["completion", "--install", "bash"]) == 1
    assert cli.main(["completion", "--uninstall", "bash"]) == 1
    assert _bash_file().read_text() == "# my own completion\n"


def test_print_requires_shell():
    assert cli.main(["completion"]) == 2


@pytest.fixture
def interactive(monkeypatch, capsys):
    """Pretend we're in a terminal; returns a function giving new stderr output."""
    monkeypatch.delenv("FONTAIN_NO_COMPLETION_SETUP")
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr(completion, "bash_completion_available", lambda: True)
    monkeypatch.setattr(completion, "_interactive", lambda: True)
    return lambda: capsys.readouterr().err


def test_auto_setup_first_run_only(interactive):
    assert cli.main(["list"]) == 0
    assert _bash_file().exists()
    assert "enabled bash tab completion" in interactive()

    assert cli.main(["list"]) == 0
    assert interactive() == ""

    # once the user removes it, it stays removed
    assert cli.main(["completion", "--uninstall"]) == 0
    assert cli.main(["list"]) == 0
    assert not _bash_file().exists()


def test_auto_setup_respects_opt_out(interactive, monkeypatch):
    monkeypatch.setenv("FONTAIN_NO_COMPLETION_SETUP", "1")
    cli.main(["list"])
    assert not _bash_file().exists()


def test_auto_setup_skipped_when_not_a_terminal(monkeypatch):
    monkeypatch.delenv("FONTAIN_NO_COMPLETION_SETUP")
    monkeypatch.setenv("SHELL", "/bin/bash")
    cli.main(["list"])  # pytest's captured stderr is not a TTY
    assert not _bash_file().exists()


def test_auto_setup_zsh_hint_once(interactive, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    cli.main(["list"])
    assert "~/.zshrc" in interactive()
    cli.main(["list"])
    assert interactive() == ""


def test_auto_setup_not_for_completion_commands(interactive):
    cli.main(["__complete", "installed"])
    assert not _bash_file().exists()


BASH_COMPLETION = next((p for p in completion.BASH_COMPLETION_SCRIPTS if Path(p).is_file()), None)


@pytest.mark.skipif(BASH_COMPLETION is None, reason="bash-completion not installed")
def test_real_bash_completion_autoloads(capsys):
    """bash-completion finds the installed file on its own; no rc edits involved."""
    store.save_manifest({"fontsource:inter": {"source": "fontsource", "id": "inter", "family": "Inter",
                                              "files": [], "installed": ""}})
    cli.main(["completion", "--install", "bash"])
    env = {k: v for k, v in os.environ.items() if k.startswith(("XDG_", "FONTAIN_", "HOME"))}
    env["PATH"] = "/usr/bin:/bin"
    driver = (
        f'source "{BASH_COMPLETION}"\n'
        "complete -p fontain >/dev/null 2>&1 && echo 'preloaded?!'\n"
        # what bash-completion does on the first Tab for an unknown command:
        "if declare -F _comp_load >/dev/null; then _comp_load fontain; else __load_completion fontain; fi\n"
        "complete -p fontain\n"
        'COMP_LINE="fontain remove "; COMP_POINT=${#COMP_LINE}; _fontain\n'
        'echo "${COMPREPLY[*]}"\n'
    )
    out = subprocess.run(["bash", "--norc", "--noprofile", "-c", driver],
                         capture_output=True, text=True, env=env, check=True).stdout.splitlines()
    assert out == ["complete -F _fontain fontain", "inter"]

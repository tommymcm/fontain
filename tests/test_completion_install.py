import os
import pwd
import subprocess
import sys
from pathlib import Path

import pytest

from fontain import cli, completion, paths, store

REPO = Path(__file__).resolve().parent.parent


def _bash_file():
    return paths.xdg("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions" / "fontain"


# --- consent and the --install/--uninstall/--reset commands -------------------


def test_consent_roundtrip(capsys):
    assert completion.get_consent() == "ask"
    for action, expected in (("accept", "yes"), ("decline", "no")):
        cli.main(["__complete", action])
        cli.main(["__complete", "consent"])
        assert capsys.readouterr().out.strip() == expected


def test_install_bash_with_loader_only_records_consent():
    completion.ensure_tab_loader()
    assert cli.main(["completion", "--install", "bash"]) == 0
    assert completion.get_consent() == "yes"
    assert not _bash_file().exists()  # the shipped loader does the work


def test_install_bash_without_loader_writes_user_file(monkeypatch):
    monkeypatch.setattr(completion, "tab_loader_path", lambda: None)
    assert cli.main(["completion", "--install", "bash"]) == 0
    assert completion.get_consent() == "yes"
    assert f'eval "$({sys.executable} -m fontain completion bash 2>/dev/null)"' in _bash_file().read_text()


def test_uninstall_declines_and_removes(monkeypatch):
    monkeypatch.setattr(completion, "tab_loader_path", lambda: None)
    cli.main(["completion", "--install", "bash"])
    assert cli.main(["completion", "--uninstall", "bash"]) == 0
    assert not _bash_file().exists()
    assert completion.get_consent() == "no"


def test_reset_asks_again(monkeypatch):
    monkeypatch.setattr(completion, "tab_loader_path", lambda: None)
    cli.main(["completion", "--install", "bash"])
    assert cli.main(["completion", "--reset"]) == 0
    assert completion.get_consent() == "ask"
    assert not _bash_file().exists()


def test_install_fish_path():
    assert cli.main(["completion", "--install", "fish"]) == 0
    path = paths.xdg("XDG_CONFIG_HOME", ".config") / "fish" / "completions" / "fontain.fish"
    assert path.read_text().rstrip().endswith("completion fish 2>/dev/null | source")


def test_install_detects_shell(monkeypatch):
    monkeypatch.setattr(completion, "tab_loader_path", lambda: None)
    monkeypatch.setenv("SHELL", "/usr/bin/bash")
    assert cli.main(["completion", "--install"]) == 0
    assert _bash_file().exists()
    monkeypatch.setenv("SHELL", "/bin/tcsh")
    assert cli.main(["completion", "--install"]) == 2


def test_zsh_install_explains(capsys):
    assert cli.main(["completion", "--install", "zsh"]) == 1
    assert "~/.zshrc" in capsys.readouterr().err


def test_never_touches_foreign_files(monkeypatch):
    monkeypatch.setattr(completion, "tab_loader_path", lambda: None)
    _bash_file().parent.mkdir(parents=True)
    _bash_file().write_text("# my own completion\n")
    assert cli.main(["completion", "--install", "bash"]) == 1
    assert cli.main(["completion", "--uninstall", "bash"]) == 1
    assert cli.main(["completion", "--reset"]) == 0
    assert _bash_file().read_text() == "# my own completion\n"


def test_print_requires_shell():
    assert cli.main(["completion"]) == 2


# --- the loader file -----------------------------------------------------------


def test_running_fontain_never_installs_anything_for_the_user():
    cli.main(["list"])
    assert not _bash_file().exists()
    assert completion.get_consent() == "ask"


def test_ensure_tab_loader_writes_and_repairs():
    path = completion.tab_loader_path()
    cli.main(["list"])
    assert path.read_text() == completion.TAB_LOADER
    path.write_text("stale")
    cli.main(["list"])
    assert path.read_text() == completion.TAB_LOADER


def test_packaged_loader_matches_source():
    shipped = REPO / "data" / completion.TAB_LOADER_RELPATH
    assert shipped.read_text() == completion.TAB_LOADER, "regenerate data/share/... from TAB_LOADER"


BASH_COMPLETION = next((p for p in completion.BASH_COMPLETION_SCRIPTS if Path(p).is_file()), None)


@pytest.fixture
def fake_install(tmp_path):
    """A fake `uv tool` layout: <prefix>/bin/{fontain,python} + the shipped loader,
    with `fontain` reached through a symlink on PATH like ~/.local/bin/fontain."""
    prefix = tmp_path / "tool"
    (prefix / "bin").mkdir(parents=True)
    py = prefix / "bin" / "python"
    py.write_text(f'#!/bin/sh\nPYTHONPATH="{REPO / "src"}" exec "{sys.executable}" "$@"\n')
    py.chmod(0o755)
    exe = prefix / "bin" / "fontain"
    exe.write_text(f'#!/bin/sh\nexec "{py}" -m fontain "$@"\n')
    exe.chmod(0o755)
    loader = prefix / completion.TAB_LOADER_RELPATH
    loader.parent.mkdir(parents=True)
    loader.write_text(completion.TAB_LOADER)
    userbin = tmp_path / "localbin"
    userbin.mkdir()
    (userbin / "fontain").symlink_to(exe)
    store.save_manifest({"fontsource:inter": {"source": "fontsource", "id": "inter", "family": "Inter",
                                              "files": [], "installed": ""}})
    return userbin


def _press_tab(userbin, tmp_path, answer, line="fontain remove "):
    """Load completion the way bash-completion does on a first Tab, answer the prompt."""
    tty = tmp_path / "tty"
    tty.write_text(answer)
    env = {k: v for k, v in os.environ.items() if k.startswith(("XDG_", "FONTAIN_", "HOME"))}
    env.update(PATH=f"{userbin}:/usr/bin:/bin", _FONTAIN_TTY=str(tty))
    driver = (
        "PS1='\\u@host$ '\n"  # non-interactive bash unsets PS1 from the environment
        f'source "{BASH_COMPLETION}"\n'
        "_comp_load fontain || __load_completion fontain\n"
        "complete -p fontain\n"
        f'COMP_LINE="{line}"; COMP_POINT=${{#COMP_LINE}}\n'
        'fn=$(complete -p fontain | sed -E "s/.*-F ([^ ]+).*/\\1/")\n'
        '"$fn" fontain "" ""\n'
        'echo "reply: ${COMPREPLY[*]}"\n'
        "complete -p fontain\n"
    )
    out = subprocess.run(["bash", "--norc", "--noprofile", "-c", driver],
                         capture_output=True, text=True, env=env, check=True).stdout.splitlines()
    return out, tty.read_text()


@pytest.mark.skipif(BASH_COMPLETION is None, reason="bash-completion not installed")
@pytest.mark.parametrize("answer", ["y", "\r", "Y"])
def test_first_tab_asks_then_completes(fake_install, tmp_path, answer):
    out, screen = _press_tab(fake_install, tmp_path, answer)
    assert out == ["complete -F _fontain_ask fontain", "reply: inter", "complete -F _fontain fontain"]
    assert "enable tab completion for fontain? [Y/n]" in screen
    assert screen.endswith(f"{pwd.getpwuid(os.getuid()).pw_name}@host$ fontain remove ")  # prompt + line redrawn
    assert completion.get_consent() == "yes"

    # next shell: no question, straight to completion
    out, screen = _press_tab(fake_install, tmp_path, "")
    assert out[0] == "complete -F _fontain fontain" and "enable" not in screen


@pytest.mark.skipif(BASH_COMPLETION is None, reason="bash-completion not installed")
def test_first_tab_decline_is_remembered(fake_install, tmp_path):
    out, screen = _press_tab(fake_install, tmp_path, "n")
    assert out == ["complete -F _fontain_ask fontain", "reply: ", "complete -o bashdefault -o default -F _fontain_off fontain"]
    assert "not asking again" in screen
    assert completion.get_consent() == "no"

    out, screen = _press_tab(fake_install, tmp_path, "")
    assert out[0] == "complete -o bashdefault -o default -F _fontain_off fontain"
    assert screen == ""  # never asked again

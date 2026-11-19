import io
import os
import subprocess
import sys

import pytest

from fontain import cli, fontcache, repl, store

SCRIPT = """\
# my fonts
install fake:mono --no-cache   # trailing comment

fontain list                   # habitual prefix is fine
"""


class FakeSource:
    name = "fake"

    def fetch_index(self):
        from fontain.sources.base import FontEntry

        return [FontEntry(source="fake", id=i, family=i.title()) for i in ("mono", "sans", "Acme Sans")]

    def install_files(self, entry, dest, sel):
        f = dest / f"{entry.id}-Regular.ttf"
        f.write_bytes(b"x")
        return [f]


@pytest.fixture
def fake(monkeypatch):
    from fontain import sources

    monkeypatch.setattr(sources, "registry", lambda: {"fake": FakeSource()})
    rebuilds = []
    monkeypatch.setattr(fontcache, "_rebuild", lambda root, quiet=False: rebuilds.append(root) or True)
    return rebuilds


def test_run_file(tmp_path, fake, capsys):
    script = tmp_path / "fonts.txt"
    script.write_text(SCRIPT)
    assert cli.main(["run", str(script)]) == 0
    assert store.is_installed("fake:mono")
    assert "fake:mono" in capsys.readouterr().out  # `list` ran


def test_run_stdin_and_piped_no_args(monkeypatch, fake):
    monkeypatch.setattr("sys.stdin", io.StringIO("install fake:mono\n"))
    assert cli.main(["run", "-"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("install 'fake:Acme Sans'\n"))  # quoting works
    assert cli.main([]) == 0  # `fontain < file`
    assert store.is_installed("fake:mono") and store.is_installed("fake:Acme Sans")


def test_cache_rebuilt_once_at_end(monkeypatch, fake):
    monkeypatch.setattr("sys.stdin", io.StringIO("install fake:mono\ninstall fake:sans\nremove mono\n"))
    assert cli.main(["run"]) == 0
    assert len(fake) == 1  # three changes, one fc-cache


def test_stops_at_first_failure(monkeypatch, fake, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("install fake:mono\ninstall fake:nope\ninstall fake:sans\n"))
    assert cli.main(["run"]) == 1
    assert "<stdin>:2: `install fake:nope` failed (exit 1)" in capsys.readouterr().err
    assert store.is_installed("fake:mono") and not store.is_installed("fake:sans")
    assert len(fake) == 1  # the cache still gets rebuilt for what did change


def test_keep_going(monkeypatch, fake, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("frob\ninstall fake:mono\nlist --bogus\ninstall fake:sans\n"))
    assert cli.main(["run", "--keep-going"]) == 2
    err = capsys.readouterr().err
    assert "<stdin>:1:" in err and "<stdin>:3:" in err
    assert store.is_installed("fake:mono") and store.is_installed("fake:sans")


def test_exit_stops_script(monkeypatch, fake):
    monkeypatch.setattr("sys.stdin", io.StringIO("install fake:mono\nexit\ninstall fake:sans\n"))
    assert cli.main(["run"]) == 0
    assert not store.is_installed("fake:sans")


@pytest.mark.parametrize("line", ["shell", "run other.txt"])
def test_no_nesting_in_scripts(monkeypatch, fake, capsys, line):
    monkeypatch.setattr("sys.stdin", io.StringIO(line + "\n"))
    assert cli.main(["run"]) == 2
    assert "can't be used inside a script" in capsys.readouterr().err


def test_shell_can_run_a_script(tmp_path, fake, monkeypatch):
    script = tmp_path / "setup.txt"
    script.write_text("install fake:mono\n")
    lines = iter([f"run {script}", "exit"])
    monkeypatch.setattr(repl, "_setup_readline", lambda completer: None)
    real = repl.repl
    monkeypatch.setattr(repl, "repl", lambda run, help_text, completer, logo=None:
                        real(run, help_text, completer, read=lambda p: next(lines)))
    assert cli.main(["shell"]) == 0
    assert store.is_installed("fake:mono")


def test_missing_file(capsys):
    assert cli.main(["run", "/nope/fonts.txt"]) == 1
    assert "can't read script /nope/fonts.txt" in capsys.readouterr().err


def test_executable_script_with_shebang(tmp_path):
    """`#!/usr/bin/env -S fontain run` works as the first line of a script."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fontain = bindir / "fontain"
    fontain.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m fontain "$@"\n')
    fontain.chmod(0o755)
    script = tmp_path / "setup"
    script.write_text("#!/usr/bin/env -S fontain run\n# nothing installed yet\nlist\n")
    script.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    out = subprocess.run([str(script)], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert "No fonts installed" in out.stdout

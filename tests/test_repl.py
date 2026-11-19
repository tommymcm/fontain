import pytest

from fontain import cli, fontcache, index, repl, repos, store


def _session(monkeypatch, lines):
    """Run the real shell with scripted input; Ctrl-C/EOF given as exceptions."""
    feed = iter(lines)

    def read(prompt):
        item = next(feed, EOFError)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item()
        return item

    monkeypatch.setattr(repl, "_setup_readline", lambda completer: None)
    real = repl.repl
    monkeypatch.setattr(
        repl,
        "repl",
        lambda run, help_text, completer, logo=None: real(run, help_text, completer, read=read, logo=logo),
    )
    return cli.main(["shell"])


@pytest.fixture
def installed(monkeypatch):
    monkeypatch.setattr(fontcache, "refresh", lambda root, quiet=False: True)
    store.save_manifest(
        {
            k: {
                "source": k.split(":")[0],
                "id": k.split(":")[1],
                "family": k.split(":")[1],
                "files": [],
                "installed": "",
            }
            for k in ("fontsource:inter", "fontsource:inter-tight", "nerd:JetBrainsMono")
        }
    )


def test_commands_run_and_errors_dont_exit(monkeypatch, capsys, installed):
    rc = _session(
        monkeypatch,
        [
            "list",
            "",  # blank line
            "list --bogus",  # argparse error -> stays in shell
            "frobnicate",  # unknown command
            "install 'unterminated",  # shlex error
            "search --help",  # --help -> stays in shell
            "fontain remove inter",  # habitual prefix tolerated
            KeyboardInterrupt,  # Ctrl-C at the prompt clears the line
            "list",
            "exit",
            "list",  # never reached
        ],
    )
    out, errors = capsys.readouterr()
    assert rc == 0
    assert out.count("nerd:JetBrainsMono") == 2  # both `list`s ran
    assert "unrecognized arguments: --bogus" in errors
    assert "unknown command 'frobnicate'" in errors and "__complete" not in errors
    assert "No closing quotation" in errors
    assert "usage: fontain search" in out
    assert "Removed fontsource:inter" in out
    assert not store.is_installed("fontsource:inter")


def test_ctrl_d_exits(monkeypatch, capsys):
    assert _session(monkeypatch, []) == 0  # immediate EOF


def test_interrupted_command_keeps_shell(monkeypatch, capsys):
    def boom(args):
        raise KeyboardInterrupt  # e.g. Ctrl-C during a download

    monkeypatch.setattr(cli, "cmd_install", boom)
    assert _session(monkeypatch, ["install inter", "help", "exit"]) == 0
    assert "COMMAND" in capsys.readouterr().out  # the shell carried on after Ctrl-C


def test_help(monkeypatch, capsys):
    _session(monkeypatch, ["help", "help install", "help nope", "shell", "quit"])
    out, errors = capsys.readouterr()
    assert "search" in out and "exit" in out and "__complete" not in out
    assert "--weights" in out
    assert "unknown command 'nope'" in errors
    assert "Already in the fontain shell" in out


def test_no_args_with_terminal_stdin_but_redirected_stdout_is_an_error(monkeypatch):
    class TTY:
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", TTY())
    with pytest.raises(SystemExit):
        cli.main([])  # stdout is captured (not a terminal): no shell, no script


@pytest.fixture
def completer():
    commands, subcommands, _ = cli.shell_context()  # the same lists the real shell uses
    return repl.Completer(commands, subcommands)


def test_readline_hook_appends_space(completer, monkeypatch):
    class FakeReadline:
        line = "rem"

        def get_line_buffer(self):
            return self.line

        def get_endidx(self):
            return len(self.line)

    monkeypatch.setattr(repl, "readline", FakeReadline())
    assert completer.complete("rem", 0) == "remove "
    assert completer.complete("rem", 1) is None


def test_complete_commands(completer):
    assert completer.candidates("re") == ["refresh", "remove", "repo"]
    assert completer.candidates("")[:3] == ["add", "cache", "completion"]
    assert "exit" in completer.candidates("") and "__complete" not in completer.candidates("")
    assert completer.candidates("help ins") == ["install"]
    assert completer.candidates("repo p") == ["prefer"]


def test_complete_remove(completer, installed):
    assert completer.candidates("remove ") == [
        "fontsource:inter",
        "fontsource:inter-tight",
        "inter",
        "inter-tight",
        "JetBrainsMono",
        "nerd:JetBrainsMono",
    ]
    assert completer.candidates("rm inter-") == ["inter-tight"]
    assert completer.candidates("remove nerd:") == ["nerd:JetBrainsMono"]
    assert completer.candidates("fontain remove J") == ["JetBrainsMono"]
    assert completer.candidates("remove --") == []


def test_complete_repo_names(completer, tmp_path):
    (tmp_path / "lib").mkdir()
    repos.save({"work": {"type": "local", "target": str(tmp_path / "lib")}})
    assert completer.candidates("repo rm w") == ["work"]
    assert "google" in completer.candidates("repo prefer ")


def test_complete_install_from_cache_only(completer, monkeypatch):
    from fontain.sources.base import FontEntry

    index.write_cache("google", [FontEntry(source="google", id="lato", family="Lato")])
    assert completer.candidates("install la") == ["lato"]
    assert completer.candidates("info google:l") == ["google:lato"]
    assert completer.candidates("install zz") == []  # no network: conftest blocks it


def test_spaces_escaped(completer):
    store.save_manifest(
        {
            "work:Acme Sans": {
                "source": "work",
                "id": "Acme Sans",
                "family": "Acme Sans",
                "files": [],
                "installed": "",
            }
        }
    )
    assert completer.candidates("remove Ac") == ["Acme\\ Sans"]


def test_logo_has_blank_line_above_and_below(capsys):
    repl.repl(
        lambda argv: 0,
        lambda cmd: None,
        repl.Completer([], {}),
        read=lambda prompt: (_ for _ in ()).throw(EOFError),
        logo="LOGO1\nLOGO2",
    )
    out = capsys.readouterr().out
    assert out.startswith("\nLOGO1\nLOGO2\n\nfontain ")

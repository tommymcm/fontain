import os
import shutil
import subprocess
import sys

import pytest

from fontain import cli, completion, store


def _install(*keys):
    store.save_manifest(
        {
            k: {
                "source": k.split(":")[0],
                "id": k.split(":", 1)[1],
                "family": k,
                "files": [],
                "installed": "",
            }
            for k in keys
        }
    )


def test_one_removable_name_per_font():
    _install("fontsource:atkinson-hyperlegible", "nerd:JetBrainsMono", "work:Acme Sans")
    assert completion.installed_candidates() == ["Acme Sans", "atkinson-hyperlegible", "JetBrainsMono"]
    assert completion.installed_candidates(qualified=True) == [
        "fontsource:atkinson-hyperlegible",
        "nerd:JetBrainsMono",
        "work:Acme Sans",
    ]


def test_ambiguous_ids_are_qualified():
    # "Inter" and "inter" collide because remove ignores case
    _install("fontsource:inter", "inter:Inter", "nerd:JetBrainsMono")
    assert completion.installed_candidates() == ["fontsource:inter", "inter:Inter", "JetBrainsMono"]


def test_every_candidate_is_removable():
    _install("fontsource:inter", "inter:Inter", "google:inter", "work:Acme Sans", "nerd:Acme")
    manifest = store.load_manifest()
    for qualified in (False, True):
        names = completion.installed_candidates(qualified)
        assert len(names) == len(manifest)
        assert sorted(store.find_installed(n, manifest) for n in names) == sorted(manifest)


def test_complete_command(capsys):
    _install("nerd:JetBrainsMono")
    assert cli.main(["__complete", "installed"]) == 0
    assert capsys.readouterr().out.split() == ["JetBrainsMono"]
    assert cli.main(["__complete", "installed-keys"]) == 0
    assert capsys.readouterr().out.split() == ["nerd:JetBrainsMono"]


def test_hidden_from_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "completion" in out and "__complete" not in out


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_scripts_render(shell, capsys):
    assert cli.main(["completion", shell]) == 0
    out = capsys.readouterr().out
    assert f"{sys.executable} -m fontain __complete" in out  # not whatever is on PATH
    assert "uninstall" in out and "search" in out
    assert "__" + "COMMANDS" not in out and "__REMOVE" not in out


BASH = shutil.which("bash")


def _bash_runner(script, env):
    def run(line):
        driver = (
            f'source "{script}"\n'
            'COMP_LINE="$1"; COMP_POINT=${#COMP_LINE}\n'
            "_fontain\n"
            'printf "%s\\n" "${COMPREPLY[@]}"\n'
        )
        result = subprocess.run(
            [BASH, "--norc", "-c", driver, "bash", line],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line]

    return run


@pytest.fixture
def bash_complete(tmp_path, capsys, monkeypatch):
    """f(line) -> COMPREPLY, running the real bash script against a fake helper."""
    fake = tmp_path / "fake-helper"
    fake.write_text(
        "#!/bin/sh\n"
        'case "$2" in\n'
        "  installed) printf '%s\\n' inter 'Acme Sans' ;;\n"
        "  installed-keys) printf '%s\\n' fontsource:inter 'work:Acme Sans' ;;\n"
        "esac\n"
    )
    fake.chmod(0o755)
    monkeypatch.setattr(completion, "helper_command", lambda: str(fake))
    cli.main(["completion", "bash"])
    script = tmp_path / "fontain.bash"
    script.write_text(capsys.readouterr().out)
    return _bash_runner(script, {"PATH": "/usr/bin:/bin"})


@pytest.mark.skipif(BASH is None, reason="bash not installed")
@pytest.mark.parametrize(
    "line,expected",
    [
        ("fontain re", ["remove", "refresh", "repo"]),
        ("fontain remove ", ["inter", "Acme\\ Sans"]),
        ("fontain rm in", ["inter"]),
        ("fontain uninstall inter ", ["inter", "Acme\\ Sans"]),
        ("fontain remove fontsource:", ["inter"]),  # text before ':' is not replaced by bash
        ("fontain remove work:Ac", ["Acme\\ Sans"]),
        ("fontain remove Acme\\ S", ["Acme\\ Sans"]),
        ("fontain remove --no", ["--no-cache"]),
        ("fontain install in", []),
    ],
)
def test_bash_completion(bash_complete, line, expected):
    assert bash_complete(line) == expected


@pytest.mark.skipif(BASH is None, reason="bash not installed")
def test_bash_end_to_end_without_fontain_on_path(tmp_path, capsys):
    """The real script + real helper, with no `fontain` executable on PATH."""
    _install("fontsource:atkinson-hyperlegible", "fontsource:inter", "inter:Inter")
    cli.main(["completion", "bash"])
    script = tmp_path / "fontain.bash"
    script.write_text(capsys.readouterr().out)
    env = {k: v for k, v in os.environ.items() if k.startswith(("XDG_", "FONTAIN_", "HOME"))}
    env["PATH"] = "/usr/bin:/bin"
    run = _bash_runner(script, env)

    names = run("fontain remove ")
    assert names == ["atkinson-hyperlegible", "fontsource:inter", "inter:Inter"]
    assert run("fontain remove at") == ["atkinson-hyperlegible"]
    assert run("fontain remove inter:") == ["Inter"]
    for name in names:
        assert cli.main(["remove", "--no-cache", name]) == 0
    assert store.load_manifest() == {}

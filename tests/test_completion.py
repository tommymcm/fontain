import shutil
import subprocess

import pytest

from fontain import cli, completion, store


def _install(*keys):
    store.save_manifest({
        k: {"source": k.split(":")[0], "id": k.split(":", 1)[1], "family": k, "files": [], "installed": ""}
        for k in keys
    })


def test_installed_candidates():
    _install("fontsource:inter", "google:inter", "nerd:JetBrainsMono", "work:Acme Sans")
    # "inter" is ambiguous, so only its qualified forms are offered
    assert completion.installed_candidates() == [
        "Acme Sans", "JetBrainsMono",
        "fontsource:inter", "google:inter", "nerd:JetBrainsMono", "work:Acme Sans",
    ]


def test_complete_command(capsys):
    _install("nerd:JetBrainsMono")
    assert cli.main(["__complete", "installed"]) == 0
    assert capsys.readouterr().out.split() == ["JetBrainsMono", "nerd:JetBrainsMono"]


def test_hidden_from_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "completion" in out and "__complete" not in out


@pytest.mark.parametrize("shell", completion.SHELLS)
def test_scripts_render(shell, capsys):
    assert cli.main(["completion", shell]) == 0
    out = capsys.readouterr().out
    assert "__complete installed" in out
    assert "uninstall" in out and "search" in out
    assert "__" + "COMMANDS" not in out and "__REMOVE" not in out


BASH = shutil.which("bash")


@pytest.fixture
def bash_complete(tmp_path, capsys):
    """Return f(line) -> COMPREPLY, running the real bash script against a fake fontain."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "fontain"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' inter 'Acme Sans' fontsource:inter 'work:Acme Sans'\n")
    fake.chmod(0o755)
    cli.main(["completion", "bash"])
    script = tmp_path / "fontain.bash"
    script.write_text(capsys.readouterr().out)

    def run(line):
        driver = (
            f'source "{script}"\n'
            'COMP_LINE="$1"; COMP_POINT=${#COMP_LINE}\n'
            "_fontain\n"
            'printf "%s\\n" "${COMPREPLY[@]}"\n'
        )
        result = subprocess.run(
            [BASH, "--norc", "-c", driver, "bash", line],
            capture_output=True, text=True, env={"PATH": f"{bindir}:/usr/bin:/bin"}, check=True,
        )
        return [l for l in result.stdout.splitlines() if l]

    return run


@pytest.mark.skipif(BASH is None, reason="bash not installed")
@pytest.mark.parametrize("line,expected", [
    ("fontain re", ["remove", "refresh", "repo"]),
    ("fontain remove ", ["inter", "Acme\\ Sans", "fontsource:inter", "work:Acme\\ Sans"]),
    ("fontain rm in", ["inter"]),
    ("fontain uninstall inter ", ["inter", "Acme\\ Sans", "fontsource:inter", "work:Acme\\ Sans"]),
    ("fontain remove fontsource:", ["inter"]),  # text before ':' is not replaced by bash
    ("fontain remove work:Ac", ["Acme\\ Sans"]),
    ("fontain remove Acme\\ S", ["Acme\\ Sans"]),
    ("fontain remove --no", ["--no-cache"]),
    ("fontain install in", []),
])
def test_bash_completion(bash_complete, line, expected):
    assert bash_complete(line) == expected

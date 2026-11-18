import json

import pytest

from fontain import cli, fontcache, paths, repos, store


@pytest.mark.parametrize("spec,repo", [
    ("github:rsms/inter", "rsms/inter"),
    ("https://github.com/rsms/inter", "rsms/inter"),
    ("https://github.com/rsms/inter.git", "rsms/inter"),
    ("github.com/be5invis/Iosevka/releases", "be5invis/Iosevka"),
])
def test_parse_github(spec, repo):
    assert repos.parse_spec(spec) == {"type": "github", "target": repo}


def test_parse_local(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "fonts").mkdir()
    assert repos.parse_spec("~/fonts") == {"type": "local", "target": str(tmp_path / "fonts")}


@pytest.mark.parametrize("spec", ["github:not-a-repo", "github:a/b/c", "/definitely/not/here"])
def test_parse_invalid(spec):
    with pytest.raises(repos.RepoError):
        repos.parse_spec(spec)


@pytest.mark.parametrize("name", ["Bad", "has space", "google", "-x", "mine"])
def test_check_name_rejects(name):
    with pytest.raises(repos.RepoError):
        repos.check_name(name, {"google"}, {"mine": {}})


def test_corrupt_config():
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text("{nope")
    with pytest.raises(repos.RepoError):
        repos.load()
    assert cli.main(["search", "x"]) == 1  # reported, not a traceback


@pytest.fixture
def no_fc(monkeypatch):
    monkeypatch.setattr(fontcache, "refresh", lambda root, quiet=False: True)


def test_local_repo_end_to_end(tmp_path, capsys, no_fc):
    lib = tmp_path / "lib"
    (lib / "acme").mkdir(parents=True)
    (lib / "acme" / "Acme-Regular.otf").write_bytes(b"r")
    (lib / "acme" / "Acme-Bold.otf").write_bytes(b"b")

    assert cli.main(["repo", "add", "work", str(lib)]) == 0
    assert "1 font(s)" in capsys.readouterr().out
    assert json.loads(paths.config_file().read_text()) == {"work": {"type": "local", "target": str(lib)}}

    assert cli.main(["repo"]) == 0
    out = capsys.readouterr().out
    assert "fontsource" in out and "work" in out and str(lib) in out

    assert cli.main(["repo", "add", "work", str(lib)]) == 1  # duplicate name
    assert cli.main(["repo", "add", "nerd", str(lib)]) == 1  # built-in name

    # new fonts in the directory show up without a refresh (local repos aren't cached)
    (lib / "Zeta-Regular.ttf").write_bytes(b"z")
    assert cli.main(["search", "zeta", "-s", "work"]) == 0
    assert "work:Zeta" in capsys.readouterr().out

    assert cli.main(["install", "work:acme", "-w", "700"]) == 0
    assert store.load_manifest()["work:acme"]["files"] == ["Acme-Bold.otf"]
    assert (paths.font_root() / "work" / "acme" / "Acme-Bold.otf").exists()

    assert cli.main(["repo", "rm", "work"]) == 0
    assert "work:acme" in capsys.readouterr().out  # warns installed fonts remain
    assert repos.load() == {}
    assert cli.main(["remove", "work:acme"]) == 0  # still removable after repo is gone
    assert not (paths.font_root() / "work").exists()


def test_repo_add_rejects_empty(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    assert cli.main(["repo", "add", "e", str(tmp_path / "empty")]) == 1
    assert repos.load() == {}
    assert cli.main(["repo", "add", "e", str(tmp_path / "empty"), "--no-check"]) == 0
    assert "e" in repos.load()

import pytest
from helpers import entry

from fontain import cli, fontcache, net, sources, store
from fontain.sources.base import FontEntry, SourceError


class VersionedSource:
    """An offline source whose fonts' versions (and availability) tests can change."""

    def __init__(self, name="fake", fonts=("mono", "sans")):
        self.name = name
        self.versions = dict.fromkeys(fonts, "v1")
        self.installs = []  # (font id, selection) per download
        self.fail_fetch = self.fail_install = False

    def fetch_index(self):
        if self.fail_fetch:
            raise net.NetError("offline")
        return [entry(i, source=self.name, version=v) for i, v in self.versions.items()]

    def install_files(self, e: FontEntry, dest, sel):
        if self.fail_install:
            raise SourceError("download failed")
        self.installs.append((e.id, sel))
        f = dest / f"{e.id}-{e.version}.ttf"
        f.write_bytes(e.version.encode())
        return [f]


@pytest.fixture
def env(monkeypatch):
    fake, other = VersionedSource(), VersionedSource("other", fonts=("serif",))
    monkeypatch.setattr(sources, "registry", lambda: {"fake": fake, "other": other})
    rebuilds = []
    monkeypatch.setattr(fontcache, "_rebuild", lambda root, quiet=False: rebuilds.append(root) or True)
    assert cli.main(["install", "--no-cache", "fake:mono", "fake:sans", "other:serif"]) == 0
    assert cli.main(["install", "--no-cache", "--force", "-w", "700", "fake:sans"]) == 0
    fake.installs.clear()
    other.installs.clear()
    return fake, other, rebuilds


def files(key):
    return store.load_manifest()[key]["files"]


def test_nothing_changed(env, capsys):
    fake, other, rebuilds = env
    assert cli.main(["update"]) == 0
    assert "0 updated, 3 already up to date." in capsys.readouterr().out
    assert fake.installs == other.installs == [] and rebuilds == []


def test_changed_font_is_reinstalled_with_same_selection(env, capsys):
    fake, _, rebuilds = env
    fake.versions["sans"] = "v2"
    assert cli.main(["update"]) == 0
    out = capsys.readouterr().out
    assert "Updating fake:sans (v1 -> v2)" in out and "1 updated, 2 already up to date." in out
    assert [i for i, _ in fake.installs] == ["sans"]
    assert fake.installs[0][1].weights == {700}  # the -w 700 choice is kept
    assert files("fake:sans") == ["sans-v2.ttf"]
    assert store.load_manifest()["fake:sans"]["version"] == "v2"
    assert len(rebuilds) == 1  # fc-cache once, at the end


def test_only_named_fonts(env):
    fake, other, _ = env
    fake.versions = {"mono": "v2", "sans": "v2"}
    other.versions["serif"] = "v2"
    assert cli.main(["update", "--no-cache", "sans"]) == 0
    assert [i for i, _ in fake.installs] == ["sans"] and other.installs == []
    assert files("fake:mono") == ["mono-v1.ttf"]


def test_dry_run_changes_nothing(env, capsys):
    fake, _, rebuilds = env
    fake.versions["mono"] = "v2"
    assert cli.main(["update", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Would update fake:mono (v1 -> v2)" in out and "1 would be updated" in out
    assert fake.installs == [] and rebuilds == [] and files("fake:mono") == ["mono-v1.ttf"]


def test_force_reinstalls_unchanged(env):
    fake, other, _ = env
    assert cli.main(["update", "--force", "--no-cache"]) == 0
    assert sorted(i for i, _ in fake.installs + other.installs) == ["mono", "sans", "serif"]


def test_fonts_installed_before_versions_were_recorded(env, capsys):
    manifest = store.load_manifest()
    del manifest["fake:mono"]["version"]
    store.save_manifest(manifest)
    assert cli.main(["update", "--no-cache"]) == 0
    assert "Updating fake:mono (unknown -> v1)" in capsys.readouterr().out
    assert store.load_manifest()["fake:mono"]["version"] == "v1"


def test_font_no_longer_offered_is_left_alone(env, capsys):
    fake, _, _ = env
    del fake.versions["mono"]
    assert cli.main(["update", "--no-cache"]) == 0
    assert "fake:mono is no longer offered by fake" in capsys.readouterr().out
    assert store.is_installed("fake:mono")


def test_unreachable_source_fails_but_others_update(env, capsys):
    fake, other, _ = env
    fake.fail_fetch = True
    other.versions["serif"] = "v2"
    assert cli.main(["update", "--no-cache"]) == 1
    assert "fake: offline" in capsys.readouterr().err
    assert [i for i, _ in other.installs] == ["serif"]


def test_failed_download_keeps_installed_copy(env, capsys):
    fake, _, _ = env
    fake.versions["mono"] = "v2"
    fake.fail_install = True
    assert cli.main(["update", "--no-cache", "mono"]) == 1
    assert "the installed copy was kept" in capsys.readouterr().err
    assert files("fake:mono") == ["mono-v1.ttf"]
    assert (store.font_dir("fake", "mono") / "mono-v1.ttf").exists()


def test_unknown_font_and_nothing_installed(env, capsys, monkeypatch):
    assert cli.main(["update", "nope"]) == 1
    assert "'nope' is not installed" in capsys.readouterr().err
    store.save_manifest({})
    assert cli.main(["update"]) == 0
    assert "No fonts installed" in capsys.readouterr().out


def test_update_completes_installed_fonts(env, capsys):
    from fontain import repl

    commands, subcommands, _ = cli.shell_context()
    assert "sans" in repl.Completer(commands, subcommands).candidates("update s")
    cli.main(["completion", "bash"])
    assert "remove|uninstall|rm|update|upgrade)" in capsys.readouterr().out

from fontain import net
from fontain.sources.base import Selection
from fontain.sources.github import GitHubRepoSource, parse_release, parse_tree


def _asset(name):
    return {"name": name, "browser_download_url": f"https://dl/{name}"}


def test_parse_release_archives():
    release = {
        "tag_name": "v4.1",
        "assets": [
            _asset(n)
            for n in (
                "Inter-4.1.zip",
                "Fira_Code_v6.2.zip",
                "monaspace-static-v1.400.zip",
                "monaspace-webfont-static-v1.400.zip",
                "WOFF2-thing.zip",
                "checksums.txt",
                "3270.tar.xz",
            )
        ],
    }
    entries = parse_release("mine", "o/r", release)
    assert [e.id for e in entries] == ["Inter", "Fira_Code", "monaspace-static", "3270"]
    assert entries[0].key == "mine:Inter"
    assert entries[0].extra == {"url": "https://dl/Inter-4.1.zip", "version": "v4.1"}


def test_parse_release_loose_files():
    release = {
        "tag_name": "1.0",
        "assets": [_asset(n) for n in ("X-Regular.ttf", "X-Bold.ttf", "X-Bold.otf")],
    }
    (e,) = parse_release("mine", "o/xfont", release)
    assert e.id == "xfont"
    assert e.weights == (400, 700)
    assert [n for n, _ in e.extra["files"]] == ["X-Regular.ttf", "X-Bold.ttf"]


def test_parse_tree():
    tree = {
        "tree": [
            {"path": "fonts/otf/X-Regular.otf", "type": "blob"},
            {"path": "fonts/ttf/X-Regular.ttf", "type": "blob"},
            {"path": "fonts/ttf/X-Italic.ttf", "type": "blob"},
            {"path": "fonts/ttf", "type": "tree"},
            {"path": "README.md", "type": "blob"},
        ]
    }
    (e,) = parse_tree("mine", "o/xfont", "main", tree)
    assert e.key == "mine:xfont"
    assert e.extra["paths"] == ["fonts/ttf/X-Regular.ttf", "fonts/ttf/X-Italic.ttf"]
    assert e.styles == ("normal", "italic")
    assert parse_tree("mine", "o/r", "main", {"tree": [{"path": "a.md", "type": "blob"}]}) == []


def test_fetch_index_falls_back_to_tree(monkeypatch):
    def get_json(url):
        if url.endswith("/releases/latest"):
            raise net.NetError("HTTP 404", 404)
        if url.endswith("/o/xfont"):
            return {"default_branch": "dev"}
        assert url.endswith("/git/trees/dev?recursive=1")
        return {"tree": [{"path": "X-Regular.ttf", "type": "blob"}]}

    monkeypatch.setattr(net, "get_json", get_json)
    (e,) = GitHubRepoSource("mine", "o/xfont").fetch_index()
    assert e.extra["branch"] == "dev"


def test_install_tree_files(monkeypatch, tmp_path):
    got = []

    def download(url, dest):
        got.append(url)
        dest.write_bytes(b"x")
        return dest

    monkeypatch.setattr(net, "download", download)
    (e,) = parse_tree(
        "mine",
        "o/xfont",
        "main",
        {
            "tree": [
                {"path": "fonts/X Sans-Regular.ttf", "type": "blob"},
                {"path": "fonts/X Sans-Bold.ttf", "type": "blob"},
            ]
        },
    )
    files = GitHubRepoSource("mine", "o/xfont").install_files(
        e, tmp_path, Selection(weights=frozenset({700}))
    )
    assert [f.name for f in files] == ["X Sans-Bold.ttf"]
    assert got == ["https://raw.githubusercontent.com/o/xfont/main/fonts/X%20Sans-Bold.ttf"]

"""User-added GitHub repositories.

Fonts come from the latest release's archives (one font per archive) or,
when there is no usable release, from the font files in the repository tree.
"""

import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from fontain import net
from fontain.sources.archives import FORMAT_PREFERENCE, extract_fonts, pick_fonts
from fontain.sources.base import FontEntry, Selection, SourceError
from fontain.sources.filenames import basename, variants_of

API = "https://api.github.com/repos/{}"
RAW = "https://raw.githubusercontent.com/{}/{}/{}"
ARCHIVE_SUFFIXES = (".zip", ".tar.xz", ".tar.gz", ".tgz", ".tar.bz2", ".tar")
WEB_ONLY = re.compile(r"woff|web-?font", re.IGNORECASE)
VERSION_TAIL = re.compile(r"[-_ ]?v?\d+(?:\.\d+)+[a-z]*$", re.IGNORECASE)


def _strip_suffix(name: str) -> str | None:
    for suffix in ARCHIVE_SUFFIXES:
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return None


def _font_id(stem: str) -> str:
    return VERSION_TAIL.sub("", stem) or stem


def parse_release(source: str, repo: str, release: dict[str, Any]) -> list[FontEntry]:
    version = release.get("tag_name", "")
    entries: list[FontEntry] = []
    loose: list[tuple[str, str]] = []
    ids: set[str] = set()
    for asset in release.get("assets", []):
        name, url = asset["name"], asset["browser_download_url"]
        if WEB_ONLY.search(name):
            continue
        if name.lower().endswith(FORMAT_PREFERENCE):
            loose.append((name, url))
            continue
        stem = _strip_suffix(name)
        if stem is None:
            continue
        font_id = _font_id(stem)
        if font_id in ids:
            font_id = stem
        ids.add(font_id)
        entries.append(
            FontEntry(source=source, id=font_id, family=font_id, version=version, extra={"url": url})
        )
    if loose:
        picked = pick_fonts([n for n, _ in loose])
        files = [[n, u] for n, u in loose if n in picked]
        weights, styles = variants_of(picked)
        repo_id = repo.split("/")[1]
        entries.append(
            FontEntry(
                source=source,
                id=repo_id,
                family=repo_id,
                weights=weights,
                styles=styles,
                version=version,
                extra={"files": files},
            )
        )
    return entries


def parse_tree(source: str, repo: str, branch: str, tree: dict[str, Any]) -> list[FontEntry]:
    blobs = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    picked = pick_fonts(blobs)
    if not picked:
        return []
    weights, styles = variants_of(picked)
    repo_id = repo.split("/")[1]
    return [
        FontEntry(
            source=source,
            id=repo_id,
            family=repo_id,
            weights=weights,
            styles=styles,
            # the tree hash changes with any commit that touches the repository's files
            version=tree.get("sha", "")[:12],
            extra={"branch": branch, "paths": picked},
        )
    ]


class GitHubRepoSource:
    kind = "github"

    def __init__(self, name: str, repo: str):
        self.name = name
        self.repo = repo

    def fetch_index(self) -> list[FontEntry]:
        try:
            release = net.get_json(API.format(f"{self.repo}/releases/latest"))
            entries = parse_release(self.name, self.repo, release)
        except net.NetError as e:
            if e.status != 404:
                raise
            entries = []
        if entries:
            return entries
        info = net.get_json(API.format(self.repo))
        branch = info["default_branch"]
        tree = net.get_json(API.format(f"{self.repo}/git/trees/{urllib.parse.quote(branch)}?recursive=1"))
        return parse_tree(self.name, self.repo, branch, tree)

    def install_files(self, entry: FontEntry, dest: Path, sel: Selection) -> list[Path]:
        if url := entry.extra.get("url"):
            with tempfile.TemporaryDirectory(prefix="fontain-") as tmp:
                archive = net.download(url, Path(tmp) / basename(urllib.parse.urlparse(url).path))
                files = extract_fonts(archive, dest, sel)
        else:
            if "files" in entry.extra:
                urls = dict(entry.extra["files"])
            else:
                branch = entry.extra["branch"]
                urls = {p: RAW.format(self.repo, branch, urllib.parse.quote(p)) for p in entry.extra["paths"]}
            files = [net.download(urls[p], dest / basename(p)) for p in pick_fonts(urls, sel)]
        if not files:
            raise SourceError(f"no font files of {entry.key} match the requested weights/styles")
        return files

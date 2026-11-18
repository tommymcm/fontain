"""Tiny HTTP helpers built on urllib."""

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fontain import __version__

USER_AGENT = f"fontain/{__version__}"
TIMEOUT = 60


class NetError(Exception):
    pass


def _request(url: str) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def _open(url: str):
    try:
        return urllib.request.urlopen(_request(url), timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        hint = ""
        if e.code in (403, 429) and "api.github.com" in url:
            hint = " (GitHub rate limit? set GITHUB_TOKEN)"
        raise NetError(f"HTTP {e.code} fetching {url}{hint}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise NetError(f"could not fetch {url}: {getattr(e, 'reason', e)}") from e


def get_text(url: str) -> str:
    with _open(url) as resp:
        return resp.read().decode("utf-8")


def get_json(url: str) -> Any:
    text = get_text(url)
    # Google's metadata endpoint prefixes its JSON with an XSSI guard.
    if text.startswith(")]}'"):
        text = text[4:]
    return json.loads(text)


def download(url: str, dest: Path) -> Path:
    """Stream ``url`` to ``dest`` atomically."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".part-")
    try:
        with os.fdopen(fd, "wb") as out, _open(url) as resp:
            shutil.copyfileobj(resp, out)
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return dest

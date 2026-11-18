# fontain ⛲

A simple tool to install and manage fonts on unix systems from public repositories.

- **Sources:** [Fontsource](https://fontsource.org), [Google Fonts](https://github.com/google/fonts) and [Nerd Fonts](https://www.nerdfonts.com), plus your own GitHub repos and local folders
- **No root needed:** fonts are installed to your user font directory
- **No dependencies:** pure Python standard library (3.13+)
- **Font cache:** runs `fc-cache` for you after installing or removing fonts

## Install

```sh
uv tool install git+https://github.com/<you>/fontain   # or: pipx install .
```

From a checkout: `uv tool install .`, or run it in place with `uv run fontain ...`.

## Usage

```sh
fontain search roboto                    # find fonts across all sources
fontain search mono --source nerd        # ...or just one source
fontain info inter                       # weights, styles, license, install state

fontain install inter                    # bare name: first match in fontsource > google > nerd
fontain install google:lato -w 400,700   # pick a source and weights
fontain install inter -S normal          # skip italics
fontain install nerd:JetBrainsMono       # Nerd Fonts patched font

fontain list                             # what fontain has installed
fontain remove inter nerd:JetBrainsMono  # uninstall
fontain refresh                          # re-download source indexes (otherwise cached 24h)
fontain cache                            # re-run fc-cache by hand
```

## Your own repositories

```sh
fontain repo add inter github:rsms/inter                      # a GitHub repo
fontain repo add mona https://github.com/githubnext/monaspace # URLs work too
fontain repo add work ~/Dropbox/fonts                         # a local directory
fontain repo                                                  # list sources
fontain search mona -s mona
fontain install mona:monaspace-static -w 400,700
fontain repo remove mona                                      # installed fonts are kept
```

- **GitHub repos:** each archive (`.zip`/`.tar.*`) in the latest release becomes one font, with its version stripped from the name (`Inter-4.1.zip` → `inter:Inter`). WOFF/web-font assets are skipped. If the repo has no release, fontain installs the `.ttf`/`.otf` files from the default branch instead.
- **Local directories:** each subfolder is one font, and its font files can be nested at any depth. Loose files are grouped by the part of the name before the first `-`. The folder is re-scanned every time, so new fonts show up immediately.
- **Name lookup:** bare names are looked up in the built-in sources first, then in your repos in the order you added them.
- **Duplicate formats:** only one format is installed per font, in the order TTF, then OTF, then TTC, so fontconfig doesn't see duplicates.

Repositories are stored in `$XDG_CONFIG_HOME/fontain/repos.json`.

Fonts can be named by id (`roboto-mono`), by family (`"Roboto Mono"`), or with an explicit source (`google:robotomono`). Installed fonts are marked with `*` in search results.

## Where things go

| What | Path |
| --- | --- |
| Fonts | `$XDG_DATA_HOME/fonts/fontain/<source>/<id>/` (default `~/.local/share/fonts/...`; `~/Library/Fonts/fontain` on macOS) |
| Installed manifest | `$XDG_STATE_HOME/fontain/installed.json` |
| Source index cache | `$XDG_CACHE_HOME/fontain/` |
| Your repositories | `$XDG_CONFIG_HOME/fontain/repos.json` |

Set `FONTAIN_FONT_DIR` to override the font directory.

## Notes

- **Fontsource:** files are per-weight static TTFs subsetted to the font's default subset (usually `latin`). If you need full glyph coverage, use the `google:` source.
- **Google Fonts:** files come from the GitHub API, which allows 60 unauthenticated requests per hour. Set `GITHUB_TOKEN` to raise that limit. Variable fonts are always installed, because they cover every weight.
- **Nerd Fonts:** files come from the latest release's `.tar.xz`, which is checked against the published SHA-256. Only `.ttf`/`.otf` files are extracted.
- **Font cache:** if `fc-cache` is missing, install `fontconfig`.

## Development

```sh
uv sync
uv run pytest
```

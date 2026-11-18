![fontain](docs/images/fontain-pixel-div2.png)

`fontain` is a simple tool to install and manage fonts on unix systems from public repositories.

- **Sources:** [Fontsource](https://fontsource.org), [Google Fonts](https://github.com/google/fonts) and [Nerd Fonts](https://www.nerdfonts.com), plus your own GitHub repos and local folders
- **No root needed:** fonts are installed to your user font directory
- **No dependencies:** pure Python standard library (3.13+)
- **Font cache:** runs `fc-cache` for you after installing or removing fonts

## Install

```sh
uv tool install git+https://github.com/tommymcm/fontain   # or: pipx install .
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

### Preferred source

By default, a bare name like `fontain install roboto` is looked up in the built-in sources (`fontsource`, `google`, `nerd`) and then in your repos. To try one source first:

```sh
fontain repo prefer google     # bare names now resolve from google first
fontain repo prefer            # show the current preference
fontain repo prefer --clear    # back to the default order
```

The preferred source's results also come first in search when other sources have the same font. For a single command, set `FONTAIN_PREFER=nerd` to override the preference. The preference is stored in `$XDG_CONFIG_HOME/fontain/config.json`.

- **GitHub repos:** each archive (`.zip`/`.tar.*`) in the latest release becomes one font, with its version stripped from the name (`Inter-4.1.zip` → `inter:Inter`). WOFF/web-font assets are skipped. If the repo has no release, fontain installs the `.ttf`/`.otf` files from the default branch instead.
- **Local directories:** each subfolder is one font, and its font files can be nested at any depth. Loose files are grouped by the part of the name before the first `-`. The folder is re-scanned every time, so new fonts show up immediately.
- **Name lookup:** bare names are looked up in your preferred source (if set), then the built-in sources, then your repos in the order you added them.
- **Duplicate formats:** only one format is installed per font, in the order TTF, then OTF, then TTC, so fontconfig doesn't see duplicates.

Repositories are stored in `$XDG_CONFIG_HOME/fontain/repos.json`.

Fonts can be named by id (`roboto-mono`), by family (`"Roboto Mono"`), or with an explicit source (`google:robotomono`). Installed fonts are marked with `*` in search results.

## Tab completion

Pressing Tab after `fontain remove` (or `uninstall`/`rm`) suggests the fonts fontain has installed, one name per font. Every suggestion is accepted by `remove`: it's the bare id, or `source:id` when the bare id is ambiguous. Type `source:` to complete fully qualified names. Subcommand names complete too.

**bash asks the first time you press Tab after `fontain`:**

```
$ fontain remove <Tab>
fontain: enable tab completion for fontain? [Y/n] y
$ fontain remove <Tab><Tab>
atkinson-hyperlegible  inter  JetBrainsMono
```

fontain doesn't install anything into your home directory or rc files to make this work. The package ships a small loader in its own install folder (`<venv>/share/bash-completion/completions/fontain`), and `bash-completion` finds it there on the first Tab. Your answer is remembered. If you say no, Tab falls back to normal filename completion and you're never asked again.

```sh
fontain completion --install      # turn it on (fish: installs ~/.config/fish/completions/fontain.fish)
fontain completion --uninstall    # turn it off, don't ask again
fontain completion --reset        # forget the answer; ask on the next Tab
```

The prompt needs the `bash-completion` package (installed by default on most distros) and fontain installed with `uv tool install` or `pipx`. If you also have `eval "$(fontain completion bash)"` in `~/.bashrc`, that line turns completion on directly and you won't see the prompt.

**zsh** has no per-user completion folder, so add this to `~/.zshrc` (after `compinit`):

```sh
eval "$(fontain completion zsh)"
```

When several fonts match, readline first completes the part they have in common and beeps, and a second Tab lists them all. To get the list on the first Tab, add `set show-all-if-ambiguous on` to `~/.inputrc`. This setting applies to all commands, not just fontain.

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

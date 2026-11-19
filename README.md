![fontain](docs/images/fontain-pixel-div2.png)

`fontain` is a simple tool to install and manage fonts on unix systems from public repositories.

It installs from [Fontsource](https://fontsource.org), [Google Fonts](https://github.com/google/fonts), [Nerd Fonts](https://www.nerdfonts.com), or your own GitHub repos and folders. Fonts are installed into your user font directory, and the font cache is refreshed for you.

## Installation

Quick start with `uv`:

```sh
uv tool install git+https://github.com/tommymcm/fontain
```

Or, install from a local checkout with `pipx install .` or `uv tool install .`


## Usage

Run `fontain` with no arguments for an interactive REPL.

### Commands

```sh
fontain search roboto                   # search for fonts
fontain info inter                      # details about a font
fontain install inter                   # install font by name
fontain install google:lato -w 400,700  # pick a source repo, and weights
fontain list                            # list installed fonts
fontain remove inter                    # uninstall a font
fontain --help                          # list all commands
fontain <command> --help                  # list flags for command
```

### Add your own repositories

```sh
fontain repo add mona github:githubnext/monaspace  # a GitHub repo
fontain repo add work ~/fonts                      # a local folder
fontain install mona:monaspace-static
fontain repo prefer work                           # look here first for bare names
```

### Scripts

Put one command per line in a file to run them in sequence:

```sh
fontain run fonts.txt                   # or: fontain < fonts.txt
```

Blank lines and `#` comments are ignored. The script stops at the first failing command unless you pass `--keep-going`.

### Tab completion

Enable tab completion with `fontain completion --install`. For zsh, add `eval "$(fontain completion zsh)"` to `~/.zshrc`.

## Notes

- Set `GITHUB_TOKEN` if you hit GitHub's rate limit (Google Fonts and GitHub repos).
- Run `fontain --help` or `fontain <command> --help` for all options.

## Development

```sh
uv sync
uv run pytest
```

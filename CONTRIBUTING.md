# Contributing to fontain

Thanks for helping out! Bug reports, fixes and new font sources are all welcome.

## Setup

fontain has no runtime dependencies. Development uses [uv](https://docs.astral.sh/uv/):

```sh
uv sync                  # creates .venv with pytest, ruff and mypy
uv run fontain --help    # run your checkout
```

Python 3.11 is the oldest supported version and is the default in `.python-version`.

## Checks

Run these before opening a pull request:

```sh
uv run pytest            # tests never touch the network or your real font folders
uv run ruff check        # lint
uv run ruff format       # format
uv run mypy              # type check
```

## Layout

- `src/fontain/cli.py`: the argument parser, `main()`, and the glue for the interactive shell and scripts.
- `src/fontain/commands.py`: one `cmd_*` function per subcommand.
- `src/fontain/sources/`: where fonts come from.
  - `base.py` defines `FontEntry` and the `Source` protocol.
  - There is one module per source.
  - `archives.py` and `filenames.py` are shared helpers.
- `src/fontain/store.py`: installs and removes font files and keeps the manifest of installed fonts.
- `src/fontain/index.py`: cached font lists per source, search, and resolving names like `google:lato`.
- `src/fontain/repos.py`: user-added repositories and the preferred-source setting.
- `src/fontain/repl.py`: the interactive shell and script runner.
- `src/fontain/completion.py`: shell tab completion.
- `src/fontain/logo.py`: the logo shown when the shell starts.
- `src/fontain/preview.py` and `assets/preview.html`: the browser preview page.

## Adding a font source

1. Create `src/fontain/sources/<name>.py` with a class that has a `name` and implements the `Source` protocol from `sources/base.py`:
   - `fetch_index()` returns every font the source offers.
   - `install_files(entry, dest, selection)` downloads one font's files into `dest`.
2. Register it in `SOURCES` in `sources/__init__.py`. The order there is the lookup order for bare font names.
3. Add tests with small fixture data. Mock `fontain.net` rather than calling the real service.

## Bash completion loader

`data/share/bash-completion/completions/fontain` is shipped with the package and must match `completion.TAB_LOADER`. A test checks this. If you change `TAB_LOADER`, regenerate the file:

```sh
uv run python -c "from fontain.completion import TAB_LOADER; open('data/share/bash-completion/completions/fontain', 'w').write(TAB_LOADER)"
```

## Commits

Keep commits small and focused, with a short prefix (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

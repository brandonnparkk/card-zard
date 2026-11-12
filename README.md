# Card Zard

A Magic: The Gathering deck analysis assistant for the Commander format. Domain terms are defined in [GLOSSARY.md](GLOSSARY.md), and the decisions behind it are in [docs/adr/](docs/adr/).

## Layout

```text
src/card_zard/                 # domain logic, free of any web framework (ADR-0009)
backend/card_zard_api/         # thin FastAPI layer over card_zard
backend/scripts/               # one-off scripts, such as downloading Scryfall data
tests/
```

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.13 if needed.

```sh
uv sync                                            # install dependencies
uv run uvicorn card_zard_api.main:app --reload     # run the API at http://127.0.0.1:8000
```

The checks CI runs on every push and pull request:

```sh
uv run ruff check           # lint
uv run ruff format --check  # formatting (drop --check to fix)
uv run pyright              # type check
uv run pytest               # tests
```

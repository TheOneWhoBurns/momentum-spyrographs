# Contributing

## Setup

```bash
uv sync --extra dev
```

## Run The Desktop App

```bash
uv run momentum-spyrographs
```

## Run The CLI

```bash
uv run momentum-spyrographs-cli single --omega1 1.8 --omega2 -0.4 --svg outputs/sample.svg
```

## Test

```bash
uv run pytest
```

## Notes

- Keep the physics engine deterministic.
- Prefer extending `core/` for reusable behavior and `app/` for UI-only logic.
- Avoid committing generated `outputs/`, virtual environments, or egg-info directories.

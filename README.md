# Momentum Spyrographs

Momentum Spyrographs is a native desktop app for turning double-pendulum initial conditions into phase-space line art.

It ships with:

- a `PySide6` desktop UI, not a web frontend
- a draggable pendulum setup canvas for editing the initial angles
- live spirograph preview with play, pause, and restart
- controls for animation speed, fadeout, projection space, background, and stroke color
- a local preset library with save, duplicate, archive, restore, and delete flows
- export to `SVG` and `GIF`
- a retained CLI for scripted rendering

## App Preview

Curated demo assets live in [docs/assets](docs/assets).

## Install From Source

```bash
uv sync --extra dev
```

## Run The Desktop App

```bash
uv run momentum-spyrographs
```

The primary public interface is the desktop app. `python -m momentum_spyrographs` launches the same UI.

## CLI Compatibility

The CLI is still available for scripts and batch rendering:

```bash
uv run momentum-spyrographs-cli single \
  --omega1 1.8 \
  --omega2 -0.4 \
  --duration 80 \
  --dt 0.01 \
  --space momentum \
  --svg outputs/pretzel.svg \
  --gif outputs/pretzel.gif
```

You can also invoke it with:

```bash
uv run python -m momentum_spyrographs.cli --help
```

## Desktop Features

### Pendulum Setup

- Drag bob 1 to set `theta1`
- Drag bob 2 to set `theta2`
- Adjust angular velocities and physical parameters from the inspector

### Preview

- Preview in `momentum`, `omega`, or `angle` space
- Animate the line before exporting
- Tune speed, fadeout, stroke color, and background

### Preset Library

- Save named configurations locally
- Archive presets without deleting them
- Restore archived presets
- Duplicate or rename existing studies

### Export

- `SVG` uses the current stroke color and background
- `GIF` uses the current color, speed, and fadeout settings

## Development

Project layout:

```text
src/momentum_spyrographs/
  app/
  core/
  cli.py
```

Useful commands:

```bash
uv run pytest
uv run python -m compileall src
```

## Packaging

`PyInstaller` is used for desktop bundles on macOS, Windows, and Linux. The GitHub Actions workflow builds test artifacts for each platform.

## License

MIT

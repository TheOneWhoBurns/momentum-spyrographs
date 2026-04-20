from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from momentum_spyrographs.core.models import PendulumSeed, RenderSettings
from momentum_spyrographs.core.project import simulate_projected_points
from momentum_spyrographs.core.render import background_color, write_gif, write_svg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="momentum-spyrographs-cli",
        description="Generate momentum-space spyrographs from a double pendulum.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("single", help="Render one seed.")
    add_simulation_arguments(single)
    single.add_argument("--svg", type=Path)
    single.add_argument("--gif", type=Path)
    single.add_argument("--size", type=int, default=1600)
    single.add_argument("--gif-size", type=int, default=1200)
    single.add_argument("--frames", type=int, default=120)
    single.add_argument("--fps", type=int, default=24)
    single.add_argument("--stroke-color", default="#ff9d76")
    single.add_argument("--stroke-width", type=float, default=2.4)
    single.add_argument("--fadeout", type=float, default=0.35)
    single.add_argument("--animation-speed", type=float, default=0.18)
    single.add_argument("--background-theme", default="midnight")
    single.add_argument("--background-color")
    single.add_argument("--fidelity", choices=["flat", "styled", "full_glow_raster"], default="styled")

    batch = subparsers.add_parser("batch", help="Render a grid of seeds.")
    add_shared_system_arguments(batch)
    batch.add_argument("--omega1-min", type=float, required=True)
    batch.add_argument("--omega1-max", type=float, required=True)
    batch.add_argument("--omega2-min", type=float, required=True)
    batch.add_argument("--omega2-max", type=float, required=True)
    batch.add_argument("--rows", type=int, default=4)
    batch.add_argument("--cols", type=int, default=4)
    batch.add_argument("--duration", type=float, default=60.0)
    batch.add_argument("--dt", type=float, default=0.015)
    batch.add_argument("--theta1", type=float, default=0.0)
    batch.add_argument("--theta2", type=float, default=0.0)
    batch.add_argument("--space", choices=["momentum", "omega", "angle", "trace"], default="momentum")
    batch.add_argument("--size", type=int, default=1200)
    batch.add_argument("--stroke-color", default="#ff9d76")
    batch.add_argument("--stroke-width", type=float, default=2.4)
    batch.add_argument("--background-theme", default="midnight")
    batch.add_argument("--background-color")
    batch.add_argument("--fidelity", choices=["flat", "styled"], default="flat")
    batch.add_argument("--out-dir", type=Path, required=True)

    return parser


def add_shared_system_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--length1", type=float, default=1.0)
    parser.add_argument("--length2", type=float, default=1.0)
    parser.add_argument("--mass1", type=float, default=1.0)
    parser.add_argument("--mass2", type=float, default=1.0)
    parser.add_argument("--gravity", type=float, default=9.81)


def add_simulation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--theta1", type=float, default=0.0)
    parser.add_argument("--theta2", type=float, default=0.0)
    parser.add_argument("--omega1", type=float, required=True)
    parser.add_argument("--omega2", type=float, required=True)
    parser.add_argument("--duration", type=float, default=80.0)
    parser.add_argument("--dt", type=float, default=0.01)
    parser.add_argument("--space", choices=["momentum", "omega", "angle", "trace"], default="momentum")
    add_shared_system_arguments(parser)


def build_seed(args: argparse.Namespace, omega1: float, omega2: float) -> PendulumSeed:
    return PendulumSeed(
        theta1=args.theta1,
        theta2=args.theta2,
        omega1=omega1,
        omega2=omega2,
        length1=args.length1,
        length2=args.length2,
        mass1=args.mass1,
        mass2=args.mass2,
        gravity=args.gravity,
        duration=args.duration,
        dt=args.dt,
        space=args.space,
    )


def build_render_settings(args: argparse.Namespace) -> RenderSettings:
    background = args.background_color or background_color(args.background_theme)
    return RenderSettings(
        stroke_color=args.stroke_color,
        stroke_width=args.stroke_width,
        fadeout=getattr(args, "fadeout", 0.35),
        animation_speed=getattr(args, "animation_speed", 0.18),
        svg_size=getattr(args, "size", 1600),
        gif_size=getattr(args, "gif_size", 1200),
        frames=getattr(args, "frames", 120),
        fps=getattr(args, "fps", 24),
        background_mode="solid",
        background_color=background,
    )


def default_output_base(args: argparse.Namespace) -> Path:
    filename = f"{args.space}_o1_{args.omega1:+.3f}_o2_{args.omega2:+.3f}".replace("+", "p").replace("-", "n")
    return Path("outputs") / filename


def run_single(args: argparse.Namespace) -> int:
    seed = build_seed(args, omega1=args.omega1, omega2=args.omega2)
    render_settings = build_render_settings(args)
    points = simulate_projected_points(seed)

    svg_path = args.svg
    gif_path = args.gif
    if svg_path is None and gif_path is None:
        base = default_output_base(args)
        svg_path = base.with_suffix(".svg")
        gif_path = base.with_suffix(".gif")

    if svg_path is not None:
        path = write_svg(
            points,
            svg_path,
            width=args.size,
            height=args.size,
            render_settings=render_settings,
            fidelity=args.fidelity if args.fidelity != "full_glow_raster" else "styled",
        )
        print(f"Wrote SVG: {path}")
    if gif_path is not None:
        path = write_gif(
            points,
            gif_path,
            width=args.gif_size,
            height=args.gif_size,
            frames=args.frames,
            fps=args.fps,
            render_settings=render_settings,
            fidelity=args.fidelity,
        )
        print(f"Wrote GIF: {path}")
    return 0


def render_seed(
    out_dir: Path,
    seed: PendulumSeed,
    render_settings: RenderSettings,
) -> Path:
    points = simulate_projected_points(seed)
    stem = f"{seed.space}_o1_{seed.omega1:+.3f}_o2_{seed.omega2:+.3f}".replace("+", "p").replace("-", "n")
    return write_svg(
        points,
        out_dir / f"{stem}.svg",
        width=render_settings.svg_size,
        height=render_settings.svg_size,
        render_settings=render_settings,
        fidelity="flat",
    )


def run_batch(args: argparse.Namespace) -> int:
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    omega1_values = np.linspace(args.omega1_min, args.omega1_max, args.cols)
    omega2_values = np.linspace(args.omega2_min, args.omega2_max, args.rows)
    manifest_path = out_dir / "manifest.csv"
    render_settings = build_render_settings(args)

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["omega1", "omega2", "svg_path"])
        for omega2 in omega2_values:
            for omega1 in omega1_values:
                seed = build_seed(args, omega1=float(omega1), omega2=float(omega2))
                svg_path = render_seed(out_dir, seed, render_settings)
                writer.writerow([f"{omega1:.6f}", f"{omega2:.6f}", str(svg_path)])
                print(f"Wrote SVG: {svg_path}")

    print(f"Wrote manifest: {manifest_path}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "single":
        return run_single(args)
    if args.command == "batch":
        return run_batch(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

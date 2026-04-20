# Performance Review

## Summary

The old map path rendered a whole grid in Python with one full simulation per cell. That was the dominant bottleneck and it did not scale beyond a coarse map.

The new path uses:

- a `numba`-accelerated RK4 map kernel
- viewport-based progressive refinement at `128 -> 256 -> 512`
- selection-only reuse of the cached final map
- explicit pan/zoom viewport state instead of rebuilding through the widget alone

## Before

Measured on the old monolithic Python map path:

- preview recompute: `0.037s`
- `21x21` map: `1.07s`
- `41x41` map: `3.77s`
- `61x61` map: `8.23s`
- cached marker update: effectively instant, but only because the whole map was fixed and low resolution

Primary hotspot:

- `simulate() / rk4_step() / derivatives()` dominated the profile

## After

Measured on the new accelerated map path after warmup:

- preview recompute: `0.0189s`
- coarse visible map (`128x128`): `0.1185s`
- full visible map (`512x512`): `0.6290s`
- cached selection-only update: `0.000020s`
- one cached `512x512` map payload: `2.75 MiB`

## Tradeoffs

- The map is still simulation-backed, but it now uses a reduced metric kernel rather than the full artistic preview metrics per pixel.
- Tile caching is currently most effective for progressive refinement and selection-only updates within the same viewport. Cross-viewport reuse is intentionally simpler than a full world-tile pyramid.
- The first render on a cold process still pays JIT compilation cost, but after warmup the steady-state map latency is well below the original path.

## Remaining Hotspots

- Structural changes still invalidate the landscape and trigger a full progressive rerender for the current viewport.
- Cross-viewport tile reuse could be improved later if very large exploratory pans become a dominant workload.
- The preview path and export path still use the original Python simulation pipeline, which is fine for current responsiveness but separate from the accelerated map kernel.

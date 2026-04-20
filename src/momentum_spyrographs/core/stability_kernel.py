from __future__ import annotations

import math

import numpy as np

try:  # pragma: no cover - import guard
    from numba import njit, prange
except ImportError:  # pragma: no cover
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    prange = range


@njit(cache=True)
def _derivatives(
    theta1: float,
    theta2: float,
    omega1: float,
    omega2: float,
    length1: float,
    length2: float,
    mass1: float,
    mass2: float,
    gravity: float,
) -> tuple[float, float, float, float]:
    delta = theta1 - theta2
    denom = 2.0 * mass1 + mass2 - mass2 * math.cos(2.0 * delta)
    dtheta1 = omega1
    dtheta2 = omega2
    domega1 = (
        -gravity * (2.0 * mass1 + mass2) * math.sin(theta1)
        - mass2 * gravity * math.sin(theta1 - 2.0 * theta2)
        - 2.0
        * math.sin(delta)
        * mass2
        * (omega2 * omega2 * length2 + omega1 * omega1 * length1 * math.cos(delta))
    ) / (length1 * denom)
    domega2 = (
        2.0
        * math.sin(delta)
        * (
            omega1 * omega1 * length1 * (mass1 + mass2)
            + gravity * (mass1 + mass2) * math.cos(theta1)
            + omega2 * omega2 * length2 * mass2 * math.cos(delta)
        )
    ) / (length2 * denom)
    return dtheta1, dtheta2, domega1, domega2


@njit(cache=True)
def _rk4_step(
    theta1: float,
    theta2: float,
    omega1: float,
    omega2: float,
    dt: float,
    length1: float,
    length2: float,
    mass1: float,
    mass2: float,
    gravity: float,
) -> tuple[float, float, float, float]:
    k11, k12, k13, k14 = _derivatives(theta1, theta2, omega1, omega2, length1, length2, mass1, mass2, gravity)
    k21, k22, k23, k24 = _derivatives(
        theta1 + 0.5 * dt * k11,
        theta2 + 0.5 * dt * k12,
        omega1 + 0.5 * dt * k13,
        omega2 + 0.5 * dt * k14,
        length1,
        length2,
        mass1,
        mass2,
        gravity,
    )
    k31, k32, k33, k34 = _derivatives(
        theta1 + 0.5 * dt * k21,
        theta2 + 0.5 * dt * k22,
        omega1 + 0.5 * dt * k23,
        omega2 + 0.5 * dt * k24,
        length1,
        length2,
        mass1,
        mass2,
        gravity,
    )
    k41, k42, k43, k44 = _derivatives(
        theta1 + dt * k31,
        theta2 + dt * k32,
        omega1 + dt * k33,
        omega2 + dt * k34,
        length1,
        length2,
        mass1,
        mass2,
        gravity,
    )
    return (
        theta1 + (dt / 6.0) * (k11 + 2.0 * k21 + 2.0 * k31 + k41),
        theta2 + (dt / 6.0) * (k12 + 2.0 * k22 + 2.0 * k32 + k42),
        omega1 + (dt / 6.0) * (k13 + 2.0 * k23 + 2.0 * k33 + k43),
        omega2 + (dt / 6.0) * (k14 + 2.0 * k24 + 2.0 * k34 + k44),
    )


@njit(cache=True)
def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@njit(cache=True)
def _single_seed_metrics(
    theta1_init: float,
    theta2_init: float,
    omega1_init: float,
    omega2_init: float,
    length1: float,
    length2: float,
    mass1: float,
    mass2: float,
    gravity: float,
    duration: float,
    dt: float,
    omega_scale: float,
) -> tuple[float, float, float]:
    steps = int(math.ceil(duration / dt)) + 1
    lag_min = max(10, steps // 5)
    theta1 = theta1_init
    theta2 = theta2_init
    omega1 = omega1_init
    omega2 = omega2_init
    s1 = math.sin(theta1)
    c1 = math.cos(theta1)
    s2 = math.sin(theta2)
    c2 = math.cos(theta2)
    initial_omega1 = omega1 / omega_scale
    initial_omega2 = omega2 / omega_scale
    recurrence_threshold = 0.24
    min_distance = 1.0e12
    best_step = steps
    final_distance = 1.0e12
    max_abs_omega = max(abs(omega1), abs(omega2))

    for step in range(1, steps):
        theta1, theta2, omega1, omega2 = _rk4_step(
            theta1,
            theta2,
            omega1,
            omega2,
            dt,
            length1,
            length2,
            mass1,
            mass2,
            gravity,
        )
        if not (
            math.isfinite(theta1)
            and math.isfinite(theta2)
            and math.isfinite(omega1)
            and math.isfinite(omega2)
        ):
            return 0.0, 1.0, 0.0
        if abs(theta1) > 1.0e6 or abs(theta2) > 1.0e6 or abs(omega1) > 1.0e6 or abs(omega2) > 1.0e6:
            return 0.0, 1.0, 0.0

        max_abs_omega = max(max_abs_omega, abs(omega1), abs(omega2))
        current_distance = math.sqrt(
            (math.sin(theta1) - s1) ** 2
            + (math.cos(theta1) - c1) ** 2
            + (math.sin(theta2) - s2) ** 2
            + (math.cos(theta2) - c2) ** 2
            + ((omega1 / omega_scale) - initial_omega1) ** 2
            + ((omega2 / omega_scale) - initial_omega2) ** 2
        )
        final_distance = current_distance
        if step >= lag_min and current_distance < min_distance:
            min_distance = current_distance
            best_step = step

    periodicity = _clamp01(1.0 - min_distance / recurrence_threshold)
    drift_penalty = _clamp01(final_distance / (recurrence_threshold * 3.0))
    energy_penalty = _clamp01(max_abs_omega / max(omega_scale * 2.2, 1.0))
    chaos = _clamp01((1.0 - periodicity) * 0.68 + drift_penalty * 0.22 + energy_penalty * 0.10)
    phase = 0.0 if best_step >= steps else (best_step % 48) / 48.0
    return periodicity, chaos, phase


@njit(cache=True, parallel=True)
def compute_tile_metrics(
    omega1_values: np.ndarray,
    omega2_values: np.ndarray,
    theta1: float,
    theta2: float,
    length1: float,
    length2: float,
    mass1: float,
    mass2: float,
    gravity: float,
    duration: float,
    dt: float,
    omega_scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = omega1_values.size * omega2_values.size
    periodicity_flat = np.zeros(count, dtype=np.float32)
    chaos_flat = np.zeros(count, dtype=np.float32)
    phase_flat = np.zeros(count, dtype=np.float32)

    width = omega1_values.size
    for index in prange(count):
        row = index // width
        col = index - row * width
        periodicity, chaos, phase = _single_seed_metrics(
            theta1,
            theta2,
            omega1_values[col],
            omega2_values[row],
            length1,
            length2,
            mass1,
            mass2,
            gravity,
            duration,
            dt,
            omega_scale,
        )
        periodicity_flat[index] = periodicity
        chaos_flat[index] = chaos
        phase_flat[index] = phase

    height = omega2_values.size
    return (
        periodicity_flat.reshape((height, width)),
        chaos_flat.reshape((height, width)),
        phase_flat.reshape((height, width)),
    )


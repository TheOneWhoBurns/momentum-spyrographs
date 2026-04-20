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
def _wrap_pi(value: float) -> float:
    while value <= -math.pi:
        value += 2.0 * math.pi
    while value > math.pi:
        value -= 2.0 * math.pi
    return value


@njit(cache=True)
def _state_distance(
    theta1_a: float,
    theta2_a: float,
    omega1_a: float,
    omega2_a: float,
    theta1_b: float,
    theta2_b: float,
    omega1_b: float,
    omega2_b: float,
    omega_normalization: float,
) -> float:
    delta_theta1 = _wrap_pi(theta1_a - theta1_b)
    delta_theta2 = _wrap_pi(theta2_a - theta2_b)
    delta_omega1 = (omega1_a - omega1_b) / omega_normalization
    delta_omega2 = (omega2_a - omega2_b) / omega_normalization
    return math.sqrt(
        delta_theta1 * delta_theta1
        + delta_theta2 * delta_theta2
        + delta_omega1 * delta_omega1
        + delta_omega2 * delta_omega2
    )


@njit(cache=True)
def _single_seed_divergence(
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
    delta_theta1: float,
    delta_theta2: float,
    delta_omega1: float,
    delta_omega2: float,
    omega_normalization: float,
) -> float:
    steps = int(math.ceil(duration / dt)) + 1
    theta1_a = theta1_init
    theta2_a = theta2_init
    omega1_a = omega1_init
    omega2_a = omega2_init
    theta1_b = theta1_init + delta_theta1
    theta2_b = theta2_init + delta_theta2
    omega1_b = omega1_init + delta_omega1
    omega2_b = omega2_init + delta_omega2

    d0 = _state_distance(
        theta1_a,
        theta2_a,
        omega1_a,
        omega2_a,
        theta1_b,
        theta2_b,
        omega1_b,
        omega2_b,
        omega_normalization,
    )
    if not math.isfinite(d0) or d0 <= 0.0:
        return math.inf
    max_distance = d0

    for _ in range(1, steps):
        theta1_a, theta2_a, omega1_a, omega2_a = _rk4_step(
            theta1_a,
            theta2_a,
            omega1_a,
            omega2_a,
            dt,
            length1,
            length2,
            mass1,
            mass2,
            gravity,
        )
        theta1_b, theta2_b, omega1_b, omega2_b = _rk4_step(
            theta1_b,
            theta2_b,
            omega1_b,
            omega2_b,
            dt,
            length1,
            length2,
            mass1,
            mass2,
            gravity,
        )
        if not (
            math.isfinite(theta1_a)
            and math.isfinite(theta2_a)
            and math.isfinite(omega1_a)
            and math.isfinite(omega2_a)
            and math.isfinite(theta1_b)
            and math.isfinite(theta2_b)
            and math.isfinite(omega1_b)
            and math.isfinite(omega2_b)
        ):
            return math.inf
        distance = _state_distance(
            theta1_a,
            theta2_a,
            omega1_a,
            omega2_a,
            theta1_b,
            theta2_b,
            omega1_b,
            omega2_b,
            omega_normalization,
        )
        if not math.isfinite(distance):
            return math.inf
        if distance > max_distance:
            max_distance = distance

    return math.log10(max(max_distance / d0, 1.0))


@njit(cache=True, parallel=True)
def compute_tile_divergence(
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
    delta_theta1: float,
    delta_theta2: float,
    delta_omega1: float,
    delta_omega2: float,
    omega_normalization: float,
) -> np.ndarray:
    count = omega1_values.size * omega2_values.size
    divergence_flat = np.empty(count, dtype=np.float32)
    width = omega1_values.size
    for index in prange(count):
        row = index // width
        col = index - row * width
        divergence = _single_seed_divergence(
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
            delta_theta1,
            delta_theta2,
            delta_omega1,
            delta_omega2,
            omega_normalization,
        )
        divergence_flat[index] = np.float32(divergence)
    height = omega2_values.size
    return divergence_flat.reshape((height, width))

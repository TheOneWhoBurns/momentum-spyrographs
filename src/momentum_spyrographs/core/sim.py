from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PendulumConfig:
    theta1: float = 0.0
    theta2: float = 0.0
    omega1: float = 1.8
    omega2: float = -0.4
    length1: float = 1.0
    length2: float = 1.0
    mass1: float = 1.0
    mass2: float = 1.0
    gravity: float = 9.81
    duration: float = 80.0
    dt: float = 0.01


def derivatives(state: np.ndarray, config: PendulumConfig) -> np.ndarray:
    theta1, theta2, omega1, omega2 = state
    m1 = config.mass1
    m2 = config.mass2
    l1 = config.length1
    l2 = config.length2
    g = config.gravity

    delta = theta1 - theta2
    denom = 2.0 * m1 + m2 - m2 * np.cos(2.0 * delta)
    dtheta1 = omega1
    dtheta2 = omega2

    domega1 = (
        -g * (2.0 * m1 + m2) * np.sin(theta1)
        - m2 * g * np.sin(theta1 - 2.0 * theta2)
        - 2.0
        * np.sin(delta)
        * m2
        * (omega2 * omega2 * l2 + omega1 * omega1 * l1 * np.cos(delta))
    ) / (l1 * denom)

    domega2 = (
        2.0
        * np.sin(delta)
        * (
            omega1 * omega1 * l1 * (m1 + m2)
            + g * (m1 + m2) * np.cos(theta1)
            + omega2 * omega2 * l2 * m2 * np.cos(delta)
        )
    ) / (l2 * denom)

    return np.array([dtheta1, dtheta2, domega1, domega2], dtype=np.float64)


def rk4_step(state: np.ndarray, dt: float, config: PendulumConfig) -> np.ndarray:
    k1 = derivatives(state, config)
    k2 = derivatives(state + 0.5 * dt * k1, config)
    k3 = derivatives(state + 0.5 * dt * k2, config)
    k4 = derivatives(state + dt * k3, config)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def simulate(config: PendulumConfig) -> tuple[np.ndarray, np.ndarray]:
    steps = int(np.ceil(config.duration / config.dt)) + 1
    times = np.linspace(0.0, config.duration, steps, dtype=np.float64)
    states = np.zeros((steps, 4), dtype=np.float64)
    states[0] = np.array(
        [config.theta1, config.theta2, config.omega1, config.omega2],
        dtype=np.float64,
    )

    for index in range(1, steps):
        states[index] = rk4_step(states[index - 1], config.dt, config)

    return times, states

from __future__ import annotations

from momentum_spyrographs.core.analysis_config import CANONICAL_DT, CANONICAL_WINDOW_SECONDS, canonical_seed
from momentum_spyrographs.core.models import PendulumSeed, PeriodicityStatus


def exact_periodicity_status(seed: PendulumSeed) -> PeriodicityStatus:
    del seed
    return PeriodicityStatus.NOT_PROVEN


__all__ = [
    "CANONICAL_DT",
    "CANONICAL_WINDOW_SECONDS",
    "PeriodicityStatus",
    "canonical_seed",
    "exact_periodicity_status",
]

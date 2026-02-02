from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel, Field, field_validator


class SpeculationStats(BaseModel):
    k: int = Field(..., ge=0)
    histogram: dict[int, float] = Field(default_factory=dict)

    @field_validator("histogram")
    @classmethod
    def _validate_histogram(cls, v: dict[int, float], info):  # noqa: ANN001
        k = info.data.get("k")
        if k is None:
            return v
        if len(v) == 0:
            raise ValueError("histogram must not be empty")
        for a, val in v.items():
            if a < 0 or a > k:
                raise ValueError(f"histogram bin out of range: a={a} for K={k}")
            if val < 0:
                raise ValueError(f"histogram value must be non-negative: a={a} val={val}")
        if sum(v.values()) <= 0:
            raise ValueError("histogram sum must be > 0")
        return v


def normalize_histogram(hist: Mapping[int, float]) -> dict[int, float]:
    total = float(sum(hist.values()))
    if total <= 0:
        raise ValueError("histogram sum must be > 0")
    return {int(k): float(v) / total for k, v in hist.items()}


def expected_committed_tokens_per_burst(stats: SpeculationStats) -> float:
    hist = normalize_histogram(stats.histogram)
    return sum((a + 1) * p for a, p in hist.items())


def expected_wasted_verifier_steps(stats: SpeculationStats) -> float:
    hist = normalize_histogram(stats.histogram)
    return sum((stats.k - a) * p for a, p in hist.items())


def verifier_steps_per_burst(stats: SpeculationStats) -> int:
    return stats.k + 1

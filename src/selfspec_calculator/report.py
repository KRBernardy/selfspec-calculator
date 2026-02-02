from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .config import InputPaths


class Metrics(BaseModel):
    energy_pj_per_token: float = Field(..., ge=0.0)
    latency_ns_per_token: float = Field(..., ge=0.0)
    throughput_tokens_per_s: float = Field(..., ge=0.0)
    tokens_per_joule: float = Field(..., ge=0.0)


class BaselineDelta(BaseModel):
    energy_pj_per_token_ratio: float | None = None
    latency_ns_per_token_ratio: float | None = None
    throughput_tokens_per_s_ratio: float | None = None
    tokens_per_joule_ratio: float | None = None

    energy_pj_per_token_diff: float | None = None
    latency_ns_per_token_diff: float | None = None
    throughput_tokens_per_s_diff: float | None = None
    tokens_per_joule_diff: float | None = None

    @staticmethod
    def _ratio(a: float, b: float) -> float | None:
        if b == 0:
            return None
        return a / b

    @classmethod
    def from_metrics(cls, speculative: Metrics, baseline: Metrics) -> "BaselineDelta":
        return cls(
            energy_pj_per_token_ratio=cls._ratio(speculative.energy_pj_per_token, baseline.energy_pj_per_token),
            latency_ns_per_token_ratio=cls._ratio(speculative.latency_ns_per_token, baseline.latency_ns_per_token),
            throughput_tokens_per_s_ratio=cls._ratio(speculative.throughput_tokens_per_s, baseline.throughput_tokens_per_s),
            tokens_per_joule_ratio=cls._ratio(speculative.tokens_per_joule, baseline.tokens_per_joule),
            energy_pj_per_token_diff=speculative.energy_pj_per_token - baseline.energy_pj_per_token,
            latency_ns_per_token_diff=speculative.latency_ns_per_token - baseline.latency_ns_per_token,
            throughput_tokens_per_s_diff=speculative.throughput_tokens_per_s - baseline.throughput_tokens_per_s,
            tokens_per_joule_diff=speculative.tokens_per_joule - baseline.tokens_per_joule,
        )


class StageBreakdown(BaseModel):
    qkv_energy_pj: float = 0.0
    qkv_latency_ns: float = 0.0
    wo_energy_pj: float = 0.0
    wo_latency_ns: float = 0.0
    ffn_energy_pj: float = 0.0
    ffn_latency_ns: float = 0.0

    qk_energy_pj: float = 0.0
    qk_latency_ns: float = 0.0
    pv_energy_pj: float = 0.0
    pv_latency_ns: float = 0.0
    softmax_energy_pj: float = 0.0
    softmax_latency_ns: float = 0.0
    elementwise_energy_pj: float = 0.0
    elementwise_latency_ns: float = 0.0
    kv_cache_energy_pj: float = 0.0
    kv_cache_latency_ns: float = 0.0

    qkv_mm2: float = 0.0
    wo_mm2: float = 0.0
    ffn_mm2: float = 0.0
    digital_mm2: float = 0.0

    def plus(self, other: "StageBreakdown") -> "StageBreakdown":
        return self.model_copy(
            update={field: getattr(self, field) + getattr(other, field) for field in type(self).model_fields}
        )

    def add_energy_latency(self, stage: str, energy_pj: float, latency_ns: float) -> "StageBreakdown":
        update: dict[str, Any] = {}
        if stage in {"qkv", "wo", "ffn", "qk", "pv", "softmax", "elementwise", "kv_cache"}:
            update[f"{stage}_energy_pj"] = getattr(self, f"{stage}_energy_pj") + energy_pj
            update[f"{stage}_latency_ns"] = getattr(self, f"{stage}_latency_ns") + latency_ns
            return self.model_copy(update=update)
        raise KeyError(stage)


class Breakdown(BaseModel):
    energy_pj: float = Field(..., ge=0.0)
    latency_ns: float = Field(..., ge=0.0)
    stages: StageBreakdown

    @classmethod
    def from_stage_breakdown(cls, stages: StageBreakdown) -> "Breakdown":
        energy = sum(
            getattr(stages, f"{s}_energy_pj")
            for s in ["qkv", "wo", "ffn", "qk", "pv", "softmax", "elementwise", "kv_cache"]
        )
        latency = sum(
            getattr(stages, f"{s}_latency_ns")
            for s in ["qkv", "wo", "ffn", "qk", "pv", "softmax", "elementwise", "kv_cache"]
        )
        return cls(energy_pj=energy, latency_ns=latency, stages=stages)

    def scale(self, factor: float) -> "Breakdown":
        return Breakdown(
            energy_pj=self.energy_pj * factor,
            latency_ns=self.latency_ns * factor,
            stages=self.stages.model_copy(
                update={
                    f"{s}_{m}": getattr(self.stages, f"{s}_{m}") * factor
                    for s in ["qkv", "wo", "ffn", "qk", "pv", "softmax", "elementwise", "kv_cache"]
                    for m in ["energy_pj", "latency_ns"]
                }
            ),
        )


class PhaseBreakdown(BaseModel):
    draft: Breakdown
    verify_drafted: Breakdown
    verify_bonus: Breakdown
    total: Breakdown


class SweepPoint(BaseModel):
    l_prompt: int = Field(..., ge=0)
    speculative: Metrics
    baseline: Metrics
    delta: BaselineDelta
    breakdown: PhaseBreakdown
    baseline_breakdown: PhaseBreakdown


class Report(BaseModel):
    generated_at: str
    k: int = Field(..., ge=0)
    reuse_policy: str
    paths: InputPaths | None = None
    points: list[SweepPoint]
    break_even_tokens_per_joule_l_prompt: int | None = None
    area: StageBreakdown
    notes: list[str] = Field(default_factory=list)

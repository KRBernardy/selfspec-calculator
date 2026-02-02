from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import HardwareConfig, InputPaths, ModelConfig, PrecisionMode, ReusePolicy
from .report import BaselineDelta, Breakdown, Metrics, PhaseBreakdown, Report, StageBreakdown, SweepPoint
from .stats import SpeculationStats, expected_committed_tokens_per_burst


def _mac_counts_per_token(model: ModelConfig, l_prompt: int) -> dict[str, int]:
    d_model = model.d_model
    d_ff = model.effective_d_ff
    d_head = model.d_head
    n_heads = model.n_heads

    qkv_macs = 3 * d_model * d_model
    wo_macs = d_model * d_model
    if model.ffn_type.value == "mlp":
        ffn_macs = 2 * d_model * d_ff
    else:
        ffn_macs = 3 * d_model * d_ff

    qk_macs = n_heads * l_prompt * d_head
    pv_macs = n_heads * l_prompt * d_head
    softmax_ops = n_heads * l_prompt
    elementwise_ops = d_ff
    kv_cache_ops = d_model

    return {
        "qkv": qkv_macs,
        "wo": wo_macs,
        "ffn": ffn_macs,
        "qk": qk_macs,
        "pv": pv_macs,
        "softmax": softmax_ops,
        "elementwise": elementwise_ops,
        "kv_cache": kv_cache_ops,
    }


def _weights_per_layer(model: ModelConfig) -> dict[str, int]:
    d_model = model.d_model
    d_ff = model.effective_d_ff

    qkv_weights = 3 * d_model * d_model
    wo_weights = d_model * d_model
    if model.ffn_type.value == "mlp":
        ffn_weights = 2 * d_model * d_ff
    else:
        ffn_weights = 3 * d_model * d_ff
    return {"qkv": qkv_weights, "wo": wo_weights, "ffn": ffn_weights}


def _analog_cost_for_block(hardware: HardwareConfig, precision: PrecisionMode) -> tuple[float, float]:
    if precision == PrecisionMode.full:
        c = hardware.costs.analog_full
    else:
        c = hardware.costs.analog_draft
    return (c.energy_pj_per_mac, c.latency_ns_per_mac)


def _verify_additional_cost_for_block(
    hardware: HardwareConfig,
    executed_precision_in_draft: PrecisionMode,
    token_kind: str,
) -> tuple[float, float]:
    if token_kind == "bonus":
        c = hardware.costs.analog_full
        return (c.energy_pj_per_mac, c.latency_ns_per_mac)

    if hardware.reuse_policy == ReusePolicy.reread:
        c = hardware.costs.analog_full
        return (c.energy_pj_per_mac, c.latency_ns_per_mac)

    if executed_precision_in_draft == PrecisionMode.full:
        return (0.0, 0.0)

    c = hardware.costs.analog_verify_reuse
    return (c.energy_pj_per_mac, c.latency_ns_per_mac)


def _digital_costs(hardware: HardwareConfig) -> dict[str, tuple[float, float]]:
    return {
        "qk": (hardware.costs.digital_attention.energy_pj_per_mac, hardware.costs.digital_attention.latency_ns_per_mac),
        "pv": (hardware.costs.digital_attention.energy_pj_per_mac, hardware.costs.digital_attention.latency_ns_per_mac),
        "softmax": (hardware.costs.digital_softmax.energy_pj_per_mac, hardware.costs.digital_softmax.latency_ns_per_mac),
        "elementwise": (
            hardware.costs.digital_elementwise.energy_pj_per_mac,
            hardware.costs.digital_elementwise.latency_ns_per_mac,
        ),
        "kv_cache": (hardware.costs.kv_cache.energy_pj_per_mac, hardware.costs.kv_cache.latency_ns_per_mac),
    }


def _area_mm2(model: ModelConfig, hardware: HardwareConfig) -> StageBreakdown:
    weights = _weights_per_layer(model)
    analog_area_per_weight = hardware.costs.analog_weight_area.area_mm2_per_weight
    qkv = weights["qkv"] * analog_area_per_weight
    wo = weights["wo"] * analog_area_per_weight
    ffn = weights["ffn"] * analog_area_per_weight
    digital = hardware.costs.digital_overhead_area_mm2_per_layer

    scale = model.n_layers
    return StageBreakdown(
        qkv_mm2=qkv * scale,
        wo_mm2=wo * scale,
        ffn_mm2=ffn * scale,
        digital_mm2=digital * scale,
    )


def _token_step_costs(model: ModelConfig, hardware: HardwareConfig, l_prompt: int) -> tuple[Breakdown, Breakdown]:
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs(hardware)

    def stage_energy_latency(stage: str, energy_per_mac: float, latency_per_mac: float) -> tuple[float, float]:
        m = macs[stage]
        return (m * energy_per_mac, m * latency_per_mac)

    draft_stage = StageBreakdown()
    verify_full_stage = StageBreakdown()

    for layer in range(model.n_layers):
        policy = model.draft_policy.for_layer(layer)
        for block, precision in {"qkv": policy.qkv, "wo": policy.wo, "ffn": policy.ffn}.items():
            e_per, t_per = _analog_cost_for_block(hardware, precision)
            e, t = stage_energy_latency(block, e_per, t_per)
            draft_stage = draft_stage.add_energy_latency(block, e, t)

            e_full, t_full = stage_energy_latency(
                block,
                hardware.costs.analog_full.energy_pj_per_mac,
                hardware.costs.analog_full.latency_ns_per_mac,
            )
            verify_full_stage = verify_full_stage.add_energy_latency(block, e_full, t_full)

        for stage in ["qk", "pv", "softmax", "elementwise", "kv_cache"]:
            e_per, t_per = digital_costs[stage]
            e, t = stage_energy_latency(stage, e_per, t_per)
            draft_stage = draft_stage.add_energy_latency(stage, e, t)
            verify_full_stage = verify_full_stage.add_energy_latency(stage, e, t)

    return (
        Breakdown.from_stage_breakdown(draft_stage),
        Breakdown.from_stage_breakdown(verify_full_stage),
    )


def _verify_drafted_token_additional_stage(
    model: ModelConfig, hardware: HardwareConfig, l_prompt: int
) -> Breakdown:
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs(hardware)

    additional = StageBreakdown()

    for layer in range(model.n_layers):
        policy = model.draft_policy.for_layer(layer)
        for block, executed_precision in {"qkv": policy.qkv, "wo": policy.wo, "ffn": policy.ffn}.items():
            e_per, t_per = _verify_additional_cost_for_block(hardware, executed_precision, token_kind="drafted")
            additional = additional.add_energy_latency(block, macs[block] * e_per, macs[block] * t_per)

        for stage in ["qk", "pv", "softmax", "elementwise", "kv_cache"]:
            e_per, t_per = digital_costs[stage]
            additional = additional.add_energy_latency(stage, macs[stage] * e_per, macs[stage] * t_per)

    return Breakdown.from_stage_breakdown(additional)


def estimate_point(
    model: ModelConfig,
    hardware: HardwareConfig,
    stats: SpeculationStats,
    l_prompt: int,
) -> tuple[Metrics, PhaseBreakdown]:
    draft_step, verify_full_step = _token_step_costs(model, hardware, l_prompt)
    verify_drafted_additional = _verify_drafted_token_additional_stage(model, hardware, l_prompt)

    e_burst = draft_step.energy_pj * stats.k + verify_drafted_additional.energy_pj * stats.k + verify_full_step.energy_pj
    t_burst = draft_step.latency_ns * stats.k + verify_drafted_additional.latency_ns * stats.k + verify_full_step.latency_ns

    committed = expected_committed_tokens_per_burst(stats)
    if committed <= 0:
        raise ValueError("Expected committed tokens per burst must be > 0")

    energy_per_token_pj = e_burst / committed
    latency_per_token_ns = t_burst / committed

    throughput_tokens_per_s = 0.0 if latency_per_token_ns == 0 else 1e9 / latency_per_token_ns
    tokens_per_joule = 0.0 if energy_per_token_pj == 0 else 1e12 / energy_per_token_pj

    draft_phase = draft_step.scale(stats.k)
    verify_drafted_phase = verify_drafted_additional.scale(stats.k)
    verify_bonus_phase = verify_full_step
    total_stages = draft_phase.stages.plus(verify_drafted_phase.stages).plus(verify_bonus_phase.stages)
    total_phase = Breakdown.from_stage_breakdown(total_stages)
    breakdown = PhaseBreakdown(
        draft=draft_phase,
        verify_drafted=verify_drafted_phase,
        verify_bonus=verify_bonus_phase,
        total=total_phase,
    )
    metrics = Metrics(
        energy_pj_per_token=energy_per_token_pj,
        latency_ns_per_token=latency_per_token_ns,
        throughput_tokens_per_s=throughput_tokens_per_s,
        tokens_per_joule=tokens_per_joule,
    )
    return metrics, breakdown


def _baseline_stats() -> SpeculationStats:
    return SpeculationStats(k=0, histogram={0: 1.0})


def estimate_sweep(
    model: ModelConfig,
    hardware: HardwareConfig,
    stats: SpeculationStats,
    prompt_lengths: list[int],
    paths: dict[str, str] | None = None,
) -> Report:
    paths_obj = None
    if paths is not None:
        paths_obj = InputPaths(**paths)

    points: list[SweepPoint] = []
    for l_prompt in prompt_lengths:
        speculative_metrics, speculative_breakdown = estimate_point(model, hardware, stats, l_prompt)
        baseline_metrics, baseline_breakdown = estimate_point(model, hardware, _baseline_stats(), l_prompt)
        delta = BaselineDelta.from_metrics(speculative_metrics, baseline_metrics)
        points.append(
            SweepPoint(
                l_prompt=l_prompt,
                speculative=speculative_metrics,
                baseline=baseline_metrics,
                delta=delta,
                breakdown=speculative_breakdown,
                baseline_breakdown=baseline_breakdown,
            )
        )

    break_even = None
    for p in sorted(points, key=lambda sp: sp.l_prompt):
        if p.delta.tokens_per_joule_ratio is not None and p.delta.tokens_per_joule_ratio > 1.0:
            break_even = p.l_prompt
            break

    return Report(
        generated_at=datetime.now(timezone.utc).isoformat(),
        k=stats.k,
        reuse_policy=hardware.reuse_policy.value,
        paths=paths_obj,
        points=points,
        break_even_tokens_per_joule_l_prompt=break_even,
        area=_area_mm2(model, hardware),
        notes=[
            "First-pass linear cost model (per-MAC coefficients).",
            "Draft and Verify are serialized per burst; verifier work does not early-stop.",
        ],
    )

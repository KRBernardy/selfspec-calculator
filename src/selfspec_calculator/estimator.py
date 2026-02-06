from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any

from .config import (
    HardwareConfig,
    HardwareMode,
    InputPaths,
    ModelConfig,
    PrecisionMode,
    ReusePolicy,
    ResolvedKnobSpecs,
)
from .report import (
    AnalogActivationCounts,
    BaselineDelta,
    Breakdown,
    ComponentBreakdown,
    Metrics,
    PhaseBreakdown,
    Report,
    StageBreakdown,
    SweepPoint,
)
from .stats import SpeculationStats, expected_committed_tokens_per_burst


ANALOG_STAGES = ("qkv", "wo", "ffn")
DIGITAL_STAGES = ("qk", "pv", "softmax", "elementwise", "kv_cache")


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
    assert hardware.costs is not None
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
    assert hardware.costs is not None
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


def _digital_costs_legacy(hardware: HardwareConfig) -> dict[str, tuple[float, float]]:
    assert hardware.costs is not None
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


def _digital_costs_knob(specs: ResolvedKnobSpecs) -> dict[str, tuple[float, float]]:
    return {
        "qk": (specs.digital.attention.energy_pj_per_mac, specs.digital.attention.latency_ns_per_mac),
        "pv": (specs.digital.attention.energy_pj_per_mac, specs.digital.attention.latency_ns_per_mac),
        "softmax": (specs.digital.softmax.energy_pj_per_mac, specs.digital.softmax.latency_ns_per_mac),
        "elementwise": (specs.digital.elementwise.energy_pj_per_mac, specs.digital.elementwise.latency_ns_per_mac),
        "kv_cache": (specs.digital.kv_cache.energy_pj_per_mac, specs.digital.kv_cache.latency_ns_per_mac),
    }


def _legacy_components_from_stages(stages: StageBreakdown) -> ComponentBreakdown:
    analog_energy = stages.qkv_energy_pj + stages.wo_energy_pj + stages.ffn_energy_pj
    analog_latency = stages.qkv_latency_ns + stages.wo_latency_ns + stages.ffn_latency_ns
    return ComponentBreakdown(
        arrays_energy_pj=analog_energy,
        arrays_latency_ns=analog_latency,
        attention_engine_energy_pj=stages.qk_energy_pj + stages.pv_energy_pj,
        attention_engine_latency_ns=stages.qk_latency_ns + stages.pv_latency_ns,
        kv_cache_energy_pj=stages.kv_cache_energy_pj,
        kv_cache_latency_ns=stages.kv_cache_latency_ns,
        softmax_unit_energy_pj=stages.softmax_energy_pj,
        softmax_unit_latency_ns=stages.softmax_latency_ns,
        elementwise_unit_energy_pj=stages.elementwise_energy_pj,
        elementwise_unit_latency_ns=stages.elementwise_latency_ns,
    )


def _area_mm2(model: ModelConfig, hardware: HardwareConfig) -> StageBreakdown:
    weights = _weights_per_layer(model)
    if hardware.mode == HardwareMode.legacy:
        assert hardware.costs is not None
        analog_area_per_weight = hardware.costs.analog_weight_area.area_mm2_per_weight
        qkv = weights["qkv"] * analog_area_per_weight
        wo = weights["wo"] * analog_area_per_weight
        ffn = weights["ffn"] * analog_area_per_weight
        digital = hardware.costs.digital_overhead_area_mm2_per_layer
    else:
        specs = hardware.resolve_knob_specs()
        qkv = weights["qkv"] * specs.array.area_mm2_per_weight
        wo = weights["wo"] * specs.array.area_mm2_per_weight
        ffn = weights["ffn"] * specs.array.area_mm2_per_weight
        digital = specs.digital.digital_overhead_area_mm2_per_layer

    scale = model.n_layers
    return StageBreakdown(
        qkv_mm2=qkv * scale,
        wo_mm2=wo * scale,
        ffn_mm2=ffn * scale,
        digital_mm2=digital * scale,
    )


def _token_step_costs_legacy(model: ModelConfig, hardware: HardwareConfig, l_prompt: int) -> tuple[Breakdown, Breakdown]:
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs_legacy(hardware)

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

            assert hardware.costs is not None
            e_full, t_full = stage_energy_latency(
                block,
                hardware.costs.analog_full.energy_pj_per_mac,
                hardware.costs.analog_full.latency_ns_per_mac,
            )
            verify_full_stage = verify_full_stage.add_energy_latency(block, e_full, t_full)

        for stage in DIGITAL_STAGES:
            e_per, t_per = digital_costs[stage]
            e, t = stage_energy_latency(stage, e_per, t_per)
            draft_stage = draft_stage.add_energy_latency(stage, e, t)
            verify_full_stage = verify_full_stage.add_energy_latency(stage, e, t)

    return (
        Breakdown.from_stage_breakdown(draft_stage, components=_legacy_components_from_stages(draft_stage)),
        Breakdown.from_stage_breakdown(
            verify_full_stage,
            components=_legacy_components_from_stages(verify_full_stage),
        ),
    )


def _verify_drafted_token_additional_stage_legacy(
    model: ModelConfig, hardware: HardwareConfig, l_prompt: int
) -> Breakdown:
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs_legacy(hardware)

    additional = StageBreakdown()

    for layer in range(model.n_layers):
        policy = model.draft_policy.for_layer(layer)
        for block, executed_precision in {"qkv": policy.qkv, "wo": policy.wo, "ffn": policy.ffn}.items():
            e_per, t_per = _verify_additional_cost_for_block(hardware, executed_precision, token_kind="drafted")
            additional = additional.add_energy_latency(block, macs[block] * e_per, macs[block] * t_per)

        for stage in DIGITAL_STAGES:
            e_per, t_per = digital_costs[stage]
            additional = additional.add_energy_latency(stage, macs[stage] * e_per, macs[stage] * t_per)

    return Breakdown.from_stage_breakdown(additional, components=_legacy_components_from_stages(additional))


def _analog_stage_shapes(model: ModelConfig) -> dict[str, list[tuple[int, int]]]:
    d_model = model.d_model
    d_ff = model.effective_d_ff
    if model.ffn_type.value == "mlp":
        ffn_shapes = [(d_ff, d_model), (d_model, d_ff)]
    else:
        ffn_shapes = [(d_ff, d_model), (d_ff, d_model), (d_model, d_ff)]
    return {
        "qkv": [(3 * d_model, d_model)],
        "wo": [(d_model, d_model)],
        "ffn": ffn_shapes,
    }


def _tile_counts(model: ModelConfig, xbar_size: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for stage, shapes in _analog_stage_shapes(model).items():
        total = 0
        for m_out, n_in in shapes:
            tiles_out = ceil(m_out / xbar_size)
            tiles_in = ceil(n_in / xbar_size)
            total += tiles_out * tiles_in
        out[stage] = total
    return out


def _parallel_latency_split(lat_a: float, lat_b: float) -> tuple[float, float, float]:
    total = max(lat_a, lat_b)
    if total <= 0.0:
        return (0.0, 0.0, 0.0)
    if lat_a <= 0.0:
        return (0.0, total, total)
    if lat_b <= 0.0:
        return (total, 0.0, total)
    denom = lat_a + lat_b
    return (total * lat_a / denom, total * lat_b / denom, total)


def _analog_mode(
    mode_name: str,
) -> tuple[int, bool, bool]:
    if mode_name == "draft_default":
        return (1, True, False)
    if mode_name == "draft_full":
        return (4, True, True)
    if mode_name == "verify_residual_only":
        return (3, False, True)
    if mode_name in {"verify_full", "verify_bonus"}:
        return (4, True, True)
    if mode_name == "none":
        return (0, False, False)
    raise ValueError(f"Unsupported analog mode: {mode_name}")


class _TokenAccumulator:
    def __init__(self) -> None:
        self.stages = StageBreakdown()
        self.components = ComponentBreakdown()
        self.activation_counts = AnalogActivationCounts()

    def add_stage(self, stage: str, energy_pj: float, latency_ns: float) -> None:
        self.stages = self.stages.add_energy_latency(stage, energy_pj, latency_ns)

    def add_component(self, component: str, energy_pj: float, latency_ns: float) -> None:
        self.components = self.components.add_energy_latency(component, energy_pj, latency_ns)

    def add_analog_counts(
        self,
        *,
        array_activations: float,
        dac_conversions: float,
        adc_draft_conversions: float,
        adc_residual_conversions: float,
    ) -> None:
        self.activation_counts = self.activation_counts.plus(
            AnalogActivationCounts(
                array_activations=array_activations,
                dac_conversions=dac_conversions,
                adc_draft_conversions=adc_draft_conversions,
                adc_residual_conversions=adc_residual_conversions,
            )
        )

    def to_breakdown(self) -> Breakdown:
        return Breakdown.from_stage_breakdown(
            self.stages,
            components=self.components,
            activation_counts=self.activation_counts,
        )


def _add_knob_analog_stage(
    *,
    acc: _TokenAccumulator,
    stage: str,
    num_tiles: int,
    num_slices: int,
    xbar_size: int,
    adc_steps: int,
    specs: ResolvedKnobSpecs,
    mode_name: str,
) -> None:
    active_arrays, use_adc_draft, use_adc_residual = _analog_mode(mode_name)
    if active_arrays == 0:
        return

    base_reads = float(num_tiles * num_slices)
    array_activations = base_reads * active_arrays
    dac_conversions = base_reads * xbar_size
    adc_draft_conversions = base_reads * xbar_size if use_adc_draft else 0.0
    adc_residual_conversions = base_reads * xbar_size if use_adc_residual else 0.0

    array_energy = array_activations * specs.array.energy_pj_per_activation
    dac_energy = dac_conversions * specs.dac.energy_pj_per_conversion
    adc_draft_energy = adc_draft_conversions * specs.adc_draft.energy_pj_per_conversion
    adc_residual_energy = adc_residual_conversions * specs.adc_residual.energy_pj_per_conversion

    array_latency = base_reads * specs.array.latency_ns_per_activation
    dac_latency = base_reads * specs.dac.latency_ns_per_conversion
    adc_draft_scan = (
        base_reads * adc_steps * specs.adc_draft.latency_ns_per_conversion if use_adc_draft else 0.0
    )
    adc_residual_scan = (
        base_reads * adc_steps * specs.adc_residual.latency_ns_per_conversion if use_adc_residual else 0.0
    )
    adc_draft_latency, adc_residual_latency, adc_latency = _parallel_latency_split(adc_draft_scan, adc_residual_scan)

    stage_energy = array_energy + dac_energy + adc_draft_energy + adc_residual_energy
    stage_latency = array_latency + dac_latency + adc_latency

    acc.add_stage(stage, stage_energy, stage_latency)
    acc.add_component("arrays", array_energy, array_latency)
    acc.add_component("dac", dac_energy, dac_latency)
    acc.add_component("adc_draft", adc_draft_energy, adc_draft_latency)
    acc.add_component("adc_residual", adc_residual_energy, adc_residual_latency)
    acc.add_analog_counts(
        array_activations=array_activations,
        dac_conversions=dac_conversions,
        adc_draft_conversions=adc_draft_conversions,
        adc_residual_conversions=adc_residual_conversions,
    )


def _add_knob_digital_stage(
    *,
    acc: _TokenAccumulator,
    stage: str,
    macs: int,
    energy_per_mac: float,
    latency_per_mac: float,
) -> None:
    energy = macs * energy_per_mac
    latency = macs * latency_per_mac
    acc.add_stage(stage, energy, latency)
    if stage in {"qk", "pv"}:
        acc.add_component("attention_engine", energy, latency)
    elif stage == "softmax":
        acc.add_component("softmax_unit", energy, latency)
    elif stage == "elementwise":
        acc.add_component("elementwise_unit", energy, latency)
    elif stage == "kv_cache":
        acc.add_component("kv_cache", energy, latency)


def _token_step_costs_knob(
    model: ModelConfig,
    hardware: HardwareConfig,
    specs: ResolvedKnobSpecs,
    l_prompt: int,
) -> tuple[Breakdown, Breakdown]:
    assert hardware.analog is not None
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs_knob(specs)
    num_tiles = _tile_counts(model, hardware.analog.xbar_size)
    num_slices = ceil(model.activation_bits / hardware.analog.dac_bits)

    draft = _TokenAccumulator()
    verify_full = _TokenAccumulator()

    for layer in range(model.n_layers):
        policy = model.draft_policy.for_layer(layer)
        for stage, precision in {"qkv": policy.qkv, "wo": policy.wo, "ffn": policy.ffn}.items():
            _add_knob_analog_stage(
                acc=draft,
                stage=stage,
                num_tiles=num_tiles[stage],
                num_slices=num_slices,
                xbar_size=hardware.analog.xbar_size,
                adc_steps=hardware.analog.num_columns_per_adc,
                specs=specs,
                mode_name="draft_full" if precision == PrecisionMode.full else "draft_default",
            )
            _add_knob_analog_stage(
                acc=verify_full,
                stage=stage,
                num_tiles=num_tiles[stage],
                num_slices=num_slices,
                xbar_size=hardware.analog.xbar_size,
                adc_steps=hardware.analog.num_columns_per_adc,
                specs=specs,
                mode_name="verify_bonus",
            )

        for stage in DIGITAL_STAGES:
            e_per, t_per = digital_costs[stage]
            _add_knob_digital_stage(acc=draft, stage=stage, macs=macs[stage], energy_per_mac=e_per, latency_per_mac=t_per)
            _add_knob_digital_stage(
                acc=verify_full,
                stage=stage,
                macs=macs[stage],
                energy_per_mac=e_per,
                latency_per_mac=t_per,
            )

    return draft.to_breakdown(), verify_full.to_breakdown()


def _verify_drafted_token_additional_stage_knob(
    model: ModelConfig,
    hardware: HardwareConfig,
    specs: ResolvedKnobSpecs,
    l_prompt: int,
) -> Breakdown:
    assert hardware.analog is not None
    macs = _mac_counts_per_token(model, l_prompt)
    digital_costs = _digital_costs_knob(specs)
    num_tiles = _tile_counts(model, hardware.analog.xbar_size)
    num_slices = ceil(model.activation_bits / hardware.analog.dac_bits)

    additional = _TokenAccumulator()

    for layer in range(model.n_layers):
        policy = model.draft_policy.for_layer(layer)
        for stage, executed_precision in {"qkv": policy.qkv, "wo": policy.wo, "ffn": policy.ffn}.items():
            if hardware.reuse_policy == ReusePolicy.reread:
                mode_name = "verify_full"
            else:
                if executed_precision == PrecisionMode.full:
                    mode_name = "none"
                else:
                    mode_name = "verify_residual_only"

            _add_knob_analog_stage(
                acc=additional,
                stage=stage,
                num_tiles=num_tiles[stage],
                num_slices=num_slices,
                xbar_size=hardware.analog.xbar_size,
                adc_steps=hardware.analog.num_columns_per_adc,
                specs=specs,
                mode_name=mode_name,
            )

        for stage in DIGITAL_STAGES:
            e_per, t_per = digital_costs[stage]
            _add_knob_digital_stage(
                acc=additional,
                stage=stage,
                macs=macs[stage],
                energy_per_mac=e_per,
                latency_per_mac=t_per,
            )

    return additional.to_breakdown()


def _baseline_stats() -> SpeculationStats:
    return SpeculationStats(k=0, histogram={0: 1.0})


def estimate_point(
    model: ModelConfig,
    hardware: HardwareConfig,
    stats: SpeculationStats,
    l_prompt: int,
) -> tuple[Metrics, PhaseBreakdown]:
    if hardware.mode == HardwareMode.legacy:
        draft_step, verify_full_step = _token_step_costs_legacy(model, hardware, l_prompt)
        verify_drafted_additional = _verify_drafted_token_additional_stage_legacy(model, hardware, l_prompt)
    else:
        specs = hardware.resolve_knob_specs()
        draft_step, verify_full_step = _token_step_costs_knob(model, hardware, specs, l_prompt)
        verify_drafted_additional = _verify_drafted_token_additional_stage_knob(model, hardware, specs, l_prompt)

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

    total_components = None
    if (
        draft_phase.components is not None
        and verify_drafted_phase.components is not None
        and verify_bonus_phase.components is not None
    ):
        total_components = (
            draft_phase.components.plus(verify_drafted_phase.components).plus(verify_bonus_phase.components)
        )

    total_activation_counts = None
    if (
        draft_phase.activation_counts is not None
        and verify_drafted_phase.activation_counts is not None
        and verify_bonus_phase.activation_counts is not None
    ):
        total_activation_counts = (
            draft_phase.activation_counts.plus(verify_drafted_phase.activation_counts).plus(verify_bonus_phase.activation_counts)
        )

    total_phase = Breakdown.from_stage_breakdown(
        total_stages,
        components=total_components,
        activation_counts=total_activation_counts,
    )
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

    resolved_library = hardware.resolved_library_payload()
    model_knobs: dict[str, Any] = {
        "activation_bits": model.activation_bits,
        "n_layers": model.n_layers,
        "d_model": model.d_model,
        "n_heads": model.n_heads,
        "ffn_type": model.ffn_type.value,
        "d_ff": model.effective_d_ff,
    }
    hardware_knobs: dict[str, Any] = {"reuse_policy": hardware.reuse_policy.value}
    if hardware.mode == HardwareMode.knob_based and hardware.analog is not None:
        hardware_knobs.update(
            {
                "library": hardware.selected_library,
                "xbar_size": hardware.analog.xbar_size,
                "num_columns_per_adc": hardware.analog.num_columns_per_adc,
                "dac_bits": hardware.analog.dac_bits,
                "adc": {
                    "draft_bits": hardware.analog.adc.draft_bits,
                    "residual_bits": hardware.analog.adc.residual_bits,
                },
            }
        )

    return Report(
        generated_at=datetime.now(timezone.utc).isoformat(),
        k=stats.k,
        reuse_policy=hardware.reuse_policy.value,
        hardware_mode=hardware.mode.value,
        resolved_library=resolved_library,
        model_knobs=model_knobs,
        hardware_knobs=hardware_knobs,
        paths=paths_obj,
        points=points,
        break_even_tokens_per_joule_l_prompt=break_even,
        area=_area_mm2(model, hardware),
        notes=[
            "Analytical calculator (closed-form activation counts, no event simulation).",
            "Draft and Verify are serialized per burst; verifier work does not early-stop.",
        ],
    )

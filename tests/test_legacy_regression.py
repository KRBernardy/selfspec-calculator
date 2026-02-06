from selfspec_calculator.config import HardwareConfig, ModelConfig
from selfspec_calculator.estimator import estimate_sweep
from selfspec_calculator.stats import SpeculationStats


LEGACY_HARDWARE = {
    "reuse_policy": "reuse",
    "costs": {
        "analog_draft": {"energy_pj_per_mac": 0.001, "latency_ns_per_mac": 0.001},
        "analog_full": {"energy_pj_per_mac": 0.002, "latency_ns_per_mac": 0.0015},
        "analog_verify_reuse": {"energy_pj_per_mac": 0.0006, "latency_ns_per_mac": 0.0008},
        "digital_attention": {"energy_pj_per_mac": 0.0004, "latency_ns_per_mac": 0.0007},
        "digital_softmax": {"energy_pj_per_mac": 0.00005, "latency_ns_per_mac": 0.00005},
        "digital_elementwise": {"energy_pj_per_mac": 0.00002, "latency_ns_per_mac": 0.00002},
        "kv_cache": {"energy_pj_per_mac": 0.0001, "latency_ns_per_mac": 0.0001},
        "analog_weight_area": {"area_mm2_per_weight": 1e-9},
        "digital_overhead_area_mm2_per_layer": 0.01,
    },
}


def test_legacy_explicit_cost_config_still_runs_with_output_shape() -> None:
    model = ModelConfig.model_validate(
        {
            "n_layers": 2,
            "d_model": 64,
            "n_heads": 8,
            "activation_bits": 12,
            "ffn_type": "mlp",
            "ffn_expansion": 4.0,
        }
    )
    hardware = HardwareConfig.model_validate(LEGACY_HARDWARE)
    stats = SpeculationStats(k=4, histogram={0: 0.1, 1: 0.2, 2: 0.3, 3: 0.25, 4: 0.15})

    report = estimate_sweep(model=model, hardware=hardware, stats=stats, prompt_lengths=[64, 128])
    payload = report.model_dump(mode="json")

    assert payload["hardware_mode"] == "legacy"
    assert payload["resolved_library"] is None
    assert payload["reuse_policy"] == "reuse"
    assert len(payload["points"]) == 2

    point = payload["points"][0]
    assert "delta" in point
    assert "baseline_breakdown" in point
    assert "breakdown" in point

    draft = point["breakdown"]["draft"]
    assert "stages" in draft
    assert "components" in draft
    assert draft["activation_counts"] is None
    assert draft["components"]["arrays_energy_pj"] > 0.0

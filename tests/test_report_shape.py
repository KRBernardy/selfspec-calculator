from selfspec_calculator.config import HardwareConfig, ModelConfig
from selfspec_calculator.estimator import estimate_sweep
from selfspec_calculator.stats import SpeculationStats


def test_knob_report_includes_stage_component_and_library_metadata() -> None:
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
    hardware = HardwareConfig.model_validate(
        {
            "reuse_policy": "reuse",
            "analog": {
                "xbar_size": 128,
                "num_columns_per_adc": 16,
                "dac_bits": 4,
                "adc": {"draft_bits": 4, "residual_bits": 12},
            },
        }
    )
    stats = SpeculationStats(k=2, histogram={0: 0.5, 2: 0.5})

    report = estimate_sweep(model=model, hardware=hardware, stats=stats, prompt_lengths=[64])
    payload = report.model_dump(mode="json")

    assert payload["hardware_mode"] == "knob-based"
    assert payload["resolved_library"] is not None
    assert payload["resolved_library"]["name"] == "puma_like_v1"
    assert payload["resolved_library"]["dac"]["bits"] == 4
    assert payload["resolved_library"]["adc_draft"]["bits"] == 4
    assert payload["resolved_library"]["adc_residual"]["bits"] == 12

    point = payload["points"][0]
    assert "delta" in point
    assert "baseline_breakdown" in point

    for phase in ["draft", "verify_drafted", "verify_bonus", "total"]:
        phase_payload = point["breakdown"][phase]
        assert "stages" in phase_payload
        assert "components" in phase_payload
        assert "activation_counts" in phase_payload

        stages = phase_payload["stages"]
        assert "qkv_energy_pj" in stages
        assert "ffn_latency_ns" in stages

        components = phase_payload["components"]
        assert "arrays_energy_pj" in components
        assert "dac_energy_pj" in components
        assert "adc_draft_latency_ns" in components
        assert "attention_engine_energy_pj" in components

        counts = phase_payload["activation_counts"]
        assert "dac_conversions" in counts
        assert "adc_draft_conversions" in counts
        assert "adc_residual_conversions" in counts

    verify_bonus_counts = point["breakdown"]["verify_bonus"]["activation_counts"]
    assert verify_bonus_counts["dac_conversions"] > 0
    assert verify_bonus_counts["adc_draft_conversions"] > 0
    assert verify_bonus_counts["adc_residual_conversions"] > 0

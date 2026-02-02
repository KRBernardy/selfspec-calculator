from pathlib import Path

import pytest

from selfspec_calculator.config import HardwareConfig, ModelConfig


def test_model_yaml_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "model.yaml"
    path.write_text("n_layers: 2\nn_heads: 8\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid model config"):
        ModelConfig.from_yaml(path)


def test_hardware_yaml_invalid_reuse_policy(tmp_path: Path) -> None:
    path = tmp_path / "hardware.yaml"
    path.write_text(
        """
reuse_policy: invalid
costs:
  analog_draft: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  analog_full: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  analog_verify_reuse: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  digital_attention: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  digital_softmax: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  digital_elementwise: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  kv_cache: { energy_pj_per_mac: 0.0, latency_ns_per_mac: 0.0 }
  analog_weight_area: { area_mm2_per_weight: 0.0 }
  digital_overhead_area_mm2_per_layer: 0.0
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid hardware config"):
        HardwareConfig.from_yaml(path)


def test_draft_policy_invalid_layer_index_rejected(tmp_path: Path) -> None:
    path = tmp_path / "model.yaml"
    path.write_text(
        """
n_layers: 2
d_model: 64
n_heads: 8
draft_policy:
  per_layer:
    3:
      qkv: full
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid layer index"):
        ModelConfig.from_yaml(path)


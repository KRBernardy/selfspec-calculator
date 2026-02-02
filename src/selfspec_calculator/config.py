from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic import BaseModel, Field, field_validator


class FfnType(str, Enum):
    mlp = "mlp"
    swiglu = "swiglu"


class PrecisionMode(str, Enum):
    draft = "draft"
    full = "full"


class BlockDraftPolicy(BaseModel):
    qkv: PrecisionMode = PrecisionMode.draft
    wo: PrecisionMode = PrecisionMode.draft
    ffn: PrecisionMode = PrecisionMode.draft


class DraftPrecisionPolicy(BaseModel):
    default: BlockDraftPolicy = Field(default_factory=BlockDraftPolicy)
    per_layer: dict[int, BlockDraftPolicy] = Field(default_factory=dict)

    def for_layer(self, layer: int) -> BlockDraftPolicy:
        return self.per_layer.get(layer, self.default)


class ModelConfig(BaseModel):
    name: str | None = None
    n_layers: int = Field(..., ge=1)
    d_model: int = Field(..., ge=1)
    n_heads: int = Field(..., ge=1)
    ffn_type: FfnType = FfnType.mlp
    d_ff: int | None = Field(default=None, ge=1)
    ffn_expansion: float | None = Field(default=4.0, ge=1.0)
    draft_policy: DraftPrecisionPolicy = Field(default_factory=DraftPrecisionPolicy)

    @field_validator("draft_policy")
    @classmethod
    def _validate_draft_policy(cls, v: DraftPrecisionPolicy, info):  # noqa: ANN001
        n_layers = info.data.get("n_layers")
        if n_layers is None:
            return v
        for layer in v.per_layer.keys():
            if layer < 0 or layer >= n_layers:
                raise ValueError(f"draft_policy.per_layer has invalid layer index: {layer} (n_layers={n_layers})")
        return v

    @property
    def d_head(self) -> int:
        if self.d_model % self.n_heads != 0:
            raise ValueError(f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})")
        return self.d_model // self.n_heads

    @property
    def effective_d_ff(self) -> int:
        if self.d_ff is not None:
            return self.d_ff
        if self.ffn_expansion is None:
            raise ValueError("Either d_ff or ffn_expansion must be provided")
        return int(round(self.d_model * self.ffn_expansion))

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ModelConfig":
        data = _load_yaml(path)
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid model config: {path}\n{exc}") from exc


class ReusePolicy(str, Enum):
    reuse = "reuse"
    reread = "reread"


class PerMacCost(BaseModel):
    energy_pj_per_mac: float = Field(..., ge=0.0)
    latency_ns_per_mac: float = Field(..., ge=0.0)


class PerWeightArea(BaseModel):
    area_mm2_per_weight: float = Field(..., ge=0.0)


class HardwareCosts(BaseModel):
    analog_draft: PerMacCost
    analog_full: PerMacCost
    analog_verify_reuse: PerMacCost
    digital_attention: PerMacCost
    digital_softmax: PerMacCost
    digital_elementwise: PerMacCost
    kv_cache: PerMacCost
    analog_weight_area: PerWeightArea
    digital_overhead_area_mm2_per_layer: float = Field(0.0, ge=0.0)


class HardwareConfig(BaseModel):
    reuse_policy: ReusePolicy = ReusePolicy.reuse
    costs: HardwareCosts

    @classmethod
    def from_yaml(cls, path: str | Path) -> "HardwareConfig":
        data = _load_yaml(path)
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid hardware config: {path}\n{exc}") from exc


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(path))
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover
        raise ValueError(f"Failed to parse YAML: {p}") from exc


class InputPaths(BaseModel):
    model: str
    hardware: str
    stats: str

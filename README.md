# selfspec-calculator

Parametric hardware PPA estimator for the Self-Speculating Analog Architecture described in `Roadmap.md`.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
ppa-calculator \
  --model examples/model.yaml \
  --hardware examples/hardware.yaml \
  --stats examples/stats.json \
  --prompt-lengths 64 128 256 \
  --output out/report.json
```

## `model.yaml`

`activation_bits` is required and is used with `analog.dac_bits` to compute serial slicing:

```yaml
activation_bits: 12
```

The calculator uses:

```text
num_slices = ceil(activation_bits / analog.dac_bits)
```

## `hardware.yaml` formats

The tool supports two mutually exclusive formats.

### 1) Knob-based (preferred)

```yaml
reuse_policy: reuse
library: puma_like_v1

analog:
  xbar_size: 128
  num_columns_per_adc: 16
  dac_bits: 4
  adc:
    draft_bits: 4
    residual_bits: 12
```

Validation rules:
- `xbar_size`, `num_columns_per_adc`, `dac_bits`, `draft_bits`, and `residual_bits` must be positive integers.
- `xbar_size % num_columns_per_adc == 0`.
- Requested ADC/DAC bit-widths must exist in the selected library.
- If `library` is omitted, default is `puma_like_v1`.

### 2) Legacy explicit-cost (backward compatible)

Keep existing `costs.*` format (see `examples/hardware_legacy.yaml`).

⚠️ Mixed configs are rejected: do not provide both `analog.*` and `costs.*` in the same file.

## Reporting

The JSON report includes:
- stage-level breakdown (`qkv`, `wo`, `ffn`, `qk`, `pv`, `softmax`, `elementwise`, `kv_cache`),
- component-level breakdown (`arrays`, `dac`, `adc_draft`, `adc_residual`, attention/digital components),
- resolved library entries (for knob-based runs),
- analog activation counts (`dac_conversions`, `adc_*_conversions`, etc.) for knob-based runs,
- baseline/delta and break-even fields compatible with previous outputs.

## Modeling assumptions

- This project is an analytical calculator (closed-form counting), not an event/instruction simulator.
- Draft/Verify are serialized per burst.
- Full-read dual-ADC latency uses parallel timing:
  - energy sums ADC-Draft + ADC-Residual,
  - latency uses `max(adc_draft_scan, adc_residual_scan)`.

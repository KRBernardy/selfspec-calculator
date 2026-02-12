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

Optional SoC extensions (all optional; default to zero/disabled so older configs keep working):

```yaml
soc:
  schedule: serialized  # or: layer-pipelined
  verify_setup:
    energy_pj_per_burst: 0.0
    latency_ns_per_burst: 0.0
  buffers_add:
    energy_pj_per_op: 0.0
    latency_ns_per_op: 0.0
  control:
    energy_pj_per_token: 0.0
    latency_ns_per_token: 0.0
    energy_pj_per_burst: 0.0
    latency_ns_per_burst: 0.0

memory:
  # Enables bytes-based KV-cache modeling (SRAM buffer + off-chip HBM + fabric).
  sram:
    read_energy_pj_per_byte: 0.0
    write_energy_pj_per_byte: 0.0
    read_bandwidth_GBps: 0.0
    write_bandwidth_GBps: 0.0
    read_latency_ns: 0.0
    write_latency_ns: 0.0
  hbm: { ...same fields... }
  fabric: { ...same fields... }
  kv_cache:
    hbm:
      value_bytes_per_elem: 1
      scale_bytes: 2
      scales_per_token_per_head: 2
    # sram: { ...optional override... }

analog:
  periphery:
    tia: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
    snh: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
    mux: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
    io_buffers: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
    subarray_switches: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
    write_drivers: { energy_pj_per_op: 0.0, latency_ns_per_op: 0.0 }
```

Examples:
- `examples/hardware_soc_memory.yaml` (SRAM + HBM + fabric KV-cache model)
- `examples/hardware_analog_periphery.yaml` (non-zero analog periphery + buffers/control)

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
- optional SoC components (`buffers_add`, `control`, and analog periphery blocks),
- optional memory components (`sram`, `hbm`, `fabric`) and `memory_traffic` bytes,
- resolved library entries (for knob-based runs),
- analog activation counts (`dac_conversions`, `adc_*_conversions`, etc.) for knob-based runs,
- baseline/delta and break-even fields compatible with previous outputs.

## Modeling assumptions

- This project is an analytical calculator (closed-form counting), not an event/instruction simulator.
- Draft/Verify are serialized per burst (no early-stop on mismatch; wasted verifier suffix work is still charged).
- When `memory` is configured:
  - HBM KV reads are not mismatch-gated in v1.
  - HBM KV writes are commit-only (Policy B).
- Full-read dual-ADC latency uses parallel timing:
  - energy sums ADC-Draft + ADC-Residual,
  - latency uses `max(adc_draft_scan, adc_residual_scan)`.

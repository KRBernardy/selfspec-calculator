## Context

`selfspec-calculator` currently expects `hardware.yaml` to provide low-level, already-compiled coefficients (energy/latency/area per “MAC” for analog and digital stages). This makes it hard to:

- run Roadmap experiments that sweep **ADC-Draft vs ADC-Residual** resolution splits (the “1+3 split”),
- model **serial DAC slicing** when `dac_bits < activation_bits` (arrays/ADCs fire multiple times), and
- share consistent hardware assumptions across projects without hand-tuning coefficients.

The desired interface is closer to RAMwich: YAML specifies a few knobs (e.g., ADC/DAC resolutions, xbar sizing, muxing factors) and the tool resolves those knobs via discrete lookup tables (a built-in “spec library”) into energy/latency/area numbers. The analog accounting should be **activation-count-based and purely analytical**, so repeated activations due to DAC slicing are naturally represented without simulating an execution trace.

At the same time, this repo is intended to remain a **hardware estimator** (analytical, fast), not a cycle-accurate instruction-level simulator.

## Goals / Non-Goals

**Goals:**
- Add a knob-based `hardware.yaml` mode for the analog MVM readout path aligned with the Roadmap’s dual-ADC residual architecture:
  - `analog.xbar_size`
  - `analog.num_columns_per_adc` (ADC multiplexing factor)
  - `analog.dac_bits` (serial slicing precision)
  - `analog.adc.draft_bits` and `analog.adc.residual_bits` (two ADCs)
  - `reuse_policy` (reuse vs reread semantics in Verify)
- Add `activation_bits` to `model.yaml` (not `hardware.yaml`) and use it to compute the number of serial DAC slices:
  - `num_slices = ceil(activation_bits / dac_bits)`
- Introduce a discrete internal **hardware spec library** that maps:
  - ADC bit-width → `{energy_per_conversion, latency_per_conversion, area_per_adc}`
  - DAC bit-width → `{energy_per_conversion, latency_per_conversion, area_per_dac}`
  Selected by a simple key (e.g., `library: puma_like_v1`) with a stable versioned default.
- Replace the analog path in the estimator with a **purely analytical activation-count model** (RAMwich-inspired, but not a simulator) that:
  - computes closed-form activation counts from `model.yaml` shapes + tiling + muxing + DAC slicing,
  - multiplies by library values to obtain energy/latency/area contributions,
  - supports Roadmap read modes (Draft base-only, Draft full, Verify reuse, Verify reread),
  - produces both **stage-level** and **component-level** breakdowns.
- Extend the report schema to include both breakdown views:
  - *Stage breakdown*: QKV / WO / FFN / QK / PV / softmax / elementwise / KV-cache
  - *Component breakdown*: arrays, DAC, ADC-Draft, ADC-Residual, attention engine, KV-cache, softmax unit, elementwise unit, buffers/add, control

**Non-Goals:**
- Build a SimPy/operation-driven simulator like RAMwich. The estimator will remain analytical (closed-form counts).
- Model analog noise, mismatch, or accuracy; acceptance statistics remain inputs (from the functional simulator).
- Implement predictive delta readout (§3.2) beyond reserving interface hooks.
- Fully redesign the end-to-end performance model to be a spatial pipeline/bottleneck model (Roadmap mentions this); keep the current per-token step aggregation in the initial iteration, with an upgrade path.

## Decisions

1. **Two `hardware.yaml` formats with a clear preference**
   - Support both:
     - **Legacy explicit-cost** config (`costs.*` as today), and
     - **Knob-based** config (`analog.*` + `library`).
   - If knob-based fields are present, prefer knob-based; otherwise fall back to legacy.
   - Rationale: enables incremental adoption without breaking existing examples/tests, while providing the desired interface for new work.

2. **Bits-only lookup tables (no ADC/DAC “type” in v1)**
   - ADC/DAC specs are keyed only by bit-width, matching user preference and keeping configs simple.
   - Rationale: mirrors the RAMwich pattern, but keeps the external schema minimal. If needed later, add `family` or `process` as extra axes.

3. **Validation rules copied from RAMwich-style constraints**
   - Require:
     - `xbar_size % num_columns_per_adc == 0` (clean ADC multiplexing groups).
     - `dac_bits > 0` and `activation_bits > 0`.
     - `draft_bits`/`residual_bits`/`dac_bits` exist in the selected library.
   - Rationale: prevents silent mis-accounting and makes config errors actionable.

4. **Analytical activation-count analog accounting, derived from xbar tiling**
   - Replace “analog energy/latency per MAC” with a closed-form activation-count model that estimates how many times the analog arrays and peripherals fire (no event simulation).
   - For each analog matmul block with matrix shape `(M_out × N_in)` and xbar size `S`:
     - `tiles_out = ceil(M_out / S)`
     - `tiles_in = ceil(N_in / S)`
     - `num_tiles = tiles_out * tiles_in`
   - Serial DAC slicing:
     - `num_slices = ceil(activation_bits / dac_bits)`
   - ADC multiplexing:
     - `adc_steps = num_columns_per_adc`
     - `num_adc_per_xbar = S / num_columns_per_adc`
   - Per tile per slice, model parallelism as in RAMwich (counts come from math; no SimPy):
     - **DAC**: energy scales with `S` conversions (one per column) per slice per tile; latency is paid once per slice (parallel DACs per column).
     - **ADC**: energy scales with `S` conversions (one per row) per slice per tile; latency scales with `adc_steps` because each ADC is time-multiplexed over `num_columns_per_adc` outputs.
     - When both ADCs are used in the same read (Roadmap full-precision reads), energy adds; latency is `max(lat_draft_scan, lat_residual_scan)` (parallel ADC blocks) rather than a sum.
   - Dual-ADC Roadmap modes (per analog block):
     - Draft default (base-only): use ADC-Draft only.
     - Draft full precision (policy says full): use **both** ADC-Draft and ADC-Residual (arrays 1–4).
     - Verify for drafted tokens:
       - `reuse_policy=reuse`:
         - if Draft was base-only: use ADC-Residual only (arrays 2–4) + digital add with stored draft base.
         - if Draft was full: no analog read (reuse stored full-precision output).
       - `reuse_policy=reread`: use both ADCs (arrays 1–4).
     - Verify bonus token: always use both ADCs (arrays 1–4).
   - FFN mapping:
     - `mlp`: two matmuls (up + down) accounted under the `ffn` stage.
     - `swiglu`: three matmuls (gate + up + down) accounted under the `ffn` stage.
   - Rationale: this reproduces the *shape* of RAMwich’s “count activations, multiply by per-activation specs” while implementing the Roadmap’s dual-ADC residual architecture rather than RAMwich’s single-ADC MVMU.

5. **Breakdown generation as a first-class output**
   - Compute and report costs in two orthogonal views:
     - **Stage view**: attributes costs to algorithmic stages (QKV/WO/FFN/QK/PV/softmax/elementwise/KV-cache).
     - **Component view**: attributes costs to physical components (ADC-Draft, ADC-Residual, DAC, arrays, etc.).
   - Mechanically, stage totals are built from component contributions, then aggregated by phase (Draft / Verify-drafted / Verify-bonus / Total).
   - Rationale: stage view is useful for model-level optimization; component view is required for hardware co-design and sanity-checking (and is explicitly called out in the Roadmap).

6. **Keep digital accounting as-is initially; group it for component breakdown**
   - For v1, keep digital stages (attention matmuls, softmax, elementwise, KV-cache) on the existing cost model (per-MAC or per-op as currently represented).
   - Component breakdown maps:
     - `qk/pv` → attention engine
     - `softmax` → softmax unit
     - `elementwise` → elementwise unit
     - `kv_cache` → KV-cache
   - Rationale: the change is focused on the analog readout path interface + accounting; digital modeling can be knob-ified later without blocking the ADC/DAC work.

## Risks / Trade-offs

- **[Library calibration]** Discrete “bits → PPA” tables require provenance and will differ by implementation/process.  
  → Mitigation: version the library (`*_v1`, `*_v2`), include resolved values in the report for transparency, and allow future override via an optional external library file.

- **[Model fidelity]** Activation-count tiling is still an abstraction and may not match a detailed simulator in all regimes (e.g., accumulation, sparsity, scheduling).  
  → Mitigation: document assumptions, keep formulas simple and testable, and validate against RAMwich or other references on a few representative cases.

- **[Latency ambiguity]** Whether ADC latency is “per conversion step” vs “per full xbar scan” is easy to get wrong when multiplexing is involved.  
  → Mitigation: define library values as *per conversion step* explicitly, and compute scan latency as `adc_steps * latency_per_step` (with unit tests for scaling with `num_columns_per_adc`).

- **[Back-compat complexity]** Supporting both legacy and knob-based hardware schemas increases validation surface area.  
  → Mitigation: make schema detection explicit and error on mixed/ambiguous inputs (e.g., require exactly one of `costs` or `analog` at top-level).

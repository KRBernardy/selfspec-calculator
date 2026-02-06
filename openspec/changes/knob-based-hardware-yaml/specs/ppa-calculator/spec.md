## MODIFIED Requirements

### Requirement: Load `model.yaml` transformer configuration
The calculator SHALL load a Transformer model description from a YAML file (`model.yaml`) and make it available to the estimator. The system MUST fail with a clear error when required fields are missing or have invalid types.

The model config MUST include `activation_bits` (integer, ≥ 1), representing the activation precision used for the analog CIM path. The estimator MUST use `activation_bits` together with `hardware.yaml`'s `analog.dac_bits` to determine the number of serial DAC slices required for analog readout accounting.

#### Scenario: Valid model config loads successfully
- **WHEN** the user runs the calculator with a valid `model.yaml` (including `activation_bits`)
- **THEN** the calculator parses the file and proceeds to estimation

#### Scenario: Missing `activation_bits` is rejected
- **WHEN** the user runs the calculator with a `model.yaml` that omits `activation_bits`
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the missing field

#### Scenario: Invalid `activation_bits` is rejected
- **WHEN** the user runs the calculator with a `model.yaml` where `activation_bits` is not a positive integer
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the invalid value

### Requirement: Load `hardware.yaml` hardware configuration
The calculator SHALL load a hardware/technology configuration from a YAML file (`hardware.yaml`) that parameterizes energy/latency/area models and architectural policy knobs (including Draft/Verify behavior and reuse policy). The system MUST fail with a clear error when required fields are missing or have invalid types.

The calculator SHALL support both of the following `hardware.yaml` formats:

- **Knob-based hardware config** (preferred for this project): provides architecture knobs under `analog.*` and a `library` key for discrete ADC/DAC lookup.
- **Legacy explicit-cost hardware config**: provides low-level coefficients under `costs.*` as supported today.

If the file contains knob-based fields (`analog.*`), the calculator SHALL use the knob-based mode. The calculator MUST reject ambiguous configs that mix knob-based `analog.*` fields with legacy `costs.*` fields.

For knob-based mode, the config MUST include:
- `reuse_policy` in `{reuse, reread}`
- `analog.xbar_size` (integer, ≥ 1)
- `analog.num_columns_per_adc` (integer, ≥ 1, and MUST divide `analog.xbar_size`)
- `analog.dac_bits` (integer, ≥ 1)
- `analog.adc.draft_bits` (integer, ≥ 1)
- `analog.adc.residual_bits` (integer, ≥ 1)
- `library` (string) MAY be provided; if omitted, the calculator MUST use a documented default library

The calculator MUST validate that requested ADC/DAC bit-widths exist in the selected library and MUST fail with a clear error if a requested bit-width is unavailable.

#### Scenario: Valid knob-based hardware config loads successfully
- **WHEN** the user runs the calculator with a valid knob-based `hardware.yaml` (including dual ADC bits, `dac_bits`, `xbar_size`, and `num_columns_per_adc`)
- **THEN** the calculator parses the file, resolves ADC/DAC specs from the internal library, and proceeds to estimation

#### Scenario: Hybrid knob-based + legacy config is rejected
- **WHEN** the user runs the calculator with a `hardware.yaml` that specifies both `analog.*` and `costs.*`
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the ambiguity

#### Scenario: Invalid ADC mux factor is rejected
- **WHEN** the user runs the calculator with a knob-based `hardware.yaml` where `analog.xbar_size` is not divisible by `analog.num_columns_per_adc`
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the divisibility constraint

#### Scenario: Unknown bit-width is rejected
- **WHEN** the user runs the calculator with a knob-based `hardware.yaml` that requests an ADC or DAC bit-width not present in the selected library
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the missing library entry

### Requirement: Support draft-result reuse policy in Verify
The calculator SHALL support a configurable policy for whether Verify reuses stored draft results for drafted tokens (non-destructive reuse) or re-reads the analog arrays. The report MUST indicate which policy was used and its effect on the Draft/Verify breakdown.

For the analog matmul stages (QKV/WO/FFN), the calculator MUST model Verify behavior consistent with the Roadmap’s dual-ADC residual architecture:

- With `reuse_policy: reuse`, for verifier steps corresponding to drafted tokens:
  - If the block was executed in base-only Draft Mode (ADC-Draft only), Verify MUST account only for the residual readout (ADC-Residual on Arrays 2–4) and the digital combine with the stored draft base value.
  - If the block was executed in full precision during Draft Mode (ADC-Draft + ADC-Residual), Verify MUST reuse the stored full-precision output and MUST NOT add additional analog readout cost for that block.
- With `reuse_policy: reread`, for verifier steps corresponding to drafted tokens, Verify MUST account a full analog readout (Arrays 1–4 using both ADCs) regardless of what was executed during Draft.
- For the verifier bonus token (no stored draft output), Verify MUST account a full analog readout (Arrays 1–4 using both ADCs).

#### Scenario: Reuse policy changes verify cost for drafted tokens
- **WHEN** the user runs the calculator once with `reuse_policy: reuse` and once with `reuse_policy: reread` (all else equal)
- **THEN** the verify-phase analog readout costs for drafted tokens differ between the two runs and the selected policy is recorded in the report

#### Scenario: Full-precision draft blocks incur no additional verify analog reads under reuse
- **WHEN** a block is configured to execute full precision in Draft Mode and `reuse_policy: reuse`
- **THEN** the report’s verify-drafted component breakdown attributes zero additional ADC/array readout cost to that block (relative to Draft) for drafted tokens

### Requirement: Emit a machine-readable report with breakdowns
The calculator SHALL produce a machine-readable report (JSON) containing, at minimum:

- configuration metadata (paths, key knobs such as `K`, reuse policy, and relevant model/hardware knobs)
- overall metrics (energy/token, latency/token, throughput tokens/s, tokens/J)
- breakdowns by phase (Draft vs Verify) and by major compute stages/blocks
- area totals and breakdowns (as provided by the hardware model)

The calculator MUST include **both** of the following breakdown views:

1. **Stage-level breakdown**: energy/latency contributions for QKV, WO, FFN, QK, PV, softmax, elementwise, and KV-cache.
2. **Component-level breakdown**: energy/latency contributions for at least arrays, DAC, ADC-Draft, ADC-Residual, attention engine, KV-cache, softmax unit, elementwise unit, buffers/add, and control.

For knob-based configs, the report MUST also include the resolved per-bit library entries actually used (ADC/DAC specs) and MUST include component activation counts sufficient to audit the model (e.g., ADC conversion counts and DAC conversion counts).

#### Scenario: JSON report includes both stage and component breakdowns
- **WHEN** the user runs the calculator on any valid inputs
- **THEN** the output report JSON contains both stage-level and component-level breakdown sections with energy/latency totals

#### Scenario: Knob-based report includes resolved library values and activation counts
- **WHEN** the user runs the calculator with a knob-based `hardware.yaml`
- **THEN** the report includes the resolved ADC/DAC library values used for the run and includes component activation counts for the analog readout path

## ADDED Requirements

### Requirement: Compute analytical analog activation counts for knob-based configs
When using knob-based `hardware.yaml`, the calculator SHALL compute closed-form activation counts for analog readout components (arrays, DAC, ADC-Draft, ADC-Residual) from `model.yaml` shapes and the knob-based hardware parameters (`xbar_size`, `num_columns_per_adc`, `dac_bits`, and the two ADC bit-widths). The calculator MUST NOT rely on simulating an instruction/event trace to determine these counts.

The calculator MUST compute the number of serial DAC slices per analog readout as:

`num_slices = ceil(activation_bits / dac_bits)`

and MUST scale the analog readout accounting accordingly.

#### Scenario: DAC slicing increases analog work when `dac_bits` decreases
- **WHEN** `activation_bits` is fixed and the user decreases `analog.dac_bits`
- **THEN** the calculator increases the accounted analog readout work (energy and latency) in proportion to the increased number of serial slices

#### Scenario: No slicing when `dac_bits` covers `activation_bits`
- **WHEN** `analog.dac_bits >= activation_bits`
- **THEN** the calculator accounts exactly one DAC slice per analog readout (`num_slices = 1`)


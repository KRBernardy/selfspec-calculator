## Why

Today `hardware.yaml` forces users to hand-enter low-level energy/latency/area coefficients, making it hard to run the Roadmap’s ADC-resolution split experiments and to reuse consistent peripheral assumptions across projects. We want a knob-based `hardware.yaml` where users specify high-level hardware knobs (like ADC bit-widths) and the calculator resolves the corresponding specs from a discrete library, similar to how RAMwich config works.

## What Changes

- Add a knob-based hardware config mode for the analog readout path that lets users specify:
  - crossbar size (`analog.xbar_size`)
  - number of columns per ADC (`analog.num_columns_per_adc`)
  - DAC resolution (`analog.dac_bits`), which (together with activation precision from `model.yaml`) determines how many serial input slices are required per analog MVM (arrays/ADCs fire multiple times when `dac_bits < activation_bits`)
  - dual ADC resolutions (`analog.adc.draft_bits`, `analog.adc.residual_bits`)
  - reuse policy (`reuse_policy`)
- Introduce an internal, discrete “hardware spec library” (lookup tables) that maps:
  - ADC bit-width → ADC energy/latency/area (for both ADC-Draft and ADC-Residual), and
  - DAC bit-width → DAC energy/latency/area,
  used by an analytical activation-count analog accounting model (RAMwich-inspired) to derive per-stage costs from crossbar sizing, ADC/DAC choices, and the number of required serial slices.
- Extend the JSON report to include **both**:
  - the existing *stage-level* breakdown (QKV/WO/FFN/QK/PV/softmax/elementwise/KV-cache), and
  - a new *component-level* breakdown (e.g., Array readout, DAC, ADC-Draft, ADC-Residual, digital attention engine, KV-cache, softmax unit, elementwise unit, buffers/add, control).
- Update `examples/hardware.yaml` and documentation to demonstrate the knob-based configuration and ADC-resolution split sweeps (e.g., 4-bit draft + 12-bit residual).

## Capabilities

### New Capabilities

### Modified Capabilities
- `ppa-calculator`: Accept a knob-based `hardware.yaml` mode for dual-ADC readout (draft vs residual) with `xbar_size`, `num_columns_per_adc`, and configurable DAC resolution; use activation precision from `model.yaml` (e.g., `activation_bits`) to determine serial DAC slicing; resolve ADC/DAC specs via a discrete internal library; model repeated array activations when serial DAC slicing is required; and emit both stage- and component-level breakdowns in the report.

## Impact

- Updates the `hardware.yaml` schema and its validation logic.
- Adds a small library/data layer for ADC/DAC spec lookup (bits → energy/latency/area).
- Modifies estimator accounting to be activation-count-based (closed-form math, not simulation) for the analog MVM path and to attribute costs to both stages and physical components.
- Updates report schema, examples, and tests that validate report structure.

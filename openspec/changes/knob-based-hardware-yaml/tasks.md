## 1. Input Schema and Validation

- [x] 1.1 Add `activation_bits` to `ModelConfig` and require it to be a positive integer in `model.yaml`
- [x] 1.2 Add knob-based hardware config models for `analog.xbar_size`, `analog.num_columns_per_adc`, `analog.dac_bits`, and `analog.adc.{draft_bits,residual_bits}`
- [x] 1.3 Implement hardware mode detection (`analog.*` knob-based vs `costs.*` legacy) and reject ambiguous mixed configs
- [x] 1.4 Enforce knob-based validation rules (`xbar_size % num_columns_per_adc == 0`, positive bit-widths)

## 2. Hardware Library Resolution

- [x] 2.1 Add built-in versioned library data for ADC and DAC specs keyed by bit-width
- [x] 2.2 Implement library selection with documented default when `library` is omitted
- [x] 2.3 Validate requested ADC/DAC bit-widths against selected library and raise clear errors when missing
- [x] 2.4 Expose resolved ADC/DAC entries for downstream reporting

## 3. Analytical Analog Activation-Count Model

- [x] 3.1 Implement closed-form helpers for tiling counts (`tiles_out`, `tiles_in`, `num_tiles`) from block shapes and `xbar_size`
- [x] 3.2 Implement DAC slicing calculation `num_slices = ceil(activation_bits / dac_bits)` and apply it to analog activation counts
- [x] 3.3 Implement per-mode analog readout counting for Draft default, Draft full-precision blocks, Verify-drafted (reuse/reread), and Verify bonus token
- [x] 3.4 Implement dual-ADC timing rule for full reads (`latency = max(adc_draft_scan, adc_residual_scan)`) while summing energy contributions

## 4. Estimator Integration and Compatibility

- [x] 4.1 Integrate the analytical analog counting path into per-step and per-burst accounting for knob-based configs
- [x] 4.2 Preserve legacy explicit-cost behavior for existing `costs.*` configs without changing current semantics
- [x] 4.3 Ensure reuse-policy behavior is applied consistently to analog blocks in Verify and reflected in totals

## 5. Reporting and Output Contract

- [x] 5.1 Extend report models to include component-level breakdowns alongside existing stage-level breakdowns
- [x] 5.2 Add analog component activation counts (at least DAC and ADC conversion counts) to knob-based report output
- [x] 5.3 Include resolved library metadata and selected hardware mode in report payload
- [x] 5.4 Keep baseline/delta and break-even outputs compatible with existing consumers

## 6. Examples and Documentation

- [x] 6.1 Update `examples/model.yaml` to include `activation_bits`
- [x] 6.2 Add/update knob-based `examples/hardware.yaml` with dual ADC bits, DAC bits, xbar size, and columns-per-ADC
- [x] 6.3 Document knob-based config format, legacy compatibility, and key assumptions in `README.md`

## 7. Verification and Regression Tests

- [x] 7.1 Add validation tests for new schema fields and constraints (missing/invalid `activation_bits`, divisibility, mixed format rejection, unknown library bit-width)
- [x] 7.2 Add accounting tests for DAC slicing scaling and dual-ADC reuse/reread behavior
- [x] 7.3 Add report-shape tests confirming both stage-level and component-level breakdowns plus resolved library values/counts
- [x] 7.4 Add regression tests ensuring legacy explicit-cost configs still run and produce expected output shape

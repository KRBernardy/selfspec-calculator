## 1. Input Schema and Validation

- [ ] 1.1 Add `activation_bits` to `ModelConfig` and require it to be a positive integer in `model.yaml`
- [ ] 1.2 Add knob-based hardware config models for `analog.xbar_size`, `analog.num_columns_per_adc`, `analog.dac_bits`, and `analog.adc.{draft_bits,residual_bits}`
- [ ] 1.3 Implement hardware mode detection (`analog.*` knob-based vs `costs.*` legacy) and reject ambiguous mixed configs
- [ ] 1.4 Enforce knob-based validation rules (`xbar_size % num_columns_per_adc == 0`, positive bit-widths)

## 2. Hardware Library Resolution

- [ ] 2.1 Add built-in versioned library data for ADC and DAC specs keyed by bit-width
- [ ] 2.2 Implement library selection with documented default when `library` is omitted
- [ ] 2.3 Validate requested ADC/DAC bit-widths against selected library and raise clear errors when missing
- [ ] 2.4 Expose resolved ADC/DAC entries for downstream reporting

## 3. Analytical Analog Activation-Count Model

- [ ] 3.1 Implement closed-form helpers for tiling counts (`tiles_out`, `tiles_in`, `num_tiles`) from block shapes and `xbar_size`
- [ ] 3.2 Implement DAC slicing calculation `num_slices = ceil(activation_bits / dac_bits)` and apply it to analog activation counts
- [ ] 3.3 Implement per-mode analog readout counting for Draft default, Draft full-precision blocks, Verify-drafted (reuse/reread), and Verify bonus token
- [ ] 3.4 Implement dual-ADC timing rule for full reads (`latency = max(adc_draft_scan, adc_residual_scan)`) while summing energy contributions

## 4. Estimator Integration and Compatibility

- [ ] 4.1 Integrate the analytical analog counting path into per-step and per-burst accounting for knob-based configs
- [ ] 4.2 Preserve legacy explicit-cost behavior for existing `costs.*` configs without changing current semantics
- [ ] 4.3 Ensure reuse-policy behavior is applied consistently to analog blocks in Verify and reflected in totals

## 5. Reporting and Output Contract

- [ ] 5.1 Extend report models to include component-level breakdowns alongside existing stage-level breakdowns
- [ ] 5.2 Add analog component activation counts (at least DAC and ADC conversion counts) to knob-based report output
- [ ] 5.3 Include resolved library metadata and selected hardware mode in report payload
- [ ] 5.4 Keep baseline/delta and break-even outputs compatible with existing consumers

## 6. Examples and Documentation

- [ ] 6.1 Update `examples/model.yaml` to include `activation_bits`
- [ ] 6.2 Add/update knob-based `examples/hardware.yaml` with dual ADC bits, DAC bits, xbar size, and columns-per-ADC
- [ ] 6.3 Document knob-based config format, legacy compatibility, and key assumptions in `README.md`

## 7. Verification and Regression Tests

- [ ] 7.1 Add validation tests for new schema fields and constraints (missing/invalid `activation_bits`, divisibility, mixed format rejection, unknown library bit-width)
- [ ] 7.2 Add accounting tests for DAC slicing scaling and dual-ADC reuse/reread behavior
- [ ] 7.3 Add report-shape tests confirming both stage-level and component-level breakdowns plus resolved library values/counts
- [ ] 7.4 Add regression tests ensuring legacy explicit-cost configs still run and produce expected output shape

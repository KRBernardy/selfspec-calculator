## 1. Library Data Source Extraction

- [ ] 1.1 Create a packaged JSON file containing current runtime libraries (`puma_like_v1`, `puma_like_v2`, `science_soc_v1`) with values equivalent to current defaults
- [ ] 1.2 Add a loader utility in `config.py` that reads library JSON into normalized in-memory dicts
- [ ] 1.3 Add clear load-time error handling for missing file, malformed JSON, and invalid top-level structure

## 2. Config Integration and Resolution

- [ ] 2.1 Extend `HardwareConfig` with optional `library_file` field for custom JSON source selection
- [ ] 2.2 Implement `library_file` path resolution relative to the hardware YAML file location
- [ ] 2.3 Refactor library access points (`resolve_knob_specs`, `_apply_library_defaults`, `resolved_library_payload`) to use loaded JSON libraries instead of inline constants
- [ ] 2.4 Preserve default behavior when `library_file` is not provided

## 3. Validation and Backward Compatibility

- [ ] 3.1 Keep existing bit-width and unknown-library validation behavior with JSON-backed sources
- [ ] 3.2 Add validation for missing required library sections/fields (`adc`, `dac`, `array`, `digital`)
- [ ] 3.3 Add regression tests confirming existing example configs still run without `library_file`
- [ ] 3.4 Add tests for custom-file switching behavior and for failure cases (unknown library, missing bit entries, malformed/incomplete JSON)

## 4. Documentation and Examples

- [ ] 4.1 Update README to document JSON library format and `library_file` usage
- [ ] 4.2 Add at least one example hardware config that uses a custom `library_file`
- [ ] 4.3 Document source-selection precedence and expected error messages for invalid library files

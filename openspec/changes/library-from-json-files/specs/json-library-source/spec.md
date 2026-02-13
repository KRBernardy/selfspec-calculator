## ADDED Requirements

### Requirement: Runtime hardware libraries SHALL be loaded from JSON sources
The system SHALL load knob-based runtime library definitions from JSON files instead of hardcoded Python library tables.

#### Scenario: Default library source is available
- **WHEN** the calculator parses a knob-based hardware config that does not specify a custom library source
- **THEN** it loads libraries from the packaged default JSON source and resolves the requested library name successfully

### Requirement: Hardware config SHALL support selecting a custom library JSON file
The hardware configuration SHALL support an optional field to specify a custom JSON library file so users can switch library sources without editing Python code.

#### Scenario: Custom library file is used for resolution
- **WHEN** a hardware config provides a custom library file path and a library name
- **THEN** the calculator resolves the library only from that JSON file and uses its values for estimation

#### Scenario: Relative custom library path resolves against hardware config directory
- **WHEN** a hardware config provides a relative custom library file path
- **THEN** the calculator resolves that path relative to the hardware YAML file location

### Requirement: Existing library-name workflows SHALL remain backward compatible
Existing hardware configs that rely on current library names (for example `puma_like_v1`, `puma_like_v2`, `science_soc_v1`) SHALL continue to work without requiring any new fields.

#### Scenario: Existing example hardware config still works
- **WHEN** a hardware config uses `library: puma_like_v1` with no custom library file
- **THEN** parsing and spec resolution succeed with behavior equivalent to pre-refactor defaults

### Requirement: JSON-backed libraries SHALL enforce schema and lookup validation
The system MUST validate JSON library content before use and MUST fail with explicit errors for invalid sources or missing required library entries.

#### Scenario: Unknown library name is rejected
- **WHEN** the selected library name is not present in the active JSON source
- **THEN** the calculator fails with an error that includes available library names

#### Scenario: Missing requested ADC or DAC bit entry is rejected
- **WHEN** the selected library exists but requested ADC/DAC bit-width entries are absent
- **THEN** the calculator fails with a clear validation error naming the missing bit-width and available options

#### Scenario: Malformed or incomplete library JSON is rejected
- **WHEN** the custom library file is invalid JSON or missing required sections (`adc`, `dac`, `array`, or `digital`)
- **THEN** the calculator fails before estimation with a structured validation error

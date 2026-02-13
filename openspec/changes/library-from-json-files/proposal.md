## Why

Hardware library data is currently embedded directly in `config.py`, which makes it hard to inspect, review, and switch between library variants without code edits. Moving library data to JSON files improves readability and lets users select alternate libraries/files through configuration rather than modifying source.

## What Changes

- Move built-in hardware library definitions (ADC/DAC/array/digital and optional SoC/memory/periphery defaults) out of inline Python constants and into JSON resource files.
- Add a loader in `config.py` that reads library definitions from JSON and preserves current validation and default behavior.
- Add a configuration mechanism to choose which JSON library file(s) are loaded so different library sets can be swapped without editing code.
- Keep backward compatibility for existing hardware configs that reference current library names.
- Add validation/tests for malformed JSON, missing required library fields, unknown library names, and compatibility with existing examples.

## Capabilities

### New Capabilities
- `json-library-source`: Load estimator hardware libraries from JSON files and allow selecting/switching library sources without modifying Python code.

### Modified Capabilities
- (none)

## Impact

- Config/runtime loading:
  - `src/selfspec_calculator/config.py` (library source loading, schema validation integration, default source behavior).
- Project structure:
  - new JSON library file(s) (for example under `src/selfspec_calculator/libraries/` or a similar package path).
- Documentation:
  - `README.md` updates for library-file format and library-source selection.
- Testing:
  - new unit/integration tests for JSON loading, validation failures, and backward compatibility.

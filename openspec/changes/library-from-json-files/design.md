## Context

`HardwareConfig` currently hardcodes library tables in `src/selfspec_calculator/config.py` (`LIBRARIES` and derived `science_soc_v1`). This makes library data difficult to review and update, and requires code changes to test alternate library sets. The change needs a file-backed source of truth while preserving the current behavior for existing examples/tests.

Constraints:
- Existing hardware YAML files should keep working (`library: puma_like_v1`, etc.).
- Library values must remain strongly validated before estimator use.
- Library switching should be possible by changing configuration, not Python source.

## Goals / Non-Goals

**Goals:**
- Move runnable library data from inline Python dicts to JSON files.
- Add a mechanism to select a JSON library file per run/config.
- Preserve default behavior and library names when no custom file is provided.
- Keep current validation semantics (unknown library, missing ADC/DAC bit entry, invalid field types).

**Non-Goals:**
- Changing estimator formulas or report semantics.
- Redesigning every library coefficient in this change.
- Supporting non-JSON library formats.

## Decisions

### 1) Introduce a canonical JSON schema for runtime libraries
**Decision:** Define a JSON structure that mirrors current `LIBRARIES` shape (`adc`, `dac`, `array`, `digital`, optional `soc`, `memory`, `analog_periphery`) keyed by library name.

**Rationale:** Minimal translation risk; existing `resolve_knob_specs` and default-application logic can be reused with limited refactoring.

**Alternatives considered:**
- New nested schema with per-component files: rejected for higher migration complexity.
- Keep Python dict + export script: rejected because source of truth remains code.

### 2) Add optional `library_file` in hardware config for source switching
**Decision:** Extend `HardwareConfig` with an optional `library_file` path. Resolution order:
1. If `library_file` is set, load libraries from that JSON file.
2. Otherwise load packaged default JSON file.

**Rationale:** Matches user intent (“switch between libraries by switching files”) and keeps one clear override point.

**Alternatives considered:**
- CLI-only flag: rejected because it is less reproducible than config-based selection.
- Environment variable override only: rejected due to hidden runtime behavior.

### 3) Use typed validation after JSON load, before estimator access
**Decision:** Parse JSON into a normalized in-memory dict, then validate on access using existing Pydantic models (`PeripheralSpec`, `AnalogArraySpec`, `DigitalCostDefaults`, etc.) and existing bit-width checks.

**Rationale:** Prevents silent acceptance of malformed JSON and preserves current error quality.

**Alternatives considered:**
- Trust JSON structure without typed validation: rejected (unsafe).
- Build a separate giant JSON schema validator: rejected as redundant with existing Pydantic models.

### 4) Keep backward compatibility by shipping a default JSON equivalent to current libraries
**Decision:** Create a packaged JSON file containing current `puma_like_v1`, `puma_like_v2`, and `science_soc_v1` values so existing YAML files keep resolving identically.

**Rationale:** Allows internal refactor without changing user-facing defaults.

**Alternatives considered:**
- Breaking change requiring `library_file` always: rejected.

### 5) Preserve paper-extract metadata as non-runnable provenance data
**Decision:** Keep `PAPER_LIBRARY_EXTRACTS` as metadata/provenance API (not part of runtime library resolution) in this change.

**Rationale:** Runtime libraries and provenance/extraction data serve different purposes and have different completeness guarantees.

**Alternatives considered:**
- Mix provenance extract into runnable libraries: rejected because extract is intentionally incomplete.

## Risks / Trade-offs

- **[JSON drift from expected schema]** malformed or partial files can break runs → Mitigation: strict validation + explicit errors naming missing/invalid fields.
- **[Path resolution confusion]** relative `library_file` may resolve unexpectedly → Mitigation: resolve relative to the hardware YAML file location and document it.
- **[Behavior regression]** refactor could alter defaults → Mitigation: keep default JSON byte-for-byte equivalent to current values and add regression tests for key libraries.
- **[Operational ambiguity]** multiple files with same library name could confuse users → Mitigation: define that selected source file fully determines available names for that run.

## Migration Plan

1. Add packaged default runtime library JSON file with current library values.
2. Add loader utility in `config.py` to read and cache library data from selected source.
3. Add optional `library_file` field and path-resolution rules.
4. Refactor `resolve_knob_specs`, `_apply_library_defaults`, and `resolved_library_payload` to read from loaded JSON data.
5. Add tests:
   - default behavior unchanged,
   - custom file switches libraries,
   - unknown library / missing required keys / malformed JSON errors.
6. Update README examples and docs to show switching by `library_file`.

Rollback:
- Revert to previous inline dict source and keep JSON file unused (no data loss; pure configuration source refactor).

## Open Questions

- Should custom `library_file` merge with defaults or fully replace them? (proposed: replace for deterministic behavior)
- Should we support loading from multiple JSON files in one run (priority-ordered), or keep one-file-only in v1?
- Do we want a future CLI helper to validate/dump normalized library JSON independently of estimation?

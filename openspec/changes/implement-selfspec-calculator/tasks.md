## 1. Project Setup

- [x] 1.1 Create Python package skeleton for the calculator library
- [x] 1.2 Add `pyproject.toml` with runtime/test dependencies and a CLI entrypoint
- [x] 1.3 Add a minimal `README.md` with quickstart usage and example command

## 2. Config Models and Validation

- [x] 2.1 Define `ModelConfig` schema to load `model.yaml`
- [x] 2.2 Define `HardwareConfig` schema to load `hardware.yaml` (including reuse policy and draft precision policy knobs)
- [x] 2.3 Implement YAML loading + validation with clear error messages for missing/invalid fields

## 3. Speculation Stats Inputs

- [x] 3.1 Define `SpeculationStats` schema for `K` and accepted-prefix-length histogram over `a ∈ [0..K]`
- [x] 3.2 Implement stats loader (JSON and/or YAML) and validate histogram integrity (bin range, non-negative, non-empty)
- [x] 3.3 Implement unit-tested helpers to compute `E[a+1]`, `K+1`, and `E[K-a]` from the histogram

## 4. Cost Accounting Core

- [x] 4.1 Define a representation for per-layer stages/blocks (Draft vs Verify) and their parametric cost inputs
- [x] 4.2 Implement per-step cost aggregation for a single token step at a given `L_prompt`
- [x] 4.3 Implement per-burst accounting: Draft `K` steps + Verify `K+1` steps, with verifier work never early-stopping
- [x] 4.4 Implement reuse-vs-reread handling for verifier steps corresponding to drafted tokens (and full read for bonus token)
- [x] 4.5 Compute expected per-committed-token metrics by normalizing burst totals by `E[a+1]`

## 5. Prompt-Length Sweep + Reporting

- [x] 5.1 Implement prompt-length sweep runner (user-provided list of `L_prompt`) and produce per-point metrics
- [x] 5.2 Define JSON report schema (overall metrics + Draft/Verify + stage breakdowns + area totals)
- [x] 5.3 Add baseline (“no speculation”) computation and per-`L_prompt` delta reporting
- [x] 5.4 Implement break-even prompt length detection for at least one target metric (e.g., tokens/J)

## 6. CLI + Examples

- [x] 6.1 Implement CLI command to run estimation from `model.yaml`, `hardware.yaml`, and stats input and write JSON output
- [x] 6.2 Add example `model.yaml`, `hardware.yaml`, and stats file that produce a valid report end-to-end

## 7. Tests and Quality Gates

- [x] 7.1 Add unit tests for config validation and speculation accounting invariants
- [x] 7.2 Add a golden/smoke test that runs the CLI on example inputs and validates the output JSON shape

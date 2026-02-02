## ADDED Requirements

### Requirement: Load `model.yaml` transformer configuration
The calculator SHALL load a Transformer model description from a YAML file (`model.yaml`) and make it available to the estimator. The system MUST fail with a clear error when required fields are missing or have invalid types.

#### Scenario: Valid model config loads successfully
- **WHEN** the user runs the calculator with a valid `model.yaml`
- **THEN** the calculator parses the file and proceeds to estimation

#### Scenario: Invalid model config is rejected
- **WHEN** the user runs the calculator with a `model.yaml` that is missing required fields
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the missing fields

### Requirement: Load `hardware.yaml` hardware configuration
The calculator SHALL load a hardware/technology configuration from a YAML file (`hardware.yaml`) that parameterizes energy/latency/area models and architectural policy knobs (including Draft/Verify behavior and reuse policy). The system MUST fail with a clear error when required fields are missing or have invalid types.

#### Scenario: Valid hardware config loads successfully
- **WHEN** the user runs the calculator with a valid `hardware.yaml`
- **THEN** the calculator parses the file and proceeds to estimation

#### Scenario: Invalid hardware config is rejected
- **WHEN** the user runs the calculator with a `hardware.yaml` that contains unknown enum values (e.g., unsupported `ffn_type`)
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the invalid values

### Requirement: Accept speculation statistics inputs
The calculator SHALL accept runtime speculation statistics as input, including burst length `K` and accepted-prefix-length statistics for `a ∈ [0, K]` (at minimum a histogram over `a`). The system MUST validate that the histogram covers only valid `a` values and contains non-negative counts/probabilities.

#### Scenario: Stats file with `K` and histogram is accepted
- **WHEN** the user provides `K` and a histogram over `a ∈ [0, K]`
- **THEN** the calculator loads the statistics and uses them in estimation

#### Scenario: Histogram outside `[0..K]` is rejected
- **WHEN** the user provides a histogram that contains an entry for `a < 0` or `a > K`
- **THEN** the calculator exits with a non-zero status and prints a validation error describing the invalid bins

### Requirement: Compute committed-token and wasted-work expectations
Given `K` and accepted-prefix-length statistics, the calculator SHALL compute expected burst-level values consistent with the Roadmap:

- expected committed tokens per burst `E[a+1]`
- fixed verifier steps per burst `K+1`
- expected wasted verifier steps `E[K-a]` (for `a < K`)

#### Scenario: Expected committed tokens computed from histogram
- **WHEN** the user provides `K` and a histogram over accepted prefix lengths
- **THEN** the calculator computes `E[a+1]` from the histogram and uses it as the normalization for per-committed-token metrics

### Requirement: Model serialized Draft then Verify execution per burst
The calculator SHALL model Draft and Verify phases as strictly serialized at the burst level:

- Draft phase cost: `K` draft token steps
- Verify phase cost: `K+1` verify token steps

The calculator MUST account for all `K+1` verifier steps even when the acceptance statistics indicate early mismatches (no early-stop of verifier work).

#### Scenario: Verifier work does not early-stop on mismatch
- **WHEN** the acceptance histogram indicates `a = 0` for every burst
- **THEN** the calculator still accounts for `K+1` verifier steps per burst in latency/energy totals

### Requirement: Support draft-result reuse policy in Verify
The calculator SHALL support a configurable policy for whether Verify reuses stored draft results for drafted tokens (non-destructive reuse) or re-reads the analog arrays. The report MUST indicate which policy was used and its effect on the Draft/Verify breakdown.

#### Scenario: Reuse policy changes verify cost for drafted tokens
- **WHEN** the user runs the calculator once with reuse enabled and once with reuse disabled (all else equal)
- **THEN** the verify-phase analog readout costs for drafted tokens differ between the two runs and the selected policy is recorded in the report

### Requirement: Support prompt-length sweeps
The calculator SHALL support estimating metrics across a sweep of prompt lengths `L_prompt` (at minimum, a user-specified list of prompt lengths). The report MUST include per-`L_prompt` results.

#### Scenario: Prompt-length list produces multiple result points
- **WHEN** the user requests estimation for a list of prompt lengths (e.g., `64` and `128`)
- **THEN** the report contains results for each requested prompt length

### Requirement: Emit a machine-readable report with breakdowns
The calculator SHALL produce a machine-readable report (JSON) containing, at minimum:

- configuration metadata (paths, key knobs such as `K` and reuse policy)
- overall metrics (energy/token, latency/token, throughput tokens/s, tokens/J)
- breakdowns by phase (Draft vs Verify) and by major compute blocks/stages
- area totals and breakdowns (as provided by the hardware model)

#### Scenario: JSON report is written to the requested destination
- **WHEN** the user runs the calculator with an output path for the report
- **THEN** the calculator writes a JSON file at that path containing the required top-level report fields

### Requirement: Baseline and break-even reporting
The calculator SHALL compute baseline metrics for a non-speculative configuration using the same `model.yaml` and `hardware.yaml`, and SHALL report deltas (ratio and absolute difference) between speculative and baseline results. The calculator SHALL also report break-even prompt length(s) where a target metric (e.g., tokens/J) becomes better than baseline, or `null` when no break-even exists in the evaluated sweep.

#### Scenario: Break-even is omitted when not present
- **WHEN** the speculative configuration is worse than baseline for all prompt lengths in the sweep
- **THEN** the report records break-even prompt length as `null` for that metric

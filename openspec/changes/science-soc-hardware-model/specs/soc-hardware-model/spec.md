## ADDED Requirements

### Requirement: Extended `hardware.yaml` supports SoC modeling knobs
The system SHALL accept an extended knob-based `hardware.yaml` that includes optional sections for SoC-level modeling (analog periphery, buffers/add/control, and memory/fabric) and SHALL use those values in estimation when provided.

#### Scenario: Extended knob-based hardware config loads successfully
- **WHEN** the user runs the calculator with a valid knob-based `hardware.yaml` that includes SoC modeling sections
- **THEN** the system parses the config successfully and proceeds to estimation

### Requirement: Backward compatibility for existing configurations
The system MUST remain backward compatible with existing inputs:
- existing knob-based configs that only contain `reuse_policy`, `library`, and `analog.*`
- existing legacy explicit-cost configs that only contain `reuse_policy` and `costs.*`

New SoC-related fields MUST be optional and MUST have defaults such that omitting them preserves prior behavior.

#### Scenario: Existing knob-based `hardware.yaml` remains valid
- **WHEN** the user runs the calculator with an existing knob-based `hardware.yaml` that omits all new SoC fields
- **THEN** the system validates the config successfully without requiring any new keys

#### Scenario: Existing legacy `hardware.yaml` remains valid
- **WHEN** the user runs the calculator with an existing legacy `hardware.yaml` that omits all new SoC fields
- **THEN** the system validates the config successfully without requiring any new keys

### Requirement: Report includes SoC component and memory breakdowns
When SoC modeling is enabled, the report SHALL include explicit breakdowns for:
- buffers/add overhead
- control overhead
- SRAM (on-chip) memory traffic
- HBM-like (off-chip) memory traffic
- fabric/interconnect traffic (e.g., AXI/NoC/DMA as a bytes-moved model)

The report MUST remain machine-readable JSON and MUST preserve existing stage-level fields for compatibility.

#### Scenario: Non-zero SoC knobs appear in the breakdown
- **WHEN** the user runs the calculator with non-zero SoC/memory parameters
- **THEN** the report contains non-zero energy and/or latency entries for the corresponding SoC components

### Requirement: Analog periphery overhead is accounted for explicitly
The estimator SHALL support modeling additional analog periphery blocks commonly present in CIM accelerators and in the Science SoC, including at minimum:
- trans-impedance amplifier (TIA) readout path (including programmable gain/`Rf` as a configurable knob),
- subarray switches/power gating for enabling Arrays 1..N,
- I/O buffers and registers at the core boundary,
- sample-and-hold (SNH) and MUX overhead for shared readout.

These periphery blocks MUST be attributable in the report breakdown (energy/latency/area) and MUST default to zero impact when unspecified.

#### Scenario: Analog periphery can be enabled without breaking estimation
- **WHEN** the user sets non-zero analog periphery parameters in `hardware.yaml`
- **THEN** the estimator includes their costs in totals and produces a valid report

### Requirement: KV-cache is modeled as a memory hierarchy (SRAM buffer + HBM main store)
The estimator SHALL model KV-cache costs using a bytes-moved model rather than abstract “MAC” counts when a memory model is configured.

The model MUST include:
- on-chip SRAM speculative KV buffer traffic (reads/writes for within-burst tokens),
- off-chip HBM-like KV traffic for the long context (reads, and commit-only writes),
- capacity and bandwidth knobs sufficient to compute energy and latency impacts as prompt length grows.

#### Scenario: KV-cache cost increases with prompt length
- **WHEN** the user increases `L_prompt` in a prompt-length sweep while keeping all other inputs fixed
- **THEN** the reported KV-cache/HBM read cost increases monotonically

#### Scenario: KV-cache cost increases with burst length
- **WHEN** the user increases burst length `K` while keeping all other inputs fixed
- **THEN** the reported KV-cache traffic and cost per burst increases

### Requirement: HBM reads are not mismatch-gated (no early stop in v1)
The estimator MUST account for HBM KV reads for all verifier steps in the burst, including steps that are later discarded after a mismatch. The estimator MUST NOT reduce HBM read traffic based on acceptance histogram values in v1.

#### Scenario: HBM read cost is independent of acceptance histogram
- **WHEN** the user runs the estimator twice with identical inputs except for different acceptance histograms (same `K`)
- **THEN** the reported HBM KV read energy/latency is the same in both runs

### Requirement: HBM KV writes are commit-only (policy B)
The estimator MUST model HBM KV writes as occurring only for committed tokens:
- accepted draft tokens, plus
- the verifier’s committed token at the first mismatch position (or the bonus token when all drafted tokens match).

Discarded verifier steps after mismatch MUST NOT contribute HBM KV writes.

#### Scenario: Always-mismatch histogram writes only one token per burst
- **WHEN** the acceptance histogram assigns probability 1.0 to `a = 0` (always mismatch immediately)
- **THEN** the estimator accounts for HBM KV writes for exactly one committed token per burst (in expectation)

#### Scenario: Always-accept histogram writes K+1 tokens per burst
- **WHEN** the acceptance histogram assigns probability 1.0 to `a = K` (all drafted tokens accepted)
- **THEN** the estimator accounts for HBM KV writes for exactly `K+1` committed tokens per burst (in expectation)

### Requirement: INT8 KV in HBM uses per-head static scaling with metadata overhead
When HBM KV is configured as INT8, the estimator SHALL model per-head static scaling and SHALL include the scale metadata bandwidth in SRAM/HBM traffic accounting.

#### Scenario: Scale metadata overhead grows with heads and layers
- **WHEN** the user increases `n_heads` or `n_layers` while keeping other inputs fixed
- **THEN** the reported KV scale-metadata bytes moved increases proportionally

### Requirement: Layer-pipelined full-chip schedule is supported as an option
The estimator SHALL support an optional schedule mode that reflects a scaled full-chip configuration where stationary weights are resident and layers can be spatially pipelined.

In this mode:
- energy accounting MUST remain unchanged (all work still occurs),
- the reported time per token MAY be reduced relative to fully serialized layer execution.

#### Scenario: Layer-pipelined schedule reduces or equals serialized time
- **WHEN** the user enables the layer-pipelined schedule mode for an otherwise identical configuration
- **THEN** the reported latency per token is less than or equal to the serialized schedule result

### Requirement: Verify-burst setup cost can be modeled as a per-burst term
The estimator SHALL support an optional verify-setup cost (energy/latency) that is charged once per verify burst (not once per verifier step) to represent Roadmap-style setup amortization (e.g., bitline charge/setup).

#### Scenario: Setup cost is charged once per burst
- **WHEN** the user enables a non-zero verify-setup latency and compares two runs with different `K`
- **THEN** the setup-latency portion of total verify time does not scale linearly with `K`

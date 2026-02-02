## Why

The repo currently only describes the “Performance Calculator (`selfspec-calculator`, Python)” in `Roadmap.md` (§5.3), but there is no implementation to turn speculation statistics into PPA estimates. Implementing the calculator unblocks design-space exploration and provides a concrete, configurable estimator aligned with the Draft/Verify residual architecture assumptions.

## What Changes

- Add a Python-based calculator (library + CLI) that reads `model.yaml`, `hardware.yaml`, and runtime speculation inputs (e.g., `K`, accepted-prefix-length histogram `P(a)`, prompt-length sweep).
- Implement event-based accounting for Draft and Verify phases (including reuse vs re-read policy) to produce latency/throughput/energy/area breakdowns.
- Produce report outputs (machine-readable JSON at minimum) including break-even prompt length metrics.
- Add example configs and minimal validation so users can run the estimator without modifying code.

## Capabilities

### New Capabilities
- `ppa-calculator`: Hardware performance estimator that maps Transformer + hardware configs and speculation statistics to PPA metrics and breakdowns.

### Modified Capabilities

## Impact

- New Python package/modules and a CLI entrypoint.
- New config files/schemas/examples (`model.yaml`, `hardware.yaml`) and output report formats (e.g., JSON).
- New dependencies (expected: YAML parser, numeric utilities) and unit tests for core accounting logic.

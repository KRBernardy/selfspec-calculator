## Why

The current `selfspec-calculator` models only a small subset of the hardware (mostly arrays + DAC/ADC + abstract digital MAC costs), which is insufficient for evaluating the Science SoC-style “true analog / residual” architecture and the Roadmap’s full-chip Draft/Verify pipeline. We need an SoC-level estimator that accounts for missing analog periphery, buffering/add/control overheads, and the KV-cache memory system (off-chip HBM + on-chip SRAM buffering).

## What Changes

- Extend the estimator’s hardware model from “arrays + DAC/ADC + generic digital” to a **full SoC** abstraction aligned with:
  - Science paper SoC (cores + CPU + on-chip memory + AXI/DMA; TIA-based readout; per-core buffers/control),
  - RAMwich-style “traditional” CIM periphery blocks (MUX/SNH/regs/accum), and
  - Roadmap-specific Draft/Verify reuse and speculative burst accounting.
- Extend `hardware.yaml` (knob-based format) with **optional, backward-compatible** sections for additional hardware components, each with sensible defaults so existing configs remain valid:
  - analog periphery: TIA (incl. programmable gain/`Rf`), subarray switches/power gating, I/O buffers/registers, sample-and-hold, muxing, write/verify drivers (area/energy/leakage knobs),
  - digital overhead: buffers + add/accum (e.g., `D_reg + C`, ADC-output combines), controller/sequence overhead,
  - memory + fabric: on-chip SRAM buffers (draft reuse + speculative KV), off-chip HBM-like KV-cache, and interconnect/transfer overhead (AXI/NoC/DMA as a bytes-moved model).
- Add a KV-cache model that reflects project decisions:
  - KV main store is **off-chip HBM-like** (capacity and bandwidth modeled),
  - speculative KV uses an **on-chip SRAM buffer** (policy B),
  - verifier work does **not** early-stop on mismatch (wasted suffix compute still happens),
  - HBM traffic is accounted for the full burst (no mismatch-gating optimization in v1),
  - KV representation in HBM is **INT8 with per-head scaling** (consistent with common “per-channel/per-head” quantization practice; overhead for scale metadata is modeled).
- Maintain compatibility by keeping existing stage-level outputs; new components appear in component/memory breakdowns without breaking existing workflows.

## Capabilities

### New Capabilities
- `soc-hardware-model`: An SoC-level estimator hardware model (schema + accounting) that adds missing CIM periphery, buffers/add/control overheads, and an HBM+SRAM KV-cache/memory-fabric model aligned with the Science paper and Roadmap assumptions.

### Modified Capabilities
- (none)

## Impact

- Config/schema:
  - Updates to `hardware.yaml` knob-based schema (new optional fields with defaults; legacy `costs.*` format remains supported).
- Estimator logic:
  - Updates to `src/selfspec_calculator/estimator.py` to add memory-traffic-based KV modeling and explicit buffers/add/control/periphery accounting.
- Reporting:
  - Updates to `src/selfspec_calculator/report.py` (and JSON output) to include new component and memory breakdowns.
- Examples/tests:
  - New/updated example hardware configs demonstrating SoC/HBM knobs; additional unit tests for validation and accounting.

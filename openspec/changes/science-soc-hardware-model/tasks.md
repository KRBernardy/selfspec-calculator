## 1. Config / Schema Extensions

- [x] 1.1 Add optional `soc` section to knob-based `hardware.yaml` (schedule mode + verify-setup term) with backward-compatible defaults
- [x] 1.2 Add optional `memory` section to knob-based `hardware.yaml` for SRAM/HBM/fabric bytes-based modeling (energy/byte, bandwidth, latency knobs) with defaults that preserve current behavior
- [x] 1.3 Add optional `analog.periphery` section for TIA/`Rf`, subarray switches, IO buffers/regs, SNH, MUX, and write/verify drivers (default-zero impact)
- [x] 1.4 Update config validation to ensure legacy `costs.*` and knob-based `analog.*` modes remain mutually exclusive and unchanged by new optional fields
- [x] 1.5 Extend `resolved_library_payload` / report `hardware_knobs` metadata to include SoC/memory/periphery knobs when present

## 2. Report Schema and Breakdown Plumbing

- [x] 2.1 Extend report models to represent SRAM/HBM/fabric contributions explicitly (energy/latency and optionally bytes moved)
- [x] 2.2 Populate `buffers_add` and `control` breakdown fields from configured knobs (default 0 when unspecified)
- [x] 2.3 Ensure existing stage-level breakdown fields remain unchanged for compatibility
- [x] 2.4 Add unit tests that old configs still produce valid reports with all new fields defaulting to zero

## 3. KV-Cache Memory Hierarchy Model (Policy B)

- [x] 3.1 Implement KV traffic accounting in bytes for each phase (Draft / Verify-drafted / Verify-bonus), parameterized by `L_prompt`, `K`, `n_layers`, `d_model`, and within-burst step index
- [x] 3.2 Model on-chip SRAM speculative KV buffer reads/writes (within-burst tokens) and include its costs in the breakdown
- [x] 3.3 Model off-chip HBM KV reads for all verifier steps (no mismatch gating / no early stop) and include its costs in the breakdown
- [x] 3.4 Model HBM KV writes as commit-only using `E[a+1]` committed tokens per burst (discarded suffix steps do not write)
- [x] 3.5 Add INT8-per-head scale metadata bytes to SRAM/HBM traffic accounting (configurable `bytes_per_scale` and per-head scaling semantics)
- [x] 3.6 Add tests: KV/HBM read cost increases monotonically with `L_prompt`
- [x] 3.7 Add tests: KV traffic/cost increases with burst length `K`
- [x] 3.8 Add tests: HBM read energy/latency is independent of acceptance histogram (same `K`)
- [x] 3.9 Add tests: HBM write bytes match commit-only expectations for `P(a=0)=1.0` and `P(a=K)=1.0`

## 4. Analog Periphery + Buffers/Add + Control Accounting

- [x] 4.1 Derive periphery activity counts from existing analog activation-count anchors (e.g., outputs, scan steps, base reads)
- [x] 4.2 Add TIA (incl. programmable gain/`Rf`) per-activation energy/latency/area knobs and attribute them in the breakdown
- [x] 4.3 Add SNH + MUX overhead knobs and attribute them in the breakdown
- [x] 4.4 Add IO buffer/register overhead knobs and attribute them in the breakdown
- [x] 4.5 Add subarray switch/power-gating overhead knobs and attribute them in the breakdown
- [x] 4.6 Add explicit `buffers_add` cost hooks for `D_reg` buffering and `Final = D_reg + C` (and ADC-output combine) operations
- [x] 4.7 Add control/controller overhead hooks (per token and/or per burst) and attribute them in the breakdown
- [x] 4.8 Add tests: enabling non-zero periphery/buffers/control knobs increases totals while keeping backward-compatible defaults at zero

## 5. Schedule Mode and Verify-Setup Amortization

- [x] 5.1 Add a schedule knob that can report a layer-pipelined full-chip token period (latency/token) while preserving energy totals
- [x] 5.2 Add a verify-setup per-burst energy/latency term (charged once per verify burst, not per verifier step)
- [x] 5.3 Add tests: layer-pipelined schedule reports latency/token less than or equal to serialized schedule
- [x] 5.4 Add tests: verify-setup term scales with bursts (not with `K` linearly)

## 6. Examples, Docs, and End-to-End Validation

- [x] 6.1 Add a new example `hardware.yaml` demonstrating SRAM buffer + HBM KV + fabric knobs (policy B: commit-only writes)
- [x] 6.2 Add a new example `hardware.yaml` demonstrating non-zero analog periphery knobs (TIA/switches/buffers/SNH/MUX)
- [x] 6.3 Update `README.md` to document new `hardware.yaml` sections and the conservative “no early stop” assumption
- [x] 6.4 Add an end-to-end CLI test (or golden JSON snapshot) that exercises the new knobs and verifies report fields exist and are non-zero when expected

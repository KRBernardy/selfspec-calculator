## Context

`selfspec-calculator` is currently an analytical (closed-form) estimator that models:
- analog matmuls via `{arrays, DAC, ADC-draft, ADC-residual}` activation counts (knob-based mode), and
- digital stages (attention/softmax/elementwise/KV-cache) via abstract per-op coefficients.

This is sufficient for early “dual-ADC residual” experiments but misses many hardware blocks that appear in:
- **RAMwich** (traditional ReRAM CiM simulator): explicit periphery blocks such as MUX, sample-and-hold, input/output registers, and shift/add accumulation.
- **Song et al., Science 2024** SoC (and supplementary): SoC-level CPU/memory/interconnect (RISC‑V + on-chip memory + AXI + DMA), and per-core circuits (driving/control, I/O buffers, TIAs, write/verify path).
- **Roadmap.md**: explicit buffers/add/control overheads, speculative burst setup amortization, and a KV-cache system that must be capacity/bandwidth realistic (off-chip HBM-like), plus an on-chip SRAM buffer for speculation (policy B).

This change designs an SoC-level estimator hardware model that remains analytical and backward compatible with existing configs, while adding missing periphery + memory/fabric blocks and the project’s updated KV decisions:
- Signed weights use **offset `B`** (extra-row approach), not differential pairs.
- KV main store is **off-chip HBM-like**; speculative KV uses an **on-chip SRAM buffer** (policy B).
- Verifier does **not** early-stop on mismatch (wasted suffix compute still happens).
- HBM reads are accounted for all verifier steps; **HBM writes only commit committed tokens**.
- KV in HBM is **INT8 with per-head (static) scale** (common KV-quant practice); scale metadata overhead is modeled.

## Goals / Non-Goals

**Goals:**
- Extend the knob-based `hardware.yaml` schema additively (defaults preserve current behavior) to include:
  - analog periphery blocks aligned to RAMwich + Science SoC (TIA, switches, buffers/regs, SNH, mux, write/verify drivers),
  - explicit digital overhead blocks (`buffers_add`, `control`),
  - memory + fabric blocks (SRAM buffers + HBM + interconnect as bytes-moved).
- Add KV-cache modeling based on **bytes** (capacity, bandwidth, energy/byte, latency) rather than “MACs”.
- Keep the estimator analytical (closed-form counts) and keep existing stage-level outputs stable.

**Non-Goals:**
- Build a cycle/instruction-level simulator (RAMwich-style event simulation is out of scope).
- Model accuracy/acceptance internally (acceptance histogram remains an input).
- Implement “early-stop” optimizations (mismatch-gated compute/traffic) in v1; treat as a future feature.
- Fully circuit-accurate modeling of TIAs/ADC linearity/noise; this is a parametric estimator.

## Decisions

### 1) Backward-compatible `hardware.yaml` extensions (additive, default-zero)

**Decision:** Extend the knob-based config with new optional sections; set defaults so old `hardware.yaml` continues to validate and produces identical results when new sections are omitted.

**Rationale:** Users want to “just add fields” without breaking existing experiments.

**Alternatives considered:**
- Breaking schema rewrite → rejected (would disrupt existing runs).
- Separate “soc_hardware.yaml” file → rejected (splits configuration and complicates usage).

### 2) Model missing analog periphery via activation-count-derived proxies

**Decision:** Add periphery blocks as optional components whose activity counts are derived from existing analog counts (e.g., `base_reads`, `xbar_size`, ADC scan steps), rather than introducing a new simulator.

**Rationale:** RAMwich shows the important blocks (SNH/MUX/regs/accum) but we want a fast estimator. Many of these blocks’ activity naturally scales with “how many outputs are converted” or “how many mux scans happen”.

**Proposed counting anchors (per analog stage):**
- Let `base_reads = num_tiles * num_slices` (already used today).
- Let `outputs = base_reads * xbar_size` (matches ADC conversion count scale).
- Let `scan_steps = base_reads * num_columns_per_adc` (matches multiplexed ADC scan loops).

Then periphery blocks can key off:
- `TIA_samples ~ outputs` (TIA sits between bitline current and ADC sample).
- `SNH_samples ~ outputs` (sample each analog output before conversion).
- `MUX_selects ~ outputs` (one effective select per output element under column-mux scanning).
- `IO_buffer_reads/writes ~ outputs` (stage I/O buffering / register file traffic).

**Alternatives considered:**
- Explicit periphery topology per library (RAMwich-style) → more accurate but high maintenance.
- Lump all periphery into “digital_overhead_area” → too coarse; hides key levers.

### 3) Signed weights use offset `B` (Science approach), not differential pairs

**Decision:** Represent signed weights using the Science paper’s offset mapping (`G = K·A + B`) rather than two crossbars (pos/neg) per weight.

**Rationale:** This matches the project’s chosen “Science-based arc” and avoids 2× device count of differential pairs. Hardware implication: model an **extra row** (or equivalent mechanism) per subarray for offset `B`, plus any control/driver overhead to activate it.

**Alternatives considered:**
- Differential pairs (RAMwich-style pos/neg xbars) → simpler conceptually but doubles array area.
- Digital sign split outside array → adds digital overhead and undermines “true analog” intent.

### 4) KV-cache memory system: HBM main + SRAM speculative buffer (policy B)

**Decision:** Replace the current “KV-cache per-MAC cost” with a bytes-based memory model:
- **HBM-like off-chip** stores the full KV cache for long context.
- **On-chip SRAM buffer** stores speculative KV during Draft/Verify (policy B).
- **HBM reads** are charged for all verifier steps (no mismatch-gating).
- **HBM writes** only occur for **committed tokens** (accepted draft tokens + verifier token); wasted suffix steps do not commit writes.

**Rationale:** Capacity and bandwidth dominate KV-cache behavior; it cannot be captured by a fixed “energy per MAC”.

**Traffic model sketch (per token step, per layer):**
- HBM KV read bytes (base context): `2 * L_prompt * d_model * bytes_hbm_kv`
- SRAM KV read bytes (within-burst context): `2 * L_burst * d_model * bytes_sram_kv` where `L_burst` depends on step index (0..K)
- SRAM KV write bytes (produced K/V for the new token): `2 * d_model * bytes_sram_kv`
- HBM KV write bytes (commit only): `2 * d_model * bytes_hbm_kv` for committed tokens only

Where:
- `bytes_hbm_kv = 1` for INT8 payload + scale metadata amortization (see next decision),
- `bytes_sram_kv` is configurable (default follows HBM KV format unless overridden).

**Alternatives considered:**
- Keep KV as per-op cost → rejected (cannot represent bandwidth/capacity).
- Store full KV in on-chip SRAM → rejected (capacity infeasible for target context lengths).

### 5) KV quantization: INT8 with per-head static scale (normal practice)

**Decision:** Use INT8 KV representation in HBM with **per-(layer, head)** static scaling (calibration-style), and account for scale metadata bytes.

**Rationale:** KV-quant implementations commonly use per-channel/per-head scaling to reduce error while keeping metadata small and static (no per-token scale stream).

**Metadata modeling:** per token, per layer, store `scale_K` and `scale_V` for each head (or reuse one scale per head if specified). This adds:
- `metadata_bytes_per_token_per_layer = 2 * n_heads * bytes_per_scale`
and is charged to SRAM buffer writes and HBM committed writes as applicable.

**Alternatives considered:**
- Per-token dynamic scales → higher metadata bandwidth and estimator complexity.
- Full-precision KV in HBM → 2× bytes vs INT8 and likely unrealistic energy.

### 6) SoC fabric + control modeled as “bytes moved” + constant overheads

**Decision:** Model AXI/NoC/DMA effects in the estimator as:
- a bytes-moved energy/latency model for transfers between memory and compute, plus
- optional constant area/leakage blocks for CPU/control infrastructure.

**Rationale:** The Science SoC description includes RISC‑V + AXI + DMA; we want the estimator to expose “data movement is a first-class cost” without committing to a specific NoC topology.

**Alternatives considered:**
- Detailed router+NoC topology (RAMwich) → too detailed for an analytical estimator’s first SoC pass.

### 7) Scheduling and “setup latency amortization” is a separate knob

**Decision:** Keep the estimator analytical but introduce explicit knobs to avoid hard-coding a schedule:
- `soc.schedule` (e.g., `serialized` vs `pipelined_throughput`) to interpret latency for throughput reporting.
- `analog.verify_setup_{energy,latency}` to model Roadmap §2.3 “setup latency” paid once per verify burst (optional, default 0).

**Rationale:** The Roadmap argues burst verification reduces repeated setup costs. The existing estimator currently charges all costs per step; adding an explicit setup term allows modeling “paid once per burst” without rewriting the whole pipeline model.

**Alternatives considered:**
- Full token-by-token timeline simulation → out of scope.

## Risks / Trade-offs

- **[Schema growth]** `hardware.yaml` may become large → Mitigation: keep new sections optional, versioned, and default-zero; document minimal “required subset” for common runs.
- **[Double counting]** Periphery costs can be counted twice if tied to both analog and digital stages → Mitigation: define a single anchor per component (e.g., per-output conversion) and test invariants on scaling.
- **[Bandwidth vs compute overlap]** Adding `latency = bytes/bw` can overestimate if overlap exists → Mitigation: expose a simple overlap model later (e.g., `max(compute, memory)`).
- **[KV buffer precision uncertainty]** SRAM buffer precision may affect both bytes and dequant costs → Mitigation: make SRAM KV precision configurable with a clear default; keep dequant costs explicit.
- **[Mismatch-gating ambiguity]** Whether post-mismatch traffic can be gated depends on control timing → Mitigation: treat early-stop as a future capability and keep v1 conservative (no gating).

## Migration Plan

1. Add new optional Pydantic models to `HardwareConfig` for SoC/memory/periphery knobs with safe defaults.
2. Extend estimator accounting:
   - derive periphery activity counts from existing analog activation counts,
   - compute KV bytes (HBM+SRAM) per burst and map to energy/latency via config,
   - charge HBM writes only for committed tokens.
3. Extend report schema to include memory/fabric breakdowns while preserving existing stage breakdown fields.
4. Add example configs showing:
   - minimal SoC additions (just HBM KV),
   - fuller Science-aligned periphery knobs (TIA/switches/buffers).
5. Add unit tests for:
   - backward compatibility (old configs unchanged),
   - KV traffic scaling with `L_prompt`, `K`, and acceptance histogram.

## Open Questions

- What is the default SRAM speculative KV precision (`bytes_sram_kv`): match HBM INT8, or BF16/FP16 for better compute locality?
- Should HBM read traffic per burst use `L_prompt` only (base context) or incorporate the `+K` growth explicitly? (Roadmap uses `L_prompt+K` as a capacity bound.)
- How should we model “buffers + add” latency: additive, or overlapped with ADC scan latency?
- Do we need explicit leakage/static power for periphery (switch power-gating benefit), or keep v1 dynamic-only?
- How should `soc.schedule` affect reported `latency_ns_per_token` vs `throughput_tokens_per_s` semantics (token period vs end-to-end latency)?

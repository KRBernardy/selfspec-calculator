## Context

This repository currently contains a roadmap description of a “Performance Calculator (`selfspec-calculator`, Python)” (Roadmap.md §5.3), but no implementation. The intended calculator takes:

- Transformer model structure (`model.yaml`)
- Hardware/technology configuration (`hardware.yaml`)
- Runtime speculation statistics (e.g., burst length `K` and accepted-prefix-length histogram `P(a)` for `a ∈ [0, K]`)

and produces parametric PPA estimates (Power, Performance, Area) for a Dual-Mode residual analog architecture (Draft Mode vs Verify Mode), including draft-result reuse policy and prompt-length sweeps.

Key architectural assumptions to model (from Roadmap.md):

- Draft and Verify are **serialized** at the burst level (no overlap).
- Verify always performs `K+1` verifier steps per burst; it cannot early-stop on mismatch (wasted work is still paid).
- Draft-mode execution can be submodule-granular via a per-layer “draft precision policy” (some blocks may execute full precision even during Draft).
- Verify may optionally reuse stored draft results for drafted tokens (non-destructive reuse path) or re-read (full read).

## Goals / Non-Goals

**Goals:**
- Provide a Python library + CLI that loads `model.yaml`, `hardware.yaml`, and speculation stats, validates inputs, and produces a machine-readable report (JSON) with:
  - expected energy / token, latency / token, throughput (tokens/s), tokens/J
  - breakdowns by phase (Draft vs Verify) and by block/stage (e.g., QKV, attention matmuls, softmax, WO, FFN)
  - area totals and per-block contributions (as provided by the hardware model)
  - prompt-length sweep support (report metrics as a function of `L_prompt`)
- Encode the speculation accounting correctly (expected committed tokens per burst `E[a+1]`, fixed verifier work `K+1`, wasted verifier steps `E[K-a]`).
- Keep the cost model configurable: the calculator should be “policy-driven” by YAML parameters rather than hard-coded constants.

**Non-Goals:**
- Implement or integrate the functional accuracy simulator (`gpt-fast` modifications) in this repo.
- Provide circuit-accurate models for ADCs/crossbars; instead, accept parametric energy/latency/area models in `hardware.yaml`.
- Model all possible scheduling/pipelining variants; the initial implementation targets the “serialized Draft then Verify” assumption.
- Provide training, fine-tuning, or perplexity evaluation.

## Decisions

1. **Library-first with a thin CLI wrapper**
   - Implement the core estimator as importable Python modules (pure functions and typed models).
   - Provide a CLI entrypoint that:
     - loads YAMLs and stats files
     - runs the estimator for a prompt-length sweep
     - writes a JSON report to stdout or a file
   - Rationale: keeps logic testable and reusable; CLI remains stable while internals evolve.

2. **Explicit data model for inputs and outputs**
   - Define typed models for:
     - `ModelConfig` (layers, hidden size, heads, FFN type, etc.)
     - `HardwareConfig` (block cost models, ADC modes, reuse policy, KV-cache characteristics, etc.)
     - `SpeculationStats` (K and histogram/counts for accepted prefix lengths)
     - `Report` (metrics + breakdowns + sweep results)
   - Validation:
     - required fields, allowed enums (e.g., FFN type, reuse policy), and histogram integrity checks (keys in `[0..K]`, non-negative, non-empty).
   - Rationale: estimator correctness depends on clean contracts; errors should be actionable early.

3. **Cost accounting model: “per token step” → “per burst” → “per committed token”**
   - Implement cost in three layers:
     - **Per-step costs**: given `L_prompt`, compute per-layer stage costs for one token step under each mode:
       - Draft token step cost (may differ by block due to draft precision policy)
       - Verify token step cost for (a) drafted tokens and (b) bonus token
     - **Per-burst costs**:
       - Draft phase: `K` draft steps
       - Verify phase: `K+1` verify steps (with reuse behavior for drafted tokens)
     - **Expected per-committed-token metrics**:
       - `E[committed_tokens_per_burst] = E[a+1]`
       - `E[cost_per_committed_token] = cost_per_burst / E[a+1]`
   - Rationale: matches Roadmap semantics (fixed verifier work, acceptance-dependent committed output).

4. **Prompt-length sweep as a first-class report dimension**
   - Treat prompt length `L_prompt` as an input axis because attention digital costs scale with `L_prompt`.
   - Report:
     - per-`L_prompt` metrics (latency, throughput, energy/token, tokens/J)
     - optional “break-even” metrics vs a baseline configuration (e.g., `K=0` or “no speculation”).
   - Rationale: Roadmap requires reporting prompt-length sweep “at the start of generation”.

5. **Baseline comparison built into the estimator**
   - Provide an internal baseline mode that computes metrics for “no speculation” (e.g., `K=0` or equivalent full-precision-only policy), using the same hardware/model configs.
   - Report baseline metrics and deltas (ratio and absolute difference) per `L_prompt`.
   - Rationale: enables break-even prompt length outputs without external tooling.

## Risks / Trade-offs

- **[Model simplicity vs fidelity]** → Keep the YAML schema flexible (block-level plug-in cost models) and document assumptions in the report metadata.
- **[Config complexity]** → Start with a minimal required schema and add optional sections with sensible defaults; provide example configs.
- **[Ambiguous hardware formulas]** → Implement a “first-pass” cost model based on parameterized per-block energy/latency/area, and evolve toward crossbar tiling only when needed; keep open questions tracked.
- **[Speculation semantics mismatch]** → Encode burst accounting in unit-tested functions (expected committed tokens, wasted verify steps, reuse behavior) independent of hardware details.

## Migration Plan

- No migration required (new project). Additive introduction of the calculator library, configs, and CLI.

## Open Questions

- What is the initial minimum viable `hardware.yaml` schema: per-block constants only, or include crossbar tiling parameters from day one?
- Should input validation use a third-party model library (e.g., Pydantic) or remain dependency-light with dataclasses + manual checks?
- What baseline definition should be default (pure full-precision token-by-token, or `K=0` with identical verify modeling)?

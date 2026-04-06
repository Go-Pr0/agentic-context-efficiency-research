# Agentic Context Efficiency Research

Research into context management and oversight reliability in multi-model agentic code generation systems.

---

## Background

Modern agentic coding systems increasingly use a two-tier model architecture: a large, capable model acts as supervisor/architect, and a smaller, faster model handles implementation. The supervisor reads a representation of the codebase, produces a specification, and delegates. The executor generates code. The supervisor reviews a summary and approves.

This pattern is efficient. It's also structurally underspecified from a safety perspective.

---

## The Core Problem

### Oversight Gap in Multi-Model Delegation

When a supervisor model delegates code generation to an executor model and receives only a summary of the output — a diff, lint results, a status flag — it is approving work it has not read. In most current implementations, this is intentional: the supervisor delegates precisely to avoid reading every generated function body.

The safety assumption embedded in this architecture is that the executor model is too limited to produce meaningfully dangerous outputs. That assumption is eroding. As small models close the capability gap, the architectural pattern stays the same while the risk profile changes.

Concretely: the executor in this architecture is a less-restricted model operating on context the supervisor assembled but did not fully read. If that context has been poisoned — adversarial instructions embedded in dependency docstrings, comments, or type annotations pulled from the indexed codebase — the executor acts on instructions the supervisor never saw, and the supervisor approves output it cannot evaluate.

### Context Fidelity and Executor Reliability

A secondary finding from building this system: when an executor model receives a synthetically reconstructed representation of its working environment rather than the real structure, output quality degrades in systematic ways. Decorators are dropped. Conditional imports disappear. Class hierarchies are misrepresented. The model produces syntactically valid but behaviorally incorrect code because its model of the codebase is wrong.

This is directly relevant to safety: a model operating on inaccurate context about its environment makes worse decisions, not just less useful ones.

---

## System Architecture

The research platform is a working multi-agent code generation system with three layers:

**Codebase Index**
A static analysis layer (Python + TypeScript) that builds a tiered representation of a codebase. Tier 1 is a compressed structural overview: imports, class structure, function signatures, and one-liner docstrings. A 1,000-line file becomes roughly 10–15 lines. Tier 2 contains full call graphs, type definitions, and resolved dependency maps. The index is persistent and updates incrementally.

**Write Pipeline**
A code generation pipeline where a large model (supervisor) reads the tier 1 index, writes a DSL specification for the target function, and delegates to a smaller executor model. The pipeline assembles a context package for the executor: the real file structure from the index, the actual bodies of functions the target calls or is called by, and relevant type definitions. The executor generates an implementation. A validator checks syntax and runs a linter. The supervisor receives a status report.

The supervisor does not read the generated function body. It reads: OK/FAIL status, line count, lint warnings, and a structural diff.

**Multi-Agent Orchestration**
An orchestration layer managing multiple agent sessions with formal role constraints enforced through XML contracts. Agent types (architect, worker, auditor) are given different tool permissions and behavioral boundaries. No agent can exceed its defined role.

---

## Research Questions

1. **Capability threshold**: At what executor model capability level does the "too weak to be dangerous" assumption break down, measured against a practical taxonomy of harmful code patterns (credential exfiltration, authorization bypass, timing side-channels, resource exhaustion)?

2. **Context poisoning**: Can adversarial content embedded in codebase artifacts — docstrings, comments, type annotations — reliably steer an executor toward harmful implementations that pass lint validation and produce benign-looking diffs?

3. **Supervisor detection**: What is the empirical detection rate for harmful implementations when a supervisor model reviews only the status report format currently standard in these architectures (diff + lint + status flag)?

4. **Verification cost**: Can a lightweight verification pass — a third model positioned between executor output and supervisor approval — catch harmful implementations at a per-function cost low enough to remain practical at scale?

5. **Uncertainty signaling**: Current implementations include a boolean `uncertain` flag the executor can set when task context is insufficient. Can this signal be extended to carry a safety dimension (implementation confidence separate from task confidence) without unacceptable false positive rates?

---

## Benchmarking Methodology

### Context Compression

Tier 1 compression is measured against raw file content across a representative sample of Python and TypeScript files.

| File size | Raw tokens (est.) | Tier 1 tokens (est.) | Compression ratio |
|---|---|---|---|
| 200–500 lines | 1,500–3,500 | 40–80 | ~40x |
| 500–1,000 lines | 3,500–7,000 | 60–120 | ~60x |
| 1,000–2,000 lines | 7,000–14,000 | 80–160 | ~80x |

Context delivered to the executor per generation call is bounded: tier 1 overview + dependency bodies (capped at 80 lines each) + type definitions. This gives the executor accurate, targeted context rather than a full file dump or a synthetic reconstruction.

### Executor Reliability: Synthetic vs. Real Context

The system was previously built with a synthetic context approach: the pipeline reconstructed a pseudo-file from index metadata (re-stringified imports, rebuilt class shells, reconstructed method signatures) and sent that to the executor. This was replaced with real context (tier 1 from cache + actual dependency bodies from disk).

Failure modes documented under the synthetic approach:
- Decorator loss (decorators not stored in index metadata, dropped silently)
- Conditional import loss (only unconditional imports were re-stringified)
- Import truncation (capped at 30 entries, silently dropping the rest on large files)
- M-operation ambiguity (executor received both old and new function definitions with no explicit replacement instruction)
- Class hierarchy misreconstruction (parent classes were approximated, not read)

These are measurable. The benchmarking methodology for this dimension is: generate a fixed set of function modification tasks against a real codebase, run each under synthetic and real context conditions, and score output on: correct behavior (unit tests), correct integration (calls neighbors with correct signatures), no regressions (existing tests still pass).

### Oversight Gap

The oversight gap is measured as: given a set of function implementations ranging from benign to harmful, what fraction does a supervisor model correctly flag when reviewing only (a) a diff, (b) a diff + lint output, (c) a diff + lint + function signature, versus (d) the full function body?

This produces a detection rate curve against review depth — the core empirical output of the safety research.

---

## Current Status

The full system is working and in active development. This repository documents the research direction and methodology. Source code for the core research platform will be published as the work matures.

---

## Contact

GitHub: [Go-Pr0](https://github.com/Go-Pr0)

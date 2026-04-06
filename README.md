# Oversight Gaps in Multi-Model Code Generation

When a large, aligned model delegates code writing to a smaller executor model and only reviews a summary of the output, the alignment properties of the supervisor become irrelevant to what actually gets produced. This project studies that gap.

## Problem Statement

A common pattern in agentic code generation systems:

1. A supervisor model (e.g. Claude Opus) reads a compressed view of a codebase and decides what code should be written
2. It produces a specification — a natural language description of the desired function
3. A smaller, faster executor model (e.g. Gemini Flash) generates the actual implementation
4. The supervisor receives a status report: success/failure, lint output, a structural diff
5. The supervisor approves and moves on

The supervisor never reads the generated code. This is by design — it delegated specifically to avoid that work. But this means the supervisor's safety training, refusal behaviors, and judgment about what should or shouldn't be produced **are not applied to the output**.

The executor model:
- Has different (often weaker) safety training from a different provider
- Receives a rich context package assembled by the pipeline — dependency bodies, type definitions, docstrings — that the supervisor didn't carefully review
- Can be steered by adversarial content embedded in that context (comments, docstrings, type annotations from the indexed codebase)
- Produces output that passes lint and generates a clean diff, regardless of whether the implementation is safe

The supervisor sees `OK: validate_token (47 lines, 0 lint warnings)` and approves. The implementation could log credentials, bypass authorization, or introduce a timing side-channel. The diff looks normal. The lint passes. Nobody reviewed the body.

## Why This Matters Now

This pattern was safe when small models genuinely couldn't produce sophisticated harmful code. That assumption is breaking down. The executor models shipping today are meaningfully more capable than the ones these architectures were designed around. The architectural pattern is staying the same while the capability floor rises.

This is not a theoretical concern. We built a production system with this exact architecture and documented the oversight gap as it emerged during development.

## Research Platform

The research is conducted on a working multi-agent code generation system with three components:

**Tiered Codebase Index** — A tree-sitter-based static analysis engine that builds compressed, multi-level representations of Python and TypeScript codebases. Tier 1 is a structural overview (imports, signatures, one-liner docstrings). Tier 2 adds call graphs, type definitions, and dependency maps. The index is the supervisor's primary view of the codebase — and the first surface for context poisoning, since its content is derived from the source files being indexed.

**Write Pipeline** — The delegation layer. Takes a supervisor's DSL specification, assembles a context package for the executor (tier 1 overview + real dependency bodies from disk + type definitions), sends it to the executor model, validates the output, and returns a status report. The context assembly step is where the supervisor's specification meets real codebase content — content that may contain adversarial instructions the supervisor never saw.

**Multi-Agent Orchestration** — Formal role constraints enforced via XML contracts. Different agent types get different tool permissions. No agent can exceed its defined role. This is the existing safety boundary — the question is whether it's sufficient.

Source code for the indexing engine and renderer is included in `src/`. The write pipeline internals are not published yet as the system is in active development.

## Research Questions

**1. Supervisor detection rate under limited visibility**

Given a set of function implementations ranging from benign to harmful, what fraction does a supervisor model correctly flag when it can only see a diff + lint output vs. the full function body? This produces a detection curve that quantifies what the oversight gap actually costs.

**2. Context poisoning via codebase artifacts**

The executor receives dependency bodies, type definitions, and docstrings extracted from the indexed codebase. If a repository contains adversarial instructions embedded in comments or docstrings, these reach the executor as trusted context. Can this reliably steer an executor toward harmful implementations that still produce clean diffs?

**3. Verification pass feasibility**

Can a third model — positioned between executor output and supervisor approval — catch harmful implementations at practical cost? What does it need to see? Can it be smaller than the supervisor, or does detection require the same capability level that makes the supervisor expensive to begin with?

**4. Uncertainty signal redesign**

The current system includes an `uncertain` boolean the executor can set when context is insufficient. This signals task confidence, not safety confidence. A model producing deliberately harmful output would not set `uncertain=True`. Can this signal be extended to carry a safety dimension without unacceptable false positive rates?

## What's In This Repo

```
src/abstract_engine/
  models.py          — Data structures for the codebase index
  renderer.py        — Tier 1/Tier 2 compression algorithms
  call_graph.py      — Cross-file call resolution and reverse index

examples/
  tier1_output.md    — Real tier 1 output from indexing the engine itself
  context_package.md — What the executor actually receives for a single function

docs/
  architecture.md    — System architecture and data flow
  threat_model.md    — Attack surfaces in the delegation pipeline
```

## Contact

GitHub: [Go-Pr0](https://github.com/Go-Pr0)

# Benchmarking Methodology

## Context Fidelity Experiment

### Setup

A fixed benchmark suite of function modification tasks is run against a real Python codebase. Each task is categorized by:

- **Complexity**: simple (no dependencies), medium (1–3 dependencies), complex (4+ dependencies or cross-file)
- **Operation type**: add new function (`+`), modify existing (`M`)
- **File size**: small (<300 lines), medium (300–800 lines), large (800+ lines)

### Conditions

Each task is run under two conditions:

**Synthetic context** — executor receives a reconstructed pseudo-file assembled from index metadata: re-stringified imports (capped), rebuilt class shells, reconstructed method signatures.

**Real context** — executor receives tier 1 text (actual compressed view cached at index time) plus actual dependency bodies extracted from disk.

### Scoring

Each generated function is scored on three dimensions:

1. **Behavioral correctness** — does it pass the existing unit test suite for that function?
2. **Integration correctness** — does it call its dependencies with the correct signatures and handle their return types correctly?
3. **Regression absence** — do unrelated tests still pass after the change is applied?

### Expected Output

A 2×3×2 results table (condition × complexity × operation type) showing pass rates on each scoring dimension. The hypothesis is that real context substantially outperforms synthetic context on integration correctness, with the gap widening at higher complexity.

---

## Oversight Gap Experiment

### Setup

A taxonomy of function implementations ranging from benign to harmful:

- **Level 0**: Correct, benign implementation
- **Level 1**: Subtly incorrect (off-by-one, wrong edge case handling)
- **Level 2**: Behavioral deviation (logs more than specified, returns cached stale data)
- **Level 3**: Security-relevant deviation (credential logging, timing side-channel)
- **Level 4**: Explicit harmful behavior (authorization bypass, data exfiltration hook)

Each harmful implementation is written to pass lint validation and produce a structurally plausible diff.

### Conditions

A supervisor model reviews each implementation under four review depths:

1. **Diff only** — the structural diff showing added/removed lines
2. **Diff + lint** — diff plus linter output (warnings, errors)
3. **Diff + lint + signature** — above plus the function's type signature and docstring
4. **Full body** — the complete generated function

### Scoring

For each review depth and harm level: what fraction of harmful implementations does the supervisor correctly flag? What is the false positive rate on benign implementations?

### Expected Output

A detection rate matrix (review depth × harm level) establishing the empirical cost of the oversight gap — how much visibility the supervisor needs to maintain reliable detection at each harm level.

---

## Verification Pass Experiment

A third model is inserted between executor output and supervisor approval. It reads the full generated function body and the original specification, and outputs a risk signal: safe / uncertain / flag.

The experiment measures:
- Detection rate vs. the oversight gap baseline
- False positive rate on benign implementations
- Per-function latency and token cost added to the pipeline
- Whether the verifier can be a smaller, cheaper model than the supervisor while maintaining detection parity

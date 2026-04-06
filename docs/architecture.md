# System Architecture

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Codebase (Python / TypeScript source files)                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ tree-sitter parsing
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Abstract Index                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Tier 1 views │  │ Call graphs  │  │ Type definitions   │    │
│  │ (compressed) │  │ (resolved)   │  │ (from source)      │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ read by supervisor
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Supervisor Model (Claude Opus)                                 │
│  - Reads tier 1 compressed views                                │
│  - Decides what to modify or add                                │
│  - Writes DSL specification                                     │
│  - Reviews status reports (does NOT read generated code)        │
└──────────────────────┬──────────────────────────────────────────┘
                       │ DSL spec
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Write Pipeline                                                 │
│                                                                 │
│  1. Parse spec (DSL or skeleton)                                │
│  2. Look up target function in index                            │
│  3. Assemble context package:                                   │
│     - Tier 1 overview of the file                               │
│     - Current function body (for modifications)                 │
│     - Dependency bodies (callees + callers, from disk)          │
│     - Type definitions                                          │
│     - Docstrings from dependencies                ◄── attack    │
│  4. Send to executor                                  surface   │
│  5. Validate output (syntax + lint)                             │
│  6. Apply to file                                               │
│  7. Return status report to supervisor                          │
│                                                                 │
│  ┌─────────────────────────────────────────┐                    │
│  │  Context Package (what executor sees)   │                    │
│  │  - File structure (from tier 1 cache)   │                    │
│  │  - Function bodies (from disk)          │                    │
│  │  - Type shapes (from index)             │                    │
│  │  - Docstrings (from source)             │◄── supervisor      │
│  │  - Spec + instruction                   │    never reads     │
│  └─────────────────────────────────────────┘    this package    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ context package
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Executor Model (Gemini Flash)                                  │
│  - Receives full context package                                │
│  - Generates function implementation                            │
│  - Returns code + imports + uncertainty flag                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ generated code
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Validator                                                      │
│  - AST parse check                                              │
│  - Linter (ruff)                                                │
│  - NO semantic/safety analysis                   ◄── gap        │
└──────────────────────┬──────────────────────────────────────────┘
                       │ status report (OK/FAIL, lint, diff)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Supervisor (again)                                             │
│  - Sees: OK/FAIL, line count, lint warnings, diff               │
│  - Does NOT see: function body, context package                 │
│  - Approves and continues                        ◄── gap        │
└─────────────────────────────────────────────────────────────────┘
```

## Tier 1 Compression

The tier 1 view is the supervisor's primary interface to the codebase. It compresses a full source file into a structural summary.

What's preserved:
- Import statements (compressed to a single line)
- Module-level constants
- Function signatures with parameter types and return types
- One-liner docstring summaries
- Class structure with attributes and method signatures
- Line ranges for every entity

What's dropped:
- Function bodies
- Full docstrings
- Comments
- Implementation details

A 1,000-line file becomes ~10-15 lines of tier 1. The supervisor reads these to understand the codebase and decide what to change. It does not read function bodies at any point in the normal workflow.

## Context Package Assembly

When the supervisor issues a write specification, the pipeline assembles a context package for the executor. This is the most safety-critical step because it determines what the executor model sees.

The package contains:
1. **Tier 1 overview** — the same compressed view the supervisor read, cached from the index
2. **Current function body** — for modify operations, the full source of the function being replaced (read from disk)
3. **Dependency bodies** — the full source of functions the target calls or is called by (read from disk, capped at 80 lines each)
4. **Type definitions** — type shapes referenced in the spec or description
5. **Reference notes** — any metadata from the spec's `refs:` field

Items 2-5 are read from the actual codebase on disk. If the codebase contains adversarial content in comments, docstrings, or function bodies, that content enters the executor's context window as trusted input.

## Role Constraints

The multi-agent orchestration layer enforces role separation through XML contracts:

| Agent Type | Can Write Code | Tools Available | Review Depth |
|---|---|---|---|
| Architect/Supervisor | No (delegates) | Index read, spec write | Tier 1 + status reports |
| Executor | Yes (generates) | None (receives context, returns code) | Full context package |
| Worker | Yes (direct edit) | Read, Edit, Write, Bash | Full file content |
| Auditor | No | Read, Grep, Glob, Bash | Full file content |

The executor has no tools — it receives a prompt and returns structured output. This means it cannot independently verify its context or refuse based on tool-level restrictions. Its safety behavior depends entirely on its own alignment training.

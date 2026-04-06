# Tier 1 Output Examples

Real output from running the abstract engine against its own source code. These demonstrate the compression ratios and what the supervisor model actually sees when reading a codebase.

## renderer.py — 388 lines → 7 tier 1 lines (55x compression)

```
src/abstract_engine/renderer.py [5fn, 388L]: Pure rendering functions for Tier 1 and Tier 2 abstract views.
# imports: re | abstract_engine.models: AttributeEntry,CallEntry,ClassEntry,FileEntry,FunctionEntry,ImportEntry
  render_tier1_function(func:FunctionEntry, is_method:bool=False)->str: Render a single function as a Tier 1 one-liner with line range.  L75-92
  render_tier1_class(ClassEntry)->str: Render a class with its methods for Tier 1.  L114-172
  render_tier1_file(file_entry:FileEntry)->str: Render a complete file-level Tier 1 view.  L242-293
  render_tier2_function(func:FunctionEntry)->str: Render enriched Tier 2 detail for a function.  L311-374
  render_all_tier1(files:dict[str, FileEntry])->str: Render the full project Tier 1 view across all files.  L377-388
```

The supervisor sees: 5 public functions, their signatures, what they do (one line each), and where they are. It does not see any implementation.

## models.py — 446 lines → 14 tier 1 lines (32x compression)

```
src/abstract_engine/models.py [22fn, 446L]: Data models for the Abstract Representation Engine.
# imports: dataclasses: dataclass,field | typing: Any
# consts: SCHEMA_VERSION=1
  ParameterEntry{name:str, type_annotation:str | None=None, has_default:bool=False, default_value:str | None=None, is_variadic:bool=False, is_keyword_variadic:bool=False}: A single function/method parameter.
  CallEntry{callee_name:str, resolved_file:str | None=None, resolved_qualified_name:str | None=None, is_external:bool=False, call_count:int=1}: A function call made from within a function body.
  CallerEntry{caller_name:str, caller_file:str, caller_qualified_name:str | None=None}: A reference to a function that calls this one.
  ImportEntry{module:str, names:list[str]=field(default_factory=list), is_from_import:bool=False, is_wildcard:bool=False, alias:str | None=None}: An import statement in a file.
  ConstantEntry{name:str, value:str | None=None, type_annotation:str | None=None}: A module-level constant (ALL_CAPS pattern).
  FunctionEntry{name:str, qualified_name:str="", ...}: A function or method extracted from source code.
  AttributeEntry{name:str, type_annotation:str | None=None, ...}: A class or instance attribute.
  ClassEntry{name:str, file_path:str="", ...}: A class definition extracted from source code.
  TypeEntry{name:str, kind:str="", ...}: A TypeScript type definition (interface, type alias, or enum).
  FunctionLocator{file_path:str, class_name:str | None=None, ...}: Lightweight reference to a function's location for cross-file lookup.
  FileEntry{relative_path:str, language:str="", ...}: A single source file in the abstract index.
```

All 11 dataclasses with their fields visible at a glance. The supervisor knows the exact shape of every data structure without reading 446 lines of serialization boilerplate.

## pipeline.py — 1,457 lines → 12 tier 1 lines (121x compression)

```
src/abstract_fs_server/write_pipeline/pipeline.py [3fn, 1457L]: Write intent pipeline orchestrator.
# imports: asyncio, logging, os, re | collections: defaultdict,deque | dataclasses: dataclass,field | ...
# consts: _STATUS_OK="OK", _STATUS_FAILED="FAILED", _STATUS_SKIPPED="SKIPPED"
  collect_cross_file_deps_from_skeleton(skeleton_content:str, index:object, project_root:str)->list[tuple[str, str]]: Resolve cross-file dependency bodies for skeleton-fill from import statements.  L279-336
  _ChangeRef{file_path:str, change:FunctionChange, flat_idx:int}: Reference to a single FunctionChange within the ParsedSpec.
  class WritePipeline: Orchestrates the end-to-end write intent pipeline.
    async execute(spec_text:str)->str: Execute the full write pipeline.  L350-1147
  _ChangeStatus{success:bool, message:str, warnings:list[str], soft_failure:bool=False, generated_code:str | None=None}: Tracks the outcome of a single change through the pipeline.
  _ApplyPlanEntry{action:str, generated_code:str | None, ...}: A change that passed pre-write validation and is ready to apply.
  _FileResult{success:bool, error:str | None=None}: Tracks the outcome of applying changes to a single file.
```

1,457 lines of async pipeline orchestration compressed to 12 lines. The supervisor sees the pipeline's public interface — one main class with one main method — without any of the implementation complexity.

## call_graph.py — 197 lines → 4 tier 1 lines (49x compression)

```
src/abstract_engine/call_graph.py [2fn, 197L]: Call graph resolution and called_by index building.
# imports: abstract_engine.models: CallerEntry,FileEntry,FunctionLocator
  build_function_lookup(files:dict[str, FileEntry])->dict[str, list[FunctionLocator]]: Build the cross-file function name lookup index.  L12-56
  resolve_call_graph(files:dict[str, FileEntry], function_lookup:dict[str, list[FunctionLocator]])->None: Resolve call names to file paths and build called_by reverse index.  L74-197
```

## Compression Summary

| File | Raw Lines | Tier 1 Lines | Ratio |
|---|---|---|---|
| renderer.py | 388 | 7 | 55x |
| models.py | 446 | 14 | 32x |
| pipeline.py | 1,457 | 12 | 121x |
| call_graph.py | 197 | 4 | 49x |

Average compression across these files: ~64x. The supervisor operates on roughly 1.5% of the raw source.

## Safety Implication

This compression is efficient but it means the supervisor's entire understanding of the codebase is derived from these summaries. It does not read function bodies. When it decides what code should be written, that decision is based on signatures and one-liner docstrings — not on what functions actually do.

When the executor generates code and the supervisor reviews only a diff, neither model has read the full picture: the supervisor read structure, the executor read context, and nobody read the final output with full understanding of both.

"""Pure rendering functions for Tier 1 and Tier 2 abstract views.

These functions take model objects and return formatted strings. They have no
side effects and perform no file I/O. All rendering rules follow the spec in
the ticket's render_format_examples section.
"""

from __future__ import annotations

import re

from abstract_engine.models import (
    AttributeEntry,
    CallEntry,
    ClassEntry,
    FileEntry,
    FunctionEntry,
    ImportEntry,
)



def _format_param_types(
    parameters: list,
    is_method: bool = False,
) -> str:
    """Format parameter types for Tier 1 display.

    Rules:
    - Types only (not names) unless the name carries semantic meaning
    - Remove 'self' and 'cls' from method params
    - Show param name when it adds semantic clarity (heuristic: non-obvious names)
    """
    parts: list[str] = []
    for param in parameters:
        # Skip self/cls for methods
        if is_method and param.name in ("self", "cls"):
            continue

        # Skip *args and **kwargs variadic markers in the type-only view
        if param.is_variadic or param.is_keyword_variadic:
            prefix = "*" if param.is_variadic else "**"
            if param.type_annotation:
                parts.append(f"{prefix}{param.name}:{param.type_annotation}")
            else:
                parts.append(f"{prefix}{param.name}")
            continue

        type_str = param.type_annotation or "?"

        # Include param name when it carries semantic meaning.
        # Heuristic: include name unless it's a single generic word that
        # duplicates the type (e.g., 'text:str' is useful, 'str' alone is not).
        if param.name and param.name not in ("self", "cls"):
            display = f"{param.name}:{type_str}"
        else:
            display = type_str

        if param.has_default and param.default_value is not None:
            display += f"={param.default_value}"

        parts.append(display)

    return ", ".join(parts)


def _one_liner(func: FunctionEntry) -> str:
    """Truncate and clean docstring_first_line for Tier 1 display."""
    text = (func.docstring_first_line or "").strip().strip("\"'").strip()
    if len(text) > 100:
        text = text[:97] + "..."
    return text


def render_tier1_function(
    func: FunctionEntry,
    is_method: bool = False,
) -> str:
    """Render a single function as a Tier 1 one-liner with line range.

    Format: function_name(param_types)->return_type: one-liner  L42-67
    Async functions are prefixed with 'async'.
    """
    prefix = "async " if func.is_async else ""
    params = _format_param_types(func.parameters, is_method=is_method)
    return_type = func.return_type or "None"
    range_str = f"  L{func.start_line}-{func.end_line}" if func.start_line else ""

    if func.docstring_first_line:
        one_liner = _one_liner(func)
        return f"{prefix}{func.name}({params})->{return_type}: {one_liner}{range_str}"
    return f"{prefix}{func.name}({params})->{return_type}{range_str}"


def _render_dataclass_tier1(cls: ClassEntry) -> str:
    """Render a dataclass as a type definition in Tier 1.

    Format: ClassName{field:type, field:type=default}
    """
    fields: list[str] = []
    # Use instance_attributes for dataclass fields
    attrs = cls.instance_attributes or cls.class_attributes
    for attr in attrs:
        type_str = attr.type_annotation or "?"
        entry = f"{attr.name}:{type_str}"
        if attr.has_default and attr.default_value is not None:
            entry += f"={attr.default_value}"
        fields.append(entry)

    field_str = ", ".join(fields)
    return f"{cls.name}{{{field_str}}}"


def render_tier1_class(cls: ClassEntry) -> str:
    """Render a class with its methods for Tier 1.

    Dataclasses are rendered as type definitions: ClassName{field:type, ...}
    Protocol classes are annotated with [Protocol] suffix.
    Regular classes show their public methods indented.
    """
    lines: list[str] = []

    # Dataclass rendering
    if cls.is_dataclass:
        dc_line = _render_dataclass_tier1(cls)
        if cls.docstring_first_line:
            dc_line += f": {cls.docstring_first_line}"
        lines.append(f"  {dc_line}")
        return "\n".join(lines)

    # Regular class header
    suffix = ""
    if cls.is_protocol:
        suffix = " [Protocol]"
    elif cls.is_abstract:
        suffix = " [Abstract]"

    all_attrs = cls.class_attributes + cls.instance_attributes
    if all_attrs:
        cap = 8
        shown_attrs = all_attrs[:cap]
        overflow = len(all_attrs) - cap
        attr_parts = []
        for attr in shown_attrs:
            entry = attr.name
            if attr.type_annotation:
                entry += f":{attr.type_annotation}"
            if attr.has_default and attr.default_value is not None:
                entry += f"={attr.default_value}"
            attr_parts.append(entry)
        if overflow > 0:
            attr_parts.append(f"+{overflow} more")
        attrs_str = "{" + ", ".join(attr_parts) + "}"
    else:
        attrs_str = ""

    header = f"  class {cls.name}{attrs_str}{suffix}"
    if cls.docstring_first_line:
        header += f": {cls.docstring_first_line}"
    lines.append(header)

    # Methods — public non-dunder only; dunders are implementation detail
    # and __init__ params are already captured in the inline {attrs}
    for method in cls.methods.values():
        if method.visibility != "public":
            continue
        if method.name.startswith("__") and method.name.endswith("__"):
            continue
        method_line = render_tier1_function(method, is_method=True)
        lines.append(f"    {method_line}")

    return "\n".join(lines)


def _count_public_functions(file_entry: FileEntry) -> int:
    """Count total public functions + methods in a file."""
    count = 0
    for func in file_entry.functions.values():
        if func.visibility == "public":
            count += 1
    for cls in file_entry.classes.values():
        for method in cls.methods.values():
            if method.visibility == "public":
                count += 1
    return count


def _file_one_liner(file_entry: FileEntry) -> str:
    """Get the one-liner for a file.

    Uses module_docstring if available, otherwise expands the filename.
    """
    if file_entry.module_docstring:
        text = file_entry.module_docstring.strip().strip("\"'").strip()
        if len(text) > 100:
            text = text[:97] + "..."
        return text

    # Derive from filename — expand snake_case to words
    name = file_entry.relative_path.rsplit("/", 1)[-1]
    name = re.sub(r"\.\w+$", "", name)  # Remove extension
    words = name.strip("_").split("_")
    return " ".join(words).capitalize() if words else name


def _render_imports_compressed(imports: list[ImportEntry]) -> str:
    """Render the import list as a single compact line.

    Format: # imports: logging, os | fastapi: Request,Response | .models: Session,User
    Plain 'import X' names come first, then from-imports grouped by module.
    Wildcard imports are shown as module: *.
    """
    plain: list[str] = []
    from_imports: dict[str, list[str]] = {}

    for entry in imports:
        if not entry.is_from_import:
            name = entry.alias if entry.alias else entry.module
            plain.append(name)
        else:
            mod = entry.module
            if entry.is_wildcard:
                from_imports.setdefault(mod, []).append("*")
            else:
                names = entry.names
                if entry.alias and len(names) == 1:
                    names = [f"{names[0]} as {entry.alias}"]
                from_imports.setdefault(mod, []).extend(names)

    segments: list[str] = []
    if plain:
        segments.append(", ".join(plain))
    for mod, names in from_imports.items():
        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped = [n for n in names if not (n in seen or seen.add(n))]  # type: ignore[func-returns-value]
        segments.append(f"{mod}: {','.join(deduped)}")

    return "# imports: " + " | ".join(segments)


def render_tier1_file(file_entry: FileEntry) -> str:
    """Render a complete file-level Tier 1 view.

    Format:
      relative/path/to/file.py [Nfn, NL]: one-liner module purpose
        function_name(param_types)->return_type: one-liner purpose
        class ClassName: ...
    """
    # Handle parse errors
    if file_entry.parse_error:
        detail = file_entry.parse_error_detail or "Could not parse file"
        return f"{file_entry.relative_path} [PARSE ERROR]: {detail}"

    fn_count = _count_public_functions(file_entry)
    one_liner = _file_one_liner(file_entry)
    header = (
        f"{file_entry.relative_path} "
        f"[{fn_count}fn, {file_entry.line_count}L]: "
        f"{one_liner}"
    )

    lines: list[str] = [header]

    # Compact imports line (one line, no matter how many imports)
    if file_entry.imports:
        lines.append(_render_imports_compressed(file_entry.imports))

    # Constants line — only when the file defines module-level constants
    if file_entry.constants:
        const_items = list(file_entry.constants.items())
        cap = 8
        shown = const_items[:cap]
        overflow = len(const_items) - cap
        const_parts = []
        for name, const in shown:
            entry = name
            if const.value is not None:
                entry += f"={const.value}"
            const_parts.append(entry)
        suffix = f", +{overflow} more" if overflow > 0 else ""
        lines.append("# consts: " + ", ".join(const_parts) + suffix)

    # Top-level functions — public only; private are implementation details
    for func in file_entry.functions.values():
        if func.visibility == "public":
            lines.append(f"  {render_tier1_function(func)}")

    # Classes
    for cls in file_entry.classes.values():
        lines.append(render_tier1_class(cls))

    return "\n".join(lines)


def _format_call_for_tier2(call: CallEntry) -> str:
    """Format a single call entry for Tier 2 display.

    Format: callee_name(signature) [module_path]
    """
    parts = call.callee_name
    if call.resolved_qualified_name and call.resolved_qualified_name != call.callee_name:
        parts = call.resolved_qualified_name
    if call.resolved_file:
        parts += f" [{call.resolved_file}]"
    elif call.is_external:
        parts += " [external]"
    return parts


def render_tier2_function(func: FunctionEntry) -> str:
    """Render enriched Tier 2 detail for a function.

    Includes: full signature with param names, docstring, calls, used_by,
    raises, async flag, and decorators.
    """
    # Full signature line
    params_parts: list[str] = []
    for param in func.parameters:
        if param.name in ("self", "cls"):
            continue
        type_str = param.type_annotation or "?"
        entry = f"{param.name}:{type_str}"
        if param.has_default and param.default_value is not None:
            entry += f"={param.default_value}"
        if param.is_variadic:
            entry = f"*{entry}"
        elif param.is_keyword_variadic:
            entry = f"**{entry}"
        params_parts.append(entry)

    return_type = func.return_type or "None"
    sig_line = f"{func.qualified_name or func.name}({', '.join(params_parts)}) -> {return_type}"

    lines: list[str] = [sig_line]

    # Full docstring preferred in enriched view; fall back to first line
    docstring = func.docstring_full or func.docstring_first_line
    if docstring:
        doc_text = docstring.strip().strip("\"'").strip()
        if len(doc_text) > 300:
            doc_text = doc_text[:297] + "..."
        lines.append(f'  "{doc_text}"')

    # Calls
    if func.calls:
        call_strs = [_format_call_for_tier2(c) for c in func.calls]
        lines.append(f"  calls: {', '.join(call_strs)}")

    # Used by
    if func.called_by:
        caller_strs: list[str] = []
        for caller in func.called_by:
            entry = caller.caller_qualified_name or caller.caller_name
            if caller.caller_file:
                entry += f" [{caller.caller_file}]"
            caller_strs.append(entry)
        lines.append(f"  used_by: {', '.join(caller_strs)}")

    # Raises
    if func.raises:
        lines.append(f"  raises: {', '.join(func.raises)}")

    # Async flag
    lines.append(f"  async: {'yes' if func.is_async else 'no'}")

    # Decorators
    if func.decorators:
        dec_str = ", ".join(f"@{d}" for d in func.decorators)
        lines.append(f"  decorators: {dec_str}")
    else:
        lines.append("  decorators: none")

    return "\n".join(lines)


def render_all_tier1(files: dict[str, FileEntry]) -> str:
    """Render the full project Tier 1 view across all files.

    Files are sorted by relative path for deterministic output.
    Each file is separated by a blank line.
    """
    blocks: list[str] = []
    for path in sorted(files.keys()):
        file_entry = files[path]
        blocks.append(render_tier1_file(file_entry))

    return "\n\n".join(blocks)

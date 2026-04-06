"""Call graph resolution and called_by index building.

Second pass over all FunctionEntry objects to resolve call names to file paths
and build the reverse caller index. Runs after all files have been parsed.
"""

from __future__ import annotations

from abstract_engine.models import CallerEntry, FileEntry, FunctionLocator


def build_function_lookup(
    files: dict[str, FileEntry],
) -> dict[str, list[FunctionLocator]]:
    """Build the cross-file function name lookup index.

    Scans all files, including top-level functions and class methods, and
    returns a mapping from function name to all locations where that name
    is defined. Multiple entries occur when the same name exists in different
    files or classes.

    Args:
        files: All parsed FileEntry objects keyed by relative path.

    Returns:
        A dict mapping function names to lists of FunctionLocator objects.
    """
    lookup: dict[str, list[FunctionLocator]] = {}

    for file_path, file_entry in files.items():
        # Top-level functions
        for func_name, func_entry in file_entry.functions.items():
            locator = FunctionLocator(
                file_path=file_path,
                class_name=None,
                function_name=func_name,
                qualified_name=func_entry.qualified_name or func_name,
            )
            if func_name not in lookup:
                lookup[func_name] = []
            lookup[func_name].append(locator)

        # Class methods
        for class_name, class_entry in file_entry.classes.items():
            for method_name, method_entry in class_entry.methods.items():
                locator = FunctionLocator(
                    file_path=file_path,
                    class_name=class_name,
                    function_name=method_name,
                    qualified_name=method_entry.qualified_name or f"{class_name}.{method_name}",
                )
                if method_name not in lookup:
                    lookup[method_name] = []
                lookup[method_name].append(locator)

    return lookup


def _get_imported_module_names(file_entry: FileEntry) -> set[str]:
    """Collect all module aliases and imported names from a file's imports."""
    names: set[str] = set()
    for imp in file_entry.imports:
        if imp.alias:
            names.add(imp.alias)
        elif imp.module:
            # For 'import foo.bar', the usable name is 'foo'
            top = imp.module.split(".")[0]
            names.add(top)
        for name in imp.names:
            names.add(name)
    return names


def resolve_call_graph(
    files: dict[str, FileEntry],
    function_lookup: dict[str, list[FunctionLocator]],
) -> None:
    """Resolve call names to file paths and build called_by reverse index.

    Mutates FunctionEntry.calls in place — sets resolved_file,
    resolved_qualified_name, and is_external on each CallEntry. Also
    populates FunctionEntry.called_by on the target functions.

    Resolution priority:
    1. Same file (prefer local definitions)
    2. Imported modules (names that match imported symbols)
    3. Any match across all files

    After resolution, re-renders tier2_text for all affected functions.

    Args:
        files: All parsed FileEntry objects keyed by relative path.
        function_lookup: Cross-file function name index for resolution.
    """
    # Import renderer here to avoid circular imports at module load time
    from abstract_engine.renderer import render_tier2_function  # noqa: PLC0415

    # Clear all existing called_by entries before rebuilding
    for file_entry in files.values():
        for func in file_entry.functions.values():
            func.called_by = []
        for cls in file_entry.classes.values():
            for method in cls.methods.values():
                method.called_by = []

    # For each caller function, resolve its calls
    for caller_file_path, file_entry in files.items():
        imported_names = _get_imported_module_names(file_entry)

        all_caller_funcs = list(file_entry.functions.items())
        for cls in file_entry.classes.values():
            for method_name, method in cls.methods.items():
                all_caller_funcs.append((method_name, method))

        for _func_name, caller_func in all_caller_funcs:
            for call in caller_func.calls:
                # Extract the base call name (strip object prefix like 'self.foo' -> 'foo')
                raw_name = call.callee_name
                # Handle attribute calls: 'obj.method' -> look up 'method'
                if "." in raw_name:
                    parts = raw_name.split(".")
                    base_name = parts[-1]
                    obj_prefix = ".".join(parts[:-1])
                else:
                    base_name = raw_name
                    obj_prefix = ""

                locators = function_lookup.get(base_name, [])

                resolved_locator: FunctionLocator | None = None

                if locators:
                    # Priority 1: same file
                    same_file = [loc for loc in locators if loc.file_path == caller_file_path]
                    if same_file:
                        resolved_locator = same_file[0]
                    else:
                        # Priority 2: imported names
                        # If obj_prefix is an imported module name, prefer that file
                        if obj_prefix:
                            imported_match = [
                                loc for loc in locators
                                if obj_prefix in imported_names
                            ]
                            if imported_match:
                                resolved_locator = imported_match[0]

                        if resolved_locator is None:
                            # Priority 3: any match
                            resolved_locator = locators[0]

                if resolved_locator is not None:
                    call.resolved_file = resolved_locator.file_path
                    call.resolved_qualified_name = resolved_locator.qualified_name
                    call.is_external = False

                    # Build reverse index: add caller to the callee's called_by
                    callee_file = files.get(resolved_locator.file_path)
                    if callee_file is not None:
                        caller_entry = CallerEntry(
                            caller_name=caller_func.name,
                            caller_file=caller_file_path,
                            caller_qualified_name=caller_func.qualified_name,
                        )
                        # Find the callee function entry
                        if resolved_locator.class_name is not None:
                            callee_class = callee_file.classes.get(resolved_locator.class_name)
                            if callee_class is not None:
                                callee_func = callee_class.methods.get(resolved_locator.function_name)
                                if callee_func is not None:
                                    # Avoid duplicate entries
                                    existing = {
                                        (c.caller_name, c.caller_file)
                                        for c in callee_func.called_by
                                    }
                                    if (caller_func.name, caller_file_path) not in existing:
                                        callee_func.called_by.append(caller_entry)
                        else:
                            callee_func = callee_file.functions.get(resolved_locator.function_name)
                            if callee_func is not None:
                                existing = {
                                    (c.caller_name, c.caller_file)
                                    for c in callee_func.called_by
                                }
                                if (caller_func.name, caller_file_path) not in existing:
                                    callee_func.called_by.append(caller_entry)
                else:
                    # Could not resolve — mark as external
                    call.is_external = True

    # Re-render tier2_text for all functions after resolution
    for file_entry in files.values():
        for func in file_entry.functions.values():
            func.tier2_text = render_tier2_function(func)
        for cls in file_entry.classes.values():
            for method in cls.methods.values():
                method.tier2_text = render_tier2_function(method)

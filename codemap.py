#!/usr/bin/env python3
"""codemap - Intelligent Codebase Map for AI Agents.

Zero-dependency tool that generates a structured, token-efficient codebase
summary designed for AI context windows. Instead of dumping every file
(like repomix/code2prompt), codemap produces an INDEX — the minimum context
needed to understand a project's structure and public API.

Typical output: <5000 tokens for a medium project (vs 100k+ for a full dump).

Usage:
    codemap                           # Map current directory
    codemap /path/to/project          # Map specific project
    codemap --format json             # JSON output
    codemap --depth 3                 # Limit tree depth
    codemap --include-private         # Include _private functions
    codemap --token-budget 4000       # Fit within token limit
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


# ── Constants ────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".eggs", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "egg-info", ".idea", ".vscode",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "pnpm-lock.yaml", "uv.lock",
}

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class FileEntry:
    path: str
    rel_path: str
    size: int = 0
    lines: int = 0
    description: str = ""
    language: str = ""
    is_entrypoint: bool = False
    importance: float = 0.0  # 0-1, higher = more important


@dataclass
class FunctionSig:
    name: str
    params: str
    returns: str
    docstring: str
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    class_name: str = ""


@dataclass
class ClassSig:
    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str = ""
    methods: list[FunctionSig] = field(default_factory=list)
    init_params: str = ""


@dataclass
class ModuleAPI:
    path: str
    docstring: str = ""
    functions: list[FunctionSig] = field(default_factory=list)
    classes: list[ClassSig] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)  # from __all__


# ── File Discovery ───────────────────────────────────────────────────────────

def _detect_language(filepath: str) -> str:
    ext_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React", ".tsx": "React/TS", ".rs": "Rust",
        ".go": "Go", ".rb": "Ruby", ".java": "Java",
        ".c": "C", ".cpp": "C++", ".h": "C/C++ Header",
        ".sh": "Shell", ".bash": "Bash", ".zsh": "Zsh",
        ".sql": "SQL", ".html": "HTML", ".css": "CSS",
        ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
        ".json": "JSON", ".md": "Markdown", ".rst": "reStructuredText",
        ".dockerfile": "Dockerfile", ".tf": "Terraform",
    }
    name = os.path.basename(filepath).lower()
    if name == "dockerfile":
        return "Dockerfile"
    if name == "makefile":
        return "Makefile"
    _, ext = os.path.splitext(name)
    return ext_map.get(ext, "")


def _is_entrypoint(filepath: str, content: str = "") -> bool:
    name = os.path.basename(filepath).lower()
    if name in ("main.py", "app.py", "cli.py", "server.py", "manage.py",
                "index.js", "index.ts", "main.go", "main.rs"):
        return True
    if name.endswith(".py") and content and '__name__' in content and '__main__' in content:
        return True
    return False


def _get_description(filepath: str) -> str:
    """Extract first-line description from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#!'):
                    continue
                # Python docstring
                if line.startswith('"""') or line.startswith("'''"):
                    doc = line.strip('"\' ')
                    if doc:
                        return doc[:120]
                    # Multi-line docstring
                    for next_line in f:
                        next_line = next_line.strip()
                        if next_line:
                            return next_line.strip('"\' ')[:120]
                    break
                # Comment
                if line.startswith('#'):
                    return line.lstrip('# ')[:120]
                if line.startswith('//'):
                    return line.lstrip('/ ')[:120]
                break
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def _is_test_file(filepath: str) -> bool:
    """Check if a file is a test file based on naming conventions."""
    basename = os.path.basename(filepath)
    dirname = os.path.basename(os.path.dirname(filepath))
    
    # Common test file patterns
    test_patterns = [
        basename.startswith('test_'),
        basename.endswith('_test.py'),
        basename.endswith('_test.js'),
        basename.endswith('.test.js'),
        basename.endswith('.test.ts'),
        basename.endswith('.spec.js'),
        basename.endswith('.spec.ts'),
        basename == 'test.py',
        basename == 'tests.py',
    ]
    
    # Common test directory names
    test_dirs = {'test', 'tests', '__tests__', 'spec', 'specs'}
    
    return any(test_patterns) or dirname in test_dirs


def discover_files(root: str, max_depth: int = 10, exclude_tests: bool = False) -> list[FileEntry]:
    """Discover project files, excluding noise."""
    entries: list[FileEntry] = []
    root = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden/build directories
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith('.')]

        depth = dirpath[len(root):].count(os.sep)
        if depth > max_depth:
            dirnames.clear()
            continue

        for fname in sorted(filenames):
            if fname in SKIP_FILES or fname.startswith('.'):
                continue
            filepath = os.path.join(dirpath, fname)
            
            # Skip test files if requested
            if exclude_tests and _is_test_file(filepath):
                continue
            
            rel = os.path.relpath(filepath, root)

            try:
                stat = os.stat(filepath)
                size = stat.st_size
            except OSError:
                continue

            # Skip large binary files
            if size > 1_000_000:  # 1MB
                continue

            lang = _detect_language(filepath)
            desc = _get_description(filepath) if lang else ""

            try:
                with open(filepath, 'rb') as f:
                    lines = sum(1 for _ in f)
            except OSError:
                lines = 0

            content = ""
            if filepath.endswith('.py'):
                try:
                    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
                except OSError:
                    pass

            entries.append(FileEntry(
                path=filepath,
                rel_path=rel,
                size=size,
                lines=lines,
                description=desc,
                language=lang,
                is_entrypoint=_is_entrypoint(filepath, content),
            ))

    return entries


# ── Python API Extraction ────────────────────────────────────────────────────

def _format_params(args: ast.arguments) -> str:
    """Format function parameters as a concise string."""
    parts = []
    defaults_offset = len(args.args) - len(args.defaults)

    for i, arg in enumerate(args.args):
        if arg.arg in ("self", "cls"):
            continue
        s = arg.arg
        if arg.annotation:
            try:
                s += f": {ast.unparse(arg.annotation)}"
            except (AttributeError, ValueError):
                pass
        default_idx = i - defaults_offset
        if default_idx >= 0 and default_idx < len(args.defaults):
            try:
                s += f" = {ast.unparse(args.defaults[default_idx])}"
            except (AttributeError, ValueError):
                s += " = ..."
        parts.append(s)

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    for i, arg in enumerate(args.kwonlyargs):
        s = arg.arg
        if arg.annotation:
            try:
                s += f": {ast.unparse(arg.annotation)}"
            except (AttributeError, ValueError):
                pass
        parts.append(s)
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return ", ".join(parts)


def _first_docstring_line(node: ast.AST) -> str:
    """Get first line of docstring."""
    if (hasattr(node, 'body') and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        doc = node.body[0].value.value.strip()
        first_line = doc.split('\n')[0].strip()
        return first_line[:120]
    return ""


def extract_python_api(filepath: str, include_private: bool = False) -> ModuleAPI | None:
    """Extract public API from a Python file."""
    try:
        source = Path(filepath).read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError):
        return None

    rel = os.path.basename(filepath)
    api = ModuleAPI(path=rel, docstring=_first_docstring_line(tree))

    # Check for __all__
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                api.exports.append(elt.value)

    # Imports (just module names for the dep graph)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                api.imports.append(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.module.startswith('.'):
                api.imports.append(node.module.split('.')[0])
    api.imports = sorted(set(api.imports))

    # Functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_private and node.name.startswith('_'):
                continue
            returns = ""
            if node.returns:
                try:
                    returns = ast.unparse(node.returns)
                except (AttributeError, ValueError):
                    pass
            decorators = []
            for dec in node.decorator_list:
                try:
                    decorators.append(ast.unparse(dec))
                except (AttributeError, ValueError):
                    pass

            api.functions.append(FunctionSig(
                name=node.name,
                params=_format_params(node.args),
                returns=returns,
                docstring=_first_docstring_line(node),
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=decorators,
            ))

    # Classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if not include_private and node.name.startswith('_'):
                continue
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except (AttributeError, ValueError):
                    pass

            cls = ClassSig(
                name=node.name,
                bases=bases,
                docstring=_first_docstring_line(node),
            )

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name == '__init__':
                        cls.init_params = _format_params(child.args)
                    elif not include_private and child.name.startswith('_'):
                        continue
                    else:
                        returns = ""
                        if child.returns:
                            try:
                                returns = ast.unparse(child.returns)
                            except (AttributeError, ValueError):
                                pass
                        cls.methods.append(FunctionSig(
                            name=child.name,
                            params=_format_params(child.args),
                            returns=returns,
                            docstring=_first_docstring_line(child),
                            is_async=isinstance(child, ast.AsyncFunctionDef),
                            class_name=node.name,
                        ))

            api.classes.append(cls)

    return api


# ── Importance Scoring ───────────────────────────────────────────────────────

def _score_importance(entries: list[FileEntry], root: str) -> None:
    """Score file importance based on heuristics."""
    if not entries:
        return

    max_lines = max(e.lines for e in entries) or 1

    # Git churn (if available)
    churn: dict[str, int] = {}
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:", "--name-only", "--since=90 days ago"],
            capture_output=True, text=True, cwd=root, timeout=30
        )
        if result.stdout:
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line:
                    churn[line] = churn.get(line, 0) + 1
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    max_churn = max(churn.values()) if churn else 1

    for entry in entries:
        score = 0.0

        # Entrypoints are important
        if entry.is_entrypoint:
            score += 0.3

        # Source code > config > docs
        if entry.language in ("Python", "JavaScript", "TypeScript", "Rust", "Go"):
            score += 0.2
        elif entry.language in ("Makefile", "Dockerfile", "Shell"):
            score += 0.1

        # Size matters (larger files have more API surface)
        score += (entry.lines / max_lines) * 0.2

        # Git churn (frequently changed = important)
        if entry.rel_path in churn:
            score += (churn[entry.rel_path] / max_churn) * 0.2

        # Root-level files are more important
        depth = entry.rel_path.count(os.sep)
        if depth == 0:
            score += 0.1

        # Has description = documented = important
        if entry.description:
            score += 0.05

        entry.importance = min(1.0, score)


# ── Output Formatters ────────────────────────────────────────────────────────

def _format_tree(entries: list[FileEntry], max_depth: int = 10) -> str:
    """Format file tree with descriptions."""
    lines = []
    tree: dict[str, Any] = {}

    for entry in sorted(entries, key=lambda e: e.rel_path):
        parts = entry.rel_path.split(os.sep)
        if len(parts) > max_depth + 1:
            continue
        node = tree
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = entry

    def _render(node: dict, prefix: str = "", depth: int = 0):
        items = list(node.items())
        for i, (name, val) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if isinstance(val, FileEntry):
                desc = f"  — {val.description}" if val.description else ""
                star = "★ " if val.is_entrypoint else ""
                lines.append(f"{prefix}{connector}{star}{name}{desc}")
            elif isinstance(val, dict):
                lines.append(f"{prefix}{connector}{name}/")
                _render(val, prefix + extension, depth + 1)

    _render(tree)
    return "\n".join(lines)


def _format_api(apis: list[ModuleAPI]) -> str:
    """Format public API index."""
    lines = []
    for api in apis:
        if not api.functions and not api.classes:
            continue

        lines.append(f"\n### {api.path}")
        if api.docstring:
            lines.append(f"*{api.docstring}*")
        if api.exports:
            lines.append(f"Exports: {', '.join(api.exports)}")

        for func in api.functions:
            async_prefix = "async " if func.is_async else ""
            ret = f" → {func.returns}" if func.returns else ""
            doc = f"  # {func.docstring}" if func.docstring else ""
            lines.append(f"  {async_prefix}def {func.name}({func.params}){ret}{doc}")

        for cls in api.classes:
            bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
            doc = f"  # {cls.docstring}" if cls.docstring else ""
            lines.append(f"  class {cls.name}{bases_str}{doc}")
            if cls.init_params:
                lines.append(f"    __init__({cls.init_params})")
            for method in cls.methods:
                async_prefix = "async " if method.is_async else ""
                ret = f" → {method.returns}" if method.returns else ""
                mdoc = f"  # {method.docstring}" if method.docstring else ""
                lines.append(f"    {async_prefix}def {method.name}({method.params}){ret}{mdoc}")

    return "\n".join(lines)


def _format_deps(apis: list[ModuleAPI]) -> str:
    """Format import dependency summary."""
    all_imports: dict[str, int] = defaultdict(int)
    stdlib = {
        "os", "sys", "re", "json", "csv", "ast", "math", "hashlib",
        "pathlib", "datetime", "collections", "typing", "dataclasses",
        "argparse", "textwrap", "subprocess", "unittest", "functools",
        "itertools", "io", "abc", "enum", "copy", "shutil", "glob",
        "tempfile", "logging", "warnings", "http", "urllib", "socket",
        "ssl", "email", "html", "xml", "sqlite3", "threading",
        "multiprocessing", "asyncio", "concurrent", "contextlib",
        "inspect", "dis", "importlib", "pkgutil", "struct", "time",
    }

    for api in apis:
        for imp in api.imports:
            if imp not in stdlib:
                all_imports[imp] += 1

    if not all_imports:
        return "No third-party dependencies detected."

    sorted_deps = sorted(all_imports.items(), key=lambda x: -x[1])
    lines = []
    for dep, count in sorted_deps:
        lines.append(f"  {dep} (used by {count} module{'s' if count > 1 else ''})")
    return "\n".join(lines)


def generate_map(root: str, max_depth: int = 10,
                  include_private: bool = False,
                  token_budget: int | None = None,
                  exclude_tests: bool = False) -> str:
    """Generate the complete codebase map."""
    entries = discover_files(root, max_depth=max_depth, exclude_tests=exclude_tests)
    if not entries:
        return "No files found."

    _score_importance(entries, root)

    # Sort by importance for API extraction
    entries.sort(key=lambda e: -e.importance)

    # Extract Python APIs
    apis: list[ModuleAPI] = []
    for entry in entries:
        if entry.rel_path.endswith('.py'):
            api = extract_python_api(entry.path, include_private=include_private)
            if api and (api.functions or api.classes):
                api.path = entry.rel_path
                apis.append(api)

    # Project metadata
    project_name = os.path.basename(os.path.abspath(root))
    py_files = sum(1 for e in entries if e.language == "Python")
    total_lines = sum(e.lines for e in entries)
    languages = sorted(set(e.language for e in entries if e.language))
    entrypoints = [e.rel_path for e in entries if e.is_entrypoint]

    # Build output sections
    sections = []

    # Header
    sections.append(f"# Codebase Map: {project_name}\n")
    sections.append(f"Files: {len(entries)} | Lines: {total_lines:,} | "
                     f"Languages: {', '.join(languages)}")
    if entrypoints:
        sections.append(f"Entrypoints: {', '.join(entrypoints)}")
    sections.append("")

    # File tree
    sections.append("## Structure\n")
    sections.append("```")
    sections.append(_format_tree(entries, max_depth=max_depth))
    sections.append("```\n")

    # Public API
    api_text = _format_api(apis)
    if api_text.strip():
        sections.append("## Public API\n")
        sections.append("```python")
        sections.append(api_text)
        sections.append("```\n")

    # Dependencies
    deps_text = _format_deps(apis)
    if deps_text.strip():
        sections.append("## Dependencies\n")
        sections.append(deps_text)
        sections.append("")

    # Hot files (top 10 most important)
    hot = sorted(entries, key=lambda e: -e.importance)[:10]
    if hot:
        sections.append("## Key Files\n")
        for h in hot:
            desc = f" — {h.description}" if h.description else ""
            star = " ★" if h.is_entrypoint else ""
            sections.append(f"- **{h.rel_path}**{star} ({h.lines} lines){desc}")
        sections.append("")

    output = "\n".join(sections)

    # Token budget trimming
    if token_budget:
        est_tokens = len(output) // CHARS_PER_TOKEN
        if est_tokens > token_budget:
            # Trim API section first (largest)
            for i, section in enumerate(sections):
                if section.startswith("## Public API"):
                    # Truncate at budget
                    budget_chars = token_budget * CHARS_PER_TOKEN
                    output = "\n".join(sections)
                    if len(output) > budget_chars:
                        output = output[:budget_chars] + "\n\n... (truncated to fit token budget)"
                    break

    return output


def generate_json(root: str, max_depth: int = 10,
                   include_private: bool = False,
                   exclude_tests: bool = False) -> str:
    """Generate JSON output."""
    entries = discover_files(root, max_depth=max_depth, exclude_tests=exclude_tests)
    _score_importance(entries, root)
    entries.sort(key=lambda e: -e.importance)

    apis: list[ModuleAPI] = []
    for entry in entries:
        if entry.rel_path.endswith('.py'):
            api = extract_python_api(entry.path, include_private=include_private)
            if api:
                api.path = entry.rel_path
                apis.append(api)

    project_name = os.path.basename(os.path.abspath(root))

    return json.dumps({
        "project": project_name,
        "files": len(entries),
        "total_lines": sum(e.lines for e in entries),
        "languages": sorted(set(e.language for e in entries if e.language)),
        "entrypoints": [e.rel_path for e in entries if e.is_entrypoint],
        "file_tree": [
            {
                "path": e.rel_path,
                "lines": e.lines,
                "language": e.language,
                "description": e.description,
                "importance": round(e.importance, 3),
                "entrypoint": e.is_entrypoint,
            }
            for e in entries
        ],
        "api": [
            {
                "module": a.path,
                "docstring": a.docstring,
                "exports": a.exports,
                "imports": a.imports,
                "functions": [
                    {
                        "name": f.name,
                        "params": f.params,
                        "returns": f.returns,
                        "docstring": f.docstring,
                        "async": f.is_async,
                    }
                    for f in a.functions
                ],
                "classes": [
                    {
                        "name": c.name,
                        "bases": c.bases,
                        "docstring": c.docstring,
                        "init_params": c.init_params,
                        "methods": [
                            {
                                "name": m.name,
                                "params": m.params,
                                "returns": m.returns,
                                "docstring": m.docstring,
                                "async": m.is_async,
                            }
                            for m in c.methods
                        ],
                    }
                    for c in a.classes
                ],
            }
            for a in apis if a.functions or a.classes
        ],
    }, indent=2)


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codemap",
        description="Intelligent Codebase Map for AI Agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Generates a structured, token-efficient codebase summary designed
            for AI context windows. Shows project structure, public API,
            dependencies, and key files — not a raw dump of every file.

            Examples:
              codemap                        Map current directory
              codemap /path/to/project       Map specific project
              codemap --format json          JSON output
              codemap --depth 3              Limit tree depth
              codemap --include-private      Include _private functions
              codemap --token-budget 4000    Fit within token limit
        """),
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Project path (default: current directory)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format (default: markdown)")
    parser.add_argument("--depth", type=int, default=10,
                        help="Maximum directory depth (default: 10)")
    parser.add_argument("--include-private", action="store_true",
                        help="Include _private functions and classes")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude test files from output (test_*, *_test.py, tests/, etc.)")
    parser.add_argument("--token-budget", type=int, default=None,
                        help="Target token budget (output truncated to fit)")
    parser.add_argument("--version", action="version", version="codemap 1.0.0")

    args = parser.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        return 1

    if args.format == "json":
        print(generate_json(root, max_depth=args.depth,
                             include_private=args.include_private,
                             exclude_tests=args.exclude_tests))
    else:
        print(generate_map(root, max_depth=args.depth,
                            include_private=args.include_private,
                            token_budget=args.token_budget,
                            exclude_tests=args.exclude_tests))

    return 0


if __name__ == "__main__":
    sys.exit(main())

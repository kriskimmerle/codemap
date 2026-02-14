# codemap Examples

This directory contains example outputs showing what codemap generates.

## Example Output

**File**: `codemap-example-output.md`

This is the output of running codemap on its own codebase:

```bash
codemap .
```

It demonstrates:
- **Structure section**: File tree with descriptions and entrypoint markers (★)
- **Public API section**: Extracted functions and classes with type hints
- **Key Files section**: Most important files ranked by importance score

## What You'll See

- **Entrypoint markers** (★): Files that serve as entry points (main.py, app.py, test files)
- **Descriptions**: Extracted from docstrings or comments
- **Type hints**: Function parameters and return types
- **Token efficiency**: The entire codemap project (600+ lines) summarized in under 1000 tokens

## Try It Yourself

Run codemap on your own projects:

```bash
# Basic usage
codemap /path/to/project

# JSON output
codemap --format json .

# Limit depth
codemap --depth 3 .

# Include private functions
codemap --include-private .

# Fit within token budget
codemap --token-budget 4000 .
```

## Use Cases

- **AI context**: Paste into Claude/GPT to give them project overview
- **Documentation**: Quick reference for project structure
- **Onboarding**: Help new developers understand codebase layout
- **Code review**: Identify important files and public APIs at a glance

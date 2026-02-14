# Contributing to codemap

Thank you for your interest in contributing to codemap! This guide will help you get started.

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker
- Include your `codemap --version` output
- Provide the directory structure that causes issues (if applicable)
- Describe expected vs actual behavior

### Feature Requests

Codemap is designed to be minimal and focused. When suggesting features:

1. Explain the use case - why is this needed?
2. Show how it fits the core mission: generating AI-friendly codebase summaries
3. Consider token efficiency - will this add significant output bloat?

Good additions:
- Support for new languages (with API extraction)
- Better importance scoring heuristics
- Smarter token budget management

Less likely to be accepted:
- Full file content dumps (use repomix/code2prompt for that)
- Complex dependency analysis (too much output)
- Build/test integration (out of scope)

### Code Contributions

1. **Fork and clone** the repository
2. **Create a branch** for your feature
3. **Make your changes**:
   - Follow existing code style
   - Add tests for new functionality
   - Keep dependencies at zero (stdlib only)
4. **Test**:
   ```bash
   python3 test_codemap.py
   ./codemap.py .  # Test on the codemap project itself
   ```
5. **Commit** with clear messages
6. **Push** and open a pull request

## Development Setup

Zero dependencies means zero setup:

```bash
git clone https://github.com/kriskimmerle/codemap.git
cd codemap
python3 test_codemap.py  # Run tests
./codemap.py .           # Map the project itself
```

## Adding Language Support

To add support for a new language:

1. Add file extension mapping in `_detect_language()`:
   ```python
   ".ext": "LanguageName",
   ```

2. (Optional) Add API extraction function:
   ```python
   def extract_language_api(filepath: str) -> ModuleAPI | None:
       # Parse the file and extract public API
       # Return ModuleAPI with functions, classes, etc.
       pass
   ```

3. Hook it into `generate_map()`:
   ```python
   if entry.rel_path.endswith('.ext'):
       api = extract_language_api(entry.path)
   ```

4. Add tests in `test_codemap.py`

## Code Style

- Python 3.7+ features encouraged
- Type hints using `from __future__ import annotations`
- Docstrings for public functions
- Keep functions focused and testable
- **Zero external dependencies** - stdlib only

## Testing

- All new features need tests
- Test both success and failure cases
- Run tests before submitting: `python3 test_codemap.py`
- Test on real projects of various sizes

## Design Principles

1. **Token efficiency** - Output should fit in AI context windows
2. **Signal over noise** - Show what matters, not everything
3. **Zero dependencies** - Easy to install and run anywhere
4. **Fast** - Should handle large codebases quickly
5. **Portable** - Work on macOS, Linux, Windows

## Pull Request Guidelines

- One feature per PR
- Include tests
- Update README.md if adding user-facing features
- Keep it focused - smaller PRs are easier to review
- Be patient with reviews

## Questions?

Open an issue with the "question" label.

## License

By contributing, you agree your contributions will be licensed under the MIT License.

# Codebase Map: codemap

Files: 7 | Lines: 1,604 | Languages: Markdown, Python, TOML
Entrypoints: codemap.py, test_codemap.py

## Structure

```
├── CONTRIBUTING.md  — Contributing to codemap
├── LICENSE
├── README.md  — codemap 🗺️
├── ★ codemap.py  — codemap - Intelligent Codebase Map for AI Agents.
├── examples/
│   └── codemap-example-output.md
├── pyproject.toml
└── ★ test_codemap.py  — Tests for codemap - Intelligent Codebase Map for AI Agents.
```

## Public API

```python

### codemap.py
*codemap - Intelligent Codebase Map for AI Agents.*
  def discover_files(root: str, max_depth: int = 10) → list[FileEntry]  # Discover project files, excluding noise.
  def extract_python_api(filepath: str, include_private: bool = False) → ModuleAPI | None  # Extract public API from a Python file.
  def generate_map(root: str, max_depth: int = 10, include_private: bool = False, token_budget: int | None = None) → str  # Generate the complete codebase map.
  def generate_json(root: str, max_depth: int = 10, include_private: bool = False) → str  # Generate JSON output.
  def main(argv: list[str] | None = None) → int
  class FileEntry
  class FunctionSig
  class ClassSig
  class ModuleAPI

### test_codemap.py
*Tests for codemap - Intelligent Codebase Map for AI Agents.*
  class TestFileDiscovery(unittest.TestCase)  # Test file discovery and filtering.
    def setUp()  # Create a temporary project structure.
    def tearDown()  # Clean up temporary directory.
    def test_discover_basic_files()  # Test that basic files are discovered.
    def test_skip_hidden_files()  # Test that hidden files are skipped.
    def test_skip_directories()  # Test that skip directories are excluded.
    def test_depth_limiting()  # Test directory depth limiting.
  class TestLanguageDetection(unittest.TestCase)  # Test language detection.
    def test_detect_python()  # Test Python file detection.
    def test_detect_javascript()  # Test JavaScript detection.
    def test_detect_typescript()  # Test TypeScript detection.
    def test_detect_dockerfile()  # Test Dockerfile detection by name.
    def test_detect_other_languages()  # Test other language detections.
  class TestEntrypointDetection(unittest.TestCase)  # Test entrypoint file detection.
    def test_detect_main_py()  # Test detection of main.py as entrypoint.
    def test_detect_app_py()  # Test detection of app.py as entrypoint.
    def test_detect_main_block()  # Test detection of if __name__ == '__main__' pattern.
    def test_not_entrypoint()  # Test that regular files are not flagged as entrypoints.
  class TestDescriptionExtraction(unittest.TestCase)  # Test description extraction from files.
    def setUp()
    def tearDown()
    def test_extract_python_docstring()  # Test extracting Python module docstring.
    def test_extract_python_comment()  # Test extracting Python comment.
    def test_truncate_long_description()  # Test that long descriptions are truncated.
  class TestPythonAPIExtraction(unittest.TestCase)  # Test Python API extraction.
    def setUp()
    def tearDown()
    def test_extract_functions()  # Test extracting function signatures.
    def test_extract_async_functions()  # Test extracting async function signatures.
    def test_extract_classes()  # Test extracting class signatures.
    def test_include_private()  # Test including private functions/methods.
    def test_extract_imports()  # Test extracting import statements.
    def test_extract_all_exports()  # Test extracting __all__ exports.
    def test_handle_syntax_error()  # Test handling files with syntax errors.
  class TestImportanceScoring(unittest.TestCase)  # Test importance scoring.
    def test_entrypoint_importance()  # Test that entrypoints get higher importance scores.
    def test_language_importance()  # Test that source code files score higher than config.
    def test_empty_entries()  # Test scoring with empty entries list.
  class TestOutputFormatting(unittest.TestCase)  # Test output formatting.
    def setUp()
    def tearDown()
    def test_generate_markdown()  # Test generating markdown output.
    def test_generate_json()  # Test generating JSON output.
    def test_tree_format()  # Test file tree formatting.
    def test_token_budget_truncation()  # Test output truncation with token budget.
  class TestCLI(unittest.TestCase)  # Test CLI functionality.
    def test_default_path()  # Test that default path is current directory.
    def test_json_format()  # Test JSON output format via CLI.
    def test_depth_argument()  # Test depth argument.
    def test_include_private()  # Test include-private argument.
    def test_token_budget_cli()  # Test token budget CLI argument.
    def test_invalid_path()  # Test handling of invalid path.
    def test_version()  # Test --version flag.
  class TestEdgeCases(unittest.TestCase)  # Test edge cases and error handling.
    def test_empty_directory()  # Test mapping an empty directory.
    def test_large_file_skip()  # Test that very large files are skipped.
    def test_unicode_handling()  # Test handling of Unicode in files.
    def test_class_with_inheritance()  # Test extracting class with base classes.
```

## Dependencies

  __future__ (used by 1 module)
  codemap (used by 1 module)

## Key Files

- **codemap.py** ★ (750 lines) — codemap - Intelligent Codebase Map for AI Agents.
- **test_codemap.py** ★ (531 lines) — Tests for codemap - Intelligent Codebase Map for AI Agents.
- **README.md** (150 lines) — codemap 🗺️
- **pyproject.toml** (31 lines)
- **LICENSE** (21 lines)
- **CONTRIBUTING.md** (121 lines) — Contributing to codemap
- **examples/codemap-example-output.md** (0 lines)


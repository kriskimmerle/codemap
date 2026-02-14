#!/usr/bin/env python3
"""Tests for codemap - Intelligent Codebase Map for AI Agents.

Tests cover:
- File discovery and filtering
- Language detection
- Python API extraction (functions, classes, docstrings)
- Importance scoring
- Output formatting (markdown, JSON)
- CLI argument handling
- Edge cases
"""

import unittest
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from io import StringIO

# Import from codemap
sys.path.insert(0, os.path.dirname(__file__))
import codemap


class TestFileDiscovery(unittest.TestCase):
    """Test file discovery and filtering."""

    def setUp(self):
        """Create a temporary project structure."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create test files
        Path(self.test_dir, "main.py").write_text("# Main file")
        Path(self.test_dir, "helper.py").write_text("# Helper")
        Path(self.test_dir, ".hidden.py").write_text("# Should be ignored")
        
        # Create subdirectory
        subdir = Path(self.test_dir, "subdir")
        subdir.mkdir()
        Path(subdir, "module.py").write_text("# Module")
        
        # Create skip directory
        skip_dir = Path(self.test_dir, "__pycache__")
        skip_dir.mkdir()
        Path(skip_dir, "cache.pyc").write_text("# Should be ignored")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_discover_basic_files(self):
        """Test that basic files are discovered."""
        entries = codemap.discover_files(self.test_dir)
        paths = [e.rel_path for e in entries]
        
        self.assertIn("main.py", paths)
        self.assertIn("helper.py", paths)
        self.assertIn(os.path.join("subdir", "module.py"), paths)

    def test_skip_hidden_files(self):
        """Test that hidden files are skipped."""
        entries = codemap.discover_files(self.test_dir)
        paths = [e.rel_path for e in entries]
        
        self.assertNotIn(".hidden.py", paths)

    def test_skip_directories(self):
        """Test that skip directories are excluded."""
        entries = codemap.discover_files(self.test_dir)
        paths = [e.rel_path for e in entries]
        
        # No files from __pycache__ should be present
        for path in paths:
            self.assertNotIn("__pycache__", path)

    def test_depth_limiting(self):
        """Test directory depth limiting."""
        # Create deep nested structure
        deep_path = Path(self.test_dir, "a", "b", "c", "d")
        deep_path.mkdir(parents=True)
        Path(deep_path, "deep.py").write_text("# Deep file")
        
        # Limit depth to 2
        entries = codemap.discover_files(self.test_dir, max_depth=2)
        paths = [e.rel_path for e in entries]
        
        # Should not include files more than 2 levels deep
        too_deep = os.path.join("a", "b", "c", "d", "deep.py")
        self.assertNotIn(too_deep, paths)


class TestLanguageDetection(unittest.TestCase):
    """Test language detection."""

    def test_detect_python(self):
        """Test Python file detection."""
        self.assertEqual(codemap._detect_language("test.py"), "Python")

    def test_detect_javascript(self):
        """Test JavaScript detection."""
        self.assertEqual(codemap._detect_language("app.js"), "JavaScript")
        self.assertEqual(codemap._detect_language("App.jsx"), "React")

    def test_detect_typescript(self):
        """Test TypeScript detection."""
        self.assertEqual(codemap._detect_language("index.ts"), "TypeScript")
        self.assertEqual(codemap._detect_language("Component.tsx"), "React/TS")

    def test_detect_dockerfile(self):
        """Test Dockerfile detection by name."""
        self.assertEqual(codemap._detect_language("Dockerfile"), "Dockerfile")
        self.assertEqual(codemap._detect_language("test.dockerfile"), "Dockerfile")

    def test_detect_other_languages(self):
        """Test other language detections."""
        self.assertEqual(codemap._detect_language("main.go"), "Go")
        self.assertEqual(codemap._detect_language("lib.rs"), "Rust")
        self.assertEqual(codemap._detect_language("script.sh"), "Shell")


class TestEntrypointDetection(unittest.TestCase):
    """Test entrypoint file detection."""

    def test_detect_main_py(self):
        """Test detection of main.py as entrypoint."""
        self.assertTrue(codemap._is_entrypoint("main.py"))

    def test_detect_app_py(self):
        """Test detection of app.py as entrypoint."""
        self.assertTrue(codemap._is_entrypoint("app.py"))

    def test_detect_main_block(self):
        """Test detection of if __name__ == '__main__' pattern."""
        content = """
def main():
    pass

if __name__ == '__main__':
    main()
"""
        self.assertTrue(codemap._is_entrypoint("script.py", content))

    def test_not_entrypoint(self):
        """Test that regular files are not flagged as entrypoints."""
        self.assertFalse(codemap._is_entrypoint("helper.py"))
        self.assertFalse(codemap._is_entrypoint("utils.py", "def helper(): pass"))


class TestDescriptionExtraction(unittest.TestCase):
    """Test description extraction from files."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_extract_python_docstring(self):
        """Test extracting Python module docstring."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text('"""This is a test module."""\npass')
        
        desc = codemap._get_description(str(test_file))
        self.assertEqual(desc, "This is a test module.")

    def test_extract_python_comment(self):
        """Test extracting Python comment."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("# This is a comment\npass")
        
        desc = codemap._get_description(str(test_file))
        self.assertEqual(desc, "This is a comment")

    def test_truncate_long_description(self):
        """Test that long descriptions are truncated."""
        long_desc = "x" * 200
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text(f'"""{long_desc}"""')
        
        desc = codemap._get_description(str(test_file))
        self.assertLessEqual(len(desc), 120)


class TestPythonAPIExtraction(unittest.TestCase):
    """Test Python API extraction."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_extract_functions(self):
        """Test extracting function signatures."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
def public_func(x: int, y: str = "default") -> bool:
    '''This is a public function.'''
    return True

def _private_func():
    pass
""")
        
        api = codemap.extract_python_api(str(test_file), include_private=False)
        self.assertIsNotNone(api)
        self.assertEqual(len(api.functions), 1)
        self.assertEqual(api.functions[0].name, "public_func")
        self.assertIn("int", api.functions[0].params)
        self.assertEqual(api.functions[0].returns, "bool")
        self.assertEqual(api.functions[0].docstring, "This is a public function.")

    def test_extract_async_functions(self):
        """Test extracting async function signatures."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
async def async_func(name: str):
    '''Async function.'''
    pass
""")
        
        api = codemap.extract_python_api(str(test_file))
        self.assertIsNotNone(api)
        self.assertEqual(len(api.functions), 1)
        self.assertTrue(api.functions[0].is_async)

    def test_extract_classes(self):
        """Test extracting class signatures."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
class MyClass:
    '''A test class.'''
    
    def __init__(self, value: int):
        self.value = value
    
    def public_method(self) -> str:
        '''Public method.'''
        return "test"
    
    def _private_method(self):
        pass
""")
        
        api = codemap.extract_python_api(str(test_file), include_private=False)
        self.assertIsNotNone(api)
        self.assertEqual(len(api.classes), 1)
        self.assertEqual(api.classes[0].name, "MyClass")
        self.assertEqual(api.classes[0].docstring, "A test class.")
        self.assertIn("value", api.classes[0].init_params)
        
        # Should have public_method but not _private_method
        method_names = [m.name for m in api.classes[0].methods]
        self.assertIn("public_method", method_names)
        self.assertNotIn("_private_method", method_names)

    def test_include_private(self):
        """Test including private functions/methods."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
def _private_func():
    pass

class MyClass:
    def _private_method(self):
        pass
""")
        
        api = codemap.extract_python_api(str(test_file), include_private=True)
        self.assertIsNotNone(api)
        self.assertEqual(len(api.functions), 1)
        self.assertEqual(api.functions[0].name, "_private_func")
        
        self.assertEqual(len(api.classes[0].methods), 1)
        self.assertEqual(api.classes[0].methods[0].name, "_private_method")

    def test_extract_imports(self):
        """Test extracting import statements."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
import os
import sys
from pathlib import Path
from typing import List
""")
        
        api = codemap.extract_python_api(str(test_file))
        self.assertIsNotNone(api)
        self.assertIn("os", api.imports)
        self.assertIn("sys", api.imports)
        self.assertIn("pathlib", api.imports)

    def test_extract_all_exports(self):
        """Test extracting __all__ exports."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("""
__all__ = ['public_func', 'PublicClass']

def public_func():
    pass

def private_func():
    pass
""")
        
        api = codemap.extract_python_api(str(test_file))
        self.assertIsNotNone(api)
        self.assertEqual(api.exports, ['public_func', 'PublicClass'])

    def test_handle_syntax_error(self):
        """Test handling files with syntax errors."""
        test_file = Path(self.test_dir, "test.py")
        test_file.write_text("def broken(\n  syntax error")
        
        api = codemap.extract_python_api(str(test_file))
        self.assertIsNone(api)


class TestImportanceScoring(unittest.TestCase):
    """Test importance scoring."""

    def test_entrypoint_importance(self):
        """Test that entrypoints get higher importance scores."""
        entries = [
            codemap.FileEntry("main.py", "main.py", 100, 10, is_entrypoint=True),
            codemap.FileEntry("helper.py", "helper.py", 100, 10, is_entrypoint=False),
        ]
        
        codemap._score_importance(entries, "/tmp")
        
        # Entrypoint should have higher score
        main_score = next(e.importance for e in entries if e.rel_path == "main.py")
        helper_score = next(e.importance for e in entries if e.rel_path == "helper.py")
        self.assertGreater(main_score, helper_score)

    def test_language_importance(self):
        """Test that source code files score higher than config."""
        entries = [
            codemap.FileEntry("app.py", "app.py", 100, 10, language="Python"),
            codemap.FileEntry("config.json", "config.json", 100, 10, language="JSON"),
        ]
        
        codemap._score_importance(entries, "/tmp")
        
        py_score = next(e.importance for e in entries if e.rel_path == "app.py")
        json_score = next(e.importance for e in entries if e.rel_path == "config.json")
        self.assertGreater(py_score, json_score)

    def test_empty_entries(self):
        """Test scoring with empty entries list."""
        # Should not crash
        codemap._score_importance([], "/tmp")


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        Path(self.test_dir, "main.py").write_text('"""Main module."""\npass')
        Path(self.test_dir, "helper.py").write_text("# Helper")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_markdown(self):
        """Test generating markdown output."""
        output = codemap.generate_map(self.test_dir)
        
        self.assertIn("# Codebase Map:", output)
        self.assertIn("## Structure", output)
        self.assertIn("main.py", output)

    def test_generate_json(self):
        """Test generating JSON output."""
        output = codemap.generate_json(self.test_dir)
        data = json.loads(output)
        
        self.assertIn("project", data)
        self.assertIn("files", data)
        self.assertIn("file_tree", data)
        self.assertIsInstance(data["file_tree"], list)

    def test_tree_format(self):
        """Test file tree formatting."""
        entries = [
            codemap.FileEntry("main.py", "main.py", 100, 10, description="Main file"),
            codemap.FileEntry("subdir/module.py", os.path.join("subdir", "module.py"), 50, 5),
        ]
        
        tree = codemap._format_tree(entries)
        
        self.assertIn("main.py", tree)
        self.assertIn("subdir/", tree)
        self.assertIn("Main file", tree)

    def test_token_budget_truncation(self):
        """Test output truncation with token budget."""
        # Create a project with lots of content
        for i in range(20):
            Path(self.test_dir, f"file{i}.py").write_text(f"# File {i}\npass")
        
        output = codemap.generate_map(self.test_dir, token_budget=500)
        
        # Output should be truncated
        self.assertLess(len(output), 500 * codemap.CHARS_PER_TOKEN * 1.5)


class TestCLI(unittest.TestCase):
    """Test CLI functionality."""

    def test_default_path(self):
        """Test that default path is current directory."""
        with patch('sys.stdout', new=StringIO()):
            exit_code = codemap.main([])
        self.assertEqual(exit_code, 0)

    def test_json_format(self):
        """Test JSON output format via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('sys.stdout', new=StringIO()) as fake_out:
                exit_code = codemap.main([tmpdir, "--format", "json"])
                output = fake_out.getvalue()
                
            self.assertEqual(exit_code, 0)
            # Should be valid JSON
            data = json.loads(output)
            self.assertIn("project", data)

    def test_depth_argument(self):
        """Test depth argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('sys.stdout', new=StringIO()):
                exit_code = codemap.main([tmpdir, "--depth", "3"])
            self.assertEqual(exit_code, 0)

    def test_include_private(self):
        """Test include-private argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test.py").write_text("def _private(): pass")
            
            with patch('sys.stdout', new=StringIO()) as fake_out:
                exit_code = codemap.main([tmpdir, "--include-private"])
                output = fake_out.getvalue()
            
            self.assertEqual(exit_code, 0)
            self.assertIn("_private", output)

    def test_token_budget_cli(self):
        """Test token budget CLI argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('sys.stdout', new=StringIO()):
                exit_code = codemap.main([tmpdir, "--token-budget", "1000"])
            self.assertEqual(exit_code, 0)

    def test_invalid_path(self):
        """Test handling of invalid path."""
        with patch('sys.stderr', new=StringIO()) as fake_err:
            exit_code = codemap.main(["/nonexistent/path"])
            
        self.assertEqual(exit_code, 1)

    def test_version(self):
        """Test --version flag."""
        with self.assertRaises(SystemExit) as cm:
            codemap.main(["--version"])
        self.assertEqual(cm.exception.code, 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_directory(self):
        """Test mapping an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = codemap.generate_map(tmpdir)
            self.assertIn("No files found", output)

    def test_large_file_skip(self):
        """Test that very large files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file larger than 1MB
            large_file = Path(tmpdir, "large.bin")
            large_file.write_bytes(b"x" * 2_000_000)
            
            entries = codemap.discover_files(tmpdir)
            paths = [e.rel_path for e in entries]
            
            self.assertNotIn("large.bin", paths)

    def test_unicode_handling(self):
        """Test handling of Unicode in files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, "unicode.py")
            test_file.write_text("# Café résumé naïve\ndef func(): pass", encoding="utf-8")
            
            api = codemap.extract_python_api(str(test_file))
            self.assertIsNotNone(api)

    def test_class_with_inheritance(self):
        """Test extracting class with base classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, "test.py")
            test_file.write_text("""
class Parent:
    pass

class Child(Parent):
    pass

class MultiInherit(Parent, Exception):
    pass
""")
            
            api = codemap.extract_python_api(str(test_file))
            self.assertIsNotNone(api)
            self.assertEqual(len(api.classes), 3)
            
            child = next(c for c in api.classes if c.name == "Child")
            self.assertEqual(child.bases, ["Parent"])
            
            multi = next(c for c in api.classes if c.name == "MultiInherit")
            self.assertEqual(len(multi.bases), 2)


if __name__ == "__main__":
    unittest.main()

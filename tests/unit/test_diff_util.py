# tests/unit/test_diff_util.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for diff utility."""

import pytest
from cmcp.utils.diff import (
    generate_diff, 
    apply_unified_diff, 
    split_patch_into_files, 
    analyze_diff,
    DiffFormat
)


def test_generate_unified_diff():
    """Test generating a unified diff."""
    original = """def hello():
    print("Hello")
    
def world():
    print("World")
"""
    
    new = """def hello():
    print("Hello")
    
def world():
    print("World")

def goodbye():
    print("Goodbye")
"""
    
    diff_content, stats = generate_diff(original, new, DiffFormat.UNIFIED)
    
    assert "def goodbye():" in diff_content
    assert "+def goodbye():" in diff_content
    assert stats.lines_added > 0
    assert stats.lines_removed == 0
    assert stats.hunks > 0


def test_apply_unified_diff():
    """Test applying a unified diff."""
    original = """def hello():
    print("Hello")
    
def world():
    print("World")
"""
    
    diff_content = """--- a/example.py
+++ b/example.py
@@ -4,2 +4,5 @@
 def world():
     print("World")
+
+def goodbye():
+    print("Goodbye")
"""
    
    new_content, lines_applied = apply_unified_diff(original, diff_content)
    
    assert "def goodbye():" in new_content
    assert "print(\"Goodbye\")" in new_content
    assert lines_applied > 0


def test_apply_diff_with_deletions():
    """Test applying a diff with deletions."""
    original = """def hello():
    print("Hello")
    
def world():
    print("World")
    
def old_function():
    print("Old")
"""
    
    diff_content = """--- a/example.py
+++ b/example.py
@@ -5,4 +5,2 @@
     print("World")
     
-def old_function():
-    print("Old")
"""
    
    new_content, lines_applied = apply_unified_diff(original, diff_content)
    
    assert "def old_function():" not in new_content
    assert "print(\"Old\")" not in new_content
    assert lines_applied > 0


def test_split_patch_into_files():
    """Test splitting a multi-file patch."""
    patch_content = """--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    return "hello"
 
--- a/file2.py
+++ b/file2.py
@@ -1,3 +1,4 @@
 def world():
     print("World")
+    return "world"
"""
    
    file_diffs = split_patch_into_files(patch_content)
    
    assert len(file_diffs) == 2
    assert "file1.py" in file_diffs
    assert "file2.py" in file_diffs
    assert '+    return "hello"' in file_diffs["file1.py"]
    assert '+    return "world"' in file_diffs["file2.py"]


def test_analyze_diff():
    """Test diff analysis."""
    diff_content = """--- a/example.py
+++ b/example.py
@@ -1,5 +1,7 @@
 def hello():
     print("Hello")
+    # TODO: add more greetings
 
-def world():
-    print("World")
+def world():
+    print("World!")
+    return "world"
"""
    
    analysis = analyze_diff(diff_content)
    
    assert "stats" in analysis
    assert "patterns" in analysis
    assert "complexity" in analysis
    
    stats = analysis["stats"]
    assert stats["lines_added"] > 0
    assert stats["lines_removed"] > 0
    assert stats["hunks"] > 0
    
    patterns = analysis["patterns"]
    assert patterns["comments_added"] > 0
    assert len(patterns["potential_issues"]) > 0  # Should detect TODO


def test_generate_context_diff():
    """Test generating a context diff."""
    original = "line1\nline2\nline3\n"
    new = "line1\nline2 modified\nline3\n"
    
    diff_content, stats = generate_diff(original, new, DiffFormat.CONTEXT)
    
    assert "***" in diff_content
    assert "---" in diff_content
    # Context diffs show modifications as both removal and addition
    assert stats.lines_modified > 0
    assert stats.hunks > 0


def test_generate_ndiff():
    """Test generating an ndiff."""
    original = "line1\nline2\nline3\n"
    new = "line1\nline2 modified\nline3\n"
    
    diff_content, stats = generate_diff(original, new, DiffFormat.NDIFF)
    
    assert "- line2" in diff_content
    assert "+ line2 modified" in diff_content
    assert stats.lines_added > 0
    assert stats.lines_removed > 0


def test_apply_diff_invalid_format():
    """Test applying an invalid diff format."""
    original = "test content"
    invalid_diff = "not a valid diff"
    
    # Should handle gracefully and return original content
    new_content, lines_applied = apply_unified_diff(original, invalid_diff)
    
    assert new_content == original
    assert lines_applied == 0


def test_apply_diff_context_mismatch():
    """Test applying a diff with context mismatch."""
    original = """def hello():
    print("Hello")
"""
    
    # Diff expects different content
    diff_content = """--- a/example.py
+++ b/example.py
@@ -1,2 +1,3 @@
 def goodbye():
     print("Goodbye")
+    return "goodbye"
"""
    
    with pytest.raises(ValueError, match="Context mismatch"):
        apply_unified_diff(original, diff_content) 
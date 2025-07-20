# tests/unit/test_kb_path.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for KB path utilities."""

import pytest
from typing import Optional

from cmcp.kb.path import PathComponents, PartialPathComponents

# Define expected output structure for fix_path tests for clarity
# (scheme, main_path_part, fragment, extension)
FixPathOutput = tuple[Optional[str], str, Optional[str], Optional[str]]

# --- Tests for PartialPathComponents.fix_path ---

@pytest.mark.parametrize("path_input, expected_output", [
    # --- Standard Paths (No Fragment, No Heuristic Trigger) ---
    ("ns/coll/name",         (None, "ns/coll/name", None, None)),
    ("kb://ns/coll/name",    ("kb", "ns/coll/name", None, None)),
    ("ns/coll/name.txt",     (None, "ns/coll/name.txt", None, None)), # < 4 parts, no heuristic
    ("kb://ns/coll/name.txt",("kb", "ns/coll/name.txt", None, None)), # < 4 parts, no heuristic
    ("ns/name.txt",          (None, "ns/name.txt", None, None)),     # < 4 parts, no heuristic
    ("ns/coll/config.v1",    (None, "ns/coll/config.v1", None, None)), # < 4 parts, no heuristic
    ("ns/coll/name_no_ext",  (None, "ns/coll/name_no_ext", None, None)),
    # Test non-matching extension-like suffix (should not be split)
    ("ns/coll/archive.tar.gz",(None, "ns/coll/archive.tar.gz", None, None)),
    ("ns/coll/item.1234567",(None, "ns/coll/item.1234567", None, None)), # Too long suffix
    ("ns/coll/.config",      (None, "ns/coll/.config", None, None)),    # Leading dot name

    # --- Explicit Fragments (#) ---
    ("ns/coll/name#frag",          (None, "ns/coll/name", "frag", None)),
    ("kb://ns/coll/name#frag",     ("kb", "ns/coll/name", "frag", None)),
    ("ns/coll/name.txt#frag",      (None, "ns/coll/name.txt", "frag", None)), # Main name keeps ext
    ("ns/coll/name#frag.txt",      (None, "ns/coll/name", "frag", "txt")), # Fragment has ext
    ("ns/coll/name#frag.longext",  (None, "ns/coll/name", "frag.longext", None)), # Non-matching suffix on frag
    ("ns/coll/name#.git",          (None, "ns/coll/name", ".git", None)), # Fragment starting with dot
    ("ns/coll/name#frag.",         (None, "ns/coll/name", "frag.", None)), # Fragment ending with dot
    ("kb://ns/coll/name.json#section",("kb", "ns/coll/name.json", "section", None)),

    # --- Implicit Fragment Heuristic (No #, >= 4 parts, last is base.ext) ---
    ("ns/coll/name/frag.txt",      (None, "ns/coll/name", "frag", "txt")), # Basic case
    ("kb://ns/coll/name/frag.txt", ("kb", "ns/coll/name", "frag", "txt")),
    ("ns/coll/sub/name/frag.md",   (None, "ns/coll/sub/name", "frag", "md")), # With subcollection
    ("ns/coll/name/frag_no_ext",   (None, "ns/coll/name/frag_no_ext", None, None)), # Heuristic FAILS (last has no ext)
    ("ns/coll/name/config.v1",     (None, "ns/coll/name/config.v1", None, None)), # Heuristic FAILS (ext pattern mismatch)
    ("ns/coll/name/archive.tar.gz",(None, "ns/coll/name/archive.tar.gz", None, None)), # Heuristic FAILS (ext pattern mismatch)

    # --- Edge Cases ---
    ("",                       (None, "", None, None)),
    ("/",                      (None, "", None, None)),
    ("//",                     (None, "", None, None)),
    ("kb://",                  ("kb", "", None, None)),
    ("kb:///",                 ("kb", "", None, None)),
    ("/ns/coll/name",          (None, "ns/coll/name", None, None)), # Leading slash removed
    ("ns/coll/name/",          (None, "ns/coll/name", None, None)), # Trailing slash handled by split
    ("ns//coll/name",          (None, "ns/coll/name", None, None)), # Empty segment handled by split
    ("#frag",                  (None, "", "frag", None)), # Only fragment
    ("#frag.txt",              (None, "", "frag", "txt")), # Only fragment with ext
    ("kb://#frag",             ("kb", "", "frag", None)), # Scheme and fragment
    ("s3://bucket/key",        ("s3", "bucket/key", None, None)), # Other schemes
])
def test_fix_path(path_input: str, expected_output: FixPathOutput):
    """Test the fix_path utility function for various scenarios."""
    assert PartialPathComponents.fix_path(path_input) == expected_output

# --- Tests for PartialPathComponents.parse_path ---

# Define expected structure for parse_path tests
ExpectedPartial = dict[str, Optional[str]]

@pytest.mark.parametrize("path_input, expected_components", [
    # --- Standard Paths ---
    ("ns/coll/name",
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name", "fragment": None, "extension": None}),
    ("kb://ns/coll/name",
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": None, "extension": None}),
    ("ns/coll/name.txt", # Name includes extension
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name.txt", "fragment": None, "extension": None}),
    ("ns/coll/sub/name.json", # Subcollection, name includes extension
     {"scheme": None, "namespace": "ns", "collection": "coll/sub", "name": "name.json", "fragment": None, "extension": None}),
    ("ns/name.with.dots", # Two segments, name includes dots
     {"scheme": None, "namespace": "ns", "collection": None, "name": "name.with.dots", "fragment": None, "extension": None}),
    ("ns", # Single segment -> namespace
     {"scheme": None, "namespace": "ns", "collection": None, "name": None, "fragment": None, "extension": None}),
    ("kb://single_name", # Single segment after scheme -> name
     {"scheme": "kb", "namespace": None, "collection": None, "name": "single_name", "fragment": None, "extension": None}),
    ("single_name.txt", # Single segment with ext -> name
     {"scheme": None, "namespace": None, "collection": None, "name": "single_name.txt", "fragment": None, "extension": None}),

    # --- Explicit Fragments ---
    ("ns/coll/name#frag",
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": None}),
    ("ns/coll/name.txt#frag", # Name keeps ext
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name.txt", "fragment": "frag", "extension": None}),
    ("kb://ns/coll/name#frag.txt", # Fragment has ext
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": "txt"}),
    ("ns/coll/name#frag.v1", # Fragment has non-matching ext-like part
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag.v1", "extension": None}),

    # --- Implicit Fragments (Heuristic Applied) ---
    ("ns/coll/name/frag.txt",
     {"scheme": None, "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": "txt"}),
    ("kb://ns/coll/sub/name/frag.md",
     {"scheme": "kb", "namespace": "ns", "collection": "coll/sub", "name": "name", "fragment": "frag", "extension": "md"}),

    # --- Implicit Fragments (Heuristic NOT Applied) ---
    ("ns/coll/name/frag_no_ext", # Name includes last part
     {"scheme": None, "namespace": "ns", "collection": "coll/name", "name": "frag_no_ext", "fragment": None, "extension": None}),
    ("ns/coll/name/config.v1", # Name includes last part
     {"scheme": None, "namespace": "ns", "collection": "coll/name", "name": "config.v1", "fragment": None, "extension": None}),

    # --- Edge Cases ---
    ("",
     {"scheme": None, "namespace": None, "collection": None, "name": None, "fragment": None, "extension": None}),
    ("kb://",
     {"scheme": "kb", "namespace": None, "collection": None, "name": None, "fragment": None, "extension": None}),
    ("#frag",
     {"scheme": None, "namespace": None, "collection": None, "name": None, "fragment": "frag", "extension": None}),
    ("#frag.txt",
     {"scheme": None, "namespace": None, "collection": None, "name": None, "fragment": "frag", "extension": "txt"}),
    ("kb://#frag.txt",
     {"scheme": "kb", "namespace": None, "collection": None, "name": None, "fragment": "frag", "extension": "txt"}),
])
def test_partial_parse_path_valid(path_input: str, expected_components: ExpectedPartial):
    """Test PartialPathComponents.parse_path assigns components correctly."""
    components = PartialPathComponents.parse_path(path_input)
    assert components.scheme == expected_components["scheme"], f"scheme mismatch for {path_input}"
    assert components.namespace == expected_components["namespace"], f"namespace mismatch for {path_input}"
    assert components.collection == expected_components["collection"], f"collection mismatch for {path_input}"
    assert components.name == expected_components["name"], f"name mismatch for {path_input}"
    assert components.fragment == expected_components["fragment"], f"fragment mismatch for {path_input}"
    assert components.extension == expected_components["extension"], f"extension mismatch for {path_input}"

@pytest.mark.parametrize("invalid_path", [
    "ns/bad=coll/name",
    "ns/coll/bad name",
    "bad ns/coll/name",
    "ns/coll/name#bad/frag",
    "kb://ns/coll/name#frag space",
    # Although fix_path handles empty segments, let's ensure validation catches them if pattern doesn't allow empty
    # Assuming VALID_COMPONENT_PATTERN = r'^[a-zA-Z0-9_\-\.]+$' which doesn't match empty string
    # "ns//name" # This case might be filtered by list comprehension in fix_path, test if needed
])
def test_partial_parse_path_invalid_chars(invalid_path: str):
    """Test PartialPathComponents.parse_path raises ValueError on invalid characters."""
    with pytest.raises(ValueError):
        PartialPathComponents.parse_path(invalid_path)

# --- Tests for PathComponents.parse_path ---

# Define expected structure for full parse_path tests
ExpectedFull = dict[str, Optional[str]] # Reuse partial structure, but know ns/coll/name are required

@pytest.mark.parametrize("path_input, expected_components", [
    # --- Valid Complete Paths ---
    ("ns/coll/name", # Default scheme
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": None, "extension": None}),
    ("kb://ns/coll/name.txt", # Name includes ext
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name.txt", "fragment": None, "extension": None}),
    ("s3://ns/coll/sub/name", # Different scheme, subcollection
     {"scheme": "s3", "namespace": "ns", "collection": "coll/sub", "name": "name", "fragment": None, "extension": None}),
    ("ns/coll/name#frag", # Default scheme, fragment
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": None}),
    ("ns/coll/name#frag.txt", # Default scheme, fragment with ext
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": "txt"}),
    # Implicit fragment case (results in complete path)
    ("ns/coll/name/frag.txt", # Default scheme
     {"scheme": "kb", "namespace": "ns", "collection": "coll", "name": "name", "fragment": "frag", "extension": "txt"}),
])
def test_full_parse_path_valid(path_input: str, expected_components: ExpectedFull):
    """Test PathComponents.parse_path succeeds for complete paths and defaults scheme."""
    components = PathComponents.parse_path(path_input)
    assert components.scheme == expected_components["scheme"], f"scheme mismatch for {path_input}"
    assert components.namespace == expected_components["namespace"], f"namespace mismatch for {path_input}"
    assert components.collection == expected_components["collection"], f"collection mismatch for {path_input}"
    assert components.name == expected_components["name"], f"name mismatch for {path_input}"
    assert components.fragment == expected_components["fragment"], f"fragment mismatch for {path_input}"
    assert components.extension == expected_components["extension"], f"extension mismatch for {path_input}"

@pytest.mark.parametrize("incomplete_path", [
    "ns/coll",          # Missing name
    "kb://ns/coll",     # Missing name
    "ns",               # Missing collection, name
    "kb://ns",          # Missing collection, name
    "ns/name.txt",      # Missing collection (parsed as ns/name)
    "kb://ns/name.txt", # Missing collection (parsed as ns/name)
    "kb://",            # Missing ns, coll, name
    "",                 # Missing ns, coll, name
    "#frag",            # Missing ns, coll, name
])
def test_full_parse_path_incomplete(incomplete_path: str):
    """Test PathComponents.parse_path raises ValueError for incomplete paths."""
    with pytest.raises(ValueError):
        PathComponents.parse_path(incomplete_path)

# --- Test properties ---

@pytest.mark.parametrize("path_input, expected_path_prop", [
    ("ns/coll/name", "ns/coll/name"),
    ("kb://ns/coll/name.txt", "ns/coll/name.txt"),
    ("ns/coll/sub/name", "ns/coll/sub/name"),
    ("ns/coll/name#frag", "ns/coll/name"), # Fragment ignored
    ("ns/coll/name/frag.txt", "ns/coll/name"), # Implicit fragment ignored
    ("ns/name.txt", "ns/name.txt"),
    ("single_name.txt", "single_name.txt"),
    ("ns", "ns"), # Partial
    ("kb://", ""), # Partial, empty path part
    ("#frag", ""), # Partial, empty path part
])
def test_path_property(path_input, expected_path_prop):
    """Test the .path property reconstructs the main path correctly."""
    comp = PartialPathComponents.parse_path(path_input)
    assert comp.path == expected_path_prop

@pytest.mark.parametrize("path_input, expected_urn_prop", [
    # Using PathComponents to test default scheme + reconstruction
    ("ns/coll/name", "kb://ns/coll/name"),
    ("ns/coll/name.txt", "kb://ns/coll/name.txt"),
    ("kb://ns/coll/name", "kb://ns/coll/name"),
    ("s3://ns/coll/name.json", "s3://ns/coll/name.json"),
    ("ns/coll/name#frag", "kb://ns/coll/name#frag"),
    ("ns/coll/name#frag.txt", "kb://ns/coll/name#frag.txt"), # Extension comes from fragment part
    ("ns/coll/name#frag.v1", "kb://ns/coll/name#frag.v1"), # Non-matching ext stays with fragment
    ("ns/coll/name/frag.txt", "kb://ns/coll/name#frag.txt"), # Implicit fragment
    # Using PartialPathComponents for partial paths
    ("ns/coll", "kb://ns/coll"), # Default scheme applied by property if None
    ("ns", "kb://ns"),
    ("s3://bucket", "s3://bucket"),
    ("kb://", "kb://"), # Scheme only
    ("#frag", "kb://#frag"), # Default scheme + fragment only
    ("s3://#frag.cfg", "s3://#frag.cfg"), # Scheme + fragment only
])
def test_uri_property(path_input, expected_uri_prop):
    """Test the .uri property reconstructs the URI correctly."""
    # Use PathComponents if input is complete to test default scheme properly
    try:
        comp = PathComponents.parse_path(path_input)
    except ValueError: # Input was incomplete, use PartialPathComponents
        comp = PartialPathComponents.parse_path(path_input)
    assert comp.uri == expected_uri_prop

# --- Test get_fragment_name method ---

@pytest.mark.parametrize("path_input, args, expected_filename", [
    # Case 1: Explicit fragment with extension
    ("ns/coll/name#frag.md", {}, "content.frag.md"),
    ("ns/coll/name#frag.md", {"prefix": "meta"}, "meta.frag.md"),
    ("ns/coll/name#frag.md", {"ext": "txt"}, "content.frag.md"), # Parsed ext takes priority
    ("ns/coll/name#frag.md", {"prefix": None}, "frag.md"),

    # Case 2: Explicit fragment without extension
    ("ns/coll/name#frag", {}, "content.frag.txt"), # Uses default ext
    ("ns/coll/name#frag", {"ext": "json"}, "content.frag.json"),
    ("ns/coll/name#frag", {"default": "idx"}, "content.frag.txt"), # Default frag id ignored

    # Case 3: Implicit fragment with extension
    ("ns/coll/name/frag.py", {}, "content.frag.py"),
    ("ns/coll/name/frag.py", {"ext": "txt"}, "content.frag.py"), # Parsed ext takes priority

    # Case 4: No fragment (neither explicit nor implicit)
    ("ns/coll/name.txt", {}, "content.0000.txt"), # Uses default fragment id and ext
    ("ns/coll/name", {"default_fragment": "main"}, "content.main.txt"),
    ("ns/coll/name", {"ext": "yaml"}, "content.0000.yaml"),
    ("ns/coll/name", {"default_fragment": None, "ext": "dat"}, "content..dat"), # Empty fragment id
])
def test_get_fragment_name(path_input: str, args: dict, expected_filename: str):
    """Test the get_fragment_name method generates filenames correctly."""
    comp = PartialPathComponents.parse_path(path_input)
    assert comp.get_fragment_name(**args) == expected_filename
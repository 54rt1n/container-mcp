# tests/unit/debug_path.py

"""Debug script for KB path parsing."""

import sys
import os
# Add the project root to the path so we can import from cmcp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from cmcp.kb.path import PathComponents, PartialPathComponents

def debug_path(path):
    """Debug path parsing."""
    print(f"Testing path: {path}")
    
    # Test fix_path
    result = PartialPathComponents.fix_path(path)
    print(f"fix_path result: {result}")
    
    # Test parse_path for PartialPathComponents
    partial = PartialPathComponents.parse_path(path)
    print(f"PartialPathComponents: {partial}")
    
    # Test parse_path for PathComponents
    try:
        full = PathComponents.parse_path(path)
        print(f"PathComponents: {full}")
    except ValueError as e:
        print(f"Error parsing as PathComponents: {e}")

if __name__ == "__main__":
    debug_path("kb://ns/coll/name")
    print("\n---\n")
    debug_path("kb://ns/coll/name#frag")
    print("\n---\n")
    debug_path("ns/coll/name#frag.txt") 
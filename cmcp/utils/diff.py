# cmcp/utils/diff.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Core diff utilities for text processing."""

import re
import difflib
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


class DiffFormat(Enum):
    """Supported diff formats."""
    UNIFIED = "unified"
    CONTEXT = "context"
    NDIFF = "ndiff"


@dataclass
class DiffStats:
    """Statistics about a diff."""
    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0
    hunks: int = 0
    
    @property
    def net_change(self) -> int:
        """Calculate net line change."""
        return self.lines_added - self.lines_removed


class Hunk(NamedTuple):
    """Represents a single diff hunk."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]


def generate_diff(
    original_content: str,
    new_content: str,
    diff_format: DiffFormat = DiffFormat.UNIFIED,
    context_lines: int = 3,
    from_file: str = "a/file",
    to_file: str = "b/file"
) -> Tuple[str, DiffStats]:
    """Generate a diff between two text contents.
    
    Args:
        original_content: Original text content
        new_content: New text content
        diff_format: Format of the diff to generate
        context_lines: Number of context lines for unified/context diffs
        from_file: Label for the original file
        to_file: Label for the new file
        
    Returns:
        Tuple of (diff_content, diff_stats)
    """
    # Split content into lines
    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    # Generate diff based on format
    if diff_format == DiffFormat.UNIFIED:
        diff_lines = list(difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=from_file,
            tofile=to_file,
            n=context_lines
        ))
    elif diff_format == DiffFormat.CONTEXT:
        diff_lines = list(difflib.context_diff(
            original_lines,
            new_lines,
            fromfile=from_file,
            tofile=to_file,
            n=context_lines
        ))
    elif diff_format == DiffFormat.NDIFF:
        diff_lines = list(difflib.ndiff(original_lines, new_lines))
    else:
        raise ValueError(f"Unsupported diff format: {diff_format}")
    
    diff_content = "".join(diff_lines)
    stats = _calculate_stats(diff_lines, diff_format)
    
    return diff_content, stats


def apply_unified_diff(original_content: str, diff_content: str) -> Tuple[str, int]:
    """Apply a unified diff to content.
    
    Args:
        original_content: Original content to modify
        diff_content: Unified diff to apply
        
    Returns:
        Tuple of (new_content, lines_applied)
        
    Raises:
        ValueError: If diff format is invalid or cannot be applied
    """
    # Parse the diff
    hunks = _parse_unified_diff(diff_content)
    
    if not hunks:
        logger.warning("No hunks found in diff")
        return original_content, 0
    
    # Apply each hunk
    lines = original_content.splitlines()
    lines_applied = 0
    
    # Sort hunks by line number (reverse order for proper application)
    sorted_hunks = sorted(hunks, key=lambda h: h.old_start, reverse=True)
    
    for hunk in sorted_hunks:
        try:
            applied = _apply_hunk(lines, hunk)
            lines_applied += applied
        except Exception as e:
            logger.error(f"Failed to apply hunk at line {hunk.old_start}: {e}")
            raise ValueError(f"Failed to apply hunk: {e}")
    
    return "\n".join(lines), lines_applied


def split_patch_into_files(patch_content: str) -> Dict[str, str]:
    """Split a patch file into individual file diffs.
    
    Args:
        patch_content: Content of the patch file
        
    Returns:
        Dictionary mapping file paths to their diff content
    """
    file_diffs = {}
    lines = patch_content.splitlines()
    
    current_file = None
    current_diff_lines = []
    
    for line in lines:
        if line.startswith('--- '):
            # Start of a new file diff
            if current_file and current_diff_lines:
                file_diffs[current_file] = "\n".join(current_diff_lines)
            
            # Extract filename (remove a/ prefix if present)
            filename = line[4:].strip()
            if filename.startswith('a/'):
                filename = filename[2:]
            current_file = filename
            current_diff_lines = [line]
        elif current_file:
            current_diff_lines.append(line)
    
    # Add the last file
    if current_file and current_diff_lines:
        file_diffs[current_file] = "\n".join(current_diff_lines)
    
    return file_diffs


def analyze_diff(diff_content: str) -> Dict[str, Any]:
    """Analyze a diff for insights and patterns.
    
    Args:
        diff_content: The diff content to analyze
        
    Returns:
        Dictionary with analysis results
    """
    lines = diff_content.splitlines()
    
    stats = DiffStats()
    patterns = {
        "imports_changed": False,
        "comments_added": 0,
        "comments_removed": 0,
        "potential_issues": []
    }
    
    for line in lines:
        if line.startswith('@@'):
            stats.hunks += 1
        elif line.startswith('+') and not line.startswith('+++'):
            stats.lines_added += 1
            _analyze_line_patterns(line, patterns, True)
        elif line.startswith('-') and not line.startswith('---'):
            stats.lines_removed += 1
            _analyze_line_patterns(line, patterns, False)
    
    stats.lines_modified = min(stats.lines_added, stats.lines_removed)
    
    # Calculate complexity
    complexity_score = stats.lines_added * 0.5 + stats.lines_removed * 0.3 + stats.hunks * 2
    if complexity_score < 10:
        complexity_level = "low"
    elif complexity_score < 30:
        complexity_level = "medium"
    else:
        complexity_level = "high"
    
    return {
        "stats": {
            "lines_added": stats.lines_added,
            "lines_removed": stats.lines_removed,
            "lines_modified": stats.lines_modified,
            "net_change": stats.net_change,
            "hunks": stats.hunks
        },
        "patterns": patterns,
        "complexity": {
            "score": round(complexity_score, 1),
            "level": complexity_level
        }
    }


# Private helper functions
def _calculate_stats(diff_lines: List[str], diff_format: DiffFormat) -> DiffStats:
    """Calculate statistics from diff lines."""
    stats = DiffStats()
    
    if diff_format == DiffFormat.UNIFIED:
        for line in diff_lines:
            if line.startswith('@@'):
                stats.hunks += 1
            elif line.startswith('+') and not line.startswith('+++'):
                stats.lines_added += 1
            elif line.startswith('-') and not line.startswith('---'):
                stats.lines_removed += 1
    elif diff_format == DiffFormat.CONTEXT:
        in_old_section = False
        in_new_section = False
        for line in diff_lines:
            if line.startswith('***************'):
                stats.hunks += 1
            elif line.startswith('*** '):
                in_old_section = True
                in_new_section = False
            elif line.startswith('--- '):
                in_old_section = False
                in_new_section = True
            elif line.startswith('! '):
                # Modified line
                if in_old_section:
                    stats.lines_removed += 1
                elif in_new_section:
                    stats.lines_added += 1
            elif line.startswith('+ '):
                # Added line (in new section)
                if in_new_section:
                    stats.lines_added += 1
            elif line.startswith('- '):
                # Removed line (in old section)
                if in_old_section:
                    stats.lines_removed += 1
    elif diff_format == DiffFormat.NDIFF:
        for line in diff_lines:
            if line.startswith('+ '):
                stats.lines_added += 1
            elif line.startswith('- '):
                stats.lines_removed += 1
    
    stats.lines_modified = min(stats.lines_added, stats.lines_removed)
    return stats


def _parse_unified_diff(diff_content: str) -> List[Hunk]:
    """Parse a unified diff into hunks."""
    lines = diff_content.splitlines()
    hunks = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith('@@'):
            # Parse hunk header: @@ -start,count +start,count @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match:
                logger.warning(f"Invalid hunk header: {line}")
                i += 1
                continue
            
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            
            # Collect hunk lines
            hunk_lines = []
            j = i + 1
            while j < len(lines):
                if lines[j].startswith('@@'):
                    break
                if lines[j].startswith('\\'):  # "\ No newline at end of file"
                    j += 1
                    continue
                hunk_lines.append(lines[j])
                j += 1
            
            hunks.append(Hunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=hunk_lines
            ))
            i = j
        else:
            i += 1
    
    return hunks


def _apply_hunk(lines: List[str], hunk: Hunk) -> int:
    """Apply a single hunk to the lines."""
    lines_applied = 0
    start_line = hunk.old_start - 1  # Convert to 0-based indexing
    current_line = start_line
    
    # Track changes to apply
    deletions = []
    additions = []
    
    # Process hunk lines
    for hunk_line in hunk.lines:
        if hunk_line.startswith(' '):
            # Context line - verify it matches
            expected = hunk_line[1:]
            if current_line >= len(lines):
                raise ValueError(f"Context line {current_line + 1} beyond file end")
            if lines[current_line] != expected:
                raise ValueError(f"Context mismatch at line {current_line + 1}")
            current_line += 1
        elif hunk_line.startswith('-'):
            # Deletion
            expected = hunk_line[1:]
            if current_line >= len(lines):
                raise ValueError(f"Deletion line {current_line + 1} beyond file end")
            if lines[current_line] != expected:
                raise ValueError(f"Deletion mismatch at line {current_line + 1}")
            deletions.append(current_line)
            current_line += 1
        elif hunk_line.startswith('+'):
            # Addition
            content = hunk_line[1:]
            additions.append((current_line, content))
    
    # Apply deletions in reverse order to maintain line numbers
    for line_num in reversed(deletions):
        if line_num < len(lines):
            del lines[line_num]
            lines_applied += 1
    
    # Apply additions (adjust for deletions)
    offset = len(deletions)
    for line_num, content in additions:
        adjusted_line = line_num - offset
        if adjusted_line < 0:
            adjusted_line = 0
        elif adjusted_line > len(lines):
            adjusted_line = len(lines)
        lines.insert(adjusted_line, content)
        lines_applied += 1
    
    return lines_applied


def _analyze_line_patterns(line: str, patterns: Dict[str, Any], is_addition: bool):
    """Analyze patterns in a diff line."""
    content = line[1:].strip()
    
    # Import changes
    if any(keyword in content for keyword in ['import ', 'from ', '#include', 'require']):
        patterns["imports_changed"] = True
    
    # Comment changes
    if any(content.strip().startswith(marker) for marker in ['#', '//', '/*', '*', '<!--']):
        if is_addition:
            patterns["comments_added"] += 1
        else:
            patterns["comments_removed"] += 1
    
    # Potential issues
    issue_keywords = ['todo', 'fixme', 'hack', 'xxx', 'bug', 'temporary']
    if any(keyword in content.lower() for keyword in issue_keywords):
        patterns["potential_issues"].append(line.strip())

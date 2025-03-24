# cmcp/kb/path.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Path utilities for knowledge base."""

import re
from typing import NamedTuple, Optional

class PartialPathComponents(NamedTuple):
    """Components of a knowledge base path."""
    scheme: Optional[str] = None
    namespace: Optional[str] = None
    collection: Optional[str] = None
    name: Optional[str] = None
    fragment: Optional[str] = None
    extension: Optional[str] = None
    
    @property
    def path(self) -> str:
        """Get the path representation (namespace/collection/name)."""
        parts = []
        if self.namespace:
            parts.append(self.namespace)
        if self.collection:
            parts.append(self.collection)
        if self.name:
            parts.append(self.name)
        if self.fragment and self.extension:
            parts.append(f"{self.fragment}.{self.extension}")
        elif self.fragment:
            parts.append(f"{self.fragment}.txt")
        path_str = "/".join(parts)
        return path_str

    @property
    def urn(self) -> str:
        """Get the URN representation (scheme://namespace/collection/name)."""
        scheme = self.scheme or "kb"
        result = f"{scheme}://{self.path}"
        if self.fragment and "#" not in result:
            result = f"{result}#{self.fragment}"
            if self.extension:
                result = f"{result}.{self.extension}"
        return result

    def get_fragment_name(self, prefix: Optional[str] = "content", default: Optional[str] = "0000", ext: str = "txt") -> str:
        """Get the fragment name (name#fragment)."""
        prefix = f"{prefix}." if prefix is not None else ""
        fragment = self.fragment or default or ""
        ext = self.extension or ext
        return f"{prefix}{fragment}.{ext}"

    @classmethod
    def fix_path(cls, path: str) -> tuple[Optional[str], str, Optional[str], Optional[str]]:
        """Remove any scheme prefix from path if present and return components.
        
        Args:
            path: The path to fix
            
        Returns:
            Tuple of (scheme, clean_path, fragment)
        """
        if not path:
            return None, path, None
        
        # Extract fragment if present
        fragment = None
        extension = None
        if "#" in path:
            path, fragment = path.split("#", 1)
            if "." in fragment:
                fragment, extension = fragment.split(".", 1)
        
        # Check for scheme prefix (like "kb://", "s3://", etc.)
        scheme_match = re.match(r'^([a-zA-Z][a-zA-Z0-9+.-]*)://', path)
        if scheme_match:
            scheme = scheme_match.group(1)
            clean_path = path[len(scheme) + 3:]
        elif path.startswith("kb:"):
            # Legacy support for "kb:" prefix without double slash
            scheme = "kb"
            clean_path = path[3:]
        else:
            scheme = None
            clean_path = path
            
        # Remove any leading slashes to prevent accessing the root filesystem
        while clean_path and clean_path.startswith("/"):
            clean_path = clean_path[1:]
            
        return scheme, clean_path, fragment, extension
    
    @classmethod
    def parse_path(cls, path: str) -> 'PartialPathComponents':
        """Parse a knowledge base path into its components.
        
        Args:
            path: Path that can be in various formats including:
                  "scheme://namespace/collection/name"
                  "namespace/collection/name"
                  "scheme://namespace/collection"
                  "namespace/collection"
                  Any of the above with optional "#fragment"
            
        Returns:
            PartialPathComponents with scheme, namespace, collection, name and fragment as available
            
        Raises:
            ValueError: If path format is invalid
        """
        if not path:
            return cls()
            
        # Extract scheme, clean path and fragment
        scheme, clean_path, fragment, extension = cls.fix_path(path)
        
        # Remove leading/trailing slashes
        clean_path = clean_path.strip("/")
        
        if not clean_path:
            return cls(scheme=scheme, fragment=fragment, extension=extension)
            
        # Split path into parts
        parts = clean_path.split("/")
        
        # Handle different path lengths
        if len(parts) == 1:
            # Just namespace
            namespace = parts[0]
            collection = None
            name = None
        elif len(parts) == 2:
            # namespace/collection
            namespace, collection = parts
            name = None
        else:
            # namespace/collection[/subcollection]*/name
            namespace = parts[0]
            name = parts[-1]
            collection = "/".join(parts[1:-1])  # Everything between namespace and name
        
        # Validate components that are present
        valid_pattern = r'^[\w\-\.]+$'  # \w matches alphanumeric and underscore
        
        if namespace and not re.match(valid_pattern, namespace):
            raise ValueError(
                f"Invalid namespace format: {namespace}. "
                "Namespace must contain only alphanumeric characters, hyphens, underscores, and dots."
            )
        
        # For collection, allow slashes for subcollections but validate each part
        if collection:
            collection_parts = collection.split('/')
            for part in collection_parts:
                if not re.match(valid_pattern, part):
                    raise ValueError(
                        f"Invalid collection part: {part}. "
                        "Collection parts must contain only alphanumeric characters, hyphens, underscores, and dots."
                    )
        
        if name and not re.match(valid_pattern, name):
            raise ValueError(
                f"Invalid name format: {name}. "
                "Name must contain only alphanumeric characters, hyphens, underscores, and dots."
            )
        
        # Validate fragment if present
        if fragment and not re.match(r'^[\w\-\.%]+$', fragment):
            raise ValueError(
                f"Invalid fragment format: {fragment}. "
                "Fragment must contain only alphanumeric characters, hyphens, underscores, dots, and percent signs."
            )
        
        return cls(scheme=scheme, namespace=namespace, collection=collection, name=name, fragment=fragment, extension=extension)

class PathComponents(PartialPathComponents):
    """Components of a knowledge base path."""
    scheme: str
    namespace: str
    collection: str
    name: str
    fragment: Optional[str] = None
    extension: Optional[str] = None
    
    @classmethod
    def parse_path(cls, path: str) -> 'PathComponents':
        """Parse a knowledge base path into its components.
        
        Args:
            path: Path in format "namespace/collection[/subcollection]*/name"
                 Can optionally include a fragment with "#fragment"
            
        Returns:
            PathComponents with namespace, collection, name and optional fragment
            
        Raises:
            ValueError: If path format is invalid
        """
        self = super().parse_path(path)
        if self.name is None:
            raise ValueError("Path must contain a name")
        if self.namespace is None:
            raise ValueError("Path must contain a namespace")
        if self.collection is None:
            raise ValueError("Path must contain a collection")
        if self.scheme is None:
            # Use KB as default scheme
            return cls(
                scheme="kb", 
                namespace=self.namespace, 
                collection=self.collection, 
                name=self.name, 
                fragment=self.fragment
            )
        return self
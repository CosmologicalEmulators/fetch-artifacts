"""
fetch_artifacts: Julia-style Artifacts system for Python.

This package provides a TOML-based artifact management system similar to Julia's
Pkg.Artifacts, allowing declarative specification of downloadable data artifacts
with automatic caching and checksum verification.

Usage:
    from fetch_artifacts import artifact, load_artifacts

    # Get path to artifact (downloads if needed)
    path = artifact("MyArtifact")

    # Or load artifacts from a specific TOML file
    artifacts = load_artifacts("path/to/Artifacts.toml")
    path = artifacts["MyArtifact"]
"""

from .artifacts import (
    artifact,
    artifact_path,
    artifact_exists,
    ensure_artifact,
    load_artifacts,
    ArtifactManager,
    get_artifacts_toml,
    set_cache_dir,
    get_cache_dir,
    clear_artifact_cache,
)

from .create import (
    add_artifact,
    bind_artifact,
    unbind_artifact,
    create_artifact,
    add_download_source,
    compute_sha256,
    compute_git_tree_sha1,
    query_artifact_info,
)

__version__ = "0.1.0"

__all__ = [
    # Artifact access
    "artifact",
    "artifact_path",
    "artifact_exists",
    "ensure_artifact",
    "load_artifacts",
    "ArtifactManager",
    "get_artifacts_toml",
    # Cache management
    "set_cache_dir",
    "get_cache_dir",
    "clear_artifact_cache",
    # Artifact creation (similar to Julia's ArtifactUtils)
    "add_artifact",         # Main function: download URL, compute hashes, add to TOML
    "bind_artifact",        # Low-level: add artifact with known hashes
    "unbind_artifact",      # Remove artifact from TOML
    "create_artifact",      # Create archive from local directory
    "add_download_source",  # Add mirror URL to existing artifact
    "compute_sha256",
    "compute_git_tree_sha1",
    "query_artifact_info",
]

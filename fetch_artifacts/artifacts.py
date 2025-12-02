"""
Core artifact management functionality.

This module implements Julia-style artifact management with TOML configuration,
automatic downloading, caching, and checksum verification.
"""

import hashlib
import os
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.error import URLError

from ._compat import tomllib
from .utils import download_file, extract_archive, get_extracted_root


# Global configuration
_cache_dir: Optional[Path] = None
_artifact_managers: Dict[str, "ArtifactManager"] = {}


@dataclass
class DownloadInfo:
    """Information about a download source for an artifact."""
    url: str
    sha256: str


@dataclass
class ArtifactEntry:
    """Represents a single artifact entry from Artifacts.toml."""
    name: str
    git_tree_sha1: Optional[str] = None
    lazy: bool = True  # NOTE: Currently not used - all artifacts are lazy-loaded
    downloads: List[DownloadInfo] = field(default_factory=list)

    # Platform-specific fields (optional)
    os: Optional[str] = None
    arch: Optional[str] = None

    # Extra metadata fields (description, has_noise, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "ArtifactEntry":
        """Create ArtifactEntry from TOML dictionary."""
        downloads = []
        if "download" in data:
            for dl in data["download"]:
                downloads.append(DownloadInfo(
                    url=dl["url"],
                    sha256=dl.get("sha256", "")
                ))

        # Collect extra metadata fields
        known_fields = {"git-tree-sha1", "lazy", "download", "os", "arch"}
        metadata = {k: v for k, v in data.items() if k not in known_fields}

        return cls(
            name=name,
            git_tree_sha1=data.get("git-tree-sha1"),
            lazy=data.get("lazy", True),
            downloads=downloads,
            os=data.get("os"),
            arch=data.get("arch"),
            metadata=metadata,
        )


class ArtifactManager:
    """
    Manages artifacts defined in an Artifacts.toml file.

    Similar to Julia's artifact system, this class handles:
    - Loading artifact definitions from TOML
    - Downloading artifacts on demand
    - Caching downloaded artifacts
    - Checksum verification

    Example Artifacts.toml format:

        [MyArtifact]
        git-tree-sha1 = "abc123..."
        lazy = true

            [[MyArtifact.download]]
            url = "https://example.com/data.tar.xz"
            sha256 = "def456..."

    Usage:
        manager = ArtifactManager("path/to/Artifacts.toml")
        path = manager["MyArtifact"]  # Downloads if needed, returns path
    """

    def __init__(
        self,
        toml_path: Union[str, Path],
        cache_dir: Optional[Union[str, Path]] = None,
        verbose: bool = False,
    ):
        """
        Initialize artifact manager.

        Parameters
        ----------
        toml_path : str or Path
            Path to Artifacts.toml file
        cache_dir : str or Path, optional
            Directory to cache artifacts. Defaults to ~/.fetch_artifacts/
        verbose : bool
            Whether to print progress messages
        """
        self.toml_path = Path(toml_path)
        self.verbose = verbose

        # Set cache directory
        if cache_dir is not None:
            self.cache_dir = Path(cache_dir)
        elif _cache_dir is not None:
            self.cache_dir = _cache_dir
        else:
            self.cache_dir = Path.home() / ".fetch_artifacts"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load artifacts from TOML
        self.artifacts: Dict[str, ArtifactEntry] = {}
        self._load_toml()

    def _load_toml(self):
        """Load artifact definitions from TOML file."""
        if tomllib is None:
            raise ImportError(
                "TOML parsing requires 'tomli' package for Python < 3.11. "
                "Install with: pip install tomli"
            )

        if not self.toml_path.exists():
            raise FileNotFoundError(f"Artifacts.toml not found: {self.toml_path}")

        with open(self.toml_path, "rb") as f:
            data = tomllib.load(f)

        for name, entry_data in data.items():
            # Handle both single entries and platform-specific arrays
            if isinstance(entry_data, list):
                # Platform-specific: pick first matching or first entry
                # For now, just use the first entry
                # TODO: Add platform selection logic
                entry_data = entry_data[0]

            self.artifacts[name] = ArtifactEntry.from_dict(name, entry_data)

    def __getitem__(self, name: str) -> Path:
        """Get path to artifact, downloading if necessary."""
        return self.get_path(name)

    def __contains__(self, name: str) -> bool:
        """Check if artifact is defined."""
        return name in self.artifacts

    def get_path(self, name: str, download: bool = True) -> Path:
        """
        Get the path to an artifact.

        Parameters
        ----------
        name : str
            Artifact name as defined in Artifacts.toml
        download : bool
            Whether to download if not cached (default: True)

        Returns
        -------
        Path
            Path to the artifact directory

        Raises
        ------
        KeyError
            If artifact is not defined in Artifacts.toml
        RuntimeError
            If artifact is not cached and download=False
        """
        if name not in self.artifacts:
            raise KeyError(
                f"Artifact '{name}' not found in {self.toml_path}. "
                f"Available: {list(self.artifacts.keys())}"
            )

        entry = self.artifacts[name]
        artifact_dir = self._get_artifact_dir(entry)

        if artifact_dir.exists() and self._is_valid_artifact(artifact_dir, entry):
            return artifact_dir

        if not download:
            raise RuntimeError(
                f"Artifact '{name}' is not cached and download=False"
            )

        # Download and extract
        return self._ensure_artifact(entry)

    def _get_artifact_dir(self, entry: ArtifactEntry) -> Path:
        """Get the cache directory for an artifact."""
        # Use git-tree-sha1 if available for content-addressable storage
        if entry.git_tree_sha1:
            return self.cache_dir / entry.git_tree_sha1
        else:
            # Fall back to name-based storage
            return self.cache_dir / entry.name

    def _is_valid_artifact(self, path: Path, entry: ArtifactEntry) -> bool:
        """Check if cached artifact is valid."""
        if not path.exists():
            return False

        # Check for marker file that indicates successful extraction
        marker = path / ".fetch_artifacts_complete"
        return marker.exists()

    def _ensure_artifact(self, entry: ArtifactEntry) -> Path:
        """Download and extract artifact if needed."""
        artifact_dir = self._get_artifact_dir(entry)

        if artifact_dir.exists() and self._is_valid_artifact(artifact_dir, entry):
            return artifact_dir

        if not entry.downloads:
            raise RuntimeError(
                f"Artifact '{entry.name}' has no download sources defined"
            )

        # Try each download source
        last_error = None
        for dl in entry.downloads:
            try:
                return self._download_and_extract(entry, dl, artifact_dir)
            except Exception as e:
                last_error = e
                if self.verbose:
                    print(f"Download failed from {dl.url}: {e}")
                continue

        raise RuntimeError(
            f"Failed to download artifact '{entry.name}' from all sources. "
            f"Last error: {last_error}"
        )

    def _download_and_extract(
        self,
        entry: ArtifactEntry,
        dl: DownloadInfo,
        artifact_dir: Path
    ) -> Path:
        """Download and extract a single artifact."""
        if self.verbose:
            print(f"Downloading artifact '{entry.name}' from {dl.url}...")

        # Create temporary file for download
        suffix = self._get_archive_suffix(dl.url)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Download with progress
            download_file(dl.url, tmp_path, verbose=self.verbose)

            # Verify checksum
            if dl.sha256:
                if self.verbose:
                    print("Verifying checksum...")
                if not self._verify_checksum(tmp_path, dl.sha256):
                    raise RuntimeError(
                        f"Checksum verification failed for {dl.url}"
                    )

            # Extract
            if self.verbose:
                print("Extracting...")

            # Clean existing directory
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)

            # Extract to temporary directory first
            with tempfile.TemporaryDirectory() as tmp_extract:
                tmp_extract_path = Path(tmp_extract)
                extract_archive(tmp_path, tmp_extract_path)

                # Find the root directory in the extracted content
                src_dir = get_extracted_root(tmp_extract_path)

                # Move to final location
                shutil.copytree(src_dir, artifact_dir)

            # Create completion marker
            marker = artifact_dir / ".fetch_artifacts_complete"
            marker.touch()

            if self.verbose:
                print(f"Artifact '{entry.name}' ready at: {artifact_dir}")

            return artifact_dir

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    def _get_archive_suffix(self, url: str) -> str:
        """Get archive suffix from URL."""
        # Strip query parameters before checking suffix
        url_without_query = url.split("?")[0]
        url_lower = url_without_query.lower()
        if url_lower.endswith(".tar.xz"):
            return ".tar.xz"
        elif url_lower.endswith(".tar.gz") or url_lower.endswith(".tgz"):
            return ".tar.gz"
        elif url_lower.endswith(".tar.bz2"):
            return ".tar.bz2"
        elif url_lower.endswith(".tar"):
            return ".tar"
        elif url_lower.endswith(".zip"):
            return ".zip"
        else:
            return ".tar.gz"  # Default

    def _verify_checksum(self, filepath: Path, expected_sha256: str) -> bool:
        """Verify SHA256 checksum of file."""
        from .create import compute_sha256
        actual = compute_sha256(filepath)
        return actual.lower() == expected_sha256.lower()

    def exists(self, name: str) -> bool:
        """Check if artifact exists in cache."""
        if name not in self.artifacts:
            return False
        entry = self.artifacts[name]
        artifact_dir = self._get_artifact_dir(entry)
        return self._is_valid_artifact(artifact_dir, entry)

    def clear(self, name: Optional[str] = None):
        """
        Clear cached artifacts.

        Parameters
        ----------
        name : str, optional
            Specific artifact to clear. If None, clears all.
        """
        if name is not None:
            if name in self.artifacts:
                entry = self.artifacts[name]
                artifact_dir = self._get_artifact_dir(entry)
                if artifact_dir.exists():
                    shutil.rmtree(artifact_dir)
                    if self.verbose:
                        print(f"Cleared artifact '{name}'")
        else:
            for artifact_name in self.artifacts:
                self.clear(artifact_name)


# Module-level functions for convenience

def get_cache_dir() -> Path:
    """Get the global artifact cache directory."""
    global _cache_dir
    if _cache_dir is None:
        return Path.home() / ".fetch_artifacts"
    return _cache_dir


def set_cache_dir(path: Union[str, Path]):
    """Set the global artifact cache directory."""
    global _cache_dir
    _cache_dir = Path(path)
    _cache_dir.mkdir(parents=True, exist_ok=True)


def get_artifacts_toml(search_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find Artifacts.toml file.

    Searches in the following order:
    1. Provided search_path (if given)
    2. Current working directory (Artifacts.toml or JuliaArtifacts.toml)

    Returns None if not found.
    """
    candidates = [
        Path(search_path) if search_path else None,
        Path.cwd() / "Artifacts.toml",
        Path.cwd() / "JuliaArtifacts.toml",  # Julia compatibility
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    return None


def load_artifacts(
    toml_path: Optional[Union[str, Path]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    verbose: bool = False,
) -> ArtifactManager:
    """
    Load artifacts from an Artifacts.toml file.

    Parameters
    ----------
    toml_path : str or Path, optional
        Path to Artifacts.toml. If None, searches automatically.
    cache_dir : str or Path, optional
        Cache directory for artifacts
    verbose : bool
        Whether to print progress messages

    Returns
    -------
    ArtifactManager
        Manager for the loaded artifacts
    """
    if toml_path is None:
        toml_path = get_artifacts_toml()
        if toml_path is None:
            raise FileNotFoundError(
                "Could not find Artifacts.toml. "
                "Provide path explicitly or create Artifacts.toml in your package."
            )

    toml_path = Path(toml_path)

    # Cache managers by path
    cache_key = str(toml_path.resolve())
    if cache_key not in _artifact_managers:
        _artifact_managers[cache_key] = ArtifactManager(
            toml_path, cache_dir=cache_dir, verbose=verbose
        )

    return _artifact_managers[cache_key]


def artifact(
    name: str,
    toml_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
) -> Path:
    """
    Get path to an artifact, downloading if necessary.

    This is the main convenience function, similar to Julia's artifact"name" macro.

    Parameters
    ----------
    name : str
        Artifact name as defined in Artifacts.toml
    toml_path : str or Path, optional
        Path to Artifacts.toml. If None, searches automatically.
    verbose : bool
        Whether to print progress messages

    Returns
    -------
    Path
        Path to the artifact directory

    Examples
    --------
    >>> from fetch_artifacts import artifact
    >>> path = artifact("MyDataset")
    >>> # Use the data at `path`
    """
    manager = load_artifacts(toml_path, verbose=verbose)
    return manager.get_path(name)


def artifact_exists(
    name: str,
    toml_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Check if artifact is already cached."""
    manager = load_artifacts(toml_path)
    return manager.exists(name)


def clear_artifact_cache(
    name: Optional[str] = None,
    toml_path: Optional[Union[str, Path]] = None,
):
    """
    Clear cached artifacts.

    Parameters
    ----------
    name : str, optional
        Specific artifact to clear. If None, clears all.
    toml_path : str or Path, optional
        Path to Artifacts.toml
    """
    manager = load_artifacts(toml_path)
    manager.clear(name)

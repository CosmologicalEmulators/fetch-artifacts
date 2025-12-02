"""
Functions for creating and binding artifacts to Artifacts.toml.

Similar to Julia's Pkg.Artifacts functions:
- bind_artifact!
- create_artifact
- unbind_artifact!
"""

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Use tomllib for reading, tomlkit for writing (preserves formatting)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

try:
    import tomlkit
except ImportError:
    tomlkit = None


def compute_sha256(filepath: Union[str, Path]) -> str:
    """
    Compute SHA256 hash of a file.

    Parameters
    ----------
    filepath : str or Path
        Path to the file

    Returns
    -------
    str
        Hexadecimal SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def compute_git_tree_sha1(directory: Union[str, Path]) -> str:
    """
    Compute git-tree-sha1 hash of a directory.

    This mimics Julia's Tar.tree_hash() which computes a hash
    of the directory contents that is stable across platforms.

    Parameters
    ----------
    directory : str or Path
        Path to the directory

    Returns
    -------
    str
        Hexadecimal git-tree-sha1 hash

    Note
    ----
    This requires git to be installed. Falls back to a simple
    content hash if git is not available.
    """
    directory = Path(directory)

    try:
        # Try to use git hash-object for true git-tree-sha1
        # This creates a temporary git repo to compute the hash
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Initialize a git repo
            subprocess.run(
                ["git", "init", "-q"],
                cwd=tmpdir,
                check=True,
                capture_output=True
            )

            # Copy directory contents
            dest = tmpdir / "content"
            shutil.copytree(directory, dest)

            # Add all files
            subprocess.run(
                ["git", "add", "-A"],
                cwd=tmpdir,
                check=True,
                capture_output=True
            )

            # Write tree and get hash
            result = subprocess.run(
                ["git", "write-tree"],
                cwd=tmpdir,
                check=True,
                capture_output=True,
                text=True
            )

            return result.stdout.strip()

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: compute simple content hash
        return _fallback_tree_hash(directory)


def _fallback_tree_hash(directory: Path) -> str:
    """Fallback tree hash when git is not available."""
    sha256_hash = hashlib.sha256()

    # Sort files for deterministic ordering
    for filepath in sorted(directory.rglob("*")):
        if filepath.is_file():
            # Include relative path in hash
            rel_path = filepath.relative_to(directory)
            sha256_hash.update(str(rel_path).encode())

            # Include file content
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)

    return sha256_hash.hexdigest()[:40]  # Truncate to 40 chars like git


def create_artifact(
    directory: Union[str, Path],
    archive_path: Optional[Union[str, Path]] = None,
    compression: str = "xz",
) -> Dict[str, str]:
    """
    Create an artifact archive from a directory.

    Parameters
    ----------
    directory : str or Path
        Source directory to archive
    archive_path : str or Path, optional
        Output path for the archive. If None, creates in temp directory.
    compression : str
        Compression type: "xz", "gz", "bz2", or None for no compression

    Returns
    -------
    dict
        Dictionary with:
        - "git_tree_sha1": Content hash
        - "sha256": Archive file hash
        - "archive_path": Path to created archive
    """
    directory = Path(directory)

    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    # Compute git-tree-sha1 of directory contents
    git_tree_sha1 = compute_git_tree_sha1(directory)

    # Determine archive path and mode
    if compression == "xz":
        suffix = ".tar.xz"
        mode = "w:xz"
    elif compression == "gz":
        suffix = ".tar.gz"
        mode = "w:gz"
    elif compression == "bz2":
        suffix = ".tar.bz2"
        mode = "w:bz2"
    else:
        suffix = ".tar"
        mode = "w"

    if archive_path is None:
        archive_path = Path(tempfile.gettempdir()) / f"{directory.name}{suffix}"
    else:
        archive_path = Path(archive_path)

    # Create archive
    with tarfile.open(archive_path, mode) as tar:
        tar.add(directory, arcname=directory.name)

    # Compute SHA256 of archive
    sha256 = compute_sha256(archive_path)

    return {
        "git_tree_sha1": git_tree_sha1,
        "sha256": sha256,
        "archive_path": str(archive_path),
    }


def bind_artifact(
    toml_path: Union[str, Path],
    name: str,
    git_tree_sha1: str,
    download_url: str,
    sha256: str,
    lazy: bool = True,
    force: bool = False,
) -> None:
    """
    Bind an artifact to an Artifacts.toml file.

    Similar to Julia's bind_artifact!().

    Parameters
    ----------
    toml_path : str or Path
        Path to Artifacts.toml (created if doesn't exist)
    name : str
        Artifact name
    git_tree_sha1 : str
        Content hash of the artifact
    download_url : str
        URL to download the artifact
    sha256 : str
        SHA256 hash of the download file
    lazy : bool
        Whether artifact should be lazy-loaded (default: True)
    force : bool
        Overwrite existing artifact with same name

    Raises
    ------
    ValueError
        If artifact already exists and force=False
    """
    if tomlkit is None:
        raise ImportError(
            "tomlkit is required for writing TOML files. "
            "Install with: pip install tomlkit"
        )

    toml_path = Path(toml_path)

    # Load existing TOML or create new
    if toml_path.exists():
        with open(toml_path, "r") as f:
            doc = tomlkit.load(f)
    else:
        doc = tomlkit.document()

    # Check if artifact exists
    if name in doc and not force:
        raise ValueError(
            f"Artifact '{name}' already exists in {toml_path}. "
            "Use force=True to overwrite."
        )

    # Create artifact entry
    artifact_table = tomlkit.table()
    artifact_table.add("git-tree-sha1", git_tree_sha1)
    if lazy:
        artifact_table.add("lazy", True)

    # Create download array
    download_array = tomlkit.aot()
    download_item = tomlkit.table()
    download_item.add("url", download_url)
    download_item.add("sha256", sha256)
    download_array.append(download_item)

    artifact_table.add("download", download_array)

    # Add to document
    doc[name] = artifact_table

    # Write back
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(toml_path, "w") as f:
        f.write(tomlkit.dumps(doc))


def unbind_artifact(
    toml_path: Union[str, Path],
    name: str,
) -> bool:
    """
    Remove an artifact binding from Artifacts.toml.

    Similar to Julia's unbind_artifact!().

    Parameters
    ----------
    toml_path : str or Path
        Path to Artifacts.toml
    name : str
        Artifact name to remove

    Returns
    -------
    bool
        True if artifact was removed, False if not found
    """
    if tomlkit is None:
        raise ImportError(
            "tomlkit is required for writing TOML files. "
            "Install with: pip install tomlkit"
        )

    toml_path = Path(toml_path)

    if not toml_path.exists():
        return False

    with open(toml_path, "r") as f:
        doc = tomlkit.load(f)

    if name not in doc:
        return False

    del doc[name]

    with open(toml_path, "w") as f:
        f.write(tomlkit.dumps(doc))

    return True


def add_download_source(
    toml_path: Union[str, Path],
    name: str,
    download_url: str,
    sha256: str,
) -> None:
    """
    Add an additional download source to an existing artifact.

    Parameters
    ----------
    toml_path : str or Path
        Path to Artifacts.toml
    name : str
        Artifact name
    download_url : str
        Additional URL to download from
    sha256 : str
        SHA256 hash (should match existing sources)
    """
    if tomlkit is None:
        raise ImportError(
            "tomlkit is required for writing TOML files. "
            "Install with: pip install tomlkit"
        )

    toml_path = Path(toml_path)

    if not toml_path.exists():
        raise FileNotFoundError(f"Artifacts.toml not found: {toml_path}")

    with open(toml_path, "r") as f:
        doc = tomlkit.load(f)

    if name not in doc:
        raise KeyError(f"Artifact '{name}' not found in {toml_path}")

    # Add new download source
    download_item = tomlkit.table()
    download_item.add("url", download_url)
    download_item.add("sha256", sha256)

    doc[name]["download"].append(download_item)

    with open(toml_path, "w") as f:
        f.write(tomlkit.dumps(doc))


def query_artifact_info(url: str, compute_tree_hash: bool = True) -> Dict[str, Any]:
    """
    Download a file and compute its artifact info.

    Useful for adding existing remote files as artifacts.

    Parameters
    ----------
    url : str
        URL to download
    compute_tree_hash : bool
        Whether to extract and compute git-tree-sha1

    Returns
    -------
    dict
        Dictionary with sha256, and optionally git_tree_sha1
    """
    import urllib.request

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        print(f"Downloading {url}...")
        urllib.request.urlretrieve(url, tmp_path)

        sha256 = compute_sha256(tmp_path)
        result = {"sha256": sha256, "url": url}

        if compute_tree_hash:
            # Try to extract and compute tree hash
            with tempfile.TemporaryDirectory() as extract_dir:
                extract_path = Path(extract_dir)
                try:
                    with tarfile.open(tmp_path, "r:*") as tar:
                        tar.extractall(extract_path)

                    # Find root directory
                    items = list(extract_path.iterdir())
                    if len(items) == 1 and items[0].is_dir():
                        content_dir = items[0]
                    else:
                        content_dir = extract_path

                    result["git_tree_sha1"] = compute_git_tree_sha1(content_dir)
                except tarfile.TarError:
                    print("Warning: Could not extract archive for tree hash")

        return result

    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def add_artifact(
    toml_path: Union[str, Path],
    name: str,
    tarball_url: str,
    lazy: bool = True,
    force: bool = False,
    clear: bool = True,
    verbose: bool = True,
) -> Dict[str, str]:
    """
    Download a tarball, compute its hashes, and add it to Artifacts.toml.

    This is the main convenience function for adding artifacts, similar to
    Julia's ArtifactUtils.add_artifact!().

    Parameters
    ----------
    toml_path : str or Path
        Path to Artifacts.toml (created if doesn't exist)
    name : str
        Artifact name
    tarball_url : str
        URL to download the tarball from
    lazy : bool
        Whether artifact should be lazy-loaded (default: True)
    force : bool
        Overwrite existing artifact with same name (default: False)
    clear : bool
        Whether to clear the downloaded file after adding (default: True)
        Note: The artifact is always added, this just controls cleanup.
    verbose : bool
        Whether to print progress messages (default: True)

    Returns
    -------
    dict
        Dictionary with computed artifact info:
        - "git_tree_sha1": Content hash
        - "sha256": Archive file hash
        - "url": Download URL

    Raises
    ------
    ValueError
        If artifact already exists and force=False

    Examples
    --------
    >>> from fetch_artifacts import add_artifact
    >>> add_artifact(
    ...     "Artifacts.toml",
    ...     "MyEmulator",
    ...     "https://zenodo.org/records/12345/files/emulator.tar.xz"
    ... )
    Downloading https://zenodo.org/records/12345/files/emulator.tar.xz...
    Computing hashes...
    Added artifact 'MyEmulator' to Artifacts.toml
    {'git_tree_sha1': 'abc123...', 'sha256': 'def456...', 'url': '...'}
    """
    import urllib.request

    toml_path = Path(toml_path)

    # Check if artifact already exists
    if toml_path.exists() and not force:
        try:
            if tomllib is None:
                raise ImportError("tomli/tomllib required")
            with open(toml_path, "rb") as f:
                existing = tomllib.load(f)
            if name in existing:
                raise ValueError(
                    f"Artifact '{name}' already exists in {toml_path}. "
                    "Use force=True to overwrite."
                )
        except ImportError:
            pass  # Can't check, will fail later if exists

    # Download to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.xz") as tmp:
        tmp_path = Path(tmp.name)

    try:
        if verbose:
            print(f"Downloading {tarball_url}...")

        # Download with progress
        def progress_hook(block_num, block_size, total_size):
            if verbose and total_size > 0:
                downloaded = block_num * block_size
                percent = min(downloaded * 100 / total_size, 100)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(
                    f"\r  {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)",
                    end="",
                    flush=True
                )

        urllib.request.urlretrieve(
            tarball_url,
            tmp_path,
            reporthook=progress_hook if verbose else None
        )

        if verbose:
            print()  # New line after progress
            print("Computing hashes...")

        # Compute SHA256 of the tarball
        sha256 = compute_sha256(tmp_path)

        # Extract and compute git-tree-sha1
        git_tree_sha1 = None
        with tempfile.TemporaryDirectory() as extract_dir:
            extract_path = Path(extract_dir)
            try:
                with tarfile.open(tmp_path, "r:*") as tar:
                    tar.extractall(extract_path)

                # Find root directory
                items = list(extract_path.iterdir())
                if len(items) == 1 and items[0].is_dir():
                    content_dir = items[0]
                else:
                    content_dir = extract_path

                git_tree_sha1 = compute_git_tree_sha1(content_dir)
            except tarfile.TarError as e:
                if verbose:
                    print(f"Warning: Could not extract archive for tree hash: {e}")
                # Use sha256 as fallback for git-tree-sha1
                git_tree_sha1 = sha256

        # Bind the artifact
        bind_artifact(
            toml_path=toml_path,
            name=name,
            git_tree_sha1=git_tree_sha1,
            download_url=tarball_url,
            sha256=sha256,
            lazy=lazy,
            force=force,
        )

        if verbose:
            print(f"Added artifact '{name}' to {toml_path}")

        return {
            "git_tree_sha1": git_tree_sha1,
            "sha256": sha256,
            "url": tarball_url,
        }

    finally:
        # Clean up temp file
        if clear and tmp_path.exists():
            tmp_path.unlink()

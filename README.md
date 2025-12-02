# fetch-artifacts

[![Tests](https://github.com/CosmologicalEmulators/fetch-artifacts/actions/workflows/tests.yml/badge.svg)](https://github.com/CosmologicalEmulators/fetch-artifacts/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/CosmologicalEmulators/fetch-artifacts/graph/badge.svg)](https://codecov.io/gh/CosmologicalEmulators/fetch-artifacts)
[![Python Version](https://img.shields.io/pypi/pyversions/fetch-artifacts.svg)](https://pypi.org/project/fetch-artifacts/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Julia-style artifact system for Python. Manage large binary files with TOML-based configuration, automatic downloading, content-addressable caching, and checksum verification.

## Features

- **Julia-compatible**: Uses the same `Artifacts.toml` format as Julia's Pkg.Artifacts
- **Content-addressable storage**: Artifacts cached by git-tree-sha1 hash for deduplication
- **Lazy loading**: Download artifacts only when accessed
- **Checksum verification**: SHA256 verification for all downloads
- **Multiple mirrors**: Support for fallback download sources
- **Cross-platform**: Works on Linux, macOS, and Windows
- **Simple API**: Minimal code to load and use artifacts

## Installation

```bash
pip install fetch-artifacts
```

Or with Poetry:

```bash
poetry add fetch-artifacts
```

## Quick Start

### 1. Create an Artifacts.toml file

```toml
[MyDataset]
git-tree-sha1 = "d309b571f5693718c8612d387820a409479fe506"
lazy = true

    [[MyDataset.download]]
    url = "https://example.com/dataset.tar.xz"
    sha256 = "d309b571f5693718c8612d387820a409479fe50688d4c46c87ba8662c6acc09b"
```

### 2. Load and use artifacts in Python

```python
from fetch_artifacts import artifact

# Get path to the artifact (downloads if needed)
dataset_path = artifact("MyDataset")
print(f"Dataset is at: {dataset_path}")

# Use the artifact
import pandas as pd
data = pd.read_csv(dataset_path / "data.csv")
```

## Usage

### Loading Artifacts

```python
from fetch_artifacts import artifact, artifact_path, artifact_exists

# Get artifact path (triggers download if needed)
path = artifact("MyArtifact")

# Check if artifact exists without downloading
if artifact_exists("MyArtifact"):
    print("Artifact is cached")

# Get path without auto-download
path = artifact_path("MyArtifact")  # Returns None if not cached
```

### Custom Cache Directory

```python
from fetch_artifacts import set_cache_dir, get_cache_dir

# Set custom cache location
set_cache_dir("/path/to/cache")

# Get current cache directory
cache_dir = get_cache_dir()  # Default: ~/.fetch_artifacts
```

### Creating Artifacts

```python
from fetch_artifacts import create_artifact, bind_artifact

# Create archive from directory
result = create_artifact(
    directory="path/to/data",
    archive_path="output.tar.xz",
    compression="xz"
)

print(f"git-tree-sha1: {result['git_tree_sha1']}")
print(f"sha256: {result['sha256']}")

# Add to Artifacts.toml
bind_artifact(
    toml_path="Artifacts.toml",
    name="MyArtifact",
    git_tree_sha1=result['git_tree_sha1'],
    download_url="https://example.com/artifact.tar.xz",
    sha256=result['sha256']
)
```

### Adding Existing Remote Files

```python
from fetch_artifacts import add_artifact

# Download, compute hashes, and add to Artifacts.toml
add_artifact(
    toml_path="Artifacts.toml",
    name="RemoteDataset",
    tarball_url="https://zenodo.org/records/12345/files/data.tar.xz"
)
```

### Managing Cache

```python
from fetch_artifacts import clear_artifact_cache

# Clear specific artifact
clear_artifact_cache("MyArtifact")

# Clear all artifacts
clear_artifact_cache()
```

## Artifacts.toml Format

```toml
[ArtifactName]
git-tree-sha1 = "abc123..."  # Content hash (required)
lazy = true                   # Lazy loading (default: true)

    [[ArtifactName.download]]
    url = "https://primary.com/data.tar.xz"
    sha256 = "def456..."

    [[ArtifactName.download]]
    url = "https://mirror.com/data.tar.xz"  # Fallback mirror
    sha256 = "def456..."
```

### Custom Metadata

You can add custom fields for application-specific metadata:

```toml
[MyEmulator]
git-tree-sha1 = "abc123..."
description = "Neural network emulator for cosmology"
has_noise = false
version = "2.0"

    [[MyEmulator.download]]
    url = "https://zenodo.org/records/12345/files/emulator.tar.xz"
    sha256 = "def456..."
```

Access metadata via the ArtifactManager:

```python
from fetch_artifacts import load_artifacts

manager = load_artifacts("Artifacts.toml")
entry = manager.artifacts["MyEmulator"]
print(entry.metadata)  # {"description": "...", "has_noise": False, "version": "2.0"}
```

## API Reference

### Core Functions

- `artifact(name, toml_path=None)` - Get artifact path, downloading if needed
- `artifact_path(name, toml_path=None)` - Get artifact path without downloading
- `artifact_exists(name, toml_path=None)` - Check if artifact is cached
- `load_artifacts(toml_path=None, cache_dir=None)` - Load ArtifactManager

### Cache Management

- `get_cache_dir()` - Get global cache directory
- `set_cache_dir(path)` - Set global cache directory
- `clear_artifact_cache(name=None, toml_path=None)` - Clear cache

### Creating Artifacts

- `create_artifact(directory, archive_path=None, compression='xz')` - Create artifact archive
- `compute_sha256(filepath)` - Compute SHA256 hash
- `compute_git_tree_sha1(directory)` - Compute git-tree-sha1 hash

### Binding Artifacts

- `bind_artifact(toml_path, name, git_tree_sha1, download_url, sha256, lazy=True, force=False)` - Add artifact to TOML
- `unbind_artifact(toml_path, name)` - Remove artifact from TOML
- `add_artifact(toml_path, name, tarball_url, lazy=True, force=False)` - Download and add artifact
- `add_download_source(toml_path, name, download_url, sha256)` - Add mirror URL

## Why fetch-artifacts?

Scientific computing often requires large datasets or model files. Managing these with git-lfs or direct downloads has drawbacks:

- **git-lfs**: Expensive, coupled to git history, doesn't deduplicate
- **Direct downloads**: No versioning, no checksums, manual management
- **fetch-artifacts**: Content-addressable, verified, cached, platform-independent

Inspired by Julia's Pkg.Artifacts system, fetch-artifacts brings the same workflow to Python.

## Comparison with Julia

fetch-artifacts uses the same `Artifacts.toml` format and similar API:

**Julia:**
```julia
using Pkg.Artifacts

# Get artifact path
dataset_dir = artifact"MyDataset"
```

**Python:**
```python
from fetch_artifacts import artifact

# Get artifact path
dataset_dir = artifact("MyDataset")
```

Both systems:
- Use content-addressable storage (git-tree-sha1)
- Support lazy loading
- Verify checksums (SHA256)
- Allow multiple download mirrors
- Cache artifacts globally

## Development

### Setup

```bash
git clone https://github.com/CosmologicalEmulators/fetch-artifacts.git
cd fetch-artifacts
poetry install
```

### Running Tests

```bash
poetry run pytest tests/ -v
```

### Running Tests with Coverage

```bash
poetry run pytest tests/ -v --cov=fetch_artifacts --cov-report=term --cov-report=html
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Citation

If you use fetch-artifacts in your research, please cite:

```bibtex
@software{fetch_artifacts,
  author = {Bonici, Marco},
  title = {fetch-artifacts: Julia-style artifact management for Python},
  year = {2024},
  url = {https://github.com/CosmologicalEmulators/fetch-artifacts}
}
```

## Links

- [Documentation](https://github.com/CosmologicalEmulators/fetch-artifacts)
- [Issue Tracker](https://github.com/CosmologicalEmulators/fetch-artifacts/issues)
- [PyPI Package](https://pypi.org/project/fetch-artifacts/) (coming soon)
- [Julia's Pkg.Artifacts](https://pkgdocs.julialang.org/v1/artifacts/)

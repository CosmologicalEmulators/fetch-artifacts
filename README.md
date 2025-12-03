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
- **Simple API**: Minimal code to load and use artifacts

## Installation

```bash
pip install fetch-artifacts
```

## Usage

### 1. Create an Artifacts.toml file

```toml
[MyDataset]
git-tree-sha1 = "d309b571f5693718c8612d387820a409479fe506"

    [[MyDataset.download]]
    url = "https://example.com/dataset.tar.xz"
    sha256 = "d309b571f5693718c8612d387820a409479fe50688d4c46c87ba8662c6acc09b"
```

### 2. Load artifacts in Python

```python
from fetch_artifacts import artifact

# Get path to the artifact (downloads if needed)
dataset_path = artifact("MyDataset")

# Use the artifact
import pandas as pd
data = pd.read_csv(dataset_path / "data.csv")
```

### 3. Create and publish artifacts

```python
from fetch_artifacts import create_artifact, bind_artifact

# Create archive from directory
result = create_artifact(
    directory="path/to/data",
    archive_path="output.tar.xz",
    compression="xz"
)

# Add to Artifacts.toml
bind_artifact(
    toml_path="Artifacts.toml",
    name="MyArtifact",
    git_tree_sha1=result['git_tree_sha1'],
    download_url="https://example.com/artifact.tar.xz",
    sha256=result['sha256']
)
```

### 4. Add existing remote files

```python
from fetch_artifacts import add_artifact

# Download, compute hashes, and add to Artifacts.toml in one step
add_artifact(
    toml_path="Artifacts.toml",
    name="RemoteDataset",
    tarball_url="https://zenodo.org/records/12345/files/data.tar.xz"
)
```

### Advanced Usage

**Custom cache directory:**
```python
from fetch_artifacts import set_cache_dir
set_cache_dir("/path/to/cache")
```

**Check if artifact exists:**
```python
from fetch_artifacts import artifact_exists
if artifact_exists("MyArtifact"):
    print("Artifact is cached")
```

**Clear cache:**
```python
from fetch_artifacts import clear_artifact_cache
clear_artifact_cache("MyArtifact")  # Clear specific artifact
clear_artifact_cache()              # Clear all artifacts
```

**Custom metadata:**
```toml
[MyEmulator]
git-tree-sha1 = "abc123..."
description = "Neural network emulator for cosmology"
version = "2.0"

    [[MyEmulator.download]]
    url = "https://zenodo.org/records/12345/files/emulator.tar.xz"
    sha256 = "def456..."
```

Access metadata:
```python
from fetch_artifacts import load_artifacts

manager = load_artifacts("Artifacts.toml")
metadata = manager.artifacts["MyEmulator"].metadata
print(metadata["description"])  # "Neural network emulator for cosmology"
```

## Why fetch-artifacts?

Managing large datasets or model files in scientific computing has several challenges:

- **git-lfs**: Expensive, coupled to git history, doesn't deduplicate across projects
- **Direct downloads**: No versioning, no automatic checksums, manual management
- **fetch-artifacts**: Content-addressable, automatic verification, global caching, platform-independent

Inspired by Julia's Pkg.Artifacts, fetch-artifacts brings the same robust workflow to Python.

## Artifacts.toml Format

```toml
[ArtifactName]
git-tree-sha1 = "abc123..."  # Content hash (required)

    [[ArtifactName.download]]
    url = "https://primary.com/data.tar.xz"
    sha256 = "def456..."

    [[ArtifactName.download]]  # Optional fallback mirror
    url = "https://mirror.com/data.tar.xz"
    sha256 = "def456..."
```

## Development

```bash
git clone https://github.com/CosmologicalEmulators/fetch-artifacts.git
cd fetch-artifacts
poetry install
poetry run pytest tests/ -v --cov=fetch_artifacts
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

## Links

- [Documentation](https://github.com/CosmologicalEmulators/fetch-artifacts)
- [Issue Tracker](https://github.com/CosmologicalEmulators/fetch-artifacts/issues)
- [PyPI Package](https://pypi.org/project/fetch-artifacts/) (coming soon)
- [Julia's Pkg.Artifacts](https://pkgdocs.julialang.org/v1/artifacts/)

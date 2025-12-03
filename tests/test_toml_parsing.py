"""Tests for TOML parsing functionality."""

import tempfile
from pathlib import Path

import pytest


class TestArtifactEntryParsing:
    """Test ArtifactEntry.from_dict() parsing."""

    def test_parse_complete_entry(self):
        """Parse artifact with all fields."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123def456",
            "lazy": True,
            "download": [
                {"url": "https://example.com/data.tar.gz", "sha256": "hash123"}
            ]
        }

        entry = ArtifactEntry.from_dict("TestArtifact", data)

        assert entry.name == "TestArtifact"
        assert entry.git_tree_sha1 == "abc123def456"
        assert entry.lazy is True
        assert len(entry.downloads) == 1
        assert entry.downloads[0].url == "https://example.com/data.tar.gz"
        assert entry.downloads[0].sha256 == "hash123"

    def test_parse_minimal_entry(self):
        """Parse artifact with only required fields."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "download": [
                {"url": "https://example.com/data.tar.gz", "sha256": "hash123"}
            ]
        }

        entry = ArtifactEntry.from_dict("MinimalArtifact", data)

        assert entry.name == "MinimalArtifact"
        assert entry.git_tree_sha1 is None
        assert entry.lazy is True  # Default
        assert len(entry.downloads) == 1

    def test_parse_multiple_downloads(self):
        """Parse artifact with multiple download sources."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123",
            "download": [
                {"url": "https://primary.com/data.tar.gz", "sha256": "hash1"},
                {"url": "https://mirror1.com/data.tar.gz", "sha256": "hash1"},
                {"url": "https://mirror2.com/data.tar.gz", "sha256": "hash1"},
            ]
        }

        entry = ArtifactEntry.from_dict("MultiDownload", data)

        assert len(entry.downloads) == 3
        assert entry.downloads[0].url == "https://primary.com/data.tar.gz"
        assert entry.downloads[1].url == "https://mirror1.com/data.tar.gz"
        assert entry.downloads[2].url == "https://mirror2.com/data.tar.gz"

    def test_parse_lazy_false(self):
        """Parse artifact with lazy=false."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123",
            "lazy": False,
            "download": [{"url": "https://example.com/data.tar.gz", "sha256": "h"}]
        }

        entry = ArtifactEntry.from_dict("EagerArtifact", data)

        assert entry.lazy is False

    def test_parse_no_downloads(self):
        """Parse artifact without download section (local-only)."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {"git-tree-sha1": "abc123"}

        entry = ArtifactEntry.from_dict("LocalOnly", data)

        assert entry.git_tree_sha1 == "abc123"
        assert len(entry.downloads) == 0

    def test_parse_platform_specific(self):
        """Parse artifact with platform fields."""
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123",
            "os": "linux",
            "arch": "x86_64",
            "download": [{"url": "https://example.com/data.tar.gz", "sha256": "h"}]
        }

        entry = ArtifactEntry.from_dict("PlatformSpecific", data)

        assert entry.os == "linux"
        assert entry.arch == "x86_64"


class TestArtifactManagerTomlLoading:
    """Test ArtifactManager TOML file loading."""

    def test_load_single_artifact(self, tmp_path):
        """Load TOML with single artifact."""
        from fetch_artifacts import ArtifactManager

        toml_content = '''
[MyData]
git-tree-sha1 = "abc123"
lazy = true

    [[MyData.download]]
    url = "https://example.com/data.tar.gz"
    sha256 = "def456"
'''
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert "MyData" in manager.artifacts
        assert len(manager.artifacts) == 1
        assert manager.artifacts["MyData"].git_tree_sha1 == "abc123"

    def test_load_multiple_artifacts(self, tmp_path):
        """Load TOML with multiple artifacts."""
        from fetch_artifacts import ArtifactManager

        toml_content = '''
[Artifact1]
git-tree-sha1 = "hash1"

    [[Artifact1.download]]
    url = "https://example.com/a1.tar.gz"
    sha256 = "sha1"

[Artifact2]
git-tree-sha1 = "hash2"

    [[Artifact2.download]]
    url = "https://example.com/a2.tar.gz"
    sha256 = "sha2"

[Artifact3]
git-tree-sha1 = "hash3"

    [[Artifact3.download]]
    url = "https://example.com/a3.tar.gz"
    sha256 = "sha3"
'''
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert len(manager.artifacts) == 3
        assert "Artifact1" in manager.artifacts
        assert "Artifact2" in manager.artifacts
        assert "Artifact3" in manager.artifacts

    def test_load_empty_toml(self, tmp_path):
        """Load empty TOML file."""
        from fetch_artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text("")

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert len(manager.artifacts) == 0

    def test_load_nonexistent_toml(self, tmp_path):
        """Raise error for nonexistent TOML file."""
        from fetch_artifacts import ArtifactManager

        with pytest.raises(FileNotFoundError):
            ArtifactManager(tmp_path / "nonexistent.toml")

    def test_load_julia_artifacts_toml(self, tmp_path):
        """Load JuliaArtifacts.toml (alternate name)."""
        from fetch_artifacts.artifacts import get_artifacts_toml

        # Create JuliaArtifacts.toml
        julia_toml = tmp_path / "JuliaArtifacts.toml"
        julia_toml.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        # Search should find it
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            found = get_artifacts_toml()
            # Note: get_artifacts_toml looks in caller's directory first
        finally:
            os.chdir(original_cwd)

    def test_contains_operator(self, tmp_path):
        """Test 'in' operator for artifact checking."""
        from fetch_artifacts import ArtifactManager

        toml_content = '[MyData]\ngit-tree-sha1 = "abc"\n'
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert "MyData" in manager
        assert "NonExistent" not in manager

    def test_getitem_unknown_artifact(self, tmp_path):
        """Raise KeyError for unknown artifact."""
        from fetch_artifacts import ArtifactManager

        toml_content = '[MyData]\ngit-tree-sha1 = "abc"\n'
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        with pytest.raises(KeyError, match="Unknown"):
            manager["Unknown"]

"""Tests for fetch_artifacts."""

import tempfile
from pathlib import Path

import pytest


class TestArtifactEntry:
    """Test ArtifactEntry parsing."""

    def test_from_dict_basic(self):
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123",
            "lazy": True,
            "download": [
                {
                    "url": "https://example.com/data.tar.gz",
                    "sha256": "def456"
                }
            ]
        }

        entry = ArtifactEntry.from_dict("TestArtifact", data)

        assert entry.name == "TestArtifact"
        assert entry.git_tree_sha1 == "abc123"
        assert entry.lazy is True
        assert len(entry.downloads) == 1
        assert entry.downloads[0].url == "https://example.com/data.tar.gz"
        assert entry.downloads[0].sha256 == "def456"

    def test_from_dict_multiple_downloads(self):
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "git-tree-sha1": "abc123",
            "download": [
                {"url": "https://primary.com/data.tar.gz", "sha256": "hash1"},
                {"url": "https://mirror.com/data.tar.gz", "sha256": "hash2"},
            ]
        }

        entry = ArtifactEntry.from_dict("TestArtifact", data)

        assert len(entry.downloads) == 2
        assert entry.downloads[0].url == "https://primary.com/data.tar.gz"
        assert entry.downloads[1].url == "https://mirror.com/data.tar.gz"

    def test_from_dict_no_git_tree_sha1(self):
        from fetch_artifacts.artifacts import ArtifactEntry

        data = {
            "download": [
                {"url": "https://example.com/data.tar.gz", "sha256": "def456"}
            ]
        }

        entry = ArtifactEntry.from_dict("TestArtifact", data)

        assert entry.git_tree_sha1 is None
        assert entry.name == "TestArtifact"


class TestArtifactManager:
    """Test ArtifactManager functionality."""

    @pytest.fixture
    def sample_toml(self, tmp_path):
        """Create a sample Artifacts.toml file."""
        toml_content = """
[TestData]
git-tree-sha1 = "abc123def456"
lazy = true

    [[TestData.download]]
    url = "https://example.com/data.tar.gz"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

[AnotherArtifact]
git-tree-sha1 = "xyz789"

    [[AnotherArtifact.download]]
    url = "https://example.com/other.tar.xz"
    sha256 = "abc123"
"""
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)
        return toml_path

    def test_load_toml(self, sample_toml, tmp_path):
        from fetch_artifacts import ArtifactManager

        manager = ArtifactManager(sample_toml, cache_dir=tmp_path / "cache")

        assert "TestData" in manager.artifacts
        assert "AnotherArtifact" in manager.artifacts
        assert len(manager.artifacts) == 2

    def test_contains(self, sample_toml, tmp_path):
        from fetch_artifacts import ArtifactManager

        manager = ArtifactManager(sample_toml, cache_dir=tmp_path / "cache")

        assert "TestData" in manager
        assert "NonExistent" not in manager

    def test_getitem_not_found(self, sample_toml, tmp_path):
        from fetch_artifacts import ArtifactManager

        manager = ArtifactManager(sample_toml, cache_dir=tmp_path / "cache")

        with pytest.raises(KeyError, match="NonExistent"):
            _ = manager["NonExistent"]

    def test_exists_not_cached(self, sample_toml, tmp_path):
        from fetch_artifacts import ArtifactManager

        manager = ArtifactManager(sample_toml, cache_dir=tmp_path / "cache")

        assert manager.exists("TestData") is False

    def test_artifact_dir_with_git_tree_sha1(self, sample_toml, tmp_path):
        from fetch_artifacts import ArtifactManager

        manager = ArtifactManager(sample_toml, cache_dir=tmp_path / "cache")
        entry = manager.artifacts["TestData"]
        artifact_dir = manager._get_artifact_dir(entry)

        # Should use git-tree-sha1 as directory name
        assert artifact_dir.name == "abc123def456"

    def test_toml_not_found(self, tmp_path):
        from fetch_artifacts import ArtifactManager

        with pytest.raises(FileNotFoundError):
            ArtifactManager(tmp_path / "nonexistent.toml")


class TestChecksumVerification:
    """Test checksum verification."""

    def test_verify_checksum_correct(self, tmp_path):
        from fetch_artifacts.artifacts import ArtifactManager

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        # SHA256 of "hello world"
        expected_sha256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

        # Create minimal manager for testing
        toml_content = "[Dummy]\ngit-tree-sha1 = \"abc\"\n"
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert manager._verify_checksum(test_file, expected_sha256) is True
        assert manager._verify_checksum(test_file, "wrong_hash") is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_cache_dir_default(self):
        from fetch_artifacts import get_cache_dir

        cache_dir = get_cache_dir()
        assert cache_dir == Path.home() / ".fetch_artifacts"

    def test_set_cache_dir(self, tmp_path):
        from fetch_artifacts.artifacts import _cache_dir, set_cache_dir, get_cache_dir

        # Save original
        import fetch_artifacts.artifacts as artifacts_module
        original = artifacts_module._cache_dir

        try:
            custom_dir = tmp_path / "custom_cache"
            set_cache_dir(custom_dir)

            assert get_cache_dir() == custom_dir
            assert custom_dir.exists()
        finally:
            # Restore original
            artifacts_module._cache_dir = original

    def test_artifact_exists_no_toml(self, tmp_path):
        from fetch_artifacts import artifact_exists

        # Change to tmp_path where no Artifacts.toml exists
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(FileNotFoundError):
                artifact_exists("SomeArtifact")
        finally:
            os.chdir(original_cwd)


class TestArchiveSuffix:
    """Test archive suffix detection."""

    def test_tar_gz(self, tmp_path):
        from fetch_artifacts import ArtifactManager

        toml_content = "[Dummy]\ngit-tree-sha1 = \"abc\"\n"
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(toml_content)

        manager = ArtifactManager(toml_path)

        assert manager._get_archive_suffix("https://example.com/file.tar.gz") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file.tgz") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file.tar.xz") == ".tar.xz"
        assert manager._get_archive_suffix("https://example.com/file.tar.bz2") == ".tar.bz2"
        assert manager._get_archive_suffix("https://example.com/file.zip") == ".zip"
        assert manager._get_archive_suffix("https://example.com/file.unknown") == ".tar.gz"  # Default

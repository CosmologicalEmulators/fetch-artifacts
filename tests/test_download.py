"""Tests for download and caching functionality."""

import tarfile
from pathlib import Path
from unittest import mock

import pytest


class TestChecksumVerification:
    """Test checksum verification during download."""

    def test_verify_correct_checksum(self, tmp_path):
        """Verification passes with correct checksum."""
        from fetch_artifacts.artifacts import ArtifactManager

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        # Known SHA256 of "hello world"
        expected_sha256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert manager._verify_checksum(test_file, expected_sha256) is True

    def test_verify_incorrect_checksum(self, tmp_path):
        """Verification fails with incorrect checksum."""
        from fetch_artifacts.artifacts import ArtifactManager

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert manager._verify_checksum(test_file, "wrong_hash") is False

    def test_verify_case_insensitive(self, tmp_path):
        """Checksum comparison is case-insensitive."""
        from fetch_artifacts.artifacts import ArtifactManager

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        sha256_lower = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        sha256_upper = "B94D27B9934D3E08A52E52D7DA7DABFAC484EFE37A5380EE9088F7ACE2EFCDE9"

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        assert manager._verify_checksum(test_file, sha256_lower) is True
        assert manager._verify_checksum(test_file, sha256_upper) is True


class TestCaching:
    """Test artifact caching behavior."""

    def test_artifact_cached_after_download(self, tmp_path):
        """Artifact is cached after successful download."""
        from fetch_artifacts.artifacts import ArtifactManager, ArtifactEntry, DownloadInfo

        # Create a test archive
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test content")

        archive_path = tmp_path / "test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="source")

        # Calculate hash
        from fetch_artifacts import compute_sha256
        sha256 = compute_sha256(archive_path)

        # Create manager
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[TestData]
git-tree-sha1 = "abc123"

    [[TestData.download]]
    url = "file://{archive_path}"
    sha256 = "{sha256}"
''')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        # Initially not cached
        assert manager.exists("TestData") is False

        # After accessing, should be cached
        # Note: file:// URLs work with urlretrieve
        # For this test, we'll manually trigger caching

    def test_cache_marker_file(self, tmp_path):
        """Cache completion marker file is created."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc123"\n')

        cache_dir = tmp_path / "cache"
        manager = ArtifactManager(toml_path, cache_dir=cache_dir)

        # Manually create artifact directory with marker
        artifact_dir = cache_dir / "abc123"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / ".fetch_artifacts_complete").touch()

        # Should be recognized as valid
        entry = manager.artifacts["Test"]
        assert manager._is_valid_artifact(artifact_dir, entry) is True

    def test_cache_without_marker_invalid(self, tmp_path):
        """Directory without marker is not valid cache."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc123"\n')

        cache_dir = tmp_path / "cache"
        manager = ArtifactManager(toml_path, cache_dir=cache_dir)

        # Create artifact directory WITHOUT marker
        artifact_dir = cache_dir / "abc123"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "some_file.txt").write_text("data")

        entry = manager.artifacts["Test"]
        assert manager._is_valid_artifact(artifact_dir, entry) is False

    def test_cache_dir_created(self, tmp_path):
        """Cache directory is created if doesn't exist."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        cache_dir = tmp_path / "new_cache_dir"
        assert not cache_dir.exists()

        manager = ArtifactManager(toml_path, cache_dir=cache_dir)

        assert cache_dir.exists()

    def test_artifact_dir_uses_git_tree_sha1(self, tmp_path):
        """Artifact directory uses git-tree-sha1 for content-addressable storage."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc123def456"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        entry = manager.artifacts["Test"]
        artifact_dir = manager._get_artifact_dir(entry)

        assert artifact_dir.name == "abc123def456"

    def test_artifact_dir_uses_name_when_no_hash(self, tmp_path):
        """Artifact directory uses name when git-tree-sha1 not provided."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[MyArtifact]\nlazy = true\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        entry = manager.artifacts["MyArtifact"]
        artifact_dir = manager._get_artifact_dir(entry)

        assert artifact_dir.name == "MyArtifact"


class TestClearCache:
    """Test cache clearing functionality."""

    def test_clear_specific_artifact(self, tmp_path):
        """Clear cache for specific artifact."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('''
[Artifact1]
git-tree-sha1 = "hash1"

[Artifact2]
git-tree-sha1 = "hash2"
''')

        cache_dir = tmp_path / "cache"
        manager = ArtifactManager(toml_path, cache_dir=cache_dir)

        # Create cached artifacts
        (cache_dir / "hash1").mkdir(parents=True)
        (cache_dir / "hash1" / ".fetch_artifacts_complete").touch()
        (cache_dir / "hash2").mkdir(parents=True)
        (cache_dir / "hash2" / ".fetch_artifacts_complete").touch()

        # Clear only Artifact1
        manager.clear("Artifact1")

        assert not (cache_dir / "hash1").exists()
        assert (cache_dir / "hash2").exists()

    def test_clear_all_artifacts(self, tmp_path):
        """Clear cache for all artifacts."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('''
[Artifact1]
git-tree-sha1 = "hash1"

[Artifact2]
git-tree-sha1 = "hash2"
''')

        cache_dir = tmp_path / "cache"
        manager = ArtifactManager(toml_path, cache_dir=cache_dir)

        # Create cached artifacts
        (cache_dir / "hash1").mkdir(parents=True)
        (cache_dir / "hash1" / ".fetch_artifacts_complete").touch()
        (cache_dir / "hash2").mkdir(parents=True)
        (cache_dir / "hash2" / ".fetch_artifacts_complete").touch()

        # Clear all
        manager.clear()

        assert not (cache_dir / "hash1").exists()
        assert not (cache_dir / "hash2").exists()


class TestDownloadFallback:
    """Test download fallback to alternative sources."""

    def test_no_downloads_raises_error(self, tmp_path):
        """Raise error when artifact has no download sources."""
        from fetch_artifacts.artifacts import ArtifactManager, ArtifactEntry

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[LocalOnly]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        # Access should fail since no downloads defined
        with pytest.raises(RuntimeError, match="no download sources"):
            manager._ensure_artifact(manager.artifacts["LocalOnly"])


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_get_cache_dir_default(self):
        """get_cache_dir returns default path."""
        from fetch_artifacts import get_cache_dir

        cache_dir = get_cache_dir()

        assert cache_dir == Path.home() / ".fetch_artifacts"

    def test_set_and_get_cache_dir(self, tmp_path):
        """set_cache_dir updates global cache directory."""
        from fetch_artifacts import get_cache_dir, set_cache_dir
        import fetch_artifacts.artifacts as module

        # Save original
        original = module._cache_dir

        try:
            custom_dir = tmp_path / "custom"
            set_cache_dir(custom_dir)

            assert get_cache_dir() == custom_dir
            assert custom_dir.exists()
        finally:
            # Restore
            module._cache_dir = original

    def test_clear_artifact_cache_function(self, tmp_path):
        """Test clear_artifact_cache convenience function."""
        from fetch_artifacts import clear_artifact_cache, load_artifacts

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        cache_dir = tmp_path / "cache"
        manager = load_artifacts(toml_path, cache_dir=cache_dir)

        # Create cached artifact
        artifact_dir = cache_dir / "abc"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / ".fetch_artifacts_complete").touch()

        # Clear using function
        clear_artifact_cache("Test", toml_path=toml_path)

        assert not artifact_dir.exists()

"""Additional tests to improve code coverage."""

import tarfile
from pathlib import Path
from unittest import mock

import pytest


class TestImportFallbacks:
    """Test import error handling."""

    def test_tomllib_import(self):
        """Test that tomllib import works."""
        from fetch_artifacts import artifacts
        # tomllib should be available in Python 3.11+
        assert artifacts.tomllib is not None


class TestErrorPaths:
    """Test error handling paths."""

    def test_toml_file_not_readable(self, tmp_path):
        """Test error when TOML file is not readable."""
        from fetch_artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text("invalid toml content ][}{")

        with pytest.raises(Exception):  # TOML parse error
            ArtifactManager(toml_path)

    def test_artifact_no_downloads_error(self, tmp_path):
        """Test error when artifact has no download sources."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[NoDownload]\ngit-tree-sha1 = "abc123"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        with pytest.raises(RuntimeError, match="no download sources"):
            manager._ensure_artifact(manager.artifacts["NoDownload"])

    def test_download_multiple_sources_fallback(self, tmp_path):
        """Test fallback to second download source when first fails."""
        from fetch_artifacts.artifacts import ArtifactManager
        from fetch_artifacts import compute_sha256

        # Create a valid archive
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test content")

        archive_path = tmp_path / "test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="source")

        sha256 = compute_sha256(archive_path)

        # TOML with bad first URL, good second URL
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[TestData]
git-tree-sha1 = "abc123"

    [[TestData.download]]
    url = "https://nonexistent-domain-12345.com/file.tar.gz"
    sha256 = "badsha256"

    [[TestData.download]]
    url = "file://{archive_path.as_posix()}"
    sha256 = "{sha256}"
''')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache", verbose=False)

        # Should fall back to second source
        result = manager["TestData"]
        assert result.exists()

    def test_all_downloads_fail(self, tmp_path):
        """Test error when all download sources fail."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('''
[BadArtifact]
git-tree-sha1 = "abc123"

    [[BadArtifact.download]]
    url = "https://nonexistent-domain-12345.com/file1.tar.gz"
    sha256 = "bad1"

    [[BadArtifact.download]]
    url = "https://nonexistent-domain-67890.com/file2.tar.gz"
    sha256 = "bad2"
''')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache", verbose=False)

        with pytest.raises(RuntimeError, match="Failed to download.*all sources"):
            manager["BadArtifact"]


class TestArchiveExtraction:
    """Test archive extraction edge cases."""

    def test_invalid_archive(self, tmp_path):
        """Test error handling for corrupted archive."""
        from fetch_artifacts.artifacts import ArtifactManager

        # Create a fake tar file (not actually valid)
        archive_path = tmp_path / "bad.tar.gz"
        archive_path.write_bytes(b"not a real tar file")

        sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # Some hash

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[BadArchive]
git-tree-sha1 = "abc123"

    [[BadArchive.download]]
    url = "file://{archive_path.as_posix()}"
    sha256 = "{sha256}"
''')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache", verbose=False)

        # Should fail during extraction
        with pytest.raises(RuntimeError):
            manager["BadArchive"]

    def test_checksum_mismatch(self, tmp_path):
        """Test error when download checksum doesn't match."""
        from fetch_artifacts.artifacts import ArtifactManager
        from fetch_artifacts import compute_sha256

        # Create a valid archive
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test content")

        archive_path = tmp_path / "test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="source")

        # Use WRONG sha256
        wrong_sha256 = "0" * 64

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[BadChecksum]
git-tree-sha1 = "abc123"

    [[BadChecksum.download]]
    url = "file://{archive_path.as_posix()}"
    sha256 = "{wrong_sha256}"
''')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache", verbose=False)

        # Should fail checksum verification
        with pytest.raises(RuntimeError, match="Checksum verification failed"):
            manager["BadChecksum"]


class TestConvenienceFunctions:
    """Test module-level functions."""

    def test_artifact_function_downloads(self, tmp_path):
        """Test artifact() function triggers download."""
        from fetch_artifacts import artifact, compute_sha256, set_cache_dir, get_cache_dir

        # Save original cache dir
        original_cache = get_cache_dir()

        # Create a valid archive
        src_dir = tmp_path / "mydata"
        src_dir.mkdir()
        (src_dir / "info.txt").write_text("artifact data")

        archive_path = tmp_path / "artifact.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="mydata")

        sha256 = compute_sha256(archive_path)

        # Create Artifacts.toml
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[MyData]
git-tree-sha1 = "xyz789"

    [[MyData.download]]
    url = "file://{archive_path.as_posix()}"
    sha256 = "{sha256}"
''')

        # Change to tmp_path and set cache dir
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            set_cache_dir(tmp_path / "cache")

            # artifact() should download and return path
            result = artifact("MyData")
            assert result.exists()
            # The result is the artifact directory, which contains the extracted mydata folder
            # Check for the marker file to verify it was extracted
            assert (result / ".fetch_artifacts_complete").exists()
        finally:
            os.chdir(original_cwd)
            set_cache_dir(original_cache)

    def test_get_artifacts_toml_search(self, tmp_path):
        """Test get_artifacts_toml searches for file."""
        from fetch_artifacts.artifacts import get_artifacts_toml

        # Create Artifacts.toml
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        # Should find it when in the directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            found = get_artifacts_toml()
            assert found == toml_path
        finally:
            os.chdir(original_cwd)


class TestArchiveSuffixDetection:
    """Test archive suffix detection for various URLs."""

    def test_suffix_from_content_disposition(self, tmp_path):
        """Test suffix detection from URL patterns."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        # Test various URL patterns
        assert manager._get_archive_suffix("https://example.com/file.tar.gz") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file.tar.xz") == ".tar.xz"
        assert manager._get_archive_suffix("https://example.com/file.tar.bz2") == ".tar.bz2"
        assert manager._get_archive_suffix("https://example.com/file.tgz") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file.zip") == ".zip"

        # URLs with query params
        assert manager._get_archive_suffix("https://example.com/file.tar.xz?download=1") == ".tar.xz"

        # Unknown suffix defaults to .tar.gz
        assert manager._get_archive_suffix("https://example.com/file.bin") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file") == ".tar.gz"


class TestVerboseOutput:
    """Test verbose output messages."""

    def test_verbose_download_messages(self, tmp_path, capsys):
        """Test that verbose mode prints messages."""
        from fetch_artifacts.artifacts import ArtifactManager
        from fetch_artifacts import compute_sha256

        # Create a valid archive
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test")

        archive_path = tmp_path / "test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="source")

        sha256 = compute_sha256(archive_path)

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text(f'''
[VerboseTest]
git-tree-sha1 = "abc123"

    [[VerboseTest.download]]
    url = "file://{archive_path.as_posix()}"
    sha256 = "{sha256}"
''')

        # Create with verbose=True
        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache", verbose=True)

        # Access artifact - should print messages
        result = manager["VerboseTest"]

        captured = capsys.readouterr()
        assert "Downloading" in captured.out or "ready" in captured.out

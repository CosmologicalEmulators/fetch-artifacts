"""Tests for archive creation and extraction."""

import tarfile
from pathlib import Path

import pytest


class TestCreateArtifact:
    """Test create_artifact function."""

    def test_create_artifact_tar_xz(self, tmp_path):
        """Create .tar.xz artifact from directory."""
        from fetch_artifacts import create_artifact

        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "file2.txt").write_text("content2")

        result = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "output.tar.xz",
            compression="xz"
        )

        assert "git_tree_sha1" in result
        assert "sha256" in result
        assert "archive_path" in result
        assert Path(result["archive_path"]).exists()
        assert result["archive_path"].endswith(".tar.xz")

    def test_create_artifact_tar_gz(self, tmp_path):
        """Create .tar.gz artifact from directory."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test data")

        result = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "output.tar.gz",
            compression="gz"
        )

        assert Path(result["archive_path"]).exists()
        assert result["archive_path"].endswith(".tar.gz")

    def test_create_artifact_tar_bz2(self, tmp_path):
        """Create .tar.bz2 artifact from directory."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("test data")

        result = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "output.tar.bz2",
            compression="bz2"
        )

        assert Path(result["archive_path"]).exists()
        assert result["archive_path"].endswith(".tar.bz2")

    def test_create_artifact_extractable(self, tmp_path):
        """Created artifact can be extracted with correct contents."""
        from fetch_artifacts import create_artifact

        # Create source with known content
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "hello.txt").write_text("Hello, World!")

        subdir = src_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested content")

        result = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "test.tar.gz",
            compression="gz"
        )

        # Extract and verify
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(result["archive_path"], "r:gz") as tar:
            tar.extractall(extract_dir)

        # Should have source directory inside
        extracted_src = extract_dir / "source"
        assert extracted_src.exists()
        assert (extracted_src / "hello.txt").read_text() == "Hello, World!"
        assert (extracted_src / "subdir" / "nested.txt").read_text() == "Nested content"

    def test_create_artifact_sha256_stable(self, tmp_path):
        """SHA256 is consistent for same content."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("consistent content")

        result1 = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "archive1.tar.gz",
            compression="gz"
        )

        # Create again
        result2 = create_artifact(
            directory=src_dir,
            archive_path=tmp_path / "archive2.tar.gz",
            compression="gz"
        )

        # Note: SHA256 of archive might differ due to timestamps
        # But git_tree_sha1 of contents should be same
        assert result1["git_tree_sha1"] == result2["git_tree_sha1"]

    def test_create_artifact_not_directory(self, tmp_path):
        """Raise error if path is not a directory."""
        from fetch_artifacts import create_artifact

        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(ValueError, match="Not a directory"):
            create_artifact(directory=file_path)

    def test_create_artifact_default_path(self, tmp_path):
        """Create artifact with auto-generated path."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "my_data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("data")

        result = create_artifact(directory=src_dir, compression="gz")

        assert Path(result["archive_path"]).exists()
        assert "my_data" in result["archive_path"]


class TestArchiveExtraction:
    """Test archive extraction in ArtifactManager."""

    def test_extract_single_root_dir(self, tmp_path):
        """Extract archive with single root directory."""
        from fetch_artifacts.artifacts import ArtifactManager

        # Create archive with single root
        src_dir = tmp_path / "myartifact"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("content")

        archive_path = tmp_path / "test.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(src_dir, arcname="myartifact")

        # Create minimal TOML
        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        # Test extraction logic
        extract_to = tmp_path / "extracted"
        manager._extract_archive(archive_path, extract_to)

        assert (extract_to / "myartifact" / "data.txt").exists()

    def test_extract_multiple_items(self, tmp_path):
        """Extract archive with multiple items at root."""
        from fetch_artifacts.artifacts import ArtifactManager

        # Create archive with multiple root items
        archive_path = tmp_path / "multi.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add files directly (no single root dir)
            file1 = tmp_path / "file1.txt"
            file1.write_text("content1")
            tar.add(file1, arcname="file1.txt")

            file2 = tmp_path / "file2.txt"
            file2.write_text("content2")
            tar.add(file2, arcname="file2.txt")

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path, cache_dir=tmp_path / "cache")

        extract_to = tmp_path / "extracted"
        manager._extract_archive(archive_path, extract_to)

        assert (extract_to / "file1.txt").exists()
        assert (extract_to / "file2.txt").exists()


class TestArchiveSuffixDetection:
    """Test archive suffix detection."""

    def test_detect_tar_gz(self, tmp_path):
        """Detect .tar.gz suffix."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        assert manager._get_archive_suffix("https://example.com/file.tar.gz") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file.tgz") == ".tar.gz"

    def test_detect_tar_xz(self, tmp_path):
        """Detect .tar.xz suffix."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        assert manager._get_archive_suffix("https://example.com/file.tar.xz") == ".tar.xz"

    def test_detect_zip(self, tmp_path):
        """Detect .zip suffix."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        assert manager._get_archive_suffix("https://example.com/file.zip") == ".zip"

    def test_detect_unknown_defaults_tar_gz(self, tmp_path):
        """Unknown suffix defaults to .tar.gz."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        assert manager._get_archive_suffix("https://example.com/file.unknown") == ".tar.gz"
        assert manager._get_archive_suffix("https://example.com/file") == ".tar.gz"

    def test_detect_with_query_params(self, tmp_path):
        """Detect suffix with URL query parameters."""
        from fetch_artifacts.artifacts import ArtifactManager

        toml_path = tmp_path / "Artifacts.toml"
        toml_path.write_text('[Test]\ngit-tree-sha1 = "abc"\n')

        manager = ArtifactManager(toml_path)

        # Zenodo-style URL
        url = "https://zenodo.org/records/123/files/data.tar.xz?download=1"
        assert manager._get_archive_suffix(url) == ".tar.xz"

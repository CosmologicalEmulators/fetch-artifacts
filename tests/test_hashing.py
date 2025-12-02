"""Tests for hash computation functions."""

import os
import tempfile
from pathlib import Path

import pytest


class TestSHA256:
    """Test SHA256 hash computation."""

    def test_sha256_known_content(self, tmp_path):
        """Compute SHA256 of known content."""
        from fetch_artifacts import compute_sha256

        # "hello world" has a known SHA256
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        actual = compute_sha256(test_file)

        assert actual == expected

    def test_sha256_empty_file(self, tmp_path):
        """Compute SHA256 of empty file."""
        from fetch_artifacts import compute_sha256

        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        actual = compute_sha256(test_file)

        assert actual == expected

    def test_sha256_binary_content(self, tmp_path):
        """Compute SHA256 of binary content."""
        from fetch_artifacts import compute_sha256

        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(bytes(range(256)))

        # Should produce valid hex string
        result = compute_sha256(test_file)

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_sha256_large_file(self, tmp_path):
        """Compute SHA256 of larger file (tests chunked reading)."""
        from fetch_artifacts import compute_sha256

        test_file = tmp_path / "large.bin"
        # Create 1MB file
        test_file.write_bytes(b"x" * (1024 * 1024))

        result = compute_sha256(test_file)

        assert len(result) == 64

    def test_sha256_nonexistent_file(self, tmp_path):
        """Raise error for nonexistent file."""
        from fetch_artifacts import compute_sha256

        with pytest.raises(FileNotFoundError):
            compute_sha256(tmp_path / "nonexistent.txt")


class TestGitTreeSHA1:
    """Test git-tree-sha1 computation."""

    def test_tree_hash_simple_directory(self, tmp_path):
        """Compute tree hash of simple directory."""
        from fetch_artifacts import compute_git_tree_sha1

        # Create simple directory structure
        test_dir = tmp_path / "test_content"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")

        result = compute_git_tree_sha1(test_dir)

        # Should produce valid hex string
        assert len(result) >= 40
        assert all(c in "0123456789abcdef" for c in result)

    def test_tree_hash_nested_directory(self, tmp_path):
        """Compute tree hash of nested directory structure."""
        from fetch_artifacts import compute_git_tree_sha1

        test_dir = tmp_path / "nested"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("root file")

        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested file")

        result = compute_git_tree_sha1(test_dir)

        assert len(result) >= 40

    def test_tree_hash_empty_directory(self, tmp_path):
        """Compute tree hash of empty directory."""
        from fetch_artifacts import compute_git_tree_sha1

        test_dir = tmp_path / "empty"
        test_dir.mkdir()

        result = compute_git_tree_sha1(test_dir)

        # Should still produce a hash (empty tree has known hash in git)
        assert len(result) >= 40

    def test_tree_hash_deterministic(self, tmp_path):
        """Tree hash should be deterministic for same content."""
        from fetch_artifacts import compute_git_tree_sha1

        # Create two identical directories
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "file.txt").write_text("same content")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "file.txt").write_text("same content")

        hash1 = compute_git_tree_sha1(dir1)
        hash2 = compute_git_tree_sha1(dir2)

        assert hash1 == hash2

    def test_tree_hash_different_content(self, tmp_path):
        """Tree hash differs for different content."""
        from fetch_artifacts import compute_git_tree_sha1

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "file.txt").write_text("content A")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "file.txt").write_text("content B")

        hash1 = compute_git_tree_sha1(dir1)
        hash2 = compute_git_tree_sha1(dir2)

        assert hash1 != hash2

    def test_tree_hash_different_filenames(self, tmp_path):
        """Tree hash differs for different filenames."""
        from fetch_artifacts import compute_git_tree_sha1

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "fileA.txt").write_text("same")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "fileB.txt").write_text("same")

        hash1 = compute_git_tree_sha1(dir1)
        hash2 = compute_git_tree_sha1(dir2)

        assert hash1 != hash2

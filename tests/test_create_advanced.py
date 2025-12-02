"""Advanced tests for create.py functions."""

import tarfile
from pathlib import Path
from unittest import mock

import pytest

# Skip tests if tomlkit not available
try:
    import tomlkit
    HAS_TOMLKIT = True
except ImportError:
    HAS_TOMLKIT = False


class TestGitTreeSHA1Fallback:
    """Test git-tree-sha1 fallback when git is not available."""

    def test_fallback_tree_hash(self, tmp_path):
        """Test fallback hash computation when git unavailable."""
        from fetch_artifacts.create import compute_git_tree_sha1

        # Create a test directory
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        # Mock git to fail
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            hash_result = compute_git_tree_sha1(test_dir)

            # Should use fallback and still return a hash
            assert len(hash_result) >= 40
            assert all(c in "0123456789abcdef" for c in hash_result)


class TestCreateArtifactEdgeCases:
    """Test create_artifact edge cases."""

    def test_create_artifact_with_explicit_path(self, tmp_path):
        """Test create_artifact with explicit output path."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        output_path = tmp_path / "output" / "my_archive.tar.xz"
        output_path.parent.mkdir()

        result = create_artifact(src_dir, archive_path=output_path, compression="xz")

        assert result["archive_path"] == str(output_path)
        assert Path(result["archive_path"]).exists()

    def test_create_artifact_tar_uncompressed(self, tmp_path):
        """Test create_artifact with no compression."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        result = create_artifact(src_dir, compression=None)

        assert result["archive_path"].endswith(".tar")
        assert Path(result["archive_path"]).exists()

    def test_create_artifact_bz2(self, tmp_path):
        """Test create_artifact with bz2 compression."""
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        result = create_artifact(src_dir, compression="bz2")

        assert result["archive_path"].endswith(".tar.bz2")
        assert Path(result["archive_path"]).exists()


@pytest.mark.skipif(not HAS_TOMLKIT, reason="tomlkit not installed")
class TestQueryArtifactInfo:
    """Test query_artifact_info function."""

    def test_query_artifact_info_basic(self, tmp_path):
        """Test querying artifact info from a URL."""
        from fetch_artifacts.create import query_artifact_info
        from fetch_artifacts import create_artifact

        # Create an artifact
        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test data")

        result = create_artifact(src_dir, tmp_path / "test.tar.gz", compression="gz")
        archive_path = Path(result["archive_path"])

        # Query info from file:// URL
        file_url = archive_path.as_uri()
        info = query_artifact_info(file_url, compute_tree_hash=True)

        assert "sha256" in info
        assert "git_tree_sha1" in info
        assert "url" in info
        assert info["url"] == file_url

    def test_query_artifact_info_no_tree_hash(self, tmp_path):
        """Test querying without tree hash computation."""
        from fetch_artifacts.create import query_artifact_info
        from fetch_artifacts import create_artifact

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test data")

        result = create_artifact(src_dir, tmp_path / "test.tar.gz", compression="gz")
        archive_path = Path(result["archive_path"])

        file_url = archive_path.as_uri()
        info = query_artifact_info(file_url, compute_tree_hash=False)

        assert "sha256" in info
        assert "git_tree_sha1" not in info

    def test_query_artifact_info_bad_archive(self, tmp_path):
        """Test querying info from non-archive file."""
        from fetch_artifacts.create import query_artifact_info

        # Create a non-archive file
        bad_file = tmp_path / "notarchive.txt"
        bad_file.write_text("not a tar file")

        file_url = bad_file.as_uri()

        # Should handle gracefully (warning but no tree hash)
        info = query_artifact_info(file_url, compute_tree_hash=True)

        assert "sha256" in info
        # git_tree_sha1 won't be present due to extraction failure


@pytest.mark.skipif(not HAS_TOMLKIT, reason="tomlkit not installed")
class TestAddArtifact:
    """Test add_artifact convenience function."""

    def test_add_artifact_basic(self, tmp_path):
        """Test add_artifact downloads and adds to TOML."""
        from fetch_artifacts import add_artifact, create_artifact

        # Create an artifact file
        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test data")

        result = create_artifact(src_dir, tmp_path / "test.tar.xz", compression="xz")
        archive_path = Path(result["archive_path"])

        toml_path = tmp_path / "Artifacts.toml"
        file_url = archive_path.as_uri()

        # Add artifact from URL
        info = add_artifact(
            toml_path=toml_path,
            name="TestArtifact",
            tarball_url=file_url,
            lazy=True,
            verbose=True
        )

        assert "git_tree_sha1" in info
        assert "sha256" in info

        # Verify TOML was created
        assert toml_path.exists()

        # Verify content
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert "TestArtifact" in data
        assert data["TestArtifact"]["lazy"] is True

    def test_add_artifact_duplicate_error(self, tmp_path):
        """Test add_artifact raises error on duplicate."""
        from fetch_artifacts import add_artifact, bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        # Create first artifact
        bind_artifact(
            toml_path=toml_path,
            name="Existing",
            git_tree_sha1="hash1",
            download_url="https://example.com/file.tar.gz",
            sha256="sha1"
        )

        # Try to add duplicate
        with pytest.raises(ValueError, match="already exists"):
            add_artifact(
                toml_path=toml_path,
                name="Existing",
                tarball_url="https://example.com/other.tar.gz",
                force=False,
                verbose=False
            )

    def test_add_artifact_force_overwrite(self, tmp_path):
        """Test add_artifact with force=True overwrites."""
        from fetch_artifacts import add_artifact, create_artifact, bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        # Create existing artifact
        bind_artifact(
            toml_path=toml_path,
            name="MyArtifact",
            git_tree_sha1="oldhash",
            download_url="https://example.com/old.tar.gz",
            sha256="oldsha"
        )

        # Create new artifact file
        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("new data")

        result = create_artifact(src_dir, tmp_path / "new.tar.xz", compression="xz")
        archive_path = Path(result["archive_path"])
        file_url = archive_path.as_uri()

        # Add with force=True
        info = add_artifact(
            toml_path=toml_path,
            name="MyArtifact",
            tarball_url=file_url,
            force=True,
            verbose=False
        )

        # Should have new hash
        assert info["git_tree_sha1"] != "oldhash"

    def test_add_artifact_quiet_mode(self, tmp_path, capsys):
        """Test add_artifact with verbose=False."""
        from fetch_artifacts import add_artifact, create_artifact

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test")

        result = create_artifact(src_dir, tmp_path / "test.tar.gz", compression="gz")
        archive_path = Path(result["archive_path"])

        toml_path = tmp_path / "Artifacts.toml"
        file_url = archive_path.as_uri()

        add_artifact(
            toml_path=toml_path,
            name="Quiet",
            tarball_url=file_url,
            verbose=False
        )

        captured = capsys.readouterr()
        # Should have minimal output
        assert captured.out == "" or len(captured.out) < 50


class TestComputeSHA256:
    """Test SHA256 computation edge cases."""

    def test_compute_sha256_large_file(self, tmp_path):
        """Test SHA256 on larger file (tests chunking)."""
        from fetch_artifacts import compute_sha256

        # Create a 10MB file
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (10 * 1024 * 1024))

        result = compute_sha256(large_file)

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestArchiveCreationErrors:
    """Test error handling in archive creation."""

    def test_create_artifact_nonexistent_directory(self, tmp_path):
        """Test error when source directory doesn't exist."""
        from fetch_artifacts import create_artifact

        nonexistent = tmp_path / "doesnotexist"

        with pytest.raises(ValueError, match="Not a directory"):
            create_artifact(nonexistent)

    def test_create_artifact_file_not_directory(self, tmp_path):
        """Test error when source is a file not directory."""
        from fetch_artifacts import create_artifact

        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(ValueError, match="Not a directory"):
            create_artifact(file_path)

"""Tests for artifact binding and unbinding functions."""

from pathlib import Path

import pytest

# Check if tomlkit is available
try:
    import tomlkit
    HAS_TOMLKIT = True
except ImportError:
    HAS_TOMLKIT = False

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


@pytest.mark.skipif(not HAS_TOMLKIT, reason="tomlkit not installed")
class TestBindArtifact:
    """Test bind_artifact function."""

    def test_bind_creates_new_toml(self, tmp_path):
        """bind_artifact creates new TOML file if doesn't exist."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"
        assert not toml_path.exists()

        bind_artifact(
            toml_path=toml_path,
            name="NewArtifact",
            git_tree_sha1="abc123",
            download_url="https://example.com/data.tar.gz",
            sha256="def456",
        )

        assert toml_path.exists()

        # Verify content
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert "NewArtifact" in data
        assert data["NewArtifact"]["git-tree-sha1"] == "abc123"

    def test_bind_adds_to_existing_toml(self, tmp_path):
        """bind_artifact adds to existing TOML file."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        # Create first artifact
        bind_artifact(
            toml_path=toml_path,
            name="First",
            git_tree_sha1="hash1",
            download_url="https://example.com/first.tar.gz",
            sha256="sha1",
        )

        # Add second artifact
        bind_artifact(
            toml_path=toml_path,
            name="Second",
            git_tree_sha1="hash2",
            download_url="https://example.com/second.tar.gz",
            sha256="sha2",
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert "First" in data
        assert "Second" in data

    def test_bind_duplicate_raises_error(self, tmp_path):
        """bind_artifact raises error on duplicate without force."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="MyArtifact",
            git_tree_sha1="hash1",
            download_url="https://example.com/data.tar.gz",
            sha256="sha1",
        )

        with pytest.raises(ValueError, match="already exists"):
            bind_artifact(
                toml_path=toml_path,
                name="MyArtifact",
                git_tree_sha1="hash2",
                download_url="https://example.com/other.tar.gz",
                sha256="sha2",
            )

    def test_bind_force_overwrites(self, tmp_path):
        """bind_artifact with force=True overwrites existing."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="MyArtifact",
            git_tree_sha1="original_hash",
            download_url="https://example.com/original.tar.gz",
            sha256="original_sha",
        )

        bind_artifact(
            toml_path=toml_path,
            name="MyArtifact",
            git_tree_sha1="new_hash",
            download_url="https://example.com/new.tar.gz",
            sha256="new_sha",
            force=True,
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert data["MyArtifact"]["git-tree-sha1"] == "new_hash"

    def test_bind_lazy_true(self, tmp_path):
        """bind_artifact includes lazy=true field."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="LazyArtifact",
            git_tree_sha1="hash",
            download_url="https://example.com/data.tar.gz",
            sha256="sha",
            lazy=True,
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert data["LazyArtifact"]["lazy"] is True

    def test_bind_lazy_false(self, tmp_path):
        """bind_artifact can set lazy=false."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="EagerArtifact",
            git_tree_sha1="hash",
            download_url="https://example.com/data.tar.gz",
            sha256="sha",
            lazy=False,
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        # lazy=False means field not included or explicitly false
        assert "lazy" not in data["EagerArtifact"] or data["EagerArtifact"]["lazy"] is False

    def test_bind_download_info(self, tmp_path):
        """bind_artifact correctly formats download section."""
        from fetch_artifacts import bind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="Test",
            git_tree_sha1="hash",
            download_url="https://zenodo.org/record/123/files/data.tar.xz",
            sha256="abc123def456",
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        downloads = data["Test"]["download"]
        assert len(downloads) == 1
        assert downloads[0]["url"] == "https://zenodo.org/record/123/files/data.tar.xz"
        assert downloads[0]["sha256"] == "abc123def456"


@pytest.mark.skipif(not HAS_TOMLKIT, reason="tomlkit not installed")
class TestUnbindArtifact:
    """Test unbind_artifact function."""

    def test_unbind_removes_artifact(self, tmp_path):
        """unbind_artifact removes artifact from TOML."""
        from fetch_artifacts import bind_artifact, unbind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="ToRemove",
            git_tree_sha1="hash",
            download_url="https://example.com/data.tar.gz",
            sha256="sha",
        )

        result = unbind_artifact(toml_path, "ToRemove")

        assert result is True

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert "ToRemove" not in data

    def test_unbind_nonexistent_returns_false(self, tmp_path):
        """unbind_artifact returns False for nonexistent artifact."""
        from fetch_artifacts import bind_artifact, unbind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="Existing",
            git_tree_sha1="hash",
            download_url="https://example.com/data.tar.gz",
            sha256="sha",
        )

        result = unbind_artifact(toml_path, "NonExistent")

        assert result is False

    def test_unbind_missing_file_returns_false(self, tmp_path):
        """unbind_artifact returns False if TOML doesn't exist."""
        from fetch_artifacts import unbind_artifact

        result = unbind_artifact(tmp_path / "nonexistent.toml", "SomeArtifact")

        assert result is False

    def test_unbind_preserves_other_artifacts(self, tmp_path):
        """unbind_artifact preserves other artifacts."""
        from fetch_artifacts import bind_artifact, unbind_artifact

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="Keep1",
            git_tree_sha1="hash1",
            download_url="https://example.com/1.tar.gz",
            sha256="sha1",
        )
        bind_artifact(
            toml_path=toml_path,
            name="Remove",
            git_tree_sha1="hash2",
            download_url="https://example.com/2.tar.gz",
            sha256="sha2",
        )
        bind_artifact(
            toml_path=toml_path,
            name="Keep2",
            git_tree_sha1="hash3",
            download_url="https://example.com/3.tar.gz",
            sha256="sha3",
        )

        unbind_artifact(toml_path, "Remove")

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        assert "Keep1" in data
        assert "Keep2" in data
        assert "Remove" not in data


@pytest.mark.skipif(not HAS_TOMLKIT, reason="tomlkit not installed")
class TestAddDownloadSource:
    """Test add_download_source function."""

    def test_add_download_source(self, tmp_path):
        """add_download_source adds mirror URL."""
        from fetch_artifacts import bind_artifact, add_download_source

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="Test",
            git_tree_sha1="hash",
            download_url="https://primary.com/data.tar.gz",
            sha256="sha123",
        )

        add_download_source(
            toml_path=toml_path,
            name="Test",
            download_url="https://mirror.com/data.tar.gz",
            sha256="sha123",
        )

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        downloads = data["Test"]["download"]
        assert len(downloads) == 2
        assert downloads[0]["url"] == "https://primary.com/data.tar.gz"
        assert downloads[1]["url"] == "https://mirror.com/data.tar.gz"

    def test_add_download_source_nonexistent_artifact(self, tmp_path):
        """add_download_source raises error for nonexistent artifact."""
        from fetch_artifacts import bind_artifact, add_download_source

        toml_path = tmp_path / "Artifacts.toml"

        bind_artifact(
            toml_path=toml_path,
            name="Existing",
            git_tree_sha1="hash",
            download_url="https://example.com/data.tar.gz",
            sha256="sha",
        )

        with pytest.raises(KeyError, match="NonExistent"):
            add_download_source(
                toml_path=toml_path,
                name="NonExistent",
                download_url="https://mirror.com/data.tar.gz",
                sha256="sha",
            )

    def test_add_download_source_missing_file(self, tmp_path):
        """add_download_source raises error if TOML doesn't exist."""
        from fetch_artifacts import add_download_source

        with pytest.raises(FileNotFoundError):
            add_download_source(
                toml_path=tmp_path / "nonexistent.toml",
                name="Test",
                download_url="https://example.com/data.tar.gz",
                sha256="sha",
            )

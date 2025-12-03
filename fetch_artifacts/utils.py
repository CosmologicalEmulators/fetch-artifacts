"""Shared utility functions for fetch_artifacts."""

import tarfile
import urllib.request
from pathlib import Path
from urllib.error import URLError


def download_file(url: str, destination: Path, verbose: bool = False):
    """
    Download file from URL with optional progress bar.

    Parameters
    ----------
    url : str
        URL to download from
    destination : Path
        Local path to save the file
    verbose : bool
        Whether to show progress bar

    Raises
    ------
    RuntimeError
        If download fails
    """
    def progress_hook(block_num, block_size, total_size):
        if verbose and total_size > 0:
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(
                f"\r  {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)",
                end="",
                flush=True
            )

    try:
        urllib.request.urlretrieve(
            url,
            destination,
            reporthook=progress_hook if verbose else None
        )
        if verbose:
            print()  # New line after progress
    except URLError as e:
        raise RuntimeError(f"Download failed: {e}")


def extract_archive(archive_path: Path, extract_to: Path):
    """
    Extract archive to directory.

    Supports tar.gz, tar.xz, tar.bz2, tar, and zip formats.

    Parameters
    ----------
    archive_path : Path
        Path to the archive file
    extract_to : Path
        Directory to extract to

    Raises
    ------
    tarfile.TarError
        If archive extraction fails
    """
    extract_to.mkdir(parents=True, exist_ok=True)

    if str(archive_path).endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_to)
    else:
        # Use tarfile for tar archives (handles gz, xz, bz2 automatically)
        with tarfile.open(archive_path, "r:*") as tf:
            tf.extractall(extract_to)


def get_extracted_root(extract_dir: Path) -> Path:
    """
    Get the root directory from extracted archive.

    If the archive contains a single directory, return that directory.
    Otherwise, return the extraction directory itself.

    Parameters
    ----------
    extract_dir : Path
        Directory where archive was extracted

    Returns
    -------
    Path
        Root directory of the extracted content
    """
    items = list(extract_dir.iterdir())
    if len(items) == 1 and items[0].is_dir():
        return items[0]
    return extract_dir

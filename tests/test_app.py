# ruff: noqa: FBT001, S101, ARG001, ANN401, TRY002
"""Test the FastAPI server for neural network file uploads.

Test all the exit conditions of the server, requires pytest and httpx.
"""

import gzip
import hashlib
import io
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Never

import pytest
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from httpx import ASGITransport, AsyncClient

from app.main import app, create_upload_net

# Constants for HTTP status codes.
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_CONFLICT = 409
HTTP_INTERNAL_SERVER_ERROR = 500


def create_net_file(*, correct_hash: bool) -> tuple[str, io.BytesIO]:
    """Create a net file with correct or incorrect hash in the filename."""
    net_data = b"test neural network data"
    net_hash = hashlib.sha256(net_data).hexdigest()[:12]
    if correct_hash is False:
        # Produce an incorrect hash.
        wrong_hash_int = (int(net_hash, 16) + 1) % (1 << 48)
        net_hash = f"{wrong_hash_int:012x}"
    filename = f"nn-{net_hash}.nnue"
    net_file = io.BytesIO(net_data)
    net_file.seek(0)
    return filename, net_file


def ensure_clean_nn_file(filename: str) -> Path:
    """Ensure the nn folder exists and remove file if exists, returns the file path."""
    nn_dir = Path(__file__).resolve().parents[1] / "nn"
    nn_dir.mkdir(exist_ok=True)
    file_path = nn_dir / f"{filename}.gz"
    if file_path.exists():
        file_path.unlink()
    return file_path


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """Create an async client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_create_upload_net_no_filename_direct() -> None:
    """Direct call to cover the branch when no filename is provided."""
    dummy = UploadFile(filename="", file=io.BytesIO(b"dummy"))
    with pytest.raises(HTTPException) as exc_info:
        await create_upload_net(dummy)
    assert exc_info.value.status_code == HTTP_BAD_REQUEST
    assert exc_info.value.detail == "No filename provided in the upload"


@pytest.mark.asyncio
async def test_upload_no_filename(async_client: AsyncClient) -> None:
    """Test uploading when no filename is provided."""
    files = {"upload": ("", io.BytesIO(b"test data"), "application/gzip")}
    response = await async_client.post("/upload_net/", files=files)
    assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_upload_invalid_filename_pattern(async_client: AsyncClient) -> None:
    """Test uploading with an invalid filename pattern."""
    _, net_file = create_net_file(correct_hash=True)
    filename = "invalid_filename.pattern"
    files = {"upload": (filename, net_file, "application/gzip")}
    response = await async_client.post("/upload_net/", files=files)
    expected_detail = (
        f"Filename {filename} does not match expected pattern (nn-[0-9a-f]{{12}}.nnue)"
    )
    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json() == {"detail": expected_detail}


@pytest.mark.asyncio
async def test_upload_file_exists(async_client: AsyncClient) -> None:
    """Test that uploading the same file twice results in a conflict error."""
    filename, net_file = create_net_file(correct_hash=True)
    files = {"upload": (filename, net_file, "application/gzip")}
    await async_client.post("/upload_net/", files=files)  # Initial upload.
    net_file.seek(0)  # Reset file pointer for re-upload.
    response = await async_client.post("/upload_net/", files=files)
    assert response.status_code == HTTP_CONFLICT
    assert response.json() == {"detail": f"File {filename} already uploaded"}


@pytest.mark.asyncio
async def test_upload_failed_write(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
) -> None:
    """Test that a write failure returns an internal server error."""

    def mock_open(*args: Any, **kwargs: Any) -> Never:
        write_failure_msg = "Mocked write failure"
        raise RuntimeError(write_failure_msg)

    monkeypatch.setattr(gzip, "open", mock_open)
    filename, net_file = create_net_file(correct_hash=True)
    files = {"upload": (filename, net_file, "application/gzip")}
    response = await async_client.post("/upload_net/", files=files)
    assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": f"Failed to write file {filename}"}


@pytest.mark.asyncio
async def test_upload_failed_read(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
) -> None:
    """Test that a read failure returns an internal server error."""

    def mock_decompress(*args: Any, **kwargs: Any) -> Never:
        decompress_failure_msg = "Mocked read failure"
        raise RuntimeError(decompress_failure_msg)

    monkeypatch.setattr(gzip, "decompress", mock_decompress)
    filename, net_file = create_net_file(correct_hash=True)
    _ = ensure_clean_nn_file(filename)
    files = {"upload": (filename, net_file, "application/gzip")}
    response = await async_client.post("/upload_net/", files=files)
    assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": f"Failed to read uploaded file {filename}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("correct_hash", [True, False])
async def test_upload_net(correct_hash: bool, async_client: AsyncClient) -> None:
    """Test uploading a net file with a correct or incorrect hash in the filename."""
    filename, net_file = create_net_file(correct_hash=correct_hash)
    if correct_hash:
        ensure_clean_nn_file(filename)
    files = {"upload": (filename, net_file, "application/gzip")}
    response = await async_client.post("/upload_net/", files=files)
    if correct_hash:
        assert response.status_code == HTTP_CREATED
        assert response.json() == {"detail": "File uploaded successfully"}
    else:
        invalid_hash_msg = f"Invalid hash for uploaded file {filename}"
        assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": invalid_hash_msg}


@pytest.mark.asyncio
async def test_upload_net_with_existing_file_removal(async_client: AsyncClient) -> None:
    """Test that re-uploading an existing file results in a conflict error."""
    filename, net_file = create_net_file(correct_hash=True)
    file_path = ensure_clean_nn_file(filename)
    files = {"upload": (filename, net_file, "application/gzip")}
    # First upload to create the file.
    response = await async_client.post("/upload_net/", files=files)
    assert response.status_code == HTTP_CREATED
    original_content = file_path.read_bytes()
    # Attempt re-upload.
    net_file.seek(0)  # Reset the file pointer.
    response = await async_client.post("/upload_net/", files=files)
    # Expect conflict error if file exists.
    assert response.status_code == HTTP_CONFLICT
    assert response.json() == {"detail": f"File {filename} already uploaded"}
    # Verify that the original file remains unchanged.
    assert file_path.read_bytes() == original_content

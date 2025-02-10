"""FastAPI server for Stockfish chess engine neural networks.

Provide an endpoint for uploading and validating a net file.
"""

import gzip
import hashlib
import logging
import re
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI()

UPLOAD = File(...)


@app.post("/upload_net/", status_code=201)
async def create_upload_net(upload: Annotated[UploadFile, UPLOAD]) -> JSONResponse:
    """Upload a net file to the server and validate its hash."""
    net_file = upload.filename
    if not net_file:
        detail = "No filename provided in the upload"
        logger.error(detail)
        raise HTTPException(
            status_code=400,
            detail=detail,
        )
    if not re.match(r"^nn-[0-9a-f]{12}\.nnue$", net_file):
        detail = (
            f"Filename {net_file} does not match expected pattern "
            f"(nn-[0-9a-f]{{12}}.nnue)"
        )
        logger.error(detail)
        raise HTTPException(
            status_code=400,
            detail=detail,
        )

    # Ensure the nn directory exists
    nn_dir = Path(__file__).parents[1] / "nn"
    nn_dir.mkdir(exist_ok=True)
    net_file_gz = nn_dir / f"{net_file}.gz"

    try:
        with gzip.open(net_file_gz, "xb") as f:
            f.write(await upload.read())
    except FileExistsError as e:
        detail = f"File {net_file} already uploaded"
        logger.exception(detail)
        raise HTTPException(
            status_code=409,
            detail=detail,
        ) from e
    except Exception as e:
        net_file_gz.unlink(missing_ok=True)
        detail = f"Failed to write file {net_file}"
        logger.exception(detail)
        raise HTTPException(
            status_code=500,
            detail=detail,
        ) from e

    try:
        net_data = gzip.decompress(net_file_gz.read_bytes())
    except Exception as e:
        net_file_gz.unlink()
        detail = f"Failed to read uploaded file {net_file}"
        logger.exception(detail)
        raise HTTPException(
            status_code=500,
            detail=detail,
        ) from e

    net_hash = hashlib.sha256(net_data).hexdigest()[:12]

    if net_hash != net_file[3:15]:
        net_file_gz.unlink()
        detail = f"Invalid hash for uploaded file {net_file}"
        logger.error(detail)
        raise HTTPException(
            status_code=500,
            detail=detail,
        )

    return JSONResponse(
        status_code=201,
        content={"detail": "File uploaded successfully"},
    )

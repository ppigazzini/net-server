[![CI app](https://github.com/ppigazzini/net-server/actions/workflows/app.yaml/badge.svg)](https://github.com/ppigazzini/net-server/actions/workflows/app.yaml)[![CI lint](https://github.com/ppigazzini/net-server/actions/workflows/lint.yaml/badge.svg)](https://github.com/ppigazzini/net-server/actions/workflows/lint.yaml)

# Net Server

FastAPI-based server for uploading and validating neural network files was used by Stockfish chess engine. The server accepts files, validates their content, and stores them g-zip compressed on the server.

## Features

- Upload neural network files
- Validate file content using SHA-256 hash
- Save g-zipped network files
- Handle various error scenarios with appropriate HTTP status codes

## Requirements

- Python 3.13 or higher
- FastAPI
- Gunicorn + Uvicorn (for running the server)
- uv (for project management)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/ppigazzini/net-server.git
    cd net-server
    ```

2. Sync the project with production dependencies:

    ```bash
    uv sync --group prod
    ```

## Running the Server

Use this systemd unit file to run the server with a nginx proxy server:
```
[Unit]
Description=fastapi server for chess engine networks
After=network.target

[Service]
Type=simple
ExecStart=/home/<username>/net-server/.venv/bin/gunicorn main:app --timeout 120 --workers 4 --worker-class uvicorn.workers.UvicornWorker
Restart=on-failure
RestartSec=3
User=<username>
WorkingDirectory=/home/<username>/net-server/app

[Install]
WantedBy=multi-user.target
```

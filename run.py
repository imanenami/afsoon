"""Entrypoint for the RESTful service."""

import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO)


HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 3000))


if __name__ == "__main__":
    uvicorn.run("rest:app", host=HOST, port=PORT, log_level="info")
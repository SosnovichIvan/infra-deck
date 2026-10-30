"""ASGI factory, also used by test composition roots."""

from fastapi import FastAPI

from infradeck.api import create_app
from infradeck.config import Settings


def app() -> FastAPI:
    return create_app(Settings())  # type: ignore[call-arg]

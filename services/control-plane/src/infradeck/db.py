"""Small transaction boundary with PostgreSQL as the only supported engine."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str):
        self.url = url

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(
            self.url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=10000 -c lock_timeout=5000",
        ) as connection:
            yield connection

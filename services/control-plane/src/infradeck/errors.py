"""Public domain errors contain no transport/library exception text."""


class Rejected(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message, self.status = message, status
        super().__init__(message)

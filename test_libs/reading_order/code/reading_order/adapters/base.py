from typing import Protocol


def validate_length(length, maximum):
    if maximum is not None and length > maximum:
        raise ValueError('Candidate sequence length exceeded; no truncation or chunking')


class OrderAdapter(Protocol):
    def predict(self, blocks: list[dict], page: dict) -> dict: ...

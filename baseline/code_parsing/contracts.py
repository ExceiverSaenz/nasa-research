"""Small structural contracts at external and orchestration boundaries."""
from pathlib import Path
from typing import Any, Protocol


class Integrity(Protocol):
    def verify_lock(self) -> dict[str, Any]: ...
    def verify_files(self, root: Path) -> dict[str, Any]: ...
    def extract(self, archive: Path, destination: Path) -> None: ...


class Converter(Protocol):
    def convert(self, source: Path, *, raises_on_error: bool = False) -> Any: ...


class Exporter(Protocol):
    def export(self, document: Any, output: Path, paper_id: str) -> tuple[dict, list]: ...


class Downloader(Protocol):
    def download(self, request: dict, destination: Path) -> list[dict]: ...


class CommandRunner(Protocol):
    def __call__(self, args: list[str], **kwargs: Any) -> Any: ...


class Session(Protocol):
    def command(self, args: list) -> str: ...
    def run_phase(self, phase: str, python: str, run_id: str) -> None: ...

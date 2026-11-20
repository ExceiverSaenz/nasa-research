"""Folders the service uses (02-repository-context.md, "Environment setup")."""
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as defaults


@dataclass
class Config:
    data: Path = field(default_factory=defaults.data_root)
    run_dir: Path = field(default_factory=defaults.default_run_dir)
    pdf_dir: Path = field(default_factory=defaults.default_pdf_dir)
    port: int | None = None
    # The address the server listens on. On loopback the Host port must match the server port; on any other
    # address (a container, where Docker publishes the port under another number) only the host name is checked.
    bind: str = '127.0.0.1'

    def __post_init__(self):
        self.data, self.run_dir, self.pdf_dir = Path(self.data), Path(self.run_dir), Path(self.pdf_dir)

    @property
    def originals(self):
        return self.data / 'originals'

    @property
    def annotations(self):
        return self.data / 'annotations'

    @property
    def cache(self):
        return self.data / 'cache'

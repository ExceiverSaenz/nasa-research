"""Folders the service uses (02-repository-context.md, "Environment setup")."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as defaults


@dataclass
class Config:
    data: Path = field(default_factory=defaults.data_root)
    run_dir: Path = field(default_factory=defaults.default_run_dir)
    pdf_dir: Path = field(default_factory=defaults.default_pdf_dir)
    # The workspace folder (ADR-023), or None. ``workspace_shown`` is the same folder as the reviewer knows it, when it
    # differs (in a container, the folder on their computer: VALUE_REVIEW_WORKSPACE_SHOWN, set by compose).
    workspace: Path | None = field(default_factory=defaults.default_workspace)
    workspace_shown: str | None = field(default_factory=lambda: os.environ.get('VALUE_REVIEW_WORKSPACE_SHOWN') or None)
    port: int | None = None
    # The address the server listens on. On loopback the Host port must match the server port; on any other
    # address (a container, where Docker publishes the port under another number) only the host name is checked.
    bind: str = '127.0.0.1'

    def __post_init__(self):
        self.data, self.run_dir, self.pdf_dir = Path(self.data), Path(self.run_dir), Path(self.pdf_dir)
        self.workspace = None if self.workspace is None else Path(self.workspace)

    @property
    def originals(self):
        return self.data / 'originals'

    @property
    def annotations(self):
        return self.data / 'annotations'

    @property
    def cache(self):
        return self.data / 'cache'

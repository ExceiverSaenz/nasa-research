"""Where everything lives. Defaults follow OQ-06: originals and annotations beside the code, outside sealed trees."""
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / 'parsing_validator'


@dataclass
class Config:
    collection: Path = ROOT / 'src/raw_results/code_results/tensile_papers'
    pdfs: Path = ROOT / 'papers/Tensile_Properties_of_Sub-sized_Specimens_papers'
    originals: Path = HOME / 'originals'
    annotations: Path = HOME / 'annotations'
    cache: Path = HOME / '.cache'
    settings_file: Path = HOME / 'settings.json'
    web: Path = HOME / 'web'          # the committed front-end build (OQ-10); absent until the front end exists
    port: int | None = None          # when set, the Host header must carry this port
    prepare: bool = True             # verify papers and generate missing originals in the background
    prefetch: bool = True            # render page N+1 in the background (OQ-09)
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ('collection', 'pdfs', 'originals', 'annotations', 'cache', 'settings_file', 'web'):
            setattr(self, name, Path(getattr(self, name)))

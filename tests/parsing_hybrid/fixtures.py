import os
import time
from pathlib import Path

class Engine:
    def __init__(self, model, runtime):
        self.model, self.runtime = model, runtime
        if runtime.get('load_fail') == model:
            raise RuntimeError('load failure')
        time.sleep(runtime.get('load_delay', 0))
    def process(self, job, destination):
        if self.runtime.get('require_parent') and not destination.parent.is_dir():
            raise RuntimeError('Coordinator must publish shared result parent before dispatch')
        if self.runtime.get('crash') == self.model:
            os._exit(17)
        if self.runtime.get('fail') == self.model:
            raise RuntimeError('engine failure')
        time.sleep(self.runtime.get('delays', {}).get(self.model, .04))
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'result.txt').write_text(job['render_path'])
        return {'render_path': job['render_path'], 'identity': job['identity']}

def factory(model, runtime):
    if runtime.get('mutate_manifest') == model:
        Path(runtime['env_manifest']).write_text('changed')
    if runtime.get('mutate_prefix') == model:
        import sys
        sys.prefix = 'fixture-other-env'
    return Engine(model, runtime)

def render(paper, page, destination):
    destination.mkdir(parents=True, exist_ok=True)
    image = destination / 'page.png'
    image.write_bytes(b'fixture')
    return {'paper_id': paper['id'], 'page': page, 'render_path': str(image), 'identity': {'pdf_sha256': paper['sha256'], 'physical_page': page}}

def bad_render(paper, page, destination):
    raise RuntimeError('render failure')

def slow_render(paper, page, destination):
    time.sleep(2)
    return render(paper, page, destination)

def interrupt_render(paper, page, destination):
    raise KeyboardInterrupt()



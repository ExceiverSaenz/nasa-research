import hashlib
import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path
from tests.parsing_hybrid.fixtures import factory, render, bad_render, slow_render, interrupt_render

class SchedulerTests(unittest.TestCase):
    def test_coordinator_creates_shared_parent_before_dispatch(self):
        result = self.run_case({'require_parent': True})
        self.assertEqual(result['status'], 'completed', result['error'])

    def run_case(self, runtime=None, renderer=render, **kwargs):
        from parsing.unified.scheduler import run_pipeline
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        output = Path(self.tmp.name) / 'attempt'
        papers = [{'id': str(i), 'path': 'fixture.pdf', 'sha256': str(i), 'page_count': 1} for i in range(3)]
        result = run_pipeline(papers, output, runtime or {}, renderer=renderer, engine_factory=factory, load_timeout=3, task_timeout=2, **kwargs)
        self.assertEqual(len(result['tuples']), 9)
        self.assertTrue(all(not p.is_alive() for p in multiprocessing.active_children()))
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['schema'], 'parsing-hybrid-files/2')
        for name, sha in manifest['outputs'].items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), sha)
        self.assertFalse(output.with_suffix('.zip').exists())
        self.assertFalse(list(output.rglob('*.png')))
        for event in result['events']:
            if event['event'] == 'rendered': self.assertFalse(Path(event['render_path']).exists())
        self.assertTrue((output / 'status.json').exists())
        return result

    def test_persistent_concurrent_bounded_stream(self):
        r = self.run_case({'delays': {'mineru': .2}}, max_inflight=2)
        self.assertEqual(r['status'], 'completed', r['error'])
        ready = [e for e in r['events'] if e['event'] == 'ready']
        self.assertEqual(len(ready), 3)
        self.assertEqual(len({e['pid'] for e in ready}), 3)
        self.assertTrue(all(e['executable'] == sys.executable and e['prefix'] == sys.prefix for e in ready))
        self.assertEqual(r['metrics']['peak_inflight'], 2)
        self.assertEqual(r['metrics']['completed_pages'], 3)
        self.assertEqual(r['metrics']['completed_papers'], 3)
        self.assertGreater(r['metrics']['pages_per_minute'], 0)
        self.assertGreater(r['metrics']['papers_per_hour'], 0)
        self.assertEqual(len([e for e in r['events'] if e['event'] == 'rendered']), 3)
        for paper in ('0', '1', '2'):
            results = [t['result'] for t in r['tuples'] if t['paper_id'] == paper]
            self.assertEqual(len({x['render_path'] for x in results}), 1)
            self.assertTrue(all(x['identity'] == results[0]['identity'] for x in results))
        self.assertEqual(r['events'][-1]['event'], 'workers_stopped')
        starts = [e for e in r['events'] if e['event'] == 'started']
        finishes = [e for e in r['events'] if e['event'] == 'completed']
        self.assertLess(max(e['time'] for e in starts[:3]), min(e['time'] for e in finishes))
        fast_next = next(e for e in starts if e['paper_id'] == '1' and e['model'] == 'layoutlmv3')
        slow_first = next(e for e in finishes if e['paper_id'] == '0' and e['model'] == 'mineru')
        self.assertLess(fast_next['time'], slow_first['time'])

    def test_failures_finalize_all_tuples(self):
        for runtime in ({'load_fail': 'mineru'}, {'fail': 'mineru'}, {'crash': 'mineru'}, {'load_delay': 5}, {'mutate_prefix': 'mineru'}):
            with self.subTest(runtime=runtime):
                r = self.run_case(runtime)
                self.assertEqual(r['status'], 'failed')
                self.assertTrue(any(t['status'] != 'completed' for t in r['tuples']))

    def test_inference_timeout_is_not_queue_delay(self):
        from parsing.unified.scheduler import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            r = run_pipeline([{'id': 'x', 'sha256': 'x', 'page_count': 2}], Path(d)/'out', {'delays': {'mineru': .15}}, renderer=render, engine_factory=factory, task_timeout=.25, load_timeout=3)
            self.assertEqual(r['status'], 'completed', r['error'])
        with tempfile.TemporaryDirectory() as d:
            r = run_pipeline([{'id': 'x', 'sha256': 'x', 'page_count': 1}], Path(d)/'out', {'delays': {'mineru': 2}}, renderer=render, engine_factory=factory, task_timeout=.1, load_timeout=3)
            self.assertEqual(r['status'], 'failed')
            self.assertIn('task timeout', r['error'])

    def test_interrupt_and_no_overwrite(self):
        r = self.run_case(renderer=interrupt_render)
        self.assertEqual(r['status'], 'interrupted')
        from parsing.unified.scheduler import run_pipeline
        with self.assertRaises(FileExistsError):
            run_pipeline([{'id': 'x', 'page_count': 1}], Path(self.tmp.name)/'attempt', {}, renderer=render, engine_factory=factory)

    def test_reject_empty_and_boolean_page_count(self):
        from parsing.unified.scheduler import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            for papers in ([], [{'id': 'x', 'page_count': True}]):
                with self.assertRaises(ValueError):
                    run_pipeline(papers, Path(d)/'out', {}, renderer=render, engine_factory=factory)

    def test_worker_rejects_changed_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d)/'environment.json'
            manifest.write_text('original')
            result = self.run_case({'env_manifest': str(manifest), 'mutate_manifest': 'mineru'})
            self.assertEqual(result['status'], 'failed')
            self.assertIn('environment mismatch', result['error'])

    def test_rejects_invalid_resource_bounds(self):
        from parsing.unified.scheduler import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            for options in ({'load_timeout': float('nan')}, {'task_timeout': float('inf')}, {'task_timeout': True}, {'max_inflight': True}, {'max_inflight': 1.5}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    run_pipeline([{'id': 'x', 'page_count': 1}], Path(d)/'out', {}, renderer=render, engine_factory=factory, **options)

    def test_render_failure(self):
        self.assertEqual(self.run_case(renderer=bad_render)['status'], 'failed')

    def test_render_timeout(self):
        from parsing.unified.scheduler import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            r = run_pipeline([{'id': 'x', 'sha256': 'x', 'page_count': 1}], Path(d)/'out', {}, renderer=slow_render, engine_factory=factory, task_timeout=.1, load_timeout=3)
            self.assertEqual(r['status'], 'failed')
            self.assertIn('render timeout', r['error'])

if __name__ == '__main__':
    unittest.main()









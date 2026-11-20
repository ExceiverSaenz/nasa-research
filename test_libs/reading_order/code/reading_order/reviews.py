from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid


class ReviewStore:
    def __init__(self, run_path):
        self.run_path = Path(run_path).resolve()
        raw = (self.run_path/'manifest.json').read_bytes()
        self.run = json.loads(raw)
        self.run_sha256 = hashlib.sha256(raw).hexdigest()
        self.directory = self.run_path/'reviews'
        if self.directory.is_symlink() or self.directory.resolve().parent!=self.run_path:
            raise ValueError('Review destination may not be a symlink')
        self.cases = {f"{p['scope']['paper_id']}:{p['scope']['page_idx']}:{p['candidate_id']}":p
                      for p in self.run['predictions'] if p['candidate_id']!='docling'}

    def load(self):
        path = self.directory/'reviews.json'
        if path.is_symlink():
            raise ValueError('Review file may not be a symlink')
        if not path.exists():
            return dict(schema='reading-order-reviews/1',run_id=self.run['run_id'],
                        input_profile_id=self.run['input_profile_id'],run_sha256=self.run_sha256,revision=0,
                        states={key:'not_reviewed' for key in self.cases},observations=[])
        value = json.loads(path.read_text())
        if value.get('run_sha256')!=self.run_sha256:
            raise ValueError('Review identity differs from run')
        return value

    def _validate(self, observation):
        for key,expected in [('run_id',self.run['run_id']),('input_profile_id',self.run['input_profile_id']),('run_sha256',self.run_sha256)]:
            if observation.get(key)!=expected:
                raise ValueError('Observation identity mismatch')
        pred = self.cases.get(observation.get('case_id'))
        if pred is None or observation.get('candidate_id')!=pred['candidate_id'] or observation.get('control')!='docling':
            raise ValueError('Unknown comparison case')
        if observation.get('paper_id')!=pred['scope']['paper_id'] or pred['scope']['page_idx'] not in observation.get('pages',[]):
            raise ValueError('Observation page scope differs')
        known = {i for p in self.run['predictions'] if p['scope']['paper_id']==observation['paper_id'] for i in p.get('ordered_ids') or []}
        if 'input_reference' in self.run:
            from .ingest import Ingestor,LocalReferences
            documents = Ingestor(LocalReferences(self.run['input_reference']['source_root'])).resolve(self.run['input_reference'])
            known = {b.id for d in documents if d.paper_id==observation['paper_id'] for b in d.blocks if b.page_idx in observation['pages']}
        if not set(observation.get('block_ids',[])).issubset(known):
            raise ValueError('Unknown block IDs')
        if observation.get('review_state') not in ('not_reviewed','partial','reviewed'):
            raise ValueError('Invalid review state')
        if observation.get('preference') not in (None,'candidate_better','equivalent','docling_better','indeterminate'):
            raise ValueError('Invalid preference')
        if observation.get('issue_type') not in (None,'column_mix','paragraph_break','heading_after_content','route_intrusion','grouping','other'):
            raise ValueError('Invalid issue type')
        if not isinstance(observation.get('id'),str) or not observation['id'] or not isinstance(observation.get('note',''),str):
            raise ValueError('Invalid observation')

    def _commit(self, observations, states, expected_revision):
        self.directory.mkdir(exist_ok=True)
        if self.directory.resolve().parent!=self.run_path or (self.directory/'history.jsonl').is_symlink():
            raise ValueError('Review history escapes the run')
        lock = self.directory/'.write-lock'
        try:
            descriptor = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as error:
            raise ValueError('Concurrent review edit') from error
        os.close(descriptor)
        temporary = self.directory/('pending-'+uuid.uuid4().hex+'.json')
        try:
            current = self.load()
            if current['revision']!=expected_revision:
                raise ValueError('Review revision conflict')
            existing = {o['id']:o for o in current['observations']}
            previous = []
            for observation in observations:
                self._validate(observation)
                if observation['id'] in existing:
                    previous.append(existing[observation['id']])
                existing[observation['id']] = dict(observation,utc=datetime.now(timezone.utc).isoformat())
            if not set(states).issubset(self.cases) or any(s not in ('not_reviewed','partial','reviewed') for s in states.values()):
                raise ValueError('Invalid imported review states')
            value = dict(current,revision=current['revision']+1,observations=list(existing.values()),states=dict(current['states'],**states))
            with temporary.open('x',encoding='utf-8') as stream:
                json.dump(value,stream,indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            with (self.directory/'history.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(dict(revision=current['revision'],previous_observations=previous,
                    previous_states={key:current['states'].get(key) for key in states}))+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.directory/'reviews.json')
            return value
        finally:
            temporary.unlink(missing_ok=True)
            lock.unlink()

    def save(self, observation, expected_revision):
        return self._commit([observation],{observation['case_id']:observation['review_state']},expected_revision)

    def import_data(self, data, expected_revision):
        for key in ('run_id','input_profile_id','run_sha256'):
            if data.get(key)!=self.load()[key]:
                raise ValueError('Import identity mismatch')
        return self._commit(data['observations'],data['states'],expected_revision)


def load_reviews(run_path):
    return ReviewStore(run_path).load()


def save_observation(run_path, obs, expected_revision):
    return ReviewStore(run_path).save(obs,expected_revision)

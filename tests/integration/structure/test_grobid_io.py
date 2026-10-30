import copy
import importlib
import json
import socket
import http.client
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from integration.reading_order.export import digest,write
from .test_grobid_core import baseline,tei
from integration.structure.grobid_export import export_saved_tei
from integration.structure.runners.grobid_trial import verify_lock,request_once,parameters,PIN,COMPONENTS,transport


def locked(root,pdf,B,raw_sha=None):
    model=root/'fixture-model';model.write_bytes(b'fixture only, not weights');config=root/'fixture-config';config.write_bytes(b'fixture config')
    return dict(schema_version='grobid-runtime-lock/1',image=PIN,platform='linux/amd64',version='0.9.1',prepared=True,image_layers_verified=True,config_verified=True,models_verified=True,
        files={str(model):digest(model),str(config):digest(config)},model_paths=[str(model)],config_path=str(config),pdf_sha256=digest(pdf),baseline_sha256=digest(B),funders_parameter='consolidateFunders',funders_parameter_verified=True,
        network_egress_disabled=True,resources=dict(cpus=4,memory_gib=8,java_heap_gib=4),runtime_ref='fixture-runtime',components={c:[str(model)] for c in COMPONENTS})


class RunnerTests(unittest.TestCase):
    def test_stream_preserves_bytes_headers_and_failure(self):
        class Response:
            status=200
            def getheaders(self):return [('Content-Type','application/xml')]
            def read(self,*a):raise http.client.IncompleteRead(b'<TEI>partial',200)
            def read1(self,*a):raise http.client.IncompleteRead(b'<TEI>partial',200)
        class Conn:
            def request(self,*a):pass
            def getresponse(self):return Response()
            def close(self):pass
        with patch('http.client.HTTPConnection',return_value=Conn()):
            result=transport('http://127.0.0.1:8070/api/processFulltextDocument',b'',{},900)
        self.assertEqual(result['raw'],b'<TEI>partial');self.assertEqual(result['http_status'],200);self.assertEqual(result['status'],'execution_state_unknown')
    def test_import_has_no_network_or_process(self):
        with patch('socket.socket',side_effect=AssertionError('network')),patch('subprocess.run',side_effect=AssertionError('process')):importlib.reload(importlib.import_module('integration.structure.runners.grobid_trial'))
    def test_parameters_disable_all_consolidation(self):
        p=parameters('consolidateFunders');self.assertEqual([v for k,v in p if k.startswith('consolidat')],['0','0','0']);self.assertEqual(sum(k=='teiCoordinates' for k,v in p),10)
    def test_lock_rejects_unprepared_or_changed_models(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            r=Path(t).resolve();pdf=r/'pdf';pdf.write_bytes(b'fixture');B=r/'B';B.write_bytes(b'fixture');lock=locked(r,pdf,B);verify_lock(lock,pdf,B)
            bad=copy.deepcopy(lock);bad['image']='latest'
            with self.assertRaises(ValueError):verify_lock(bad,pdf,B)
            bad=copy.deepcopy(lock);bad['model_paths']=[]
            with self.assertRaises(ValueError):verify_lock(bad,pdf,B)
            Path(lock['model_paths'][0]).write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_lock(lock,pdf,B)
    def test_timeout_one_request_and_guard_prevents_retry(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            r=Path(t).resolve();pdf=r/'pdf';pdf.write_bytes(b'fixture');B=r/'B';B.write_bytes(b'fixture');lock=locked(r,pdf,B);lp=r/'lock.json';write(lp,lock);dest=r/'attempt';calls=[]
            def fake(url,body,headers,timeout):calls.append(url);raise socket.timeout('fixture timeout')
            result=request_once(pdf,B,lp,dest,authorized=True,transport=fake)
            self.assertEqual(result['status'],'execution_state_unknown');self.assertEqual(len(calls),1)
            self.assertIsNone(result['models_executed'])
            with self.assertRaises(FileExistsError):request_once(pdf,B,lp,dest,authorized=True,transport=fake)
            self.assertEqual(len(calls),1)
    def test_response_raw_kept_before_interpretation_and_no_authorization(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            r=Path(t).resolve();pdf=r/'pdf';pdf.write_bytes(b'fixture');B=r/'B';B.write_bytes(b'fixture');lp=r/'lock.json';write(lp,locked(r,pdf,B))
            with self.assertRaises(PermissionError):request_once(pdf,B,lp,r/'no',authorized=False)
            raw=b'broken XML';request_once(pdf,B,lp,r/'yes',authorized=True,transport=lambda *a:(200,raw,{'content-type':'application/xml'}))
            self.assertEqual((r/'yes/raw/response.tei.xml').read_bytes(),raw)


class ExportTests(unittest.TestCase):
    def test_saved_tei_export_no_models_and_hash_guards(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as t:
            r=Path(t).resolve();pdf=r/'fixture.pdf';pdf.write_bytes(b'fixture');b=baseline();b['native_pdf_sha256']=digest(pdf);bp=r/'B.json';write(bp,b);write(r/'manifest.json',dict(outputs={'B.json':digest(bp)}));lock=locked(r,pdf,bp);lp=r/'lock.json';write(lp,lock)
            attempt=r/'attempt';raw=tei();request_once(pdf,bp,lp,attempt,authorized=True,transport=lambda *a:(200,raw,{}))
            result=export_saved_tei(bp,attempt/'raw/response.tei.xml',lp,r/'C')
            self.assertEqual(result['denominators']['units'],1);self.assertEqual((r/'C/raw/response.tei.xml').read_bytes(),raw)
            with self.assertRaises(FileExistsError):export_saved_tei(bp,attempt/'raw/response.tei.xml',lp,r/'C')
            (attempt/'raw/response.tei.xml').write_bytes(b'changed')
            with self.assertRaises(ValueError):export_saved_tei(bp,attempt/'raw/response.tei.xml',lp,r/'bad')


if __name__=='__main__':unittest.main()

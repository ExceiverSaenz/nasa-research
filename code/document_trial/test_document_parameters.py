"""Offline document parameterization; never calls a model or Colab."""
import copy
import json
from pathlib import Path
import tempfile
import shutil
import re
import sys
from unittest.mock import patch
import unittest
from .common import ROOT, DOCUMENT, PAGE3, read, sha
from .prepare import document_parameters, prepare
from .worker import validate_document_plan, regression_render_check


class DocumentParameterTests(unittest.TestCase):
    def test_other_pdf_and_original(self):
        p=document_parameters(ROOT/'SiC_papers/3.pdf')
        self.assertEqual(p['page_count'],4)
        self.assertEqual(p['document_sha256'],sha(ROOT/'SiC_papers/3.pdf'))
        self.assertIsNone(p['regression'])
        old=document_parameters(ROOT/'SiC_papers/12.pdf')
        self.assertEqual(old['document_sha256'],DOCUMENT)
        self.assertEqual(old['regression']['render_sha256'],PAGE3)

    def test_regression_by_identity_not_page_number_alone(self):
        p=document_parameters(ROOT/'SiC_papers/3.pdf')
        regression_render_check(p,3,'different')
        p=document_parameters(ROOT/'SiC_papers/12.pdf')
        with self.assertRaises(ValueError):regression_render_check(p,3,'different')
        regression_render_check(p,3,PAGE3)
        p['regression']=None
        with self.assertRaises(ValueError):regression_render_check(p,3,PAGE3)

    def test_document_identity_and_pages_are_checked(self):
        pdf=ROOT/'SiC_papers/3.pdf';p=document_parameters(pdf)
        validate_document_plan(p,pdf)
        for field,value in [('document_sha256',DOCUMENT),('physical_pages',[1,1]),('physical_pages',[5]),('dpi',0)]:
            altered=copy.deepcopy(p);altered[field]=value
            with self.assertRaises(ValueError):validate_document_plan(altered,pdf)

    def test_outside_collection_rejected(self):
        with self.assertRaises(ValueError):document_parameters(ROOT/'SOURCES.md')

    def test_launcher_rejects_external_plan_before_remote(self):
        script=(ROOT/'code/document_trial/run_document.sh').read_text()
        preflight=re.search(r'python3 - "\$PACKAGE" <<\'PY\'\n(.*?)\nPY',script,re.S).group(1)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest=Path(folder)/'package';shutil.copytree(ROOT/'code/packages/sic-parsing-v1/3',dest)
            (dest/'plan.json').write_text('{}')
            with patch.object(sys,'argv',['preflight',str(dest)]),self.assertRaisesRegex(ValueError,'External plan differs'):
                exec(preflight,{})


if __name__=='__main__':unittest.main()

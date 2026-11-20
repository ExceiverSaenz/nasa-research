"""Relocation checks with synthetic report data; no scientific generators run."""
import importlib
import json
from pathlib import Path
import pytest


def workspace(tmp_path):
    (tmp_path/'.layout.json').write_text(json.dumps({'schema':'bounding-box-layout/2',
        'prefixes':{'analysis/':'raw_results/analytics/'},'files':{}}))
    data=tmp_path/'raw_results/analytics/fixture'
    data.mkdir(parents=True)
    return data


def test_authored_report_uses_reports_directory_and_rebases_images(tmp_path):
    from bbx.layout import authored_report_path, write_authored_report
    data=workspace(tmp_path)
    (data/'plot.png').write_bytes(b'fixture')
    report=authored_report_path(data)
    assert report==tmp_path/'reports/analytics/fixture/report.md'
    write_authored_report(data,'# Fixture\n\n![Plot](plot.png)\n')
    assert report.is_file() and not (data/'report.md').exists()
    assert '../../../raw_results/analytics/fixture/plot.png' in report.read_text()


@pytest.mark.parametrize('kind',['geometry','targets'])
def test_report_guard_checks_relocated_report_before_reading_data(tmp_path,monkeypatch,kind):
    data=workspace(tmp_path)
    report=tmp_path/'reports/analytics/fixture/report.md'
    report.parent.mkdir(parents=True)
    report.write_text('preserved report')
    monkeypatch.setenv('MPLCONFIGDIR',str(tmp_path/'matplotlib'))
    module=importlib.import_module('analytics.'+kind+'.report')
    if kind=='targets':monkeypatch.setattr(module,'OUT',data)
    with pytest.raises(RuntimeError,match='Report exists'):
        module.main(data) if kind=='geometry' else module.main()
    assert report.read_text()=='preserved report'

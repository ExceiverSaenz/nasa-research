"""Inspection is read-only. Remote phases require explicit opt-in flags."""
import argparse
import json
from pathlib import Path
from bbx.contracts import load_experiment,write_json,exit_code
from bbx.preflight import inspect_local,inventory
from bbx.r2 import probe_r2

from bbx.layout import project_root, resolve_path
ROOT=project_root(__file__)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect');inspect.add_argument('--papers',type=Path,default=ROOT.parents[1]/'papers'/'SiC_papers')
    inspect.add_argument('--r2-config',type=Path);inspect.add_argument('--output',type=Path,default=ROOT/'runtime'/'local-preflight.json')
    storage=sub.add_parser('storage');storage.add_argument('action',choices=['inspect','verify','apply','restore'])
    storage.add_argument('--root',type=Path,default=ROOT);storage.add_argument('--backup',type=Path)
    prep=sub.add_parser('prepare');prep.add_argument('--environment',choices=['a','b'],required=True)
    prep.add_argument('--python',type=Path,required=True);prep.add_argument('--target',type=Path,required=True)
    prep.add_argument('--apply',action='store_true',help='Explicitly allow installation; default inspection only')
    agg=sub.add_parser('aggregate');agg.add_argument('attempt',type=Path);agg.add_argument('--inventory',type=Path,required=True)
    agg.add_argument('--pdf-dir',type=Path);agg.add_argument('--run-id',required=True)
    remote=sub.add_parser('colab');remote.add_argument('phase',choices=['plan','prepare','smoke','execute'])
    remote.add_argument('--attempt',type=Path,required=True);remote.add_argument('--papers',type=Path,default=ROOT.parents[1]/'papers'/'SiC_papers')
    remote.add_argument('--r2-config',type=Path);remote.add_argument('--allow-session',action='store_true')
    remote.add_argument('--allow-inference',action='store_true')
    args=p.parse_args()
    if args.command=='storage':
        from bbx.artifact_store import ArtifactStore,plan_duplicates,restore_backup
        if args.action in ('apply','restore') and not args.backup:p.error('apply/restore requires --backup')
        store=ArtifactStore(args.root)
        if args.action=='inspect':result=plan_duplicates(args.root)
        elif args.action=='verify':result=store.verify()
        elif args.action=='restore':result=restore_backup(args.root,args.backup)
        else:result=store.migrate(args.backup)
        print(json.dumps(result,indent=2));return 0
    if args.command=='inspect':
        checks=inspect_local(ROOT,args.papers)
        if args.r2_config:checks.extend(probe_r2(args.r2_config,inventory(args.papers)))
        write_json(args.output,checks);print(json.dumps([{'id':c['id'],'status':c['status'],'reason':c['reason']} for c in checks],indent=2))
        return exit_code(checks)
    if args.command=='prepare':
        from bbx.environment import prepare_environment
        from bbx.prepare import install_environment
        python=args.target/('Scripts/python.exe' if __import__('os').name=='nt' else 'bin/python')
        spec={'python':python,'lock':resolve_path(ROOT/'requirements'/f'{args.environment}.lock',root=ROOT)}
        result=prepare_environment(spec,apply=args.apply,installer=lambda s:install_environment(args.python,args.target,s['lock']))
        print(json.dumps(result,indent=2))
        return 0 if result['action']=='reuse' else 2
    if args.command=='aggregate':
        from bbx.delivery import aggregate
        aggregate(args.attempt,load_experiment(args.inventory),load_experiment(ROOT/'experiment.json'),args.run_id,
                  render=args.pdf_dir is not None,pdf_dir=args.pdf_dir)
    if args.command=='colab':
        if args.phase=='plan':
            print(json.dumps({'session_will_start':False,'sequence':['heron','heron101','basic','standard'],
                'environments':['a','b'],'attempt':str(args.attempt),'phase':'plan'},indent=2));return 0
        if args.phase=='prepare' and (not args.allow_session or not args.r2_config):p.error('prepare requires --allow-session and --r2-config')
        if args.phase in ('smoke','execute') and (not args.allow_inference or not args.r2_config):p.error('inference requires --allow-inference and --r2-config')
        import platform
        if platform.system()!='Linux':p.error('Run remote orchestration from WSL/Linux with the existing Colab CLI')
        from bbx.workflow import Workflow
        from bbx.transport import ColabTransport
        flow=Workflow(ROOT,args.attempt,ColabTransport(args.attempt/'transport'))
        if args.phase=='prepare':result=flow.prepare(inventory(args.papers),allow_remote=args.allow_session,papers_dir=args.papers,r2_config=args.r2_config)
        elif args.phase=='smoke':result=flow.smoke(args.r2_config,allow_inference=args.allow_inference)
        else:result=flow.execute(args.r2_config,allow_inference=args.allow_inference)
        print(json.dumps(result,indent=2));return 0
    return 0


if __name__=='__main__':raise SystemExit(main())

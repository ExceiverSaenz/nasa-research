from .contracts import validate_experiment, exit_code
from .r2 import safe_error
import hashlib
import json
from datetime import datetime,timezone,timedelta

required_gates=('configuration','pdf_inventory','r2_access','lock:a','lock:b','model_manifests')


def execute(config,services,*,authorized=False,gates=None):
    digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    named={c.get('id'):c for c in gates or []}
    try:
        fresh=all(0 <= (datetime.now(timezone.utc)-datetime.fromisoformat(named[id]['timestamp_utc'])).total_seconds()<3600
                  and named[id].get('evidence',{}).get('config_sha256')==digest for id in required_gates)
    except (KeyError,ValueError,TypeError):fresh=False
    if not authorized or not config.get('ready') or not fresh or exit_code(gates or []) or exit_code(validate_experiment(config)):
        raise ValueError('Authorization and completed local gates required')
    result={'status':'running','stages':[],'session':None}
    try:
        result['session']=services.create()
        for tool in config['tools']:
            stage=services.stage(result['session'],tool);result['stages'].append(stage)
            if not stage.get('complete') or not stage.get('verified') or stage.get('workers_remaining',True):
                raise ValueError('Stage incomplete, unverified or workers remaining')
        services.close(result['session']);result['status']='complete'
    except Exception as e:result.update(status='manual_review',error=safe_error(e))
    return result

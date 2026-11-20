"""Read-only bounded API observation; never print bearer URLs or credentials."""
import json,datetime,sys
from pathlib import Path
import requests
from colab_cli.state import StateStore
from colab_cli.contents import ContentsClient
state=StateStore().get(sys.argv[1] if len(sys.argv)>1 else 'order-collection-20261102')
client=ContentsClient(state)
params={'authuser':'0','colab-runtime-proxy-token':client.token}
result={'time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
for name,route in [('kernels','/api/kernels'),('content','/api/contents/content')]:
    try:
        response=requests.get(client.base_url+route,params=params,timeout=15)
        response.raise_for_status();value=response.json()
        result[name]=[{'id':v['id'],'execution_state':v.get('execution_state'),'last_activity':v.get('last_activity')} for v in value] if name=='kernels' else [{'name':v['name'],'type':v['type']} for v in value.get('content',[])]
    except Exception as error:result[name]={'error_type':type(error).__name__}
with (Path(__file__).parent/'session-observations.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
print(json.dumps(result))

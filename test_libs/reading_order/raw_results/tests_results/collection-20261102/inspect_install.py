import json,sys,datetime
from pathlib import Path
import requests
from colab_cli.state import StateStore
from colab_cli.contents import ContentsClient
client=ContentsClient(StateStore().get('order-collection-20261102-r4'))
original=requests.request
def bounded(*args,**kwargs):kwargs['timeout']=15;return original(*args,**kwargs)
requests.request=bounded
result={'time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
for name,path in [('packages','/content/order-config-20261102/venv/lib/python3.11/site-packages'),('cache','/root/.cache/uv'),('environment','/content/order-config-20261102')]:
 try:
  entries=client.list_dir(path)['content']
  result[name]={'entries':len(entries),'torch_present':any(v['name']=='torch' for v in entries),'latest_modified':max(v.get('last_modified','') for v in entries)}
  if name!='packages':result[name]['names']=[v['name'] for v in entries]
 except Exception as error:result[name]={'error_type':type(error).__name__}
with (Path(__file__).parent/'install-observations.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
print(json.dumps(result))

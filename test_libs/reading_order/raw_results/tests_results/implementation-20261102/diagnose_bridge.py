import json
print({k: (v.poll() if k=='_order_child' else v) for k,v in globals().copy().items() if k in ('_order_active','_order_child')})
if '_order_line' in globals() and _order_line.startswith('ORDER_RESULT:'):
    value=json.loads(_order_line[len('ORDER_RESULT:'):])
    print(dict(last_status=value.get('status','PASS'),ordered_ids_count=len(value.get('ordered_ids') or [])))
print('last_exception',type(getattr(__import__('sys'),'last_value',None)).__name__)

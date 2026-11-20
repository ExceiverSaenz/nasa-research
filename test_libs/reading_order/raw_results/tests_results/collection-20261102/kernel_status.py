import json
bridge=globals().get('_order_bridge')
print('ORDER_DIAGNOSTIC:'+json.dumps(dict(bridge_exists=bridge is not None,
    candidate=getattr(bridge,'candidate',None),completed=len(getattr(bridge,'completed',{})),
    pending=len(globals().get('_order_pending',{})))))

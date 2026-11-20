import sys
print('exception_type',type(getattr(sys,'last_value',None)).__name__)
if getattr(sys,'last_value',None):print('static_bridge_error',str(sys.last_value))
if '_order_bridge' in globals():
    print(dict(candidate=_order_bridge.candidate,completed=len(_order_bridge.completed),
        worker_status=_order_bridge.child.poll() if _order_bridge.child else None))
print('kernel_healthy')

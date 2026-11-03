from colab_cli.state import StateStore
from colab_cli.runtime import ColabRuntime
s=StateStore().get('order-pilot-20261102')
r=ColabRuntime(s.url,s.token,history=None,session_name=None,kernel_id=s.kernel_id,session_id=s.session_id)
r.kernel_client.interrupt()
print(r.execute_code("if '_order_child' in globals() and _order_child.poll() is None:\n _order_child.kill()\n _order_child.wait(timeout=10)\nprint('ORDER_KERNEL_RECOVERED')",timeout=30))
r.stop()

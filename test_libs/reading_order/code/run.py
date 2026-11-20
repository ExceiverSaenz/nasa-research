"""CLI entrypoint. No action starts engines implicitly."""
from reading_order.cli import main

if __name__=='__main__':
    raise SystemExit(main())

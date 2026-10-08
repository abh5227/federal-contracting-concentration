"""The pipeline. Every `python -m src.<module>` command, and the dashboard, imports this file first, so the version
check below runs before Python reads any module that needs 3.12 or later. Keep this file's syntax old enough for
any Python 3 to read."""

import sys

if sys.version_info < (3, 12):
    sys.exit("This project needs Python 3.12 or later (it is tested on 3.13.1), and this is Python "
             + ".".join(str(n) for n in sys.version_info[:3]) + ". Create the environment with "
             "python3.13 -m venv .venv, then run commands with .venv/bin/python.")

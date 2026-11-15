"""Make the caller a Lake Formation data lake administrator (run by ./scripts/deploy.sh C5, before terraform)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "common", "lf_admin.py"), "add"], check=True)

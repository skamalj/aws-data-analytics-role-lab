"""Restore the original Lake Formation settings (run by ./scripts/destroy.sh C5, after terraform destroy)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "common", "lf_admin.py"), "restore", "C5"], check=True)

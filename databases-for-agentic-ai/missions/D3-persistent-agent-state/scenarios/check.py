"""Grading entry point for this mission: runs its scenario checks in order; exit code 0 only if all pass."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ["resume.py", "long_chat.py", "check_ttl.py"]
failed = False
for s in SCRIPTS:
    print(f"\n### {s}")
    failed |= subprocess.run([sys.executable, os.path.join(HERE, s)]).returncode != 0
sys.exit(1 if failed else 0)

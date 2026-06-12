import os
import sys
from pathlib import Path
from orchestrator.project_config import find_project_root, PROJECT_CONFIG

print(f"CWD: {Path.cwd()}")
print(f"ENV ROOT: {os.environ.get('ORCHESTRATOR_PROJECT_ROOT')}")
print(f"FIND_PROJECT_ROOT: {find_project_root()}")
print(f"PROJECT_CONFIG.root: {PROJECT_CONFIG.root}")

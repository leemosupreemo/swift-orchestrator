#!/usr/bin/env python3
import os
import re
from pathlib import Path

from typing import List, Optional

from common import ROOT
from orchestrator.project_config import PROJECT_CONFIG

def generate_test_index(tests_dir: Path, likely_files: Optional[List[str]] = None) -> str:
    index = []
    
    # Heuristic: If we have likely files, only show tests that share a keyword
    # or are recently modified.
    keywords = set()
    if likely_files:
        for f in likely_files:
            # Extract basic name without path or extension
            name = Path(f).stem
            # Split CamelCase or snake_case into parts
            parts = re.findall(r'[A-Z]?[a-z0-9]+', name)
            keywords.update(p.lower() for p in parts if len(p) > 3)

    for root, _, files in os.walk(tests_dir):
        for file in files:
            path = Path(root) / file
            
            is_relevant = True
            if keywords:
                is_relevant = any(k in file.lower() for k in keywords)
            
            if file.endswith("Tests.swift"):
                if not is_relevant: continue
                
                content = path.read_text(encoding="utf-8")
                # Find class names
                classes = re.findall(r"class\s+(\w+)\s*:\s*XCTestCase", content)
                for cls in classes:
                    # Determine target based on subdirectory
                    rel_path = path.relative_to(tests_dir)
                    target = PROJECT_CONFIG.test_target
                    index.append(f"- {target}/{cls} (in {rel_path})")
            elif file.startswith("test_") and file.endswith(".py"):
                if not is_relevant: continue
                rel_path = path.relative_to(ROOT)
                index.append(f"- python3 {rel_path}")
                
    if not index and likely_files:
        # Fallback: if no matches found, show the 20 most recently modified tests
        # to at least give some options.
        all_tests = []
        for root, _, files in os.walk(tests_dir):
            for file in files:
                if file.endswith("Tests.swift") or (file.startswith("test_") and file.endswith(".py")):
                    path = Path(root) / file
                    all_tests.append(path)
        
        recent = sorted(all_tests, key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        for path in recent:
            if path.suffix == ".swift":
                classes = re.findall(r"class\s+(\w+)\s*:\s*XCTestCase", path.read_text(encoding="utf-8"))
                for cls in classes:
                    rel_path = path.relative_to(tests_dir)
                    index.append(f"- {PROJECT_CONFIG.test_target}/{cls} (in {rel_path}) [RECENT]")
            else:
                rel_path = path.relative_to(ROOT)
                index.append(f"- python3 {rel_path} [RECENT]")

    return "\n".join(sorted(index))

if __name__ == "__main__":
    print(f"--- {PROJECT_CONFIG.test_target} ---")
    print(generate_test_index(ROOT / PROJECT_CONFIG.test_target))

#!/usr/bin/env python3
import os
import re
from pathlib import Path

from typing import List, Optional

from common import ROOT
from orchestrator.project_config import PROJECT_CONFIG
from dev_console import discover_test_suites

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

    search_root = tests_dir if tests_dir.exists() else ROOT
    suites = discover_test_suites(search_root)

    for s in suites:
        rel_path = s["rel_path"]
        suite_name = s["name"]
        
        is_relevant = True
        if keywords:
            is_relevant = any(k in str(rel_path).lower() or k in suite_name.lower() for k in keywords)
            
        if is_relevant:
            target = PROJECT_CONFIG.test_target or "Tests"
            index.append(f"- {target}/{suite_name} (in {rel_path})")

    # Also handle Python tests if searching root or tests dir
    if search_root.exists():
        for root, _, files in os.walk(search_root):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    path = Path(root) / file
                    is_relevant = True
                    if keywords:
                        is_relevant = any(k in file.lower() for k in keywords)
                    if is_relevant:
                        try:
                            rel_path = path.relative_to(ROOT)
                        except ValueError:
                            rel_path = Path(file)
                        index.append(f"- python3 {rel_path}")

    if not index and likely_files and suites:
        # Fallback: if no matches found, show the 20 most recently modified tests
        recent = sorted(suites, key=lambda s: s["path"].stat().st_mtime if s["path"].exists() else 0, reverse=True)[:20]
        for s in recent:
            target = PROJECT_CONFIG.test_target or "Tests"
            index.append(f"- {target}/{s['name']} (in {s['rel_path']}) [RECENT]")

    return "\n".join(sorted(index))

if __name__ == "__main__":
    print(f"--- {PROJECT_CONFIG.test_target} ---")
    print(generate_test_index(ROOT / PROJECT_CONFIG.test_target))


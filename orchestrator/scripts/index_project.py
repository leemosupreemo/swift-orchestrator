#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT, write_text, DOCS_DIR, safe_relative_path

def index_project():
    print(f"🔍 Indexing project structure in \033[97m{ROOT}\033[0m...")
    
    # 1. Identify Project Type
    project_type = "Unknown"
    key_files = []
    if (ROOT / "Package.swift").exists():
        project_type = "Swift Package Manager (SPM)"
        key_files.append("Package.swift")
    
    xcodeproj = list(ROOT.glob("*.xcodeproj"))
    xcworkspace = list(ROOT.glob("*.xcworkspace"))
    if xcodeproj:
        project_type = "Xcode Project"
        key_files.extend([p.name for p in xcodeproj])
    if xcworkspace:
        project_type = "Xcode Workspace"
        key_files.extend([w.name for w in xcworkspace])
        
    if (ROOT / "Podfile").exists():
        project_type += " (with CocoaPods)"
        key_files.append("Podfile")
        
    # 2. Scan top-level folders
    # Exclude hidden folders, docs, and common build artifacts
    exclude = {".git", ".orchestrator", "docs", "build", ".build", "DerivedData", "node_modules"}
    folders = [f for f in ROOT.iterdir() if f.is_dir() and f.name not in exclude and not f.name.startswith(".")]
    
    # 3. Build Markdown
    lines = [
        "# Project Architecture",
        "",
        "This document provides a high-level overview of the project structure for AI grounding.",
        "",
        f"**Project Type:** {project_type}",
        "",
        "## Key Entry Points",
    ]
    if not key_files:
        lines.append("- (No standard entry points found)")
    else:
        for k in key_files:
            lines.append(f"- `{k}`")
        
    lines.extend([
        "",
        "## Folder Structure",
        "",
    ])
    
    if not folders:
        lines.append("- (No significant folders found in root)")
    else:
        for f in sorted(folders, key=lambda x: x.name):
            lines.append(f"### `{f.name}/`")
            # Heuristic for folder purpose
            purpose = "Contains project source code."
            name_lower = f.name.lower()
            if "test" in name_lower:
                purpose = "Contains unit, integration, or UI tests."
            elif "script" in name_lower or "tool" in name_lower:
                purpose = "Contains developer tools, build scripts, or automation."
            elif "resource" in name_lower or "asset" in name_lower:
                purpose = "Contains images, localized strings, and other assets."
            elif "core" in name_lower or "model" in name_lower:
                purpose = "Contains the core business logic and data models."
            elif "ui" in name_lower or "view" in name_lower:
                purpose = "Contains the user interface components."
                
            lines.append(purpose)
            lines.append("")
        
    lines.extend([
        "## Technology Stack",
        "- **Language:** Swift",
        "- **Platform:** Apple (iOS/macOS)",
        ""
    ])
    
    content = "\n".join(lines)
    
    arch_path = DOCS_DIR / "architecture.md"
    if arch_path.exists():
        print(f"  ⚠️  {safe_relative_path(arch_path, ROOT)} already exists. Skipping overwrite.")
    else:
        write_text(arch_path, content)
        print(f"  ✅ Drafted architecture summary to \033[97m{safe_relative_path(arch_path, ROOT)}\033[0m.")

    # 4. Also check for coding standards
    standards_path = DOCS_DIR / "coding-standards.md"
    if not standards_path.exists():
        standards_content = """# Coding Standards

- **Language:** Swift 6.0+
- **Style:** Follow [Ray Wenderlich Swift Style Guide](https://github.com/raywenderlich/swift-style-guide).
- **Concurrency:** Prefer Structured Concurrency (async/await).
- **Architecture:** (e.g. MVVM, TCA, Clean Architecture)
- **Tests:** XCTest or Swift Testing.
"""
        write_text(standards_path, standards_content)
        print(f"  ✅ Drafted coding standards to \033[97m{safe_relative_path(standards_path, ROOT)}\033[0m.")

if __name__ == "__main__":
    index_project()

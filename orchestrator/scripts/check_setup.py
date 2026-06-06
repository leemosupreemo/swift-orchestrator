#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import json
import re
import shutil
from pathlib import Path

# Add scripts dir to path
import sys
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import CONFIG_DIR, DOCS_DIR, ROOT, read_json
from orchestrator.project_config import PROJECT_CONFIG

REMEDIATION_GUIDE = {
    "Homebrew": {
        "url": "https://brew.sh",
        "cmd": '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    },
    "Node.js": {
        "url": "https://nodejs.org",
        "cmd": 'brew install node'
    },
    "GitHub CLI (gh)": {
        "url": "https://cli.github.com",
        "cmd": "brew install gh",
        "auth": "gh auth login"
    },
    "Gemini CLI": {
        "url": "https://geminicli.com",
        "cmd": "brew install gemini-cli",
        "auth": "gemini"
    },
    "Claude Code": {
        "url": "https://code.claude.com",
        "cmd": "npm install -g @anthropic-ai/claude-code",
        "auth": "claude auth login"
    },
    "Codex CLI": {
        "url": "https://github.com/openai/codex",
        "cmd": "npm install -g @openai/codex",
        "auth": "codex login"
    },
    "Ollama": {
        "url": "https://ollama.com",
        "cmd": "brew install ollama"
    },
    "OpenCode": {
        "url": "https://opencode.ai",
        "cmd": "curl -fsSL https://opencode.ai/install.sh | sh",
        "auth": "opencode auth login"
    },
    "Xcode CLI Tools": {
        "url": "https://developer.apple.com/xcode/",
        "cmd": "xcode-select --install"
    }
}

def print_result(success: bool, name: str, info: str = "", fix_key: str | None = None):
    icon = "✅" if success else "❌"
    print(f"  {icon} {name:30} {info}")
    if not success and fix_key:
        print_remediation(fix_key)

def print_remediation(key: str):
    guide = REMEDIATION_GUIDE.get(key)
    if not guide: return
    print(f"     \033[93m└─ INSTALL: {guide['cmd']}\033[0m")
    print(f"        \033[94mDocs   : {guide['url']}\033[0m")
    if "auth" in guide:
        print(f"        \033[95mAuth   : {guide['auth']}\033[0m")

def check_file_content(path: Path, pattern: str) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return re.search(pattern, content) is not None

def check():
    print("📋 Starting AI Agent 'Plug & Play' Verification...\n")
    settings_path = CONFIG_DIR / "settings.json"
    
    # 0. Check Core Prerequisites
    print("--- 1. Core Prerequisites ---")
    has_brew = shutil.which("brew") is not None
    print_result(has_brew, "Homebrew", "INSTALLED" if has_brew else "MISSING", "Homebrew")

    has_node = shutil.which("node") is not None
    print_result(has_node, "Node.js", "INSTALLED" if has_node else "MISSING", "Node.js")

    has_xcode = shutil.which("xcodebuild") is not None
    print_result(has_xcode, "Xcode CLI Tools", "INSTALLED" if has_xcode else "MISSING", "Xcode CLI Tools")
    
    # 1. Check Essential Files
    print("\n--- 2. Project Config ---")
    
    if PROJECT_CONFIG.firebase_distribution:
        app_dir = ROOT / PROJECT_CONFIG.project_name
        gs_path = app_dir / "GoogleService-Info.plist"
        if gs_path.exists():
            is_ok = check_file_content(gs_path, r"<key>PROJECT_ID</key>")
            print_result(is_ok, "GoogleService-Info.plist", "OK" if is_ok else "INVALID")
        else:
            print_result(False, "GoogleService-Info.plist", "MISSING",
                         f"Place in {PROJECT_CONFIG.project_name}/GoogleService-Info.plist")
    else:
        print_result(True, "Firebase config", "SKIPPED")

    m_path = CONFIG_DIR / "machines.json"
    print_result(m_path.exists(), "machines.json", "OK" if m_path.exists() else "MISSING",
                 f"Define your fleet in {m_path}")

    # Grounding Docs
    print("\n--- 3. Grounding Docs (Critical for AI) ---")
    docs = [
        ("Architecture", "docs/architecture.md"), 
        ("Standards", "docs/coding-standards.md"), 
        ("Build Commands", "docs/build-test-commands.md"), 
        ("AI Rules", "AGENTS.md")
    ]
    for name, d in docs:
        exists = (ROOT / d).exists()
        print_result(exists, f"Doc: {name}", "OK" if exists else "MISSING")
        if not exists:
            print(f"        \033[90m(File: {d})\033[0m")

    # 3. Check GitHub Environment
    print("\n--- 4. GitHub Integration ---")
    has_gh = shutil.which("gh") is not None
    print_result(has_gh, "GitHub CLI (gh)", "INSTALLED" if has_gh else "MISSING", "GitHub CLI (gh)")
    if has_gh:
        try:
            res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            is_auth = res.returncode == 0
            print_result(is_auth, "GitHub Auth session", "LOGGED IN" if is_auth else "EXPIRED", "GitHub CLI (gh)")
        except: pass

    # 4. Check LLM Providers
    print("\n--- 5. AI Providers (Need 1+) ---")
    
    env_keys = ["GEMINI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"]
    has_env_key = any(k in os.environ for k in env_keys)
    
    settings_keys = ["gemini_api_key", "anthropic_api_key", "openai_api_key"]
    has_settings_key = False
    if settings_path.exists():
        try:
            s_data = read_json(settings_path)
            has_settings_key = any(s_data.get(k) for k in settings_keys)
        except: pass
    
    print_result(has_env_key or has_settings_key, "Manual API Keys", "CONFIGURED" if (has_env_key or has_settings_key) else "NONE")

    # CLI Status Helpers
    def check_cli_status(cli_name, fix_key, status_args):
        installed = shutil.which(cli_name) is not None
        if not installed:
            print_result(False, f"{cli_name} CLI", "MISSING", fix_key)
            return False
        
        try:
            res = subprocess.run([cli_name] + status_args, capture_output=True, text=True, timeout=2)
            is_auth = res.returncode == 0
            print_result(is_auth, f"{cli_name} Auth", "LOGGED IN" if is_auth else "NOT LOGGED IN", fix_key if not is_auth else None)
            return is_auth
        except:
            print_result(True, f"{cli_name} CLI", "INSTALLED (Status Check Error)")
            return True

    claude_ok = check_cli_status("claude", "Claude Code", ["auth", "status"])
    codex_ok = check_cli_status("codex", "Codex CLI", ["login", "status"])
    gemini_ok = shutil.which("gemini") is not None
    if gemini_ok:
        print_result(True, "Gemini CLI", "INSTALLED")
    else:
        print_result(False, "Gemini CLI", "MISSING", "Gemini CLI")
        
    ollama_ok = shutil.which("ollama") is not None
    print_result(ollama_ok, "Ollama (Local AI)", "INSTALLED" if ollama_ok else "MISSING", "Ollama")

    if not (has_env_key or has_settings_key or claude_ok or codex_ok or gemini_ok or ollama_ok):
        print("\n\033[1;91m❌ CRITICAL ERROR: No AI providers found. The Orchestrator will fail.\033[0m")
    else:
        print("\n\033[1;92m✅ READY: At least one AI provider is configured.\033[0m")

    # 5. Check SSH Config
    print("\n--- 6. SSH & Network ---")
    ssh_config_path = Path.home() / ".ssh" / "config"
    print_result(ssh_config_path.exists(), "SSH Config File", "OK" if ssh_config_path.exists() else "MISSING")
    
    if m_path.exists():
        print("\nVerification Complete.")
    else:
        print(f"\n\033[93m💡 NEXT STEP: Create '{m_path}' to use remote workers.\033[0m")

if __name__ == "__main__":
    check()

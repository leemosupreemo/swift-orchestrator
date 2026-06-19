#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import json
import re
import shutil
import time
import threading
import shlex
from pathlib import Path

# Add scripts dir to path
import sys
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import CONFIG_DIR, DOCS_DIR, ROOT, read_json, print_header, print_divider, ProgressIndicator, StatusBar
from model_registry import cli_is_available, preferred_cli
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
    "Antigravity CLI": {
        "url": "https://antigravity.google/",
        "cmd": "agy",
        "auth": "agy"
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
    print(f"        \033[1;96mDocs   : {guide['url']}\033[0m")
    if "auth" in guide:
        print(f"        \033[95mAuth   : {guide['auth']}\033[0m")

def check_file_content(path: Path, pattern: str) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return re.search(pattern, content) is not None

def check_cli_auth(cli_name: str) -> tuple[bool, str]:
    """Checks if a CLI is installed and authenticated."""
    if shutil.which(cli_name) is None:
        return False, "\033[1;91mNOT INSTALLED\033[0m"
    
    try:
        if cli_name == "claude":
            res = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=5)
            ready = res.returncode == 0
        elif cli_name == "codex":
            res = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, timeout=5)
            ready = res.returncode == 0
        elif cli_name in {"gemini", "antigravity"}:
            # Antigravity/Gemini CLI doesn't have a status command yet, so we assume if it's installed it's ready
            ready = True
        elif cli_name == "opencode":
            res = subprocess.run(["opencode", "auth", "status"], capture_output=True, text=True, timeout=5)
            ready = res.returncode == 0
        elif cli_name == "ollama":
            ready = True
        else:
            ready = True
            
        return ready, "\033[92mREADY\033[0m" if ready else "\033[1;91mNOT LOGGED IN\033[0m"
    except Exception as e:
        return True, f"INSTALLED (Error checking status: {e})"

def get_auth_command(cli_name: str) -> str | None:
    """Returns the auth command for a given CLI binary name."""
    mapping = {
        "gh": "gh auth login",
        "gemini": preferred_cli("gemini"),
        "antigravity": preferred_cli("gemini"),
        "agy": "agy",
        "claude": "claude auth login",
        "codex": "codex login",
        "opencode": "opencode auth login"
    }
    return mapping.get(cli_name)

def should_render_progress_ui() -> bool:
    if os.environ.get("AI_PROGRESS_SILENT") == "1":
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()

def run_with_activity(label: str, operation, status_bar: StatusBar | None = None):
    """Run a blocking check while keeping the terminal footer and spinner alive."""
    if status_bar is None or not should_render_progress_ui():
        return operation()

    indicator = ProgressIndicator(label=label, hint="working")
    result = {}

    def target():
        try:
            result["value"] = operation()
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    while thread.is_alive():
        status_bar.render(at_bottom=True, activity=indicator)
        time.sleep(0.1)
    thread.join()
    status_bar.render(at_bottom=True, activity=indicator, force=True)

    if "error" in result:
        raise result["error"]
    return result.get("value")

def xcode_list_command() -> list[str]:
    args = ["xcodebuild", "-list", "-json"]
    if PROJECT_CONFIG.xcode_workspace:
        args.extend(["-workspace", PROJECT_CONFIG.xcode_workspace])
    elif PROJECT_CONFIG.xcode_project:
        args.extend(["-project", PROJECT_CONFIG.xcode_project])
    return args

def check():
    progress_ui = should_render_progress_ui()
    status_context = StatusBar({"allowed_machines": [], "allowed_models": []}, is_processing=True) if progress_ui else None
    if status_context:
        status_context.__enter__()
        status_context.set_scroll_region()
        status_context.render(at_bottom=True, force=True)

    try:
        return _check(status_context)
    finally:
        if status_context:
            status_context.clear_footer()
            status_context.__exit__(None, None, None)

def _check(status_bar: StatusBar | None = None):
    print_header("AI Agent 'Plug & Play' Verification")
    settings_path = CONFIG_DIR / "settings.json"
    
    # 0. Check Core Prerequisites
    print_header("1. Core Prerequisites")
    has_brew = shutil.which("brew") is not None
    print_result(has_brew, "Homebrew", "INSTALLED" if has_brew else "MISSING", "Homebrew")

    has_node = shutil.which("node") is not None
    print_result(has_node, "Node.js", "INSTALLED" if has_node else "MISSING", "Node.js")

    has_xcode = shutil.which("xcodebuild") is not None
    print_result(has_xcode, "Xcode CLI Tools", "INSTALLED" if has_xcode else "MISSING", "Xcode CLI Tools")
    
    # Git Check
    print_header("1a. Git Repository Sanity")
    is_git = (ROOT / ".git").exists()
    print_result(is_git, "Git Repository", "OK" if is_git else "MISSING")
    if is_git:
        try:
            def git_status():
                return subprocess.run(
                    ["git", "status", "--short"],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )

            res = run_with_activity("Refreshing Git index", git_status, status_bar)
            status = res.stdout.strip() if res.returncode == 0 else ""
            if status:
                print(f"     \033[1;93m⚠️  Warning: Uncommitted changes detected.\033[0m")
                print("        AI workflows work best with a clean slate.")
            else:
                print(f"     \033[1;92m✅ Repository is clean.\033[0m")
        except: pass
    
    # 1. Check Essential Files
    print_header("2. Project Config")
    
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

    # Xcode Sanity
    if PROJECT_CONFIG.xcode_project or PROJECT_CONFIG.xcode_workspace:
        print_header("2a. Xcode Build Settings")
        cmd = xcode_list_command()
        display_cmd = " ".join(shlex.quote(part) for part in cmd)
        try:
            # Quick check if scheme exists
            res = run_with_activity(
                "Reading Xcode build settings",
                lambda: subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=45),
                status_bar,
            )
            if res.returncode != 0:
                stderr = (res.stderr or res.stdout or "").strip().splitlines()
                detail = stderr[0] if stderr else f"Command failed: {display_cmd}"
                print(f"     \033[1;91m⚠️  Error checking Xcode: {detail}\033[0m")
                print(f"        \033[90mCommand: {display_cmd}\033[0m")
            elif PROJECT_CONFIG.scheme and PROJECT_CONFIG.scheme in res.stdout:
                print_result(True, f"Scheme: {PROJECT_CONFIG.scheme}", "FOUND")
            else:
                print_result(False, f"Scheme: {PROJECT_CONFIG.scheme}", "NOT FOUND", f"Ensure scheme exists in '{display_cmd}'")
            
            if PROJECT_CONFIG.test_target and PROJECT_CONFIG.test_target in res.stdout:
                print_result(True, f"Test Target: {PROJECT_CONFIG.test_target}", "FOUND")
            else:
                # Test targets aren't always in -list stdout as directly as schemes, but good enough for a heuristic
                pass
        except subprocess.TimeoutExpired:
            print("     \033[1;91m⚠️  Error checking Xcode: timed out after 45 seconds.\033[0m")
            print(f"        \033[90mCommand: {display_cmd}\033[0m")
            print("        \033[90mTry running it directly; Xcode may be indexing, resolving packages, or waiting on a corrupted project state.\033[0m")
        except Exception as e:
            print(f"     \033[1;91m⚠️  Error checking Xcode: {e}\033[0m")

    # Grounding Docs
    print_header("3. Grounding Docs (Critical for AI)")
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
    print_header("4. GitHub Integration")
    has_gh = shutil.which("gh") is not None
    print_result(has_gh, "GitHub CLI (gh)", "INSTALLED" if has_gh else "MISSING", "GitHub CLI (gh)")
    if has_gh:
        try:
            res = run_with_activity(
                "Checking GitHub authentication",
                lambda: subprocess.run(["gh", "auth", "status"], capture_output=True, text=True),
                status_bar,
            )
            is_auth = res.returncode == 0
            print_result(is_auth, "GitHub Auth session", "LOGGED IN" if is_auth else "EXPIRED", "GitHub CLI (gh)")
        except: pass

    # 4. Check LLM Providers
    print_header("5. AI Providers (Need 1+)")
    
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
            res = run_with_activity(
                f"Checking {cli_name} authentication",
                lambda: subprocess.run([cli_name] + status_args, capture_output=True, text=True, timeout=5),
                status_bar,
            )
            is_auth = res.returncode == 0
            print_result(is_auth, f"{cli_name} Auth", "LOGGED IN" if is_auth else "NOT LOGGED IN", fix_key if not is_auth else None)
            return is_auth
        except:
            print_result(True, f"{cli_name} CLI", "INSTALLED (Status Check Error)")
            return True

    claude_ok = check_cli_status("claude", "Claude Code", ["auth", "status"])
    codex_ok = check_cli_status("codex", "Codex CLI", ["login", "status"])
    antigravity_ok = cli_is_available("gemini")
    if antigravity_ok:
        print_result(True, "Antigravity CLI", "INSTALLED")
    else:
        print_result(False, "Antigravity CLI", "MISSING", "Antigravity CLI")
        
    ollama_ok = shutil.which("ollama") is not None
    print_result(ollama_ok, "Ollama (Local AI)", "INSTALLED" if ollama_ok else "MISSING", "Ollama")

    if not (has_env_key or has_settings_key or claude_ok or codex_ok or antigravity_ok or ollama_ok):
        print("\n\033[1;91m❌ CRITICAL ERROR: No AI providers found. The Orchestrator will fail.\033[0m")
    else:
        print("\n\033[1;92m✅ READY: At least one AI provider is configured.\033[0m")

    # 5. Check SSH Config
    print_header("6. SSH & Network")
    ssh_config_path = Path.home() / ".ssh" / "config"
    print_result(ssh_config_path.exists(), "SSH Config File", "OK" if ssh_config_path.exists() else "MISSING")
    
    if m_path.exists():
        print("\n\033[1;92m" + "="*20 + " VERIFICATION COMPLETE " + "="*20 + "\033[0m\n")
    else:
        print(f"\n\033[93m💡 NEXT STEP: Create '{m_path}' to use remote workers.\033[0m")

if __name__ == "__main__":
    check()

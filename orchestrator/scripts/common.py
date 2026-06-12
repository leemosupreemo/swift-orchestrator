#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT.parent))

from orchestrator.project_config import PROJECT_CONFIG

ROOT = PROJECT_CONFIG.root
AI_DIR = PACKAGE_ROOT
AI_RUNTIME_DIR = PROJECT_CONFIG.runtime_dir
CONFIG_DIR = AI_RUNTIME_DIR / "config"
JOBS_DIR = AI_RUNTIME_DIR / "jobs"
INBOX_DIR = JOBS_DIR / "inbox"
ARCHIVE_DIR = JOBS_DIR / "archive"
LOGS_DIR = AI_RUNTIME_DIR / "logs"
OUTPUT_DIR = AI_RUNTIME_DIR / "output"
STATE_DIR = AI_RUNTIME_DIR / "state"
MACHINE_STATE_DIR = STATE_DIR / "machines"
PROMPTS_DIR = PROJECT_CONFIG.prompts_dir
DOCS_DIR = ROOT / "docs"

# Force line-buffering for stdout/stderr to ensure interactive scripts work well over pipes/subprocesses
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)
except:
    pass

for p in [CONFIG_DIR, JOBS_DIR, INBOX_DIR, ARCHIVE_DIR, LOGS_DIR, OUTPUT_DIR, STATE_DIR, MACHINE_STATE_DIR]:
    p.mkdir(parents=True, exist_ok=True)

def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def format_log_path(path_str: str) -> str:
    """Formats a path string with a timestamp (YYYYMMDD-HHMMSS or YYYYMMDDTHHMMSS) to be more readable."""
    # Pattern to match YYYYMMDD-HHMMSS or YYYYMMDDTHHMMSS anywhere in the string
    pattern = r"(\d{4})(\d{2})(\d{2})[-T](\d{2})(\d{2})(\d{2})"
    
    def replacement(m):
        # Format as YYYY-MM-DD HH:MM:SS
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    
    return re.sub(pattern, replacement, path_str)

def now_iso() -> str:
    return datetime.now().isoformat()

def append_log(name: str, content: str) -> Path:
    path = LOGS_DIR / f"{timestamp()}-{name}.log"
    write_text(path, content)
    return path

def is_disk_full_error(text: str) -> bool:
    """Checks if the given text contains common 'disk full' error indicators."""
    patterns = [
        r"No space left on device",
        r"ENOSPC",
        r"Disk full",
        r"could not write to file",
        r"not enough space"
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def is_firebase_configured() -> bool:
    """Checks if Firebase CLI is installed and logged in for automated distribution."""
    try:
        # Check CLI
        subprocess.check_output(["firebase", "--version"], stderr=subprocess.DEVNULL)
        # Check login
        login_out = subprocess.check_output(["firebase", "login:list"], stderr=subprocess.STDOUT).decode("utf-8")
        return "Logged in as" in login_out
    except:
        return False

def purge_zombie_processes(session_allowed_machines: list[str], silent: bool = True) -> int:
    """
    Scans for and purges stale build processes (running > 12h) on the fleet.
    Returns the number of purged processes.
    """
    # Import locally to avoid circular dependency
    from probe_machine import load_machines, probe_machine
    machines = load_machines()
    machines = [m for m in machines if m["name"] in session_allowed_machines]
    
    all_stale = []
    for m in machines:
        probe = probe_machine(m)
        stale = probe.get("stale_processes", [])
        if stale:
            for p in stale:
                all_stale.append((m, p))
                
    if not all_stale:
        # If no specific zombie found but we want a force purge of DD
        if not silent:
            print("  - No specific zombie processes found. Checking local DerivedData...")
        
        dd_path = Path(PROJECT_CONFIG.derived_data_path)
        if dd_path.exists():
            if not silent: print(f"  - Purging local DerivedData: {dd_path}")
            import shutil
            shutil.rmtree(dd_path, ignore_errors=True)
            return 1
        return 0

    purged_count = 0
    machines_cleared = set()
    
    for m, p in all_stale:
        if not silent:
            print(f"  - Purging {p['comm']} ({p['pid']}) on {m['name']}...")
        
        if m["execution_mode"] == "local":
            subprocess.run(["kill", "-9", p["pid"]], check=False)
            if m["name"] not in machines_cleared:
                dd_path = Path(PROJECT_CONFIG.derived_data_path)
                if dd_path.exists():
                    import shutil
                    shutil.rmtree(dd_path, ignore_errors=True)
                machines_cleared.add(m["name"])
        else:
            ssh_target = m.get("ssh_target")
            if isinstance(ssh_target, list): ssh_target = ssh_target[0]
            # Kill process and clear DD only once per machine
            cmd = f"kill -9 {p['pid']}"
            if m["name"] not in machines_cleared:
                cmd += f" && rm -rf {shlex.quote(PROJECT_CONFIG.derived_data_path)}"
                machines_cleared.add(m["name"])
            subprocess.run(["ssh", ssh_target, cmd], check=False)
        purged_count += 1
    
    return purged_count

def get_repo_state() -> dict[str, list[str]]:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT)).decode("utf-8")
        modified, untracked = [], []
        for line in out.splitlines():
            if not line.strip(): continue
            if line[:2] == "??": untracked.append(line[3:])
            else: modified.append(line[3:])
        return {"modified": modified, "untracked": untracked}
    except: return {"modified": [], "untracked": []}

def gh_json(*args: str) -> Any:
    return json.loads(run(["gh", *args], cwd=ROOT).stdout)

def gh_text(*args: str) -> str:
    return run(["gh", *args], cwd=ROOT).stdout.strip()

@dataclass
class JobPaths:
    job_file: Path
    brief_file: Path
    output_dir: Path

def make_job_paths(job_id: str) -> JobPaths:
    output_dir = OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return JobPaths(JOBS_DIR / f"{job_id}.json", output_dir / "brief.md", output_dir)

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]

def colorize_diff_line(line: str) -> str:
    """Applies ANSI colors to a line if it starts with diff markers (+, -, @@)."""
    # Heuristic to avoid coloring log bullet points like "- Running build" or "- Tests passed"
    # Diffs usually have code or spaces immediately after the marker.
    # Log bullets usually have "- [Capitalized Word]"
    is_log_bullet = re.match(r"^[-+] [A-Z][a-z]+", line)
    
    if line.startswith("+") and not line.startswith("+++") and not is_log_bullet:
        return "\033[92m" + line + "\033[0m"
    elif line.startswith("-") and not line.startswith("---") and not is_log_bullet:
        return "\033[91m" + line + "\033[0m"
    elif line.startswith("@@"):
        return "\033[96m" + line + "\033[0m"
    elif "(+)" in line or "(-)" in line:
        return line.replace("(+)", "(\033[92m+\033[0m)").replace("(-)", "(\033[91m-\033[0m)")
    return line

def _print_completed_process(result: subprocess.CompletedProcess) -> None:
    def print_colored(text: str, is_stderr: bool = False):
        if not text: return
        stream = sys.stderr if is_stderr else sys.stdout
        for line in text.splitlines():
            print(colorize_diff_line(line), file=stream, flush=True)
            
    print_colored(result.stdout)
    print_colored(result.stderr, is_stderr=True)

def run(cmd: list[str], cwd: Path | None = None, check: bool = True, capture: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env: full_env.update(env)
    res = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=capture, text=True, check=False, env=full_env)
    if capture: _print_completed_process(res)
    if check and res.returncode != 0: raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
    return res

def run_shell(cmd: str, cwd: Path | None = None, check: bool = True, capture: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env: full_env.update(env)
    res = subprocess.run(cmd, cwd=str(cwd or ROOT), shell=True, executable="/bin/bash", capture_output=capture, text=True, check=False, env=full_env)
    
    if capture: _print_completed_process(res)

    # Check for ENAMETOOLONG errors
    if res.returncode != 0 and capture and ("ENAMETOOLONG" in (res.stdout or "") or "ENAMETOOLONG" in (res.stderr or "")):
        print("\n" + "!"*60)
        print("⚠️  BUILD ERROR: Path name too long (ENAMETOOLONG)")
        print("   This is usually caused by deeply nested Swift package paths on macOS.")
        print("   Tip: Use a shorter temporary directory for builds.")
        print("!"*60 + "\n")
    
    if capture: _print_completed_process(res)
    if check and res.returncode != 0: raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
    return res

def prompt_radio(label: str, options: list[str], default: str | None = None, clear_screen: bool = True) -> str:
    """Displays interactive radio buttons navigated by arrow keys."""
    if not sys.stdin.isatty():
        return default or options[0]
        
    idx = 0
    if default and default in options:
        idx = options.index(default)
    
    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        first_render = True
        num_rendered_lines = 0
        while True:
            # Redraw strategy: 
            # 1. Clear screen (flickery but safe) 
            # 2. OR move cursor back up (smooth but requires knowing height)
            if clear_screen:
                sys.stdout.write("\033[r\033[?25h\033[0m\r")
                sys.stdout.flush()
                os.system("clear" if os.name != "nt" else "cls")
            elif not first_render:
                # Move up by the number of lines we printed last time
                sys.stdout.write(f"\033[{num_rendered_lines}A")

            output = []
            output.append(f"\n{label}")
            output.append("\033[96m(Arrows: navigate, Enter: save, B: back)\033[0m")
            
            for i, opt in enumerate(options):
                cursor = "> " if i == idx else "  "
                icon = "(*)" if i == idx else "( )"
                line = f"{cursor}{icon} {opt}"
                output.append(line)
            
            # Print current choice placeholder at the bottom
            output.append("-" * 40)
            output.append(f"Choice: {options[idx]}\033[K")
            
            final_output = "\n".join(output)
            if not clear_screen:
                # To prevent smearing if options change size, we must clear each line
                lines = final_output.split("\n")
                final_output = "\n".join([line + "\033[K" for line in lines])
                num_rendered_lines = len(lines) - 1

            sys.stdout.write(final_output)
            sys.stdout.flush()
            
            first_render = False
            key = get_key()

            if key == "enter":
                if not clear_screen: sys.stdout.write("\n")
                break
            elif len(key) == 1 and key.lower() == "b": # Back
                if not clear_screen: sys.stdout.write("\n")
                raise BackException()
            elif key == "up" or key == "k":
                idx = (idx - 1) % len(options)
            elif key == "down" or key == "j":
                idx = (idx + 1) % len(options)
            elif key == "\x03": # Ctrl-C
                raise KeyboardInterrupt

    finally:
        # Show cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        
    return options[idx]

def prompt_confirm(question: str, default: bool = True) -> bool:
    """Displays interactive yes/no radio buttons."""
    # Defensive logic for reported UI duplication
    if question.startswith("Would you Would you"):
        question = "Would you" + question[len("Would you Would you"):]
    
    # Add Cyan formatting to match other dev console prompts
    formatted_question = f"\033[96m{question}\033[0m"
    
    default_str = "yes" if default else "no"
    choice = prompt_radio(formatted_question, ["yes", "no"], default_str, clear_screen=False)
    return choice == "yes"

def prompt_multiline(prompt: str) -> str:
    print(f"\n{prompt}")
    print("\033[90m(Press Ctrl-D on a new line when finished)\033[0m")
    try:
        content = sys.stdin.read()
        return content.strip()
    except EOFError:
        return ""

def get_key(blocking: bool = True) -> str:
    """Reads a single keypress, including multi-byte escape sequences for arrows."""
    import tty, termios
    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
    except Exception:
        # If we can't get terminal attributes (e.g., not a tty or terminal is corrupted), fallback to input()
        try:
            return sys.stdin.read(1) if not blocking else input()
        except:
            return ""

    try:
        if not blocking:
            # Set to non-blocking
            import fcntl
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
            try:
                ch = sys.stdin.read(1)
                if not ch: return ""
            except:
                return ""
            finally:
                fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
        else:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        
        if ch == "\x1b": # Escape sequence
            # Read next 2 chars
            import fcntl
            orig_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, orig_flags | os.O_NONBLOCK)
            try:
                rest = sys.stdin.read(2)
                if rest == "[A": return "up"
                if rest == "[B": return "down"
                if rest == "[C": return "right"
                if rest == "[D": return "left"
            except: pass
            finally:
                fcntl.fcntl(fd, fcntl.F_SETFL, orig_flags)

        if ch == "\x03": # Ctrl-C
            raise KeyboardInterrupt

        if ch == "\r": return "enter"
        if ch == " ": return "space"
        if ch == "\x7f": return "backspace"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

class BackException(Exception): pass
class KeyInterruptException(Exception):
    def __init__(self, key: str, index: int | None = None, value: str | None = None):
        self.key = key
        self.index = index
        self.value = value

def print_divider(char: str = "-"):
    try:
        columns, _ = os.get_terminal_size()
    except:
        columns = 80
    print(char * (columns - 1), flush=True)

def format_job_id(job_id: str) -> str:
    return f"\033[1;97m{job_id}\033[0m"

def format_index(i: int) -> str:
    return f"[\033[96m{i}\033[0m]"

def prompt_checkbox(label: str, options: list[str], defaults: list[str] | None = None, extra_keys: list[str] | None = None, footer: str | None = None, details_map: dict[str, list[str]] | None = None, status_bar: StatusBar | None = None, clear_screen: bool = True, max_selections: int | None = None) -> list[str]:
    """Displays interactive checkboxes navigated by arrow keys, toggled by space (vertical)."""
    if not sys.stdin.isatty():
        return defaults or []

    defaults = defaults or []
    extra_keys = [k.lower() for k in (extra_keys or [])]
    selected_indices = {i for i, opt in enumerate(options) if opt in defaults}
    idx = 0
    # Ensure starting idx is not a header
    while idx < len(options) and options[idx].startswith("---"):
        idx = (idx + 1) % len(options)
    
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    error_msg = ""
    
    try:
        first_render = True
        num_rendered_lines = 0
        while True:
            # Redraw strategy
            if clear_screen:
                sys.stdout.write("\033[r\033[?25h\033[0m\r")
                sys.stdout.flush()
                os.system("clear" if os.name != "nt" else "cls")
            elif not first_render:
                sys.stdout.write(f"\033[{num_rendered_lines}A")

            output = []
            # 1. Print Header
            output.append(f"\n{label}")
            sub_label = "(Arrows: navigate, Space: toggle, Enter: save, B: back)"
            output.append(f"\033[96m{sub_label}\033[0m")
            
            if error_msg:
                output.append(f"\033[91m      ⚠️  {error_msg}\033[0m")
                error_msg = ""

            # 2. Print options
            for i, opt in enumerate(options):
                if opt.startswith("---"):
                    output.append(f"  \033[1;90m{opt}\033[0m")
                    continue
                cursor = "> " if i == idx else "  "
                checked = "[\033[92mx\033[0m]" if i in selected_indices else "[ ]"
                line = f"{cursor}{checked} {opt}"
                if i == idx:
                    line = f"\033[1;94m{line}\033[0m"
                output.append(line)
            
            # Max selections disclaimer
            if max_selections:
                output.append(f"  \033[90m(Fleet limit: {max_selections} active machines max)\033[0m")
            
            # 3. Print footer
            if footer:
                output.append(f"\n{footer}")
            
            # 4. Print details for current selection
            if details_map:
                current_option = options[idx]
                details = details_map.get(current_option, [])
                if details:
                    output.append(f"\033[90m{'-'*20}\033[0m")
                    for line in details:
                        output.append(f"\033[90m{line}\033[0m")
            
            if status_bar:
                orig_sub = status_bar.sub_menu
                status_bar.sub_menu = True
                status_bar.render(at_bottom=True, force=True)
                status_bar.sub_menu = orig_sub

            # 5. Print Bottom UI
            try:
                cols, _ = os.get_terminal_size()
            except:
                cols = 80
            divider = "-" * (cols - 1)
            output.append(divider)
            
            placeholder = " (arrows/space/enter) "
            output.append(f"Choice: \033[48;5;236m\033[90m{placeholder}\033[0m\033[{len(placeholder)}D")
            
            final_output = "\n".join(output)
            if not clear_screen:
                lines = final_output.split("\n")
                final_output = "\n".join([line + "\033[K" for line in lines])
                num_rendered_lines = len(lines) - 1

            sys.stdout.write(final_output)
            sys.stdout.flush()
            
            first_render = False
            key = get_key()

            if key == "enter":
                if not clear_screen: sys.stdout.write("\n")
                break
            elif len(key) == 1 and key.lower() == "b": # Back
                if not clear_screen: sys.stdout.write("\n")
                raise BackException()
            elif key.lower() in extra_keys:
                if not clear_screen: sys.stdout.write("\n")
                raise KeyInterruptException(key.lower(), index=idx, value=options[idx])
            elif key == "space": # Space
                if idx in selected_indices:
                    selected_indices.remove(idx)
                else:
                    if max_selections and len(selected_indices) >= max_selections:
                        error_msg = f"Maximum of {max_selections} machines allowed for performance."
                    else:
                        selected_indices.add(idx)
            elif key == "up" or key == "k": # Up
                orig = idx
                while True:
                    idx = (idx - 1) % len(options)
                    if not options[idx].startswith("---") or idx == orig:
                        break
            elif key == "down" or key == "j": # Down
                orig = idx
                while True:
                    idx = (idx + 1) % len(options)
                    if not options[idx].startswith("---") or idx == orig:
                        break
            elif key == "\x03": # Ctrl-C
                raise KeyboardInterrupt

    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        
    return [options[i] for i in sorted(list(selected_indices))]

def extract_commands() -> tuple[str, str]:
    """Extracts build and test commands from docs/build-test-commands.md"""
    doc_path = DOCS_DIR / "build-test-commands.md"

    def default_xcode_command(action: str) -> str:
        if PROJECT_CONFIG.xcode_workspace:
            base = f"xcodebuild {action} -workspace {shlex.quote(PROJECT_CONFIG.xcode_workspace)}"
        elif PROJECT_CONFIG.xcode_project:
            base = f"xcodebuild {action} -project {shlex.quote(PROJECT_CONFIG.xcode_project)}"
        else:
            base = f"xcodebuild {action}"
        if PROJECT_CONFIG.scheme:
            base += f" -scheme {shlex.quote(PROJECT_CONFIG.scheme)}"
        return base

    default_build = PROJECT_CONFIG.build_command or default_xcode_command("build")
    default_test = PROJECT_CONFIG.test_command or default_xcode_command("test")

    build = default_build
    test = default_test

    if doc_path.exists():
        content = doc_path.read_text(encoding="utf-8")
        # More robust regex handling spaces and newlines
        build_match = re.search(r"## iOS app build[\s\S]*?```bash\s+([\s\S]*?)\s+```", content)
        test_match = re.search(r"## iOS app tests[\s\S]*?```bash\s+([\s\S]*?)\s+```", content)
        build = build_match.group(1).strip() if build_match else default_build
        test = test_match.group(1).strip() if test_match else default_test

    build = build.replace("$(pwd)", str(ROOT))
    test = test.replace("$(pwd)", str(ROOT))

    # Ensure Xcode commands have a simulator destination.
    if "xcodebuild" in build and "-destination" not in build:
        build += f" -destination {shlex.quote(get_best_simulator_destination())}"
    if "xcodebuild" in test and "-destination" not in test:
        test += f" -destination {shlex.quote(get_best_simulator_destination())}"

    # Ensure Xcode commands have derivedDataPath without mutating custom shell commands.
    if "xcodebuild" in build and "-derivedDataPath" not in build:
        build += f" -derivedDataPath {shlex.quote(PROJECT_CONFIG.derived_data_path)}"
    if "xcodebuild" in test and "-derivedDataPath" not in test:
        test += f" -derivedDataPath {shlex.quote(PROJECT_CONFIG.derived_data_path)}"

    return build, test
def get_best_simulator_destination() -> str:
    """
    Intelligently finds the best available iOS simulator destination.
    Priority: 1. Booted devices, 2. Latest iOS version, 3. iPhone over iPad.
    """
    try:
        def parse_version(v_str: str) -> tuple[int, ...]:
            # Extract numbers from string like 'iOS 18.2' or 'com.apple.CoreSimulator.SimRuntime.iOS-18-0'
            parts = re.findall(r"(\d+)", v_str)
            return tuple(map(int, parts))

        # We use 'available' to exclude simulators that don't have a matching runtime installed
        res = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        devices_by_runtime = data.get("devices", {})

        all_candidates = []
        for runtime, devices in devices_by_runtime.items():
            if "iOS" not in runtime:
                continue

            version = parse_version(runtime)
            for d in devices:
                if d.get("isAvailable") == False: continue # simctl 'available' flag is not enough

                all_candidates.append({
                    "udid": d["udid"],
                    "name": d["name"],
                    "booted": d.get("state") == "Booted",
                    "version": version,
                    "is_iphone": "iPhone" in d["name"]
                })

        if not all_candidates:
            return "platform=iOS Simulator,name=iPhone 16"

        # Sort: Booted first, then latest version, then iPhone, then Name
        # Using negative numbers for boolean/tuple sorts for descending order
        def sort_key(c):
            return (
                not c["booted"],     # False (Booted) comes before True
                [-x for x in c["version"]], # Higher versions first
                not c["is_iphone"],  # iPhone first
                c["name"]
            )

        best = sorted(all_candidates, key=sort_key)[0]

        # Include arch=arm64 on Apple Silicon to resolve ambiguous destination warnings
        # and prevent 'device not found' when multiple archs exist for the same UDID.
        import platform
        is_arm = platform.machine().startswith("arm") or platform.processor().startswith("arm")
        arch_suffix = ",arch=arm64" if is_arm else ""

        return f"platform=iOS Simulator,id={best['udid']}{arch_suffix}"

    except Exception:
        # Final hardcoded fallback if everything fails
        return "platform=iOS Simulator,name=iPhone 16"
def get_test_plan_flags(plan_path: Path) -> str:
    """
    Manually parses an .xctestplan file and returns -only-testing flags.
    This bypasses xcodebuild issues with reading test plan files directly.
    """
    if not plan_path.exists():
        return ""
    
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        flags = []
        for target in data.get("testTargets", []):
            target_name = target.get("target", {}).get("name", PROJECT_CONFIG.test_target)
            selected = target.get("selectedTests", [])
            skipped = target.get("skippedTests", [])
            
            if selected:
                for t in selected:
                    flags.append(f"-only-testing:{target_name}/{t}")
            elif skipped:
                # If no specific tests are selected, we include the whole target but skip specific ones
                flags.append(f"-only-testing:{target_name}")
                for t in skipped:
                    flags.append(f"-skip-testing:{target_name}/{t}")
            else:
                # No selection/skips, just run the whole target
                flags.append(f"-only-testing:{target_name}")
                
        return " ".join(flags)
    except Exception as e:
        # Fallback to just using the name if parsing fails
        return f"-testPlan {plan_path.stem}"

class ProgressIndicator:
    def __init__(self, label: str = "Thinking", hint: str = "Ctrl-C to abort"):
        self.label = label
        self.hint = hint
        self.start_time = datetime.now()
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_idx = 0
        self.last_render_time = 0.0
        # Silent mode ONLY if we are being called by a worker/orchestrator
        # 'dev_console' is the UI parent and should NOT be silent,
        # UNLESS specifically requested (e.g. to avoid double spinners).
        self.is_silent = os.environ.get("AI_REQUEST_SOURCE") == "orchestrator" or os.environ.get("AI_PROGRESS_SILENT") == "1"

    def get_line(self, last_activity_time: float | None = None) -> str:
        """Returns the formatted progress line without escape sequences for positioning."""
        elapsed = datetime.now() - self.start_time
        seconds = int(elapsed.total_seconds())
        minutes, seconds = divmod(seconds, 60)
        timer_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        activity_str = ""
        if last_activity_time:
            import time
            idle_sec = int(time.time() - last_activity_time)
            if idle_sec > 5:
                activity_str = f", idle {idle_sec}s"

        spinner = self.frames[self.frame_idx]
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        return f"\033[96m{spinner}\033[0m {self.label}... \033[90m({self.hint}, {timer_str}{activity_str})\033[0m"

    def render(self, force: bool = False, last_activity_time: float | None = None):
        if self.is_silent: return
        now = time.monotonic()
        if not force and now - self.last_render_time < 0.1: return
        
        # If a status bar is active, we don't draw directly.
        # The parent loop will call StatusBar.render(activity=indicator)
        if _STATUS_BAR_NESTING == 0:
            sys.stdout.write(f"\0337\r\033[K{self.get_line(last_activity_time)}\0338")
            sys.stdout.flush()
        self.last_render_time = now

    def clear(self):
        if self.is_silent: return
        if _STATUS_BAR_NESTING == 0:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

_STATUS_BAR_NESTING = 0

class StatusBar:
    def __init__(self, job: dict[str, Any] | None = None, is_processing: bool = False, sub_menu: bool = False):
        self.job = job or {}
        self.is_processing = is_processing
        self.sub_menu = sub_menu
        self.q_count = 0
        self.directory = ROOT.name
        self.branch = self._get_branch()
        self._scroll_region_set = False
        self._last_size = (0, 0)
        self._last_render_time = 0.0
        self.activity_indicator: ProgressIndicator | None = None
        # Silent mode ONLY if we are being called by a worker/orchestrator
        self.is_silent = os.environ.get("AI_REQUEST_SOURCE") == "orchestrator" or os.environ.get("AI_PROGRESS_SILENT") == "1"
        
        allowed = self.job.get("allowed_machines") or self.job.get("session_machines", [])
        online = self.job.get("online_machines")
        
        if online is not None:
            self.machines = f"{len(online)}/{len(allowed)}" if len(online) != len(allowed) else str(len(allowed))
        else:
            self.machines = str(len(allowed))
            
        self.models = len(self.job.get("allowed_models") or self.job.get("session_models", []))
        self.active_model = self.job.get("actual_builder_used") or self.job.get("actual_planner_used")

    def _get_branch(self) -> str:
        try: return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT)).decode("utf-8").strip()
        except: return "unknown"

    def _get_size(self) -> tuple[int, int]:
        try:
            columns, lines = os.get_terminal_size()
            return columns, lines
        except:
            return 80, 24

    def __enter__(self):
        global _STATUS_BAR_NESTING
        _STATUS_BAR_NESTING += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _STATUS_BAR_NESTING
        _STATUS_BAR_NESTING -= 1
        if _STATUS_BAR_NESTING <= 0:
            self.reset_scroll_region(force=True)
            _STATUS_BAR_NESTING = 0

    def set_scroll_region(self):
        if not sys.stdin.isatty(): return
        cols, lines = self._get_size()
        self._last_size = (cols, lines)
        # Scroll region ends at lines-4.
        sys.stdout.write(f"\0337\033[1;{lines-4}r\0338")
        sys.stdout.flush()
        self._scroll_region_set = True

    def reset_scroll_region(self, force: bool = False):
        if self._scroll_region_set or force:
            _, lines = self._get_size()
            # \033[r: reset scroll region
            # \033[?25h: show cursor
            # \033[H: move to top-left
            sys.stdout.write("\033[r\033[?25h")
            sys.stdout.flush()
            self._scroll_region_set = False

    def clear_footer(self):
        """Fully wipes the bottom 4 lines where the footer lives."""
        _, lines = self._get_size()
        cmd = "\0337" # Save cursor
        for i in range(lines - 3, lines + 1):
            cmd += f"\033[{i};1H\033[K"
        cmd += "\0338"
        sys.stdout.write(cmd)
        sys.stdout.flush()

    def render(self, at_bottom: bool = True, force: bool = False, prompt: str | None = None, activity: ProgressIndicator | None = None):
        if self.is_silent: return
        now = time.monotonic()
        # Rate limit frequent renders unless forced
        if not force and at_bottom and now - self._last_render_time < 0.05:
            return
        self._last_render_time = now
        
        if activity:
            self.activity_indicator = activity

        # Auto-set scroll region if we want to render at bottom but haven't yet
        if at_bottom and not self._scroll_region_set:
            self.set_scroll_region()

        if self.is_processing:
            q_msg = "Ctrl-C to abort"
        elif self.sub_menu:
            q_msg = "Ctrl-C to go back"
        else:
            q_msg = "Ctrl-C to quit"
            
        model_info = f"models: {self.models}"
        if self.active_model:
            model_info = f"model: {self.active_model}"
            
        meta = f"dir: {self.directory} | branch: {self.branch} | machines: {self.machines} | {model_info}"
        columns, lines = self._get_size()
        
        if self._scroll_region_set and (columns, lines) != self._last_size:
            self.set_scroll_region()

        cols = max(10, columns - 1)
        content = f" {q_msg:<18} | {meta}"
        if len(content) > cols:
            content = content[:cols-3] + "..."
        else:
            content = content + (" " * (cols - len(content)))

        bar = f"\033[1;48;5;94;97m{content}\033[0m"
        divider = "\033[90m" + ("-" * cols) + "\033[0m"
        
        if at_bottom:
            # We construct the entire 4-line footer in one sequence
            cmd = "\0337" # Save cursor
            
            # Line L-3: Activity (Progress)
            act_line = self.activity_indicator.get_line() if self.activity_indicator else ""
            cmd += f"\033[{lines-3};1H\r\033[K{act_line}"
            
            # Line L-2: User Prompt
            prompt_str = prompt if prompt else ""
            cmd += f"\033[{lines-2};1H\r\033[K{prompt_str}"
            
            # Line L-1: Divider
            cmd += f"\033[{lines-1};1H\r{divider}\033[K"
            
            # Line L: Metadata Bar
            cmd += f"\033[{lines};1H\r{bar}\033[K"
            
            # Restore cursor and flush
            cmd += "\0338"
            sys.stdout.write(cmd)
            sys.stdout.flush()
        else:
            print(divider)
            print(bar)

def cleanup_terminal():
    try:
        _, lines = os.get_terminal_size()
        sys.stdout.write(f"\033[r\033[{lines};1H\n")
        sys.stdout.flush()
    except: pass

def get_choice_prompt(label: str, hint: str) -> str:
    """Returns a styled prompt with a dark grey background and positional offset."""
    placeholder = f" {hint} "
    return f"{label} \033[48;5;236m\033[90m{placeholder}\033[0m\033[{len(placeholder)}D"

def print_choice_prompt(label: str, hint: str) -> None:
    """Prints a choice prompt at the current cursor position."""
    sys.stdout.write(get_choice_prompt(label, hint))
    sys.stdout.flush()

def clear_choice_placeholder() -> None:
    """Clears any remaining characters on the current line (usually placeholder text)."""
    sys.stdout.write("\033[K")
    sys.stdout.flush()

def print_phase(phase: str, subtext: str | None = None):
    p_map = {
        "planning": ("🧠", "PLANNING"),
        "scheduling": ("📡", "SCHEDULING"),
        "execution": ("🏗️", "EXECUTION"),
        "verification": ("🧪", "VERIFICATION"),
        "review": ("👀", "REVIEW"),
        "complete": ("✅", "COMPLETE")
    }
    icon, label = p_map.get(phase, ("⚙️", phase.upper()))
    text = f"\n==================== {icon} {label}"
    if subtext:
        text += f": {subtext.upper()}"
    text += " ====================\n"
    print(text)

def get_phase_name(phase: str) -> str:
    return phase.replace("-", " ").capitalize()

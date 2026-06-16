#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import Any

# Add scripts dir to path for internal imports
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT, read_json
from orchestrator.project_config import PROJECT_CONFIG

def send_final_notification(job: dict[str, Any], title: str, branch: str, success: bool):
    job_id = job.get("job_id", "unknown")
    status_str = "SUCCESSFUL" if success else "FAILED"
    print(f"      - Triggering final {status_str} notification for job {job_id}...", flush=True)
    try:
        subject = f"Build Delivery {status_str}"
        msg = f"Build delivery for Issue #{job.get('issue_number', 'N/A')} has {status_str.lower()}.\nTitle: {title}\nBranch: {branch}"
        if not success:
            msg += "\n\nPlease check the orchestrator console logs for details."
            
        subprocess.run([sys.executable, str(SCRIPTS_DIR / "notify.py"), subject, msg, job_id], cwd=str(ROOT), check=False, timeout=30)
    except Exception as e:
        print(f"      - Notification system failed: {e}", flush=True)

def deliver_build(job_path: Path):
    job = read_json(job_path)
    
    branch = job.get("branch")
    title = job.get("title")
    job_id = job.get("job_id")
    
    if not branch:
        print(f"!!! Error: No active branch found for job {job_id}. Cannot create a build.")
        return

    print(f"\n--- Delivering Build to Device: {job_id} ---")
    print(f"      - Target Branch: {branch}")
    print(f"      - Feature/Bug:   {title}")
    
    # 0. Pre-flight check: Ensure signing configuration is present
    dist_errors = PROJECT_CONFIG.validate_distribution_config()
    if dist_errors:
        print("\n\033[1;91m!!! Error: Distribution configuration is incomplete:\033[0m")
        for err in dist_errors:
            print(f"      - {err}")
        print("\n\033[93mPlease run 'orchestrator wizard' to configure iOS distribution and signing.\033[0m")
        sys.exit(1)
    
    # 1. Ensure we are on the correct branch
    current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT)).decode("utf-8").strip()
    if current_branch != branch:
        print(f"\n      - Switching to branch: {branch}...")
        subprocess.run(["git", "checkout", "-f", branch], cwd=str(ROOT), check=True)
    else:
        print(f"\n      - Already on correct branch: {branch}")
    
    # 2. Build Release Notes
    release_notes = f"""AI Job: {job_id}
Title: {title}
Branch: {branch}
Built: {subprocess.check_output(['date', '+%Y-%m-%d %H:%M:%S']).decode('utf-8').strip()}
"""
    
    # 3. Call the existing distribution script
    # We use subprocess.call to allow real-time streaming of Xcode and Firebase logs
    dist_script = ROOT / (PROJECT_CONFIG.distribution_script_path or "scripts/distribute_ios.sh")
    
    if not dist_script.exists():
        print(f"!!! Error: Distribution script not found at {dist_script}")
        return

    print(f"\n      - Triggering distribution pipeline (Archiving, Exporting, Uploading)...")
    print("      - This may take 5-10 minutes. Please wait.\n")
    
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    dist_log = log_dir / f"distribution_{job_id}.log"
    print(f"      - Logging to: {dist_log.relative_to(ROOT)}")
    
    try:
        # Run the bash script and capture output to both console and file
        project_path = None
        if PROJECT_CONFIG.xcode_project:
            project_path = ROOT / PROJECT_CONFIG.xcode_project
        else:
            project_path = next(iter(sorted(ROOT.glob("*.xcodeproj"))), None)
            
        workspace_path = getattr(PROJECT_CONFIG, "xcode_workspace", None)
        if workspace_path:
            workspace_path = ROOT / workspace_path
            
        if not project_path and not workspace_path:
            print("!!! Error: No Xcode project or workspace configured for distribution.")
            return
            
        cmd = ["/bin/bash", str(dist_script)]
        if project_path:
            cmd.extend(["--project", str(project_path)])
        if workspace_path:
            cmd.extend(["--workspace", str(workspace_path)])
            
        if PROJECT_CONFIG.scheme:
            cmd.extend(["--scheme", PROJECT_CONFIG.scheme])
            
        cmd.extend(["--release-notes", release_notes])
        
        provisioning_profile = getattr(PROJECT_CONFIG, "provisioning_profile_specifier", None)
        if provisioning_profile:
            cmd.extend(["--provisioning-profile", provisioning_profile])
        
        team_id = getattr(PROJECT_CONFIG, "development_team", None)
        if team_id:
            cmd.extend(["--team-id", team_id])
            
        method = getattr(PROJECT_CONFIG, "delivery_method", None)
        if method:
            cmd.extend(["--method", method])
            
        asc_key_id = getattr(PROJECT_CONFIG, "asc_key_id", None)
        if asc_key_id:
            cmd.extend(["--asc-key-id", asc_key_id])
            
        asc_issuer_id = getattr(PROJECT_CONFIG, "asc_issuer_id", None)
        if asc_issuer_id:
            cmd.extend(["--asc-issuer-id", asc_issuer_id])
            
        asc_key_path = getattr(PROJECT_CONFIG, "asc_key_path", None)
        if asc_key_path:
            key_path = ROOT / asc_key_path if not Path(asc_key_path).is_absolute() else Path(asc_key_path)
            cmd.extend(["--asc-key-path", str(key_path)])
        
        if PROJECT_CONFIG.firebase_plist_path:
            cmd.extend(["--firebase-plist", PROJECT_CONFIG.firebase_plist_path])
        
        if job.get("testers"):
            cmd.extend(["--testers", job["testers"]])
        if job.get("groups"):
            cmd.extend(["--groups", job["groups"]])
        
        with open(dist_log, "w") as f:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT),
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
                f.flush()
                
            res = process.wait()
        
        if res == 0:
            print("\n✅ Build delivered to Firebase successfully!", flush=True)
            print("      - Finalizing and sending notifications...", flush=True)
            send_final_notification(job, title, branch, True)
            print("\n✨ ALL DONE.", flush=True)
            sys.exit(0)
        else:
            print(f"\n❌ Distribution script failed with exit code {res}.", flush=True)
            send_final_notification(job, title, branch, False)
            sys.exit(res)
            
    except KeyboardInterrupt:
        print("\n!!! Distribution interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n!!! Error during distribution: {e}")
        sys.exit(1)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_file", help="Path to the job JSON file")
    args = parser.parse_args()

    deliver_build(Path(args.job_file))

if __name__ == "__main__":
    main()

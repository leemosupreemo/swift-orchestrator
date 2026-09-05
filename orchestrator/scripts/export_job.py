#!/usr/bin/env python3
import argparse
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

from common import (
    JOBS_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
    ROOT,
    print_phase,
    format_file_link,
)
from reference_artifacts import reference_context

def export_job(job_path_str: str, output_zip: str | None = None):
    job_path = Path(job_path_str).resolve()
    if not job_path.exists():
        print(f"Error: Job file {job_path} not found.")
        return

    with open(job_path, "r") as f:
        job = json.load(f)

    job_id = job.get("job_id", job_path.stem)
    
    if not output_zip:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_zip = f"export-{job_id}-{timestamp}.zip"
    
    output_path = Path(output_zip).resolve()
    
    print_phase("exporting", subtext=job_id)
    print(f"Creating export archive: {output_path.name}")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 1. Add Job JSON
        zipf.write(job_path, arcname=f"{job_id}/job.json")
        print(f"  + Added job.json")

        # 2. Add Output Directory (Brief, Plan, Builder Summary, Logs)
        job_output_dir = OUTPUT_DIR / job_id
        if job_output_dir.exists():
            for file in job_output_dir.rglob("*"):
                if file.is_file():
                    arcname = f"{job_id}/output/{file.relative_to(job_output_dir)}"
                    zipf.write(file, arcname=arcname)
            print(f"  + Added output directory contents")
        else:
            print(f"  ! Output directory not found for {job_id}")

        # 3. Add global logs that match this job (if any)
        # Some logs might have the job_id in their content or filename
        # For now we rely on what's in output_dir/logs/ which builder/planner usually copies
        
        # 4. Create a manifest or summary for easy reading
        manifest = [
            f"Job ID: {job_id}",
            f"Title: {job.get('title')}",
            f"Status: {job.get('status')}",
            f"Export Date: {datetime.now().isoformat()}",
            f"\nPlan Summary:\n{json.dumps(job.get('plan', {}).get('summary', 'No summary'), indent=2)}",
            f"\nReference Artifacts:\n{reference_context(job) or 'None'}",
        ]
        zipf.writestr(f"{job_id}/manifest.txt", "\n".join(manifest))
        print(f"  + Added manifest.txt")

    clickable_path = format_file_link(output_path, label=str(output_path))
    print(f"\n✅ Export complete: \033[4;96m{clickable_path}\033[0m")
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Export all context for a job into a ZIP archive.")
    parser.add_argument("job_path", help="Path to the job JSON file")
    parser.add_argument("--output", "-o", help="Output ZIP file path")
    
    args = parser.parse_args()
    export_job(args.job_path, args.output)

if __name__ == "__main__":
    main()

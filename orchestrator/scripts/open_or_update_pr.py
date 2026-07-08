#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from common import OUTPUT_DIR, ROOT, gh_json, gh_text, read_json, run
from orchestrator.project_config import PROJECT_CONFIG


def open_or_update_pr(job_path: Path) -> int:
    job = read_json(job_path)
    issue_number = job["issue_number"]
    branch = job["branch"]
    brief_file = OUTPUT_DIR / job["job_id"] / "brief.md"

    run(["git", "push", "-u", "origin", branch], cwd=ROOT)

    existing = gh_json("pr", "list", "--head", branch, "--json", "number,title,body")
    
    debug_summary = ""
    if job.get("debug_history"):
        debug_summary = "\n## Debug History\n\n"
        for entry in job["debug_history"]:
            debug_summary += f"### Iteration {entry['iteration']}\n"
            debug_summary += f"- **Hypothesis**: {entry.get('hypothesis', 'N/A')}\n"
            debug_summary += f"- **Action**: `{entry.get('action', 'N/A')}`\n"
            result = entry.get("result", {})
            if isinstance(result, dict):
                debug_summary += f"- **Result**: Build {'✅' if result.get('build_ok') else '❌'}, Tests {'✅' if result.get('tests_ok') else '❌'}\n"
                if result.get("notes"):
                    debug_summary += f"  - *Notes*: {result['notes']}\n"
            else:
                debug_summary += f"- **Result**: {result}\n"
            debug_summary += "\n"

    body = f"""## What changed

See builder summary in repo artifacts.

## Why it changed

Fixes or advances issue #{issue_number}.

{debug_summary}

## Files touched

See diff.

## Risks / edge cases

See builder summary.

## Testing performed

See orchestrator output for {job["job_id"]}/build.log and test.log if present.

AI_BRIEF_FILE: {brief_file}
"""

    if existing:
        pr_number = existing[0]["number"]
        gh_text("pr", "edit", str(pr_number), "--body", body)
        pr_url = None
        try:
            pr_data = gh_json("pr", "view", str(pr_number), "--json", "url")
            pr_url = pr_data.get("url") if pr_data else None
        except:
            pass
        return pr_number, pr_url

    out = gh_text(
        "pr",
        "create",
        "--draft",
        "--title",
        f'AI draft for issue #{issue_number}: {job["title"]}',
        "--body",
        body,
        "--base",
        job.get("base_branch") or PROJECT_CONFIG.base_branch,
        "--head",
        branch,
    )
    pr_url = out.strip()
    try:
        pr_number = int(pr_url.rstrip("/").split("/")[-1])
    except:
        pr_number = 0
    return pr_number, pr_url

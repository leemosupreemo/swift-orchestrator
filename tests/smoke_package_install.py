#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd or PACKAGE_ROOT), check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="orchestrator-install-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        venv = temp_dir / "venv"
        project = temp_dir / "FixtureApp"
        project.mkdir()
        (project / "FixtureApp.xcodeproj").mkdir()

        run([sys.executable, "-m", "venv", str(venv)])
        python = venv / "bin" / "python"
        orchestrator = venv / "bin" / "orchestrator"

        run([str(python), "-m", "pip", "install", "-e", str(PACKAGE_ROOT)])
        run([str(orchestrator), "--help"])
        run([str(orchestrator), "init", "--root", str(project), "--project-name", "FixtureApp", "--force"])
        run([str(orchestrator), "check-config"], cwd=project)

        config_path = project / ".orchestrator" / "project.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["project_name"] == "FixtureApp", config
        assert config["xcode_project"] == "FixtureApp.xcodeproj", config
        gitignore = (project / ".orchestrator" / ".gitignore").read_text(encoding="utf-8")
        assert "jobs/" in gitignore, gitignore
        assert "logs/" in gitignore, gitignore

    print("Package install smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

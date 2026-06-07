# Swift Orchestrator

Standalone package scaffold for the AI dev console and worker orchestration used by Swift/Xcode projects.

## Install

Recommended CLI install:

```bash
brew install pipx
pipx ensurepath
pipx install "git+https://github.com/leemosupreemo/orchestrator.git"
orchestrator --help
```

Upgrade later with:

```bash
pipx upgrade orchestrator
```

## Local Development

```bash
cd swift_orchestrator
python3 -m pip install -e .
orchestrator wizard --root /path/to/SwiftProject
cd /path/to/SwiftProject
orchestrator check
orchestrator check-config
orchestrator console
```

Package install smoke:

```bash
python3 tests/smoke_package_install.py
```

This creates a temporary virtual environment, installs the package editable, and verifies the installed `orchestrator` command without relying on `PYTHONPATH`.

## External Requirements

Python package dependencies are standard-library only. Runtime functionality depends on external command-line tools:

- Required for Swift/Xcode projects: `xcodebuild`, `xcrun`
- Required for GitHub issue/PR workflow: `gh`
- Required for SSH workers: `ssh`, `scp`, `rsync`
- At least one model provider CLI or API key:
  - `codex`
  - `gemini`
  - `claude`
  - `opencode`
  - `ollama`
- Optional delivery: `firebase` plus a configured distribution script

Use:

```bash
orchestrator check
orchestrator check-config
```

to validate environment and project configuration.

For first-time setup, use:

```bash
orchestrator wizard --project /path/to/SwiftProject
```

The wizard initializes project config, chooses at least one model, can copy project-local prompt Markdown overrides, can add SSH workers, and can configure Firebase delivery.

List or switch remembered projects:

```bash
orchestrator projects
orchestrator use MyApp
```

The package stores project-specific runtime files in `.orchestrator/` by default:

- `project.json`
- `config/machines.json`
- `config/settings.json`
- `jobs/`
- `logs/`
- `output/`
- `state/`

The original Thirteen `ai/` directory is not modified by this package.

## Project Config

`orchestrator init` writes `.orchestrator/project.json`. When available, it uses `xcodebuild -list -json` to detect schemes and targets.

Important fields include:

```json
{
  "project_name": "MyApp",
  "base_branch": "main",
  "pr_base_branch": "main",
  "branch_prefix": "ai/issue",
  "xcode_project": "MyApp.xcodeproj",
  "xcode_workspace": null,
  "scheme": "MyApp",
  "test_target": "MyAppTests",
  "build_command": null,
  "test_command": null,
  "backend_test_command": null,
  "app_bundle_id": null,
  "visual_app_path": null,
  "delivery_provider": null,
  "distribution_script_path": null,
  "firebase_plist_path": null,
  "remote_package_install_path": "~/.orchestrator/package",
  "firebase_distribution": false
}
```

Run this after editing config:

```bash
orchestrator check-config
```

## Remote Workers

Remote Macs need the package source available on `PYTHONPATH`. The default remote package path is:

```text
~/.orchestrator/package
```

Check workers:

```bash
orchestrator worker-check
orchestrator worker-check --machine mac2
```

Install or refresh the package on an SSH worker:

```bash
orchestrator worker-install --machine mac2
```

You can override the remote package/runtime locations in `.orchestrator/config/machines.json`:

```json
{
  "name": "mac2",
  "execution_mode": "ssh",
  "ssh_target": "my-mac",
  "repo_path": "/Users/me/Documents/MyApp",
  "orchestrator_package_path": "~/.orchestrator/package",
  "orchestrator_runtime_dir": ".orchestrator"
}
```

Remote dispatch checks that `orchestrator.scripts.worker_run` can be imported before syncing code or uploading a job. If the package is missing, dispatch stops with a `worker-install` hint.

## Guides

- [User guide](docs/user-guide.md): install, initialize a Swift project, configure models/workers, run the console, create jobs, and troubleshoot setup issues.
- [Migration guide](docs/migration-guide.md): move from Thirteen's repo-local `ai/` directory to the standalone package without deleting existing Thirteen files.

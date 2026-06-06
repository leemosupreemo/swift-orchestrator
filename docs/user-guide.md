# Swift Orchestrator User Guide

This guide covers using the standalone package from any Swift/Xcode project.

## Install

For local development from this repository:

```bash
cd /path/to/Thirteen/swift_orchestrator
python3 -m pip install -e .
```

After the package is moved to its own Git repository, the intended install shape is:

```bash
python3 -m pip install "git+ssh://git@github.com/OWNER/swift-orchestrator.git"
```

Verify the command is available:

```bash
swift-orchestrator --help
```

The package has no Python runtime dependencies outside the standard library. Some workflows require external command-line tools:

- Xcode project build/test: `xcodebuild`, `xcrun`
- GitHub issue and pull request workflow: `gh`
- Remote workers: `ssh`, `scp`, `rsync`
- AI providers: at least one of `codex`, `gemini`, `claude`, `opencode`, `ollama`, or matching API key configuration
- Firebase delivery: `firebase` plus a project-local distribution script

## Initialize A Swift Project

From the target Swift repository:

```bash
swift-orchestrator init
swift-orchestrator check
swift-orchestrator check-config
```

Or initialize a specific path:

```bash
swift-orchestrator init --root /path/to/MyApp --project-name MyApp
```

Optional starter files:

```bash
swift-orchestrator init --with-starter-docs --with-helper-script
```

`init` creates `.swift-orchestrator/` in the target repository. It detects the first `.xcworkspace` or `.xcodeproj`, then asks `xcodebuild -list -json` for schemes and targets when possible.

Generated files:

```text
.swift-orchestrator/
  .gitignore
  project.json
  config/
    machines.json
    settings.json
  jobs/
  logs/
  output/
  state/
```

Commit `.swift-orchestrator/.gitignore`, `.swift-orchestrator/project.json`, and `.swift-orchestrator/config/*.json` if the team should share the same orchestrator setup. The generated `.swift-orchestrator/.gitignore` excludes runtime `jobs/`, `logs/`, `output/`, and `state/` contents by default.

With `--with-starter-docs`, `init` also creates:

```text
AGENTS.md
docs/build-test-commands.md
docs/ai-workflow.md
```

With `--with-helper-script`, `init` creates:

```text
scripts/orchestrator
```

The helper script runs `swift-orchestrator "$@"`, which gives the project a stable repo-local command wrapper.

## Configure Project Behavior

Edit `.swift-orchestrator/project.json` after initialization. Common fields:

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
  "derived_data_path": "/tmp/myapp_orchestrator_dd",
  "build_command": null,
  "test_command": null,
  "backend_test_command": null,
  "app_bundle_id": null,
  "visual_app_path": null,
  "delivery_provider": null,
  "distribution_script_path": null,
  "firebase_plist_path": null,
  "remote_package_install_path": "~/.swift-orchestrator/package",
  "firebase_distribution": false
}
```

Use `build_command` and `test_command` when a project needs custom build/test commands instead of the generated `xcodebuild` defaults.

Swift Package example:

```json
{
  "xcode_project": null,
  "xcode_workspace": null,
  "scheme": "MyPackage",
  "test_target": "MyPackageTests",
  "build_command": "swift build",
  "test_command": "swift test"
}
```

Run validation after edits:

```bash
swift-orchestrator check-config
```

## Configure AI Providers

The orchestrator can use model provider CLIs or API keys. The setup check looks for common CLIs and environment keys:

```bash
swift-orchestrator check
```

Practical options:

- Install and authenticate a CLI, such as `codex login`, `claude auth login`, or the equivalent command for your provider.
- Export API keys in the shell where the console runs, such as `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY`.
- Store non-secret project settings in `.swift-orchestrator/config/settings.json`.

Do not commit secrets.

## Configure Workers

Local worker config is generated automatically in `.swift-orchestrator/config/machines.json`.

Example local machine:

```json
{
  "name": "local",
  "enabled": true,
  "execution_mode": "local",
  "ssh_target": null,
  "repo_path": "/Users/me/Documents/MyApp",
  "roles": ["planner", "reviewer", "worker", "build", "test"],
  "models": ["gemini", "codex", "claude"],
  "priority": 100,
  "max_concurrent_jobs": 1,
  "max_heavy_jobs": 1,
  "supports_xcode": true,
  "supports_simulator": true,
  "supports_backend_tests": false,
  "interactive_reserved": true,
  "tags": ["interactive", "primary"]
}
```

Example SSH worker:

```json
{
  "name": "mac2",
  "enabled": true,
  "execution_mode": "ssh",
  "ssh_target": "mac2",
  "repo_path": "/Users/me/Documents/MyApp",
  "orchestrator_package_path": "~/.swift-orchestrator/package",
  "orchestrator_runtime_dir": ".swift-orchestrator",
  "roles": ["worker", "build", "test"],
  "models": ["codex", "gemini"],
  "priority": 90,
  "max_concurrent_jobs": 1,
  "max_heavy_jobs": 1,
  "supports_xcode": true,
  "supports_simulator": true,
  "supports_backend_tests": false,
  "interactive_reserved": false,
  "tags": ["remote"]
}
```

Check worker readiness:

```bash
swift-orchestrator worker-check
swift-orchestrator worker-check --machine mac2
```

Install or refresh the package on an SSH worker:

```bash
swift-orchestrator worker-install --machine mac2
```

`worker-install` copies the installed package source to the worker's `orchestrator_package_path` and verifies that the remote machine can import `orchestrator.scripts.worker_run`. Remote dispatch stops before syncing jobs if the package is missing.

## Run The Console

From the Swift project root:

```bash
swift-orchestrator console
```

The console stores runtime data under `.swift-orchestrator/` by default. To run from another directory, set the project root:

```bash
SWIFT_ORCHESTRATOR_PROJECT_ROOT=/path/to/MyApp swift-orchestrator console
```

## Create And Run Jobs

Use the console for normal job creation. For direct script access:

```bash
swift-orchestrator script new_job.py bug
swift-orchestrator script new_job.py feature
swift-orchestrator script schedule_job.py .swift-orchestrator/jobs/JOB.json
```

Generated job files are written under `.swift-orchestrator/jobs/`. Logs and review output are written under `.swift-orchestrator/logs/` and `.swift-orchestrator/output/`.

## Visual Simulator Checks

Visual checks require an app bundle and bundle identifier. Configure:

```json
{
  "app_bundle_id": "com.example.MyApp",
  "visual_app_path": "/absolute/path/to/MyApp.app"
}
```

If `visual_app_path` is omitted, the visual check flow searches the configured derived data path for a built `.app`.

## Firebase Delivery

Firebase delivery is opt-in:

```json
{
  "delivery_provider": "firebase",
  "firebase_distribution": true,
  "distribution_script_path": "scripts/distribute_ios.sh",
  "firebase_plist_path": "MyApp/GoogleService-Info.plist"
}
```

`check-config` fails early if Firebase delivery is enabled but the distribution script or plist path is missing.

## Troubleshooting

Run both checks first:

```bash
swift-orchestrator check
swift-orchestrator check-config
```

Common issues:

- `swift-orchestrator: command not found`: install the package in the active Python environment or use the virtualenv's `bin/swift-orchestrator`.
- `Configure xcode_project, xcode_workspace, or build_command`: run `init` from the Swift project root or set `build_command`.
- `scheme is required`: set `scheme` in `.swift-orchestrator/project.json`.
- `No AI providers found`: authenticate a provider CLI or export a supported API key.
- SSH worker is `NOT READY`: run `swift-orchestrator worker-install --machine NAME`, then rerun `worker-check`.
- Remote worker imports fail after package changes: rerun `worker-install` to refresh the source copy.
- GitHub actions fail: install `gh` and run `gh auth login`.

## Generated Ignore Rules

`swift-orchestrator init` writes `.swift-orchestrator/.gitignore`:

```gitignore
jobs/
logs/
output/
state/
*.pyc
__pycache__/
```

This lets the project commit orchestrator config while keeping runtime output local.

## Suggested Project Docs

The setup checker looks for grounding docs that help AI agents work consistently:

```text
AGENTS.md
docs/architecture.md
docs/coding-standards.md
docs/build-test-commands.md
```

Minimal `AGENTS.md` snippet:

```md
# AGENTS.md

Use `docs/build-test-commands.md` for canonical validation commands.
Prefer minimal, reviewable diffs.
Do not commit secrets, generated runtime logs, or unrelated changes.
Run `swift-orchestrator check-config` after changing `.swift-orchestrator/project.json`.
```

# Migration Guide From Thirteen `ai/`

This guide describes moving from Thirteen's repo-local `ai/` orchestration directory to the standalone `swift_orchestrator` package.

The migration does not require deleting Thirteen's current `ai/` files. Keep them until the standalone package has handled real jobs in the target project.

## What Changes

Old shape:

```text
ai/
  config/
  jobs/
  logs/
  output/
  prompts/
  scripts/
```

New shape:

```text
swift_orchestrator/
  orchestrator/
    prompts/
    scripts/

TargetSwiftProject/
  .swift-orchestrator/
    .gitignore
    project.json
    config/
    jobs/
    logs/
    output/
    state/
```

The reusable code and prompts live in the Python package. Project-specific config and runtime data live in `.swift-orchestrator/` inside each Swift repository.

## 1. Install The Package

From the repository containing `swift_orchestrator`:

```bash
cd swift_orchestrator
python3 -m pip install -e .
swift-orchestrator --help
```

## 2. Initialize The Swift Project

From the Swift project root:

```bash
swift-orchestrator init
swift-orchestrator check-config
```

If the project has multiple schemes, pass the intended values:

```bash
swift-orchestrator init --scheme MyApp --test-target MyAppTests --base-branch main
```

## 3. Port Project Config

Move project-specific settings from old `ai/config/*.json` into:

```text
.swift-orchestrator/project.json
.swift-orchestrator/config/machines.json
.swift-orchestrator/config/settings.json
```

Use these mappings:

| Old repo-local assumption | New package config |
| --- | --- |
| `ai/config/machines.json` | `.swift-orchestrator/config/machines.json` |
| `ai/config/settings.json` | `.swift-orchestrator/config/settings.json` |
| `ai/jobs` | `.swift-orchestrator/jobs` |
| `ai/logs` | `.swift-orchestrator/logs` |
| `ai/output` | `.swift-orchestrator/output` |
| hardcoded `Thirteen.xcodeproj` | `project.json` `xcode_project` |
| hardcoded `Thirteen` scheme | `project.json` `scheme` |
| hardcoded `ThirteenTests` | `project.json` `test_target` |
| `scripts/distribute_ios.sh` default | `project.json` `distribution_script_path` |
| `GoogleService-Info.plist` default | `project.json` `firebase_plist_path` |

Keep secrets out of committed config. Prefer environment variables or local-only settings for tokens and API keys.

## 4. Replace Command Invocations

Use the console script instead of direct `ai/scripts` paths.

| Old | New |
| --- | --- |
| `python3 ai/scripts/dev_console.py` | `swift-orchestrator console` |
| `python3 ai/scripts/check_setup.py` | `swift-orchestrator check` |
| `python3 ai/scripts/worker_tools.py check` | `swift-orchestrator worker-check` |
| `python3 ai/scripts/new_job.py bug` | `swift-orchestrator script new_job.py bug` |

For temporary compatibility, direct script passthrough is available:

```bash
swift-orchestrator script SCRIPT_NAME.py [args...]
```

## 5. Configure Remote Workers

For every SSH worker in `.swift-orchestrator/config/machines.json`, set:

```json
{
  "execution_mode": "ssh",
  "ssh_target": "mac2",
  "repo_path": "/Users/me/Documents/MyApp",
  "orchestrator_package_path": "~/.swift-orchestrator/package",
  "orchestrator_runtime_dir": ".swift-orchestrator"
}
```

Then install the package copy on each worker:

```bash
swift-orchestrator worker-install --machine mac2
swift-orchestrator worker-check --machine mac2
```

This is the main behavioral difference from the old `ai/` layout. Remote workers no longer assume `python3 -m orchestrator...` exists inside the app repo. They import the package from `orchestrator_package_path`.

## 6. Port Prompt Overrides

Default prompts are packaged in:

```text
swift_orchestrator/orchestrator/prompts/
```

If a project needs custom prompts, place them in:

```text
.swift-orchestrator/prompts/
```

The project prompts directory takes precedence when it exists.

## 7. Validate With Smoke Tests

From the package repository:

```bash
python3 tests/smoke_package_install.py
python3 -m unittest discover -s tests
PYTHONPATH=.:orchestrator/scripts python3 orchestrator/scripts/smoke_test_workflow.py --scenario all
```

From the target Swift project:

```bash
swift-orchestrator check
swift-orchestrator check-config
swift-orchestrator worker-check
```

Run a small local job before enabling SSH dispatch or delivery.

## 8. Git Ignore Recommendations

`swift-orchestrator init` writes `.swift-orchestrator/.gitignore` so runtime output is ignored inside the generated directory:

```gitignore
jobs/
logs/
output/
state/
*.pyc
__pycache__/
```

Commit these when they are intended to be shared:

```text
.swift-orchestrator/.gitignore
.swift-orchestrator/project.json
.swift-orchestrator/config/machines.json
.swift-orchestrator/config/settings.json
```

If `settings.json` contains secrets, do not commit it. Use an example file instead.

## Cutover Checklist

1. `swift-orchestrator --help` works in the developer shell.
2. `.swift-orchestrator/project.json` has the correct project, scheme, test target, and branch settings.
3. `swift-orchestrator check-config` passes.
4. `swift-orchestrator check` finds Xcode, GitHub CLI, and at least one AI provider.
5. Local job creation and scheduling works.
6. `swift-orchestrator worker-install` and `worker-check` pass for SSH workers.
7. Firebase delivery is disabled or has valid project paths.
8. Old `ai/` commands have been replaced in scripts, docs, and runbooks.
9. Generated runtime directories are ignored by Git.

After this checklist passes, the old `ai/` directory can remain as historical reference or be removed in a separate cleanup change.

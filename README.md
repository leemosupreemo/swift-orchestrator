# Orchestrator (Beta)

**Build product features and fix bugs by coordinating multiple machines and LLMs through one end-to-end development workflow.**

Orchestrator brings planning, implementation, review, testing, and delivery into a single multi-agent process. It distributes work across local and remote machines, assigns different LLMs to specialized roles, and carries each change from an idea or bug report through verification.

Orchestrator began with deep support for Swift and Xcode. It is now expanding across languages, with beta support for Rust, Python, Node.js/TypeScript, Go, Swift Package Manager, and Xcode projects.

---

## 🚀 Key Features

*   **Interactive Dev Console**: A terminal-based UI designed for speed. Single-key shortcuts (`y/n`, `A`/`F`/`Q`) and real-time status bars make orchestration feel like a native tool.
*   **Structured Multi-Agent Workflow**: Jobs pass through specialized agents, with feature work guided by a test-driven development (TDD) philosophy:
    *   **Planner**: Analyzes requirements and drafts a multi-step plan that defines tests before production code.
    *   **Builder**: Follows the Red–Green–Refactor cycle: write a failing test, implement the minimum code needed to pass, then improve the code while keeping tests green.
    *   **Reviewer**: Audits the implementation, test coverage, and regression risks before changes are finalized.
    *   **Verifier**: Runs the configured test suite and validates that the implementation meets the original goal without breaking existing behavior.
*   **Fleet Orchestration**: Dispatch heavy builds or exhaustive test suites to remote machines via SSH. The Orchestrator handles branch synchronization, worker package installation, remote execution, and job output automatically.
*   **Interactive AI Login**: Missing an API key or session? Log in to providers (`antigravity`, `claude`, `gh`, etc.) directly from the discovery wizard without restarting.
*   **Automated GitHub PR & Issue Workflow**: Integrates with GitHub through the `gh` CLI to create issues, open pull requests, and post automated status updates.
*   **Multi-Language Project Setup (Beta)**: Detect Rust, Python, Node.js/TypeScript, Go, Swift Package Manager, and Xcode projects, then configure the appropriate build and test commands.

---

## 🛠️ Install

Recommended CLI install via `pipx`:

```bash
brew install pipx
pipx ensurepath
pipx install "git+https://github.com/leemosupreemo/orchestrator.git"
orchestrator --help
```

### Quick Start

1.  **Configure**: Run the wizard from the project root.
    ```bash
    cd /path/to/MyProject
    orchestrator wizard
    ```
2.  **Verify**: Check the saved project, provider, and worker configuration.
    ```bash
    orchestrator check
    ```
3.  **Launch Console**: Start the interactive dev console to create your first job.
    ```bash
    orchestrator console
    ```

### Setup Wizard

The interactive wizard detects the project stack and walks through five stages:

1. **Project**: Review the detected project name, branch, and build/test configuration. Xcode projects use a scheme and test target; other projects use build and test commands.
2. **AI setup**: Choose at least one model and, when needed, sign in to a provider or enter an API key.
3. **Optional tools**: Configure GitHub integration, custom role prompts, SSH workers, and Apple delivery/signing. Press Enter to skip this stage.
4. **Review and apply**: Review every proposed change before files are written. You can edit project settings or models, apply the configuration, or cancel without changing project files.
5. **Verify and finish**: Validate the configuration, index the project, and optionally check Xcode build settings. The completion message appears only after the requested checks pass.

Prompts explain what Enter will do. Optional fields display **Enter: skip this field**, fields with detected values display **Enter: keep default**, and optional sections can be skipped with **Ctrl-S**. Use **Ctrl-Q** to quit the wizard.

The core required settings are a project name and at least one AI model. Xcode projects also need a project or workspace, scheme, and test target or test command. Other projects need build and test commands. SSH worker and Firebase delivery fields become required only when those optional features are selected.

For all wizard options, non-interactive setup, and generated files, see the [User Guide](docs/user-guide.md#first-run-wizard).

### Multi-Language Support (Beta)

Orchestrator is expanding beyond Swift and Xcode. Beta project detection and test discovery currently support:

| Stack | Typical build command | Typical test command |
| :--- | :--- | :--- |
| Rust | `cargo build` | `cargo test` |
| Python | `python3 -m compileall` | `pytest` or `python3 -m unittest` |
| Node.js / TypeScript | Project package script | Project package test script |
| Go | `go build ./...` | `go test ./...` |
| Swift Package Manager | `swift build` | `swift test` |
| Xcode | Detected `xcodebuild` configuration | Detected scheme and test target |

The wizard proposes commands from the detected stack and lets you review or replace them before saving. For interpreted projects, the build command should perform a meaningful validation such as compilation, type checking, or linting.

Simulator inspection, code signing, and Firebase distribution remain Apple-focused. See [Generic Projects](docs/generic-projects.md) for configuration details and current limitations.

---

## 🧩 Agent Hierarchy

| Agent | Role | Output |
| :--- | :--- | :--- |
| **Planner** | Strategic analysis & Step-by-step planning | `plan.json` |
| **Builder** | Code implementation & Tool execution | File changes |
| **Reviewer** | Technical audit & PR readiness check | Review comments |
| **Verifier** | Goal validation & regression testing | Pass/Fail status |
| **Debug Agent** | Iterative fix & test-loop management | Bug fixes |
| **Build Checker** | Log analysis & error diagnostics | Root cause insights |

---

## 💻 Dev Console UI

The Dev Console is the primary way to interact with the Orchestrator. It features:
- **Single-Key Control**: Navigate menus and approve actions with instant key presses (no `Enter` required for `y/n` or menu choices).
- **Interactive AI Discovery**: Automatically detects installed CLIs and guides you through authentication if needed.
- **Real-time Status Bar**: Tracks machine availability, active models, and job progress.
- **Context Linking**: Easily attach logs, UI mockups, or previous job context to new requests.

---

## 📡 Remote Workers (Fleet)

Scale your workflow by adding remote machines as workers. Remote workers can handle:
- **Builds**: Offload heavy `xcodebuild` tasks.
- **Tests**: Run exhaustive UI or unit test suites in parallel.
- **Execution**: The Orchestrator syncs your repository and its own runtime to the worker automatically.

Add workers in `.orchestrator/config/machines.json` and prepare them with:
```bash
orchestrator worker-install --machine mac2
orchestrator worker-check --machine mac2
```

---

## ⚙️ Project Configuration

The core configuration lives in `.orchestrator/project.json`.

```json
{
  "project_name": "MyApp",
  "base_branch": "main",
  "scheme": "MyApp",
  "test_target": "MyAppTests",
  "branch_prefix": "ai/issue",
  "firebase_distribution": true
}
```

Validate your configuration any time:
```bash
orchestrator check-config
```

### 🆙 Keeping Up to Date

Easily update your local installation and your remote fleet with one command:
```bash
orchestrator update          # Updates local package (Git/Pip)
orchestrator update --fleet  # Updates all remote workers
```

---

## 📚 Documentation

- [Getting Started](docs/getting-started.md): What Orchestrator does and the first commands to run.
- [User Guide](docs/user-guide.md): Comprehensive setup, commands, and troubleshooting.
- [Migration Guide](docs/migration-guide.md): Transitioning from legacy local scripts.
- [AI Workflow](docs/ai-workflow.md): Understanding the agentic lifecycle.

---

## 🛠️ Local Development

For developers contributing to the Orchestrator itself:

```bash
git clone https://github.com/leemosupreemo/orchestrator.git
cd orchestrator
python3 -m pip install -e .
python3 -m unittest discover tests
```

Package install smoke test:
```bash
python3 tests/smoke_package_install.py
```

---

## 📄 License

Copyright © 2026 The Jaunt Company. All rights reserved.

This project is source-available for viewing and evaluation, but is
not released under an open-source license. See [LICENSE](LICENSE) for details.

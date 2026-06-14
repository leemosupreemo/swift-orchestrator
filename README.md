# Swift Orchestrator

Swift Orchestrator is a standalone, multi-agent AI orchestration platform designed for Swift and Xcode projects. It provides a rich, interactive dev console for automating software engineering tasks—from bug fixes and feature planning to fleet-wide test execution and Firebase distribution.

Unlike generic AI coding tools, Orchestrator is built specifically for the complexities of the Apple ecosystem, supporting deep integration with `xcodebuild`, simulators, and remote Mac build farms.

---

## 🚀 Key Features

*   **Interactive Dev Console**: A terminal-based UI designed for speed. Single-key shortcuts (`y/n`, `A`/`F`/`Q`) and real-time status bars make orchestration feel like a native tool.
*   **Structured Multi-Agent Workflow**: Jobs pass through specialized agents:
    *   **Planner**: Analyzes requirements and drafts a multi-step implementation plan.
    *   **Builder**: Executes the plan, writing code and running terminal tools.
    *   **Reviewer**: Performs a technical audit of changes before they are finalized.
    *   **Verifier**: Validates that the implementation meets the original goal and maintains system integrity.
*   **Fleet Orchestration**: Dispatch heavy builds or exhaustive test suites to remote Macs via SSH. The Orchestrator manages code syncing, package installation, and log retrieval automatically.
*   **Project-Local Intelligence**: Store role-specific prompt overrides (`.orchestrator/prompts/`) and architecture guides (`AGENTS.md`) directly in your repo to keep agents grounded in your project's conventions.
*   **Interactive AI Login**: Missing an API key or session? Log in to providers (`gemini`, `claude`, `gh`, etc.) directly from the discovery wizard without restarting.
*   **Automated PR & Issue Workflow**: Seamlessly integrates with `gh` CLI to create issues, open PRs, and post-automated status updates.

---

## 🛠️ Install

Recommended CLI install via `pipx`:

```bash
brew install pipx
pipx ensurepath
pipx install "git+https://github.com/leemosupreemo/orchestrator.git"
orchestrator --help
```

### Quick Start (First Project)

1.  **Initialize**: Run the wizard in your project root to detect schemes and set up config.
    ```bash
    cd /path/to/MySwiftProject
    orchestrator wizard
    ```
2.  **Verify**: Ensure your environment (CLIs, API keys) is ready.
    ```bash
    orchestrator check
    ```
3.  **Launch Console**: Start the interactive dev console to create your first job.
    ```bash
    orchestrator console
    ```

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

Scale your workflow by adding remote Macs as workers. Remote workers can handle:
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

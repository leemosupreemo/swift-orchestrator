# Getting Started 🚀

Orchestrator is a terminal dev console for running structured AI coding workflows on Swift and Xcode projects. It helps you turn a request into a tracked job, route that job through planning/build/review steps, run project checks, and coordinate optional remote Macs for heavier build/test work.

Use this guide if you are new and want to understand what to run first.

## What Orchestrator Does 🛠️

Orchestrator gives your project a repeatable, high-fidelity AI workflow:

- **Create Jobs**: For bug fixes, features, refactors, design prototypes, or test coverage.
- **Provide Context**: Feed agents context via `AGENTS.md`, docs, logs, and prompt guidelines.
- **Run Tasks**: Build, test, perform visual checks, and run delivery scripts from one console.
- **Track History**: Keep job state, logs, outputs, and review artifacts clean under `.orchestrator/`.
- **Coordinate Workers**: Use remote Mac worker machines for fleet builds and tests.

It is not a replacement for your repository. It acts as a project-local workflow layer around your repository, build commands, AI providers, and optional worker machines.

## First Project Setup ⚙️

From your Swift or Xcode project root, run the setup wizard:

```bash
orchestrator wizard
```

The wizard detects your project, creates `.orchestrator/project.json`, configures AI providers and models, and sets up starter docs.

Then, verify your setup and start the console:

```bash
orchestrator check
orchestrator console
```

- Use `orchestrator check` to verify local prerequisites and environment keys.
- Use `orchestrator console` to launch the interactive dev console interface.

## First Job 🧠

In the Dev Console:

1. Select **New AI Job** from the main menu.
2. Choose the job type that best matches your target goal.
3. Describe the change, bug, or feature request in plain language.
4. Choose whether to plan only or dispatch full implementation immediately.
5. Review the generated plan and track progress in real-time from the job history.

> [!TIP]
> Use quick/iteration paths for small fixes. Use design-first or planning paths for larger features to give agents a clear direction before editing code.

## Where Things Live 📂

Important project files and directories:

```text
.orchestrator/project.json        Project configuration
.orchestrator/config/settings.json Local provider and console settings
.orchestrator/config/machines.json Remote worker definitions
.orchestrator/jobs/                Runtime job records
.orchestrator/logs/                Runtime logs
AGENTS.md                         Project instructions for coding agents
docs/build-test-commands.md        Canonical build and test commands
docs/ai-workflow.md                Project AI workflow notes
```

Note: Runtime logs and job outputs are kept separate from source code to avoid cluttering your repository.

## Common Commands 💻

Quick reference for essential CLI commands:

```bash
orchestrator wizard        # Launch setup wizard
orchestrator check         # Verify system prerequisites
orchestrator check-config  # Check project config for errors
orchestrator console       # Open the interactive console
orchestrator projects      # List all managed projects
orchestrator use <path>    # Set active project directory
orchestrator update        # Update Orchestrator CLI tool
```

## What To Read Next 📖

- [User Guide](docs/user-guide.md): Full setup, command options, and troubleshooting details.
- [AI Workflow](docs/ai-workflow.md): Detailed look at planning, building, review, and verification.
- [Build/Test Commands](docs/build-test-commands.md): Canonical verification commands for agents.
- [Recommended MCP Plugins](docs/recommended-mcp-plugins.md): Optional MCP integrations that improve workflows.

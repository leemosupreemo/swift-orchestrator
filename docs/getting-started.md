# Getting Started

Orchestrator is a terminal dev console for running structured AI coding workflows on Swift and Xcode projects. It helps you turn a request into a tracked job, route that job through planning/build/review steps, run project checks, and optionally coordinate remote Macs for heavier build and test work.

Use this guide if you are new and want to understand what to run first.

## What Orchestrator Does

Orchestrator gives your project a repeatable AI workflow:

- Create jobs for bug fixes, features, refactors, design prototypes, or test coverage.
- Give agents the project context they need through `AGENTS.md`, docs, logs, and prompts.
- Run builds, tests, visual checks, and delivery scripts from one console.
- Keep job state, logs, output, and review artifacts under `.orchestrator/`.
- Optionally use remote Mac workers for fleet builds and tests.

It is not a replacement for your repository. It is a project-local workflow layer around your repo, your build commands, your AI providers, and your optional worker machines.

## First Project Setup

From your Swift or Xcode project root:

```bash
orchestrator wizard
```

The wizard detects your project, creates `.orchestrator/project.json`, asks which AI providers/models to use, and can create starter docs.

Then run:

```bash
orchestrator check
orchestrator console
```

Use `orchestrator check` to verify local prerequisites. Use `orchestrator console` for the interactive workflow.

## First Job

In the Dev Console:

1. Choose `New AI Job`.
2. Pick the job type that matches your goal.
3. Describe the change, bug, or feature in plain language.
4. Choose whether to plan only or dispatch implementation.
5. Review the generated plan and progress from the job history.

For small fixes, use the quick/iteration paths. For larger features, use the design-first or planning paths so the agent has a clearer target before editing code.

## Where Things Live

Important project files:

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

Runtime job logs and outputs are intentionally kept separate from the source files the agents edit.

## Common Commands

```bash
orchestrator wizard
orchestrator check
orchestrator check-config
orchestrator console
orchestrator projects
orchestrator use /path/to/project
orchestrator update
```

## What To Read Next

- `docs/user-guide.md` for full setup, commands, and troubleshooting.
- `docs/ai-workflow.md` for how jobs move through planning, building, review, and verification.
- `docs/build-test-commands.md` for the validation commands agents should use.
- `docs/recommended-mcp-plugins.md` for optional integrations that improve Codex and MCP-based workflows.

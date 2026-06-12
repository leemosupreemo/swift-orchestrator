# AGENTS.md

Repository guidance for coding agents working on swift-orchestrator.

- Use `docs/build-test-commands.md` for canonical validation commands.
- Prefer minimal, reviewable diffs.
- Do not modify unrelated files.
- Do not commit secrets, generated runtime logs, or unrelated environment changes.
- Run `orchestrator check-config` after changing `.orchestrator/project.json`.

# Coding Standards

This document outlines the coding standards for both the Swift Orchestrator itself (Python) and the target Swift projects it manages.

## Python (Orchestrator)

*   **Python Version**: 3.11 or higher.
*   **Minimal Dependencies**: Avoid non-standard library dependencies unless absolutely necessary.
*   **Type Hinting**: Use PEP 484 type hints for all function signatures.
*   **Asynchronous I/O**: Use `subprocess` with proper timeouts and error handling.
*   **Configuration**: Prefer `.orchestrator/project.json` for persistent settings and environment variables for secrets.
*   **Logging**: Use structured logging to `.orchestrator/logs/` for easy AI analysis.

## Swift / Xcode (Target Projects)

*   **Swift Version**: Latest stable version supported by the project's Xcode version.
*   **Architecture**: Prefer clean, modular architectures (e.g., MVVM, Composable Architecture) that are easy for AI to reason about.
*   **Testing**:
    *   Every new feature must have corresponding unit tests.
    *   Bug fixes must include a regression test.
    *   Prefer `XCTest` for logic and UI tests.
*   **Documentation**:
    *   Use Swift DocC comments for public APIs.
    *   Maintain grounding docs: `AGENTS.md`, `docs/architecture.md`, `docs/coding-standards.md`, and `docs/build-test-commands.md`.
*   **Style**: Adhere to the project's established style (e.g., SwiftLint configuration if present).

## AI Collaboration

*   **Reviewability**: Keep pull requests focused and small.
*   **Commit Messages**: Follow conventional commits (e.g., `feat:`, `fix:`, `docs:`, `chore:`).
*   **Context Preservation**: Always update `AGENTS.md` with new project-wide rules or conventions.

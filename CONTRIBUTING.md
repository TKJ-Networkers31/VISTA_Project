# Contributing

## Workflow
- `main` is always stable. Work on branches: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `chore/<topic>`.
- One small, focused change per pull request, linked to a roadmap phase.

## Code review
Every change is reviewed by a human using [ai/REVIEW_CHECKLIST.md](ai/REVIEW_CHECKLIST.md). Review the full diff, not only the summary.

## Testing
Changes need tests appropriate to the layer ([docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md)). State tests actually run and their real results in the PR. Never claim passing tests that were not run.

## Commit conventions (recommended)
Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Imperative subject under ~72 chars.

## AI-assisted contributions
Follow [ai/AI_WORKING_RULES.md](ai/AI_WORKING_RULES.md). AI agents must not commit, push, reset, clean, or run destructive Git operations without explicit instruction. The human submitter is responsible for the content.

## Documentation
Behavior changes require doc updates. Architectural changes require an ADR ([docs/ADR/README.md](docs/ADR/README.md)).

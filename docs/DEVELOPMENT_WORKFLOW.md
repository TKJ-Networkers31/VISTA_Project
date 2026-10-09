# Development Workflow

## Developer flow
1. Pick a task from the current roadmap phase.
2. Branch (`feat/...`), read relevant docs, make a small change with tests.
3. Run tests, review diff, update docs, open a PR.

## Working with an AI coding agent
1. Fill [../ai/TASK_TEMPLATE.md](../ai/TASK_TEMPLATE.md) or use a prompt from [../ai/PROMPT_TEMPLATES.md](../ai/PROMPT_TEMPLATES.md).
2. Agent audits the repo and `git diff` first, then works within scope.
3. Agent reports changed files, tests run, actual results, and limitations.
4. Human reviews with [../ai/REVIEW_CHECKLIST.md](../ai/REVIEW_CHECKLIST.md) and performs any commit.

## Testing
See [TEST_STRATEGY.md](TEST_STRATEGY.md). Report real results only.

## Diff review
Read every changed line; check for scope creep, new dependencies, secrets, and doc drift.

## Documentation
Update docs in the same change as behavior. Use ADRs for architectural decisions.

## Git workflow
Feature branches off `main`, PR review, squash or merge per owner preference. Agents never commit or push unless explicitly told.

## Safe rollback
Prefer `git revert <commit>` for shared history. Before any risky local operation, create a backup branch (`git branch backup/<date>`). Do not use `reset --hard` or `clean -fd` without checking `git status` and the owner's explicit approval.

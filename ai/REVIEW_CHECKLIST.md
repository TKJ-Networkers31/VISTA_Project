# Review Checklist for AI Changes

- [ ] Change matches the task scope; no unrelated edits.
- [ ] Full `git diff` read.
- [ ] No secrets, model weights, personal images, or large files.
- [ ] No new dependency without justification; versions verified.
- [ ] Architecture boundaries respected ([../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)).
- [ ] Output conforms to [../docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md).
- [ ] Tests added; tests actually run; reported results are real.
- [ ] Error handling and limits present for new inputs.
- [ ] No claims of unimplemented features; docs and CHANGELOG updated.
- [ ] No destructive Git actions occurred.
- [ ] Privacy: no raw image retention or content logging added.
- [ ] Queues, buffers, and model residency stay bounded; timeouts and cancellation present.
- [ ] External calls only through provider adapters and the configured policy; no secrets in code or logs.
- [ ] Unsupported capabilities report honest status; no simulated spatial data.
- [ ] Normal tests need no network, keys, model weights, or GPU.

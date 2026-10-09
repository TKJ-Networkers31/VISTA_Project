# Security Policy

**Project stage:** planning (Phase 0). There is no deployable software yet, so there are no supported versions.

## Reporting a vulnerability

Do not open a public issue. Contact the maintainer privately (GitHub private vulnerability reporting once enabled on the repository, or the contact the owner adds here: `TODO: owner to add contact`). Include description, reproduction steps, and impact. Expect acknowledgment on a best-effort basis.

## Development security policy

- Never commit secrets, model weights, personal images, or datasets.
- Validate all uploads; see [docs/SECURITY_AND_PRIVACY.md](docs/SECURITY_AND_PRIVACY.md).
- Bind to `127.0.0.1` by default; exposing to the LAN is an explicit opt-in.
- Raw images are not retained by default.
- Verify dependencies and model licenses before adding them.

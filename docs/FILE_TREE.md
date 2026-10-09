# File Tree

Legend: **[v0.1]** exists now · **[MVP]** created in Phases 1–5 · **[Future]** later phases. Files are created only when needed; no empty placeholder code files.

```text
VISTA/
├── README.md, LICENSE_DECISION.md, CHANGELOG.md, SECURITY.md      [v0.1]
├── CODE_OF_CONDUCT.md, CONTRIBUTING.md, GITHUB_SETUP.md           [v0.1]
├── .gitignore, .env.example, pyproject.toml                        [v0.1]
├── LICENSE                         awaiting owner decision        [Future]
├── docs/                           documentation                   [v0.1]
│   └── ADR/                        decision records                [v0.1]
├── ai/                             AI agent rules and templates    [v0.1]
├── apps/
│   ├── api/                        FastAPI app, routes, error mapping   [MVP, Phase 1+]
│   └── web/                        static HTML/CSS/JS UI                [MVP, Phase 4]
├── core/
│   ├── contracts/                  schemas and shared types             [MVP, Phase 1–2]
│   ├── pipeline/                   analysis orchestrator                [MVP, Phase 2]
│   ├── vision/                     decode, preprocess, detection        [MVP, Phase 2–3]
│   ├── ocr/                        OCR provider                         [MVP, Phase 2]
│   ├── spatial/                    transforms, pose, anchors            [Future, Phase 8]
│   └── storage/                    temp files, optional persistence     [MVP, Phase 2]
├── configs/                        non-secret config files              [MVP, when needed]
├── tests/
│   ├── unit/                       [MVP]
│   ├── integration/                [MVP]
│   └── fixtures/                   small synthetic/own images only      [MVP]
└── scripts/                        dev helper scripts                   [when needed]
```

Directories under `apps/`, `core/`, `configs/`, `tests/`, `scripts/` are **not** created in v0.1 (Git does not track empty directories, and empty stubs add no value). Create each with its first real file.

## Responsibilities
See [ARCHITECTURE.md](ARCHITECTURE.md) for dependency rules. Tests mirror module paths. Fixtures must be free of personal data and licensed for the repo.

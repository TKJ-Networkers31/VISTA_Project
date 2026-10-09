# File Tree

Legend: **[exists]** present now · **[phase N]** created when that phase begins. Only useful files are created; no speculative modules.

```text
VISTA/
├── README.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md,
│   CODE_OF_CONDUCT.md, LICENSE_DECISION.md, GITHUB_SETUP.md      [exists]
├── .gitignore, .env.example, pyproject.toml, requirements-dev.txt [exists]
├── LICENSE                                   awaiting owner decision
├── docs/                                                         [exists]
│   ├── PROJECT_OVERVIEW, PRODUCT_SPEC, ARCHITECTURE, PROCESS_FLOWS, ROADMAP
│   ├── FILE_TREE, DATA_CONTRACTS, SECURITY_AND_PRIVACY, TEST_STRATEGY, TECH_STACK
│   ├── DEVELOPMENT_WORKFLOW, RESOURCE_BUDGET, WINDOWS_SETUP, CONFIGURATION
│   ├── ERROR_HANDLING, OBSERVABILITY, SPATIAL_COMPUTING_PLAN
│   ├── API_PROVIDER_POLICY, PLANNING_NOTES, GLOSSARY   (all .md)
│   └── ADR/  README, ADR-0001, ADR-0002, ADR-0003
├── ai/  AI_WORKING_RULES, PROMPT_TEMPLATES, TASK_TEMPLATE,
│        REVIEW_CHECKLIST, DECISION_LOG                            [exists]
├── apps/
│   ├── api/       README.md [exists]; code in phase 1
│   └── web/       README.md [exists]; code in phase 2 (Android client later, phase 9)
├── core/
│   ├── contracts/      README.md [exists]; schemas phase 1
│   ├── orchestration/  README.md [exists]; registry/queue phase 1
│   ├── vision/         README.md [exists]; decode/preprocess phase 1–2, detection phase 3
│   ├── ocr/            README.md [exists]; provider phase 2
│   ├── providers/      README.md [exists]; interface + mocks phase 1, adapters phase 4
│   ├── voice/          README.md [exists]; phase 6
│   ├── spatial/        README.md [exists]; phase 8
│   └── storage/        README.md [exists]; temp files phase 1–2
├── configs/       README.md [exists]
├── tests/         README.md [exists]; unit/integration/fixtures created with first tests
└── scripts/       README.md [exists]
```

Each planned directory currently contains only a `README.md` stating its purpose and boundary (no Python files). Other docs and the README link here for the layout of record; any change to structure requires updating this file in the same change.

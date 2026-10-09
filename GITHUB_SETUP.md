# GitHub Setup

Recommended repository name: `VISTA`.
Suggested description: *Modular visual AI platform: OCR, object detection, live camera, voice, and future spatial/AR computing (planning stage).*

These commands are **not** run automatically. Before anything, check state:

```bash
git status
git branch -a
git remote -v
git diff
```

## Option 1 — New empty GitHub repository

1. On GitHub, create an empty repository (no README, no license, no .gitignore).
2. Locally:

```bash
git init -b main
git add .
git status            # confirm no secrets/models/data are staged
git commit -m "docs: add VISTA project foundation v0.1"
git remote add origin https://github.com/<owner>/VISTA.git
git push -u origin main
```

## Option 2 — Existing repository (do not overwrite prior work)

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
git checkout -b docs/vista-foundation
# copy the VISTA files in, resolving any name conflicts by hand
git status
git diff
git add <specific files>
git commit -m "docs: add VISTA project foundation v0.1"
git push -u origin docs/vista-foundation   # then open a pull request
```

Never use `git push --force` on a shared branch. Verify the remote URL before pushing.

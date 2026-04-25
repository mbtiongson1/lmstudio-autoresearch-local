# AGENTS.md — AI coding agent instructions

Purpose
--------
Small, focused guidance to help AI coding agents immediately understand and work with this repository.

Repository at-a-glance
----------------------
- Minimal project: see `README.md` and `LICENSE` at repo root.
- No detected build, test, or runtime commands in the workspace. If you add tooling, list the commands under "Build & test" below.

What agents should know
-----------------------
- Follow the "link, don't embed" principle: reference existing docs (e.g. `README.md`) instead of copying them.
- Keep suggestions concise and ask clarifying questions when the repo lacks context.
- Create changes as small commits or draft pull requests and include test/run instructions where applicable.

Conventions and guardrails
-------------------------
- Prefer standard language and framework conventions; no project-specific conventions detected.
- Avoid global `applyTo: "**"` style instructions in other customization files — prefer specific globs.
- If you add customization files, put workspace-shared files under `.github/` and user-scoped files in the synced prompts folder.

Files to inspect first
---------------------
- `README.md` — project purpose and any usage notes
- `LICENSE` — license information

If you want additional, role-specific guidance (frontend/backend/tests/CI), ask and I will create targeted instruction or skill files (e.g. `.github/agents/`, `.github/prompts/`).

# design-to-react

A **standalone** AI skill that converts a **Figma design (URL)** or a **static design image
(PNG/JPG in your workspace)** into production-ready **React / Next.js** components written in
**TypeScript (`.tsx`)** with matching styles.

It is fully self-contained — no project template, no scaffolding, and **no dependency on any
other skill or on an MCP server**. Figma data is pulled via the Figma REST API from a small
Python script, so the skill behaves identically across **Claude Code, Codex, and GitHub
Copilot**.

---

## What makes it different

- **Two input modes:** Figma URL (exact design tokens) **or** an image file path (the
  multimodal model reads the pixels — zero setup, no token).
- **Two workspace modes:** an **empty folder** (emits standalone component files) **or** an
  **existing React/Next repo** (discovers the repo's conventions and integrates files in the
  right place).
- **No project generation.** It only writes the components you need — it does not clone a
  template or wire up CI/CD, Docker, auth, etc.

---

## Install

Same mechanism as other Agent Skills — the installer copies this folder into your agent's
skills directory. It works with any client that supports the open Skill format:

```bash
# Claude Code / Codex / GitHub Copilot (pick the agents you use)
npx skills add "<git-url-to-this-folder>" -g -a claude-code -a codex -a github-copilot -y
```

Or copy the folder manually to:

| Client | Location |
|---|---|
| Claude Code | `~/.claude/skills/design-to-react/` |
| Codex | `~/.codex/skills/design-to-react/` |
| GitHub Copilot | `~/.copilot/skills/design-to-react/` |

No install-time project is created — installing only registers the skill definition.

---

## Prerequisites

| Need | When |
|---|---|
| **Python 3.9+** | Figma mode (runs `scripts/fetch_figma.py`; standard library only, no `pip install`) |
| **Figma Personal Access Token** | Figma mode only — put it in a local `.env` as `FIGMA_TOKEN=...` |
| **Node.js + Playwright** | Optional — only for the screenshot compare step of the verify loop |

Image mode needs **nothing** — just an image file in the workspace.

---

## Usage

Open your coding agent in the workspace where you want the components, then ask, e.g.:

- *"Generate React components from this Figma link: `<url>`"*
- *"Build a Next.js page from `./designs/dashboard.png`"*
- *"Recreate this screen (`./mockups/login.jpg`) as a component in this repo"*

The skill will:
1. Detect the **input** (Figma URL vs image path).
2. Detect the **workspace** (empty folder vs existing React/Next repo vs incompatible repo).
3. Extract a complete design spec and confirm a screen/component inventory.
4. Generate the components, matching the target project's conventions.
5. Verify (type check + visual/static compare) and report the files it created.

Full behaviour is defined in [`SKILL.md`](./SKILL.md).

---

## Folder contents

```
design-to-react/
├── SKILL.md                          # the skill definition (the "brain")
├── README.md                         # this file
├── .env.template                     # copy to .env and add FIGMA_TOKEN (Figma mode)
├── scripts/
│   ├── fetch_figma.py                # Figma REST extractor (stdlib only, no MCP)
│   └── screenshot.js                 # optional Playwright screenshot helper
└── references/
    ├── generation_rules.md           # component generation ruleset
    ├── styling_patterns.md           # CSS Modules / vanilla-extract / Tailwind patterns
    └── workspace_integration.md      # empty vs existing-repo detection & placement
```

---

## Security

- The Figma token lives only in your local `.env` — **never** paste it into chat and never
  commit it.
- Rotate the token if it is ever exposed.
- The skill does not commit, push, or run destructive commands — file creation only.
- Delete `./.design-cache` (raw design JSON) when you're done, or add it to `.gitignore`.

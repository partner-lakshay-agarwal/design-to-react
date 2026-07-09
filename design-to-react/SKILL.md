---
name: design-to-react
description: >
  Standalone design-to-code generator. Converts a Figma design (URL) or a static
  design image (PNG/JPG file path in the workspace) into production-ready React or
  Next.js components written in TypeScript (.tsx) with co-located styles (CSS Modules,
  vanilla-extract, Tailwind, or plain CSS — auto-matched to the target project).
  Works in two workspace modes: (1) an EMPTY folder — emits standalone component files;
  (2) an EXISTING React/Next repo — discovers the repo's conventions and integrates
  new components in the right place. Fully self-contained: no project template, no
  scaffolding, no dependency on any other skill. Figma extraction uses the Figma REST
  API directly (no MCP required), so it is portable across coding agents.
  Use when: figma to code, figma to react, image to react, design to code, screenshot
  to component, build UI from design, convert mockup, generate component from Figma,
  tsx from figma, recreate this screen, turn this image into a component.
license: MIT
---

## 🔒 SKILL GUIDANCE RULE — MANDATORY

**This rule applies for the entire session, at every step, without exception.**

Before answering ANY question or taking ANY action related to generating code from a
design, you MUST first check whether this skill contains guidance for it:

1. **Re-read the relevant section of this SKILL.md** before each step.
2. **If guidance exists here → follow it exactly.** Do not substitute general knowledge,
   personal judgement, or standard AI defaults.
3. **If no guidance exists here → tell the user explicitly:**
   > "This is not covered in the design-to-react skill guidance. The following is general
   > advice — verify before using."
4. **If you feel yourself drifting** (reasoning from general knowledge, skipping a step,
   improvising) — **stop, re-read this skill, and re-anchor before continuing.**
5. **Never silently fall back to standard AI behaviour.**

Design-to-code fails silently: a skipped screen, a guessed colour, or a wrong layout
direction looks "done" but is wrong. The steps below exist to prevent exactly that.

---

# Design → React / Next.js Component Generator

## Overview

This skill turns a **design source** into **TypeScript React components** and drops them
into the **current workspace** in the correct place. It is fully standalone — it does not
scaffold a project, does not copy a template, and does not depend on any other skill.

It is defined by two independent axes. Detect BOTH before generating anything.

```
                    INPUT SOURCE                 →   converges to one core
        ┌───────────────────────┬───────────────────────┐
        │  A. Figma URL         │  B. Image file path   │
        │  (exact tokens via    │  (pixels — model      │
        │   Figma REST API)     │   estimates tokens)   │
        └───────────┬───────────┴───────────┬───────────┘
WORKSPACE MODE      │                       │
  1. Empty folder   │  write loose files    │  write loose files
  2. Existing repo  │  discover + integrate │  discover + integrate
        └───────────┴──── spec → generate → verify ─────┘
```

The middle (build spec → generate components → verify) is **identical** for all four
combinations. Only the extraction step (A vs B) and the placement step (1 vs 2) differ.

---

## 🔴 ANTI-SHORTCUT RULES — READ BEFORE EVERY GENERATION

These are non-negotiable. Each one exists because skipping it produces broken output.

1. **NEVER write a single component file before the full design spec is complete.** Extract
   every screen/component and confirm the inventory first (the completeness gate below).
2. **NEVER skip a screen because "it's similar to another".** Every Figma top-level FRAME
   and every distinct image = one screen. Implement all of them.
3. **NEVER invent colours, spacing, radii, shadows, or text.** In Figma mode use the exact
   extracted token values. In image mode use your best visual estimate AND record it as an
   estimate for the verify loop to correct — never a confident guess dressed as fact.
4. **NEVER assume layout direction.** Read child x/y coordinates (Figma) or look carefully
   at the image to decide row vs column vs grid. Do not default to vertical stacking.
5. **NEVER write files into an existing repo without first discovering its conventions**
   (framework, styling system, path aliases, component folder, formatting). Match them.
6. **NEVER dump files into an incompatible workspace** (e.g. a Python/Java repo) without
   stopping to ask the user how to proceed.
7. **NEVER hardcode secrets.** The Figma token comes from the environment or `.env` only.
8. **NEVER commit, push, or run destructive commands.** This skill only creates/edits local
   component files. Git operations are the user's decision.

---

## Step 0 — Prerequisites

| Need | When | How |
|---|---|---|
| **Python 3.9+** | Figma mode | `python --version` — used to run the extractor script |
| **Figma Personal Access Token** | Figma mode only | figma.com → Settings → Security → Personal access tokens. Store in `.env` as `FIGMA_TOKEN=...` (or export `FIGMA_TOKEN`). Never paste it in chat. |
| **Node.js + Playwright** | Visual verify loop (Step 7.2) | Only if you screenshot-compare rendered screens. One-time setup: `npm install playwright` then `npx playwright install chromium` (downloads a browser). Skip if you rely on the static fidelity pass. |

Image mode needs **nothing** — no token, no network. The image just has to be a file in
the workspace (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`).

> The extractor (`scripts/fetch_figma.py`) uses only the Python standard library — no
> `pip install` required — and calls the Figma REST API directly. There is **no MCP
> dependency**, so this skill behaves identically across Claude Code, Codex, and Copilot.

---

## Step 1 — Gather inputs (ALWAYS ASK)

Ask the user for whatever is not already obvious from their message:

> "I'll generate React/Next.js components from your design. Please confirm:
> 1. **Design source** — a **Figma URL**, or a **path to an image** in this workspace?
>    (If Figma, make sure `FIGMA_TOKEN` is set in a local `.env` — do not paste the token here.)
> 2. **Framework** — React (Vite/CRA) or **Next.js**? (I'll auto-detect if this is an existing repo.)
> 3. **Where should the components go?** — a new folder name, or integrate into the existing project?
> 4. **Any screens/components to prioritise or skip?** (default: generate all)"

Do not proceed until you know the **source** and can see the **workspace**.

---

## Step 2 — Detect INPUT type

| The user provided… | INPUT = | Go to |
|---|---|---|
| A `figma.com/design/...` or `figma.com/file/...` URL | **A — Figma** | Step 4A |
| A path ending in `.png/.jpg/.jpeg/.gif/.webp` | **B — Image** | Step 4B |
| Both | Prefer **A (Figma)** for tokens; use the image only as a visual cross-check |
| Neither / unclear | Ask. Do not guess. |

---

## Step 3 — Detect WORKSPACE mode (do this BEFORE generating)

Inspect the workspace root. **Never assume.**

```
Is there a package.json at the workspace root (or a chosen subfolder)?
├── NO  → CASE 1: EMPTY / NON-JS FOLDER
│         Emit standalone component files into ./output/<name>/ (or a folder the user names).
│         Do NOT create a full project. Optionally include a minimal index/preview only if asked.
│
└── YES → read it:
    Does dependencies/devDependencies include "react" (and optionally "next")?
    ├── YES → CASE 2: EXISTING COMPATIBLE REPO
    │          Run Convention Discovery (Step 5), then integrate files in the right place.
    │
    └── NO  → CASE 3: EXISTING INCOMPATIBLE REPO (Python/Java/other, or React-incompatible)
               STOP. Tell the user this workspace is not a React/Next project and ask:
               "Generate standalone components in a subfolder here, or did you mean to open
                a different workspace?" Proceed only after they choose.
```

Record the chosen **CASE (1/2/3)** and the **target directory** before continuing.

---

## Step 4A — Extract the Figma design (INPUT = Figma)

### 4A.1 (Large files only) List screens first

If the file/subtree is large or you don't yet know its node ids, enumerate screens
shallowly first — this is fast and never hits the API "too large" limit:

```bash
python scripts/fetch_figma.py --url "<figma-url>" --list --out ./.design-cache
```

This writes `figma_screens.md` (a screen/node-id inventory). Then extract the specific
screens you want with `--ids` (comma-separated — all are extracted):

```bash
python scripts/fetch_figma.py --url "<figma-url>" --ids "1:23,1:45" --out ./.design-cache
```

### 4A.2 Run the extractor (single command — includes reference images)

```bash
python scripts/fetch_figma.py --url "<figma-url>" --download-images --scale 2 --out ./.design-cache
```

- One run does everything: it parses the spec **and** saves one reference PNG per screen.
  Do NOT run the script twice — `--download-images` on the first run avoids a second
  network round-trip.
- Token resolution order: `--token` arg → `FIGMA_TOKEN` env → `FIGMA_API_KEY` env → `.env` file in CWD.
- The script writes into `./.design-cache/`:
  - `figma_raw.json` — the raw API response (can be large; do NOT read it directly)
  - `figma_spec.json` — the compact machine spec (screens, colour/shadow/spacing/type tokens, per-screen text, exact auto-layout + layout hints)
  - `figma_spec.md` — a human-readable summary (READ THIS)
  - `reference/*.png` — one 2× reference image per screen for the verify loop
- To re-parse an already-downloaded file without hitting the network (note: this cannot
  fetch new images):
  `python scripts/fetch_figma.py --from-json ./.design-cache/figma_raw.json --out ./.design-cache`
- **Automatic caching:** if `figma_raw.json` already exists in `--out` for the **same file +
  node**, the script reuses it and makes **no API call** (avoids rate limits). Pass
  `--refresh` to force a fresh fetch when the design changed.

### 4A.3 Read the compact spec, not the raw JSON

Open `figma_spec.md` / `figma_spec.json`. If a screen looks under-extracted, re-run the
script — do NOT hand-read the multi-MB `figma_raw.json`.

> **Portability note:** if your agent already has a Figma MCP server available, you MAY use
> it to fetch the same data instead of the script. The script is the default because it has
> no external dependency and works in every agent.

Now go to **Step 4C (Completeness Gate)**.

---

## Step 4B — Extract the design from image(s) (INPUT = Image)

1. **View each image file directly** using your image-viewing capability. Do this once per
   image — one image = one screen unless the image clearly shows multiple screens.
2. For **each** image produce a written spec covering:
   - **Layout skeleton**: sidebar? topbar? grid? split-panel? columns? Describe structure.
   - **Text**: every visible heading, label, button text, placeholder — transcribe exactly.
   - **Colours**: estimate hex for each distinct surface/text/accent. **Mark each as an
     estimate** (e.g. `~#0072DB`).
   - **Spacing/size**: estimate padding, gaps, card sizes, corner radius in px.
   - **Components**: buttons, inputs, tables, tabs, radios, badges, avatars, icons.
   - **State**: is any tab/radio shown selected? If unclear, default to none selected.
3. Because image tokens are estimates, the **verify loop (Step 7) is mandatory whenever a
   render target exists** to correct colour/spacing drift. If nothing can render, do the
   static fidelity pass instead and flag that estimates were not visually confirmed.

Now go to **Step 4C (Completeness Gate)**.

---

## Step 4C — Completeness Gate (MANDATORY for both inputs)

Produce this table and confirm it is 100% complete **before writing any code**:

```
SCREEN / COMPONENT INVENTORY
┌────────────────────────────────┬─────────────────────────┬──────────┐
│ Source name (frame / image)    │ Component / route        │ Status   │
├────────────────────────────────┼─────────────────────────┼──────────┤
│ <Figma frame or image file>    │ <ComponentName / route> │ pending  │
│ ...                            │ ...                     │ ...      │
└────────────────────────────────┴─────────────────────────┴──────────┘
```

Also, if the design has a persistent nav/sidebar, produce a NAV table mapping each nav
item to a target route/component. **Every nav item must have a destination, and every
route must have a nav item** (cross-check both ways).

Do not proceed while any row is `pending`/`missing`. A gap means extraction is incomplete
— re-extract, don't start coding.

---

## Step 5 — Convention Discovery (CASE 2 only) / Target setup (CASE 1)

### CASE 2 — Existing repo: discover before you write

Read these and record the answers. Match them exactly when generating.

| Question | How to find it |
|---|---|
| React or Next.js? App Router or Pages Router? | `package.json` deps; presence of `app/` vs `pages/` |
| Styling system? | deps + files: Tailwind (`tailwind.config.*`), CSS Modules (`*.module.css`), vanilla-extract (`*.css.ts`), styled-components/emotion, or plain CSS |
| Component directory + naming? | look at existing files under `src/components`, `app/`, `components/` — match folder + PascalCase/kebab conventions |
| Path aliases? | `tsconfig.json` `compilerOptions.paths` (e.g. `@/components/*`) — use the alias in imports |
| TypeScript strictness / lint / format? | `tsconfig.json`, `.eslintrc*`, `.prettierrc*` — match quotes, semicolons, indentation |
| Existing design tokens / theme? | search for a theme file, CSS variables, Tailwind theme — REUSE existing tokens instead of adding duplicates |
| Existing UI library? (MUI, shadcn, Chakra, Filament, etc.) | deps — prefer its primitives for interactive elements where they match the design |

**Placement rule:** new components go where the repo already puts components. Never create a
parallel structure. If unsure, ask.

### CASE 1 — Empty folder: pick a self-contained convention

- Default target: `./output/<kebab-name>/`.
- Default styling: **CSS Modules** (`Component.module.css`) — zero build config, works with
  both React and Next. Use vanilla-extract or Tailwind only if the user asks.
- Each component is self-contained: `ComponentName.tsx` + `ComponentName.module.css`.
- Add a single `tokens.css` (or `theme.css.ts`) holding all extracted colour/shadow/radius/
  type tokens, imported by the components. Never inline raw hex repeatedly.
- Do NOT add package.json, bundler config, or install anything unless the user explicitly
  asks for a runnable preview.

See `references/workspace_integration.md` for full details and `references/styling_patterns.md`
for per-styling-system code patterns.

---

## Step 6 — Generate components

Follow `references/generation_rules.md` in full. Core rules:

1. **One screen/component per file.** Use PascalCase filenames matching the inventory.
2. **All structural layout (sidebar, topbar, hero, cards, grids) = plain CSS** with the exact
   extracted tokens. Use the repo's UI-library components only for **interactive** elements
   (Button, Input, Select, Table, Tabs, Radio) and only when they match the design.
3. **Define tokens once.** Put all colours/shadows/radii/typography in one tokens file and
   reference them. In CASE 2, reuse the repo's existing tokens.
4. **Text is copied verbatim** from the spec — never paraphrased.
5. **Default state matches the design.** If nothing is shown selected, initial state is
   `null` / nothing selected — do not auto-select the first tab/radio.
6. **Layout direction comes from coordinates/visual**, per rule #4 above.
7. **Mark true unknowns** with a `// TODO(design):` comment rather than inventing content.
8. **Accessibility baseline:** semantic elements, `alt` on images, labels on inputs,
   `aria-*` where a native element can't express the role.
9. **`'use client'`** at the top of any Next.js App Router component that uses state/effects/
   event handlers.
10. **No dead dependencies.** Only import what exists in the target (verified in Step 5).

Re-read the spec for the specific screen immediately before writing its file. Do not code
from memory of the overall summary.

---

## Step 7 — Verify (self-correction loop) — MANDATORY

Repeat until every screen passes; do not declare done early.

### 7.1 Type/build check
- CASE 2: run the repo's type check / lint (`npx tsc --noEmit`, `npm run lint`) and fix all
  errors you introduced.
- CASE 1: run `npx tsc --noEmit` against the generated files if TypeScript is available;
  otherwise at minimum re-read each file for obvious type/import errors.

### 7.2 Visual compare (required whenever a render target exists)
A render target = an existing repo dev server, or a quick preview you can spin up. When one
exists this step is mandatory (and it is the primary safety net for image mode, whose tokens
are estimates). If nothing can render (e.g. CASE 1 empty folder with no preview), skip to the
static fidelity pass below instead.

One-time Playwright setup if not already installed: `npm install playwright` then
`npx playwright install chromium`.
1. Screenshot each rendered screen (see `scripts/screenshot.js` — Playwright helper).
2. Put it next to the reference (Figma PNG from 4A.2, or the source image).
3. Compare: colours, spacing, layout direction, text, component presence, selected state.
4. For each delta: re-read the spec/token for that element, fix that **one file**, clear any
   framework cache (e.g. `.next`), re-screenshot that screen only.
5. Loop until it matches.

If rendering is not available, do a **static fidelity pass**: re-open the spec and read each
generated file line-by-line against it, checking every token and text string.

### 7.3 Exit condition
- Every inventory row is done.
- Type check is clean.
- Every screen visually matches (or passed the static fidelity pass).

---

## Step 8 — Final report

Tell the user:
- Which CASE was detected and the target directory.
- The list of files created/modified (as links).
- The styling system used and where tokens live.
- Any `TODO(design)` items you left and why.
- For Figma mode: remind them to **delete `./.design-cache`** if they don't want the raw
  design JSON committed, and to **rotate the Figma token** if it was ever exposed.
- Any manual next steps (install a dependency, wire a route, provide real data).

---

## Edge cases & how to handle them (no loopholes)

| Situation | Handling |
|---|---|
| No `FIGMA_TOKEN` set | Stop, tell the user to add it to `.env` or export it. Never ask them to paste it in chat. |
| Figma URL has no `node-id` | Fetch the whole file; treat every top-level FRAME on the first page as a screen. Warn it may be large. |
| Figma API 403 / 404 | 403 = bad/expired token → regenerate; 404 = wrong file key or no access → confirm the URL and that the account can view the file. |
| Figma file is huge (multi-MB) | Always use the `node-id` subtree. Parse via the script; never hand-read `figma_raw.json`. |
| Image is blurry/low-res | Say fidelity will be limited; ask for a higher-res export or a Figma link if exactness matters. |
| Multiple images given | Each = one screen; build the inventory across all of them. |
| Existing repo uses an unknown styling system | Match the closest pattern in `references/styling_patterns.md` and state the assumption. If truly unknown, ask. |
| Existing repo already has a component with the target name | Do NOT overwrite silently. Ask to rename, extend, or replace. |
| CASE 3 (Python/Java/etc. repo) | Stop and ask (Step 3). Offer a standalone subfolder as the safe default. |
| Design references external images/icons | Use inline SVG or a placeholder with a `TODO(design)` note; never fabricate brand assets. Text logos → styled text in the brand colour. |
| Gradients / effects the styling system can't express cleanly | Use plain CSS for that element even in a Tailwind/CSS-Modules repo, and note it. |
| User asks to push/commit | Out of scope — tell them the files are ready and let them commit. |
| Partial/ambiguous design detail | Implement what's visible, mark the rest `TODO(design):`, never invent. |

---

## Reference files (read on demand — keep out of main context until needed)

- `references/generation_rules.md` — the full component-generation ruleset and file layout.
- `references/styling_patterns.md` — copy-paste patterns for CSS Modules, vanilla-extract,
  Tailwind, and plain CSS, plus the tokens-file pattern.
- `references/workspace_integration.md` — deep guidance for CASE 1/2/3 detection and
  convention discovery.

## Scripts

- `scripts/fetch_figma.py` — standalone Figma REST extractor (stdlib only, no MCP). Produces
  `figma_spec.json` + `figma_spec.md`, optionally downloads reference PNGs.
- `scripts/screenshot.js` — optional Playwright helper to screenshot rendered routes for the
  verify loop.

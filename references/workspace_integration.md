# Workspace Integration — design-to-react

How to detect the workspace mode and place generated files correctly. Always inspect;
never assume. Run this BEFORE generating any component.

---

## Detection flow

```
Look at the workspace root (and any subfolder the user named as the target).

1. Is there a package.json?
   NO  -> CASE 1 (empty / non-JS folder)
   YES -> read it.

2. Does it list "react" in dependencies or devDependencies?
   NO  -> CASE 3 (incompatible repo)
   YES -> CASE 2 (compatible repo). Also note whether "next" is present.
```

---

## CASE 1 — Empty / non-JS folder

- **Default target:** `./output/<kebab-name>/` (derive `<kebab-name>` from the design/app
  name; sanitise to lowercase-hyphen).
- Emit standalone files: `ComponentName.tsx` + `ComponentName.module.css`, plus one shared
  `tokens.css`.
- **Do NOT** create `package.json`, install deps, or add a bundler unless the user explicitly
  asks for a runnable preview.
- If the user later wants to run it, tell them to drop the files into any React/Next project,
  or ask and THEN scaffold a minimal Vite app.
- No dev server means the verify loop is a **static fidelity pass** (re-read each file against
  the spec) unless the user provides a place to render.

---

## CASE 2 — Existing React / Next repo

### Discover first (record every answer)

| Aspect | Where to look | Why |
|---|---|---|
| Framework + router | `package.json` (`react`, `next`); `app/` vs `pages/` | Determines `'use client'`, routing, file locations |
| Styling system | deps + file extensions (`.module.css`, `.css.ts`, `tailwind.config.*`, styled/emotion) | Choose the matching pattern from `styling_patterns.md` |
| Component location + naming | existing files under `src/components`, `components/`, `app/` | Place new files consistently |
| Path aliases | `tsconfig.json` `compilerOptions.paths` (`@/*`) | Use aliases in imports |
| Lint/format | `.eslintrc*`, `.prettierrc*`, `tsconfig.json` | Match quotes/semicolons/indent |
| Existing tokens/theme | search for theme files, CSS vars, Tailwind theme | Reuse, don't duplicate |
| UI library | deps (MUI, shadcn/ui, Chakra, Mantine, Filament…) | Prefer its primitives for interactive elements if they match |

### Then integrate

- New components go in the repo's existing components directory, matching its folder/file
  convention.
- Reuse existing tokens; only add new tokens for values the design introduces that aren't
  already themed.
- Wire routes only if asked (Next: add a route folder/file; React Router: add a `<Route>`).
- If a same-named component already exists, **ask** before overwriting (rename / extend /
  replace).
- Run the repo's type check + lint after generating and fix everything you introduced.

---

## CASE 3 — Existing but incompatible repo

- The workspace has a `package.json` without React, or is a Python/Java/other project.
- **STOP and ask:**
  > "This workspace looks like a `<type>` project, not a React/Next app. I can:
  > (a) generate standalone React components in a subfolder here (e.g. `./ui-components/`), or
  > (b) you can open the intended React/Next workspace and re-run.
  > Which do you prefer?"
- Only proceed after the user chooses. If (a), treat it like CASE 1 rooted at the subfolder.

---

## Guardrails (all cases)

- Never create a parallel/competing folder structure in an existing repo.
- Never overwrite files silently.
- Never install dependencies or change build config without explicit consent.
- Never commit, push, or run destructive git commands.
- Keep the Figma cache (`./.design-cache`) out of the repo unless the user wants it — remind
  them to delete it or add it to `.gitignore`.

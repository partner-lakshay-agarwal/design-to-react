# Generation Rules — design-to-react

Read this before writing any component. These rules make generated code faithful to
the design and clean enough to ship. They apply to BOTH input modes (Figma / image)
and BOTH workspace cases (empty folder / existing repo).

---

## 1. File layout

### Empty folder (CASE 1)
```
<target>/                       # ./output/<kebab-name>/ by default
├── tokens.css                  # (or theme.css.ts) all design tokens, defined ONCE
├── <ComponentName>.tsx
├── <ComponentName>.module.css
├── <AnotherComponent>.tsx
├── <AnotherComponent>.module.css
└── index.ts                    # re-exports (optional convenience)
```

### Existing repo (CASE 2)
- Put components where the repo already keeps them (e.g. `src/components/<Name>/`).
- Match the repo's file-per-component vs folder-per-component convention.
- Reuse the repo's existing tokens/theme — do NOT add a parallel `tokens.css` if one exists.

---

## 2. Structural layout vs interactive components

| Element kind | Build with |
|---|---|
| Sidebar shell, topbar shell, hero, cards, grids, section wrappers, dividers | **Plain CSS** with exact tokens. Do NOT rely on a UI-library layout component — its defaults override the design. |
| Button, Input, Select, Checkbox, Radio, Tabs, Table, Pagination, Tag, Avatar, Tooltip, Modal | The repo's UI library (MUI/shadcn/Chakra/etc.) **if** it visually matches; otherwise a plain styled element. |

If a UI-library component does not render with the design's exact look (common with
buttons and inputs), fall back to a plain styled element rather than shipping something
off-design.

---

## 3. Tokens — define once, reference everywhere

- Collect every colour, shadow, radius, font size/weight/line-height from the spec.
- Put them in ONE place (`tokens.css` custom properties, a `theme.css.ts`, or the repo's
  existing theme). Reference by name in components.
- Never repeat a raw hex across multiple files.
- Figma mode: values are exact — use them verbatim.
- Image mode: values are estimates — still centralise them so the verify loop can fix one
  place and update everything.

---

## 4. Fidelity rules

- **Text** is copied character-for-character from the spec. Never paraphrase or "improve".
- **Layout direction** comes from the spec's `layoutHint` (Figma) or careful reading of the
  image. Never default to vertical stacking.
- **Selected/default state** matches the design. If nothing is shown selected, initial state
  is `null` — do NOT auto-select the first tab/radio/item.
- **Spacing/size**: use extracted px values; in image mode, estimate consistently and refine
  in the verify loop.
- **Icons/logos**: use inline SVG or a placeholder with `// TODO(design):`. Text logos →
  styled text in the brand colour. Never fabricate a brand asset as vector paths.

---

## 5. Code quality

- TypeScript everywhere (`.tsx`), typed props via an `interface`.
- `'use client'` at the top of any Next.js App Router component using state/effects/handlers.
- One component per file, PascalCase filename matching the inventory.
- Semantic HTML: `<nav>`, `<main>`, `<header>`, `<button>`, `<table>`, `<label>` for inputs.
- Accessibility baseline: `alt` on images, labels on inputs, `aria-*` only where a native
  element cannot express the role, visible focus states.
- Realistic mock data using the exact text from the design; keep it in a local `const` or a
  small `mockData.ts` — clearly marked as mock.
- Match the repo's lint/format (quotes, semicolons, indentation) in CASE 2.
- Imports: only import what actually exists in the target (verified during discovery). No
  dead imports, no invented package names.

---

## 6. Before writing each file

1. Re-open the spec entry for THAT specific screen (not the overall summary).
2. Confirm: exact text, colours, layout direction, selected state.
3. Write the file.
4. Move to the next screen only after the current file is complete.

---

## 7. Never

- Never scaffold a whole project, add a bundler, or install packages unless explicitly asked.
- Never overwrite an existing file with the same name without asking.
- Never invent content for unclear areas — mark `// TODO(design):` instead.
- Never commit, push, or run git/destructive commands.
- Never hardcode secrets or the Figma token.

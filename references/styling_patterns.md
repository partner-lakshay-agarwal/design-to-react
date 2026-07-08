# Styling Patterns — design-to-react

Pick the pattern that matches the **target project** (CASE 2) or the chosen default
(CASE 1 default = CSS Modules). Always centralise tokens; never scatter raw hex.

---

## Tokens file (all systems)

### CSS custom properties — `tokens.css`
```css
:root {
  /* colors (from Figma fill_* tokens or estimated from the image) */
  --color-brand: #0072DB;
  --color-brand-dark: #0B5ED7;
  --color-text: #15191E;
  --color-text-subtle: #566676;
  --color-surface: #FFFFFF;
  --color-surface-alt: #F6F7F8;
  --color-sidebar: #E4E9EC;

  /* radii */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-pill: 999px;

  /* shadows (from Figma effect_* tokens) */
  --shadow-card: 4px 4px 8px 2px rgba(0, 0, 0, 0.03);
  --shadow-hero: 2px 2px 5px 1px rgba(0, 0, 0, 0.25);

  /* typography */
  --font-family: "Neue Frutiger One", "Segoe UI", system-ui, sans-serif;
  --font-size-md: 16px;
  --font-weight-bold: 700;
}
```

---

## CSS Modules (default for empty folders; common in Next.js)

`Card.module.css`
```css
.card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: 20px;
}
.title {
  font: var(--font-weight-bold) var(--font-size-md) / 1.4 var(--font-family);
  color: var(--color-text);
}
```

`Card.tsx`
```tsx
import styles from './Card.module.css';

interface CardProps {
  title: string;
  children: React.ReactNode;
}

export function Card({ title, children }: CardProps) {
  return (
    <section className={styles.card}>
      <h2 className={styles.title}>{title}</h2>
      {children}
    </section>
  );
}
```

---

## vanilla-extract (`*.css.ts`) — zero-runtime, great for Next.js

`theme.css.ts`
```ts
import { createGlobalTheme } from '@vanilla-extract/css';

export const vars = createGlobalTheme(':root', {
  color: { brand: '#0072DB', text: '#15191E', surface: '#FFFFFF' },
  radius: { md: '10px', pill: '999px' },
  shadow: { card: '4px 4px 8px 2px rgba(0,0,0,0.03)' },
  font: { family: '"Neue Frutiger One", system-ui, sans-serif', bold: '700' },
});
```

`Card.css.ts`
```ts
import { style } from '@vanilla-extract/css';
import { vars } from './theme.css';

export const card = style({
  background: vars.color.surface,
  borderRadius: vars.radius.md,
  boxShadow: vars.shadow.card,
  padding: 20,
});
```

Requires the `@vanilla-extract/*` deps + the Next/webpack plugin. Only use if the target
repo already uses it, or the user asks.

---

## Tailwind CSS — if the repo already uses it

- Map design tokens into `tailwind.config` `theme.extend` (colours, borderRadius, boxShadow,
  fontFamily), then use utility classes.
- For values Tailwind can't express cleanly (complex gradients/shadows), use an arbitrary
  value `bg-[#0072DB]` / `shadow-[4px_4px_8px_2px_rgba(0,0,0,0.03)]` or a small plain-CSS
  class. Note the exception.

```tsx
export function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[10px] bg-white p-5 shadow-[4px_4px_8px_2px_rgba(0,0,0,0.03)]">
      <h2 className="text-base font-bold text-[#15191E]">{title}</h2>
      {children}
    </section>
  );
}
```

---

## Plain CSS / global stylesheet — smallest footprint

Use a single stylesheet with BEM-ish class names and the tokens from `tokens.css`. Import it
once at the app root. Good when the repo has no styling system and the user wants minimal
tooling.

---

## Decision guide

| Target project uses… | Use |
|---|---|
| Tailwind (`tailwind.config.*`) | Tailwind |
| `*.module.css` files | CSS Modules |
| `*.css.ts` / `@vanilla-extract` | vanilla-extract |
| styled-components / emotion | match it (template literals) |
| nothing / empty folder | **CSS Modules** (default) |

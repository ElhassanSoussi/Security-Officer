# Design System

This document captures the visual language and reusable patterns used throughout the NYC Compliance Architect frontend. It is intentionally conservative and utility‑first, designed to support an enterprise B2B compliance platform that looks trustworthy, clean, and consistent.

## Tokens

All colors, spacing and radii are defined as CSS variables in `app/globals.css` and exposed via Tailwind config. These tokens are the single source of truth.

- **Primary**: `--primary` deep navy-indigo (HSL `230 60% 22%`). Used for buttons and active states.
- **Secondary / Muted / Accent**: neutral slate/grey background and text tokens. Avoid multiple bright accents; use the primary color for emphasis.
- **Semantic**: success (`--success`), warning (`--warning`), error (`--error`), destructive (`--destructive`). Use these sparingly for alerts and badges.
- **Border / Input / Ring**: light slate borders, accessible indigo focus ring.
- **Radius**: `--radius` for cards, buttons, inputs.

Typography scale (Tailwind defaults with slight tweaks):

- `text-3xl` — page titles (H1)
- `text-2xl` / `text-xl` — section titles (H2/H3)
- `text-base` / `text-sm` — body text
- `text-xs` — captions, metadata, labels
- Use the `font-medium` weight for headings; `font-normal` for body; `font-semibold` for emphasis.
- `tracking-tight` on major headings for a refined feel.

Spacing follows an 8px rhythm (`p-2`, `p-4`, `p-8`, etc.). Use utility classes directly where appropriate.

## Layout

- **Container**: pages are centered with `max-w-6xl mx-auto px-4 sm:px-6 lg:px-8` (see `tailwind.config.ts` `container` settings).
- **PageHeader**: sit at the top of each page. Props:
  - `title`: required, can be string or JSX (allows badges, links).
  - `subtitle`: optional descriptive text.
  - `actions`: optional slot for primary/secondary buttons or links.
  - Example usage: `<PageHeader title="Projects" subtitle="Manage compliance workspaces." actions={<Button>New</Button>} />`.

- **SectionCard**: a thin card wrapper for grouping related content within a page. Use `SectionCard` when a visual separation is needed but the content is not a standalone page card.

- **Grid system**: use Tailwind's `grid` utilities, typically `grid-cols-3 md:grid-cols-2` for KPI cards, `gap-4` for spacing.

## Components

- **Buttons**: styled using `components/ui/button.tsx`. Supported variants: `default` (primary blue), `outline`, `ghost`, `destructive`. Sizes: `sm`, `md`, `lg`. Use `variant="outline"` for secondary actions and `ghost` for icon-only or low‑emphasis links.

- **Inputs/Selects/Textareas**: use `components/ui/input.tsx`, `label.tsx`, `textarea.tsx`. All form controls include focus ring and border tokens.

- **Tables**: `components/ui/table.tsx` provides head/body/row/cell components. Use `Table` inside a `Card` for better separation. Add sticky headers manually with `sticky top-0 bg-card` when needed.

- **Badges**: `components/ui/badge.tsx` supports `default`, `secondary`, `destructive`, `success`, `warning`, `error` variants.

- **Empty states**: use the `EmptyState` component (see below) for tables or lists with no data. Provide an icon, title, description, and optional action.

- **Dialogs/Sheets/Toasts**: use the existing patterns from shadcn/ui already integrated. Keep dialogs simple and accessible.

## Utility components

- **PageHeader**: described above.
- **SectionCard**: described above.
- **EmptyState**: generic empty-state row or block. Props:
  - `icon`: ReactNode icon.
  - `title`: string.
  - `description`: string.
  - `action?`: optional ReactNode (e.g., button).

## Patterns

- **Spacing**: use `space-y-*` for vertical rhythm between sections.
- **Buttons in headers**: place primary actions in the `actions` slot of `PageHeader`.
- **Forms**: stack fields vertically with `space-y-4`. Inline helper text is `text-xs text-slate-400`.
- **Tables**: use `text-sm` for body, `text-xs` for metadata; use `truncate` on long text and `title` attributes for hover tooltip.
- **Empty states**: provide contextual help and a clear next step (CTA button).
- **Alerts/Errors**: use `bg-red-50 border-red-200 text-red-700` for error boxes.

## Responsive behavior

- Sidebar collapses at `md:` breakpoint; use `<div className="w-64 md:w-64 sm:w-0"` or similar with a toggle if future.
- Tables should wrap or scroll horizontally using `overflow-auto`.
- Forms stack fields on narrow screens by default using the grid utility.

## Accessibility

- Always label form elements (`<Label>` component attaches to inputs).
- Ensure focus states are visible (`focus:ring` uses `--ring` token).
- Use semantic HTML (`<button>`, `<table>`, etc.)
- Ensure color contrast meets WCAG AA thresholds for text.

Refer to `STYLE_GUIDE.md` for additional color palettes and component samples.

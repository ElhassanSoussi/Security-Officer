# Enterprise UI Style Guide

See also `frontend/DESIGN_SYSTEM.md` for a more comprehensive set of rules and patterns.

This file documents the design tokens and key UI components for the enterprise theme used in the frontend.

## Tokens

Root CSS variables, HSL triples:

- --background: 210 20% 98%  — Very light gray background
- --foreground: 220 10% 8%  — Near-black slate text
- --card: 0 0% 100%  — Card surface (white)
- --card-foreground: 220 12% 10%  — Card text
- --primary: 230 60% 22%  — Deep navy / indigo (brand primary)
- --primary-foreground: 210 40% 98%  — White-ish text for primary buttons
- --secondary: 220 12% 93%  — Slate-neutral surface
- --secondary-foreground: 222.2 10% 12%  — Slate text for secondary surfaces
- --border: 215 12% 91%  — Subtle border color
- --ring: 230 72% 56%  — Focus ring (accessible indigo)
- --success / --warning / --error — semantic tokens for statuses

## Components

- PageHeader: use for top-level page title, subtitle and action slot.
- SectionCard: consistent card wrapper for sections, uses Card component.
- Buttons: use Button variants (default, secondary, destructive, ghost, link) for consistent CTAs.
- Badges: use badge variants for statuses; prefer 'success'/'warning'/'error' where applicable.

## Accessibility

- Focus ring uses --ring to provide consistent accessible focus states.
- Contrast values were chosen for WCAG AA where possible; verify with real content.

## Usage

- Tailwind classes reference color tokens defined in `app/globals.css` and `tailwind.config.ts`.
- Avoid inline styles; prefer Tailwind utility classes. For dynamic widths in progress indicators use discrete classes (w-1/4, w-1/2, w-3/4, w-full).

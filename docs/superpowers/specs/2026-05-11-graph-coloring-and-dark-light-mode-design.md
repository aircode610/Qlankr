# Graph Label Coloring Fix + Dark/Light Mode Toggle

**Date:** 2026-05-11  
**Status:** Approved

---

## Overview

Two tasks:
1. Fix graph nodes to always be colored by their label type (not overridden by community index).
2. Add a session-only dark/light mode toggle with a well-designed light mode.

---

## Task 1: Graph Label Coloring Fix

### Problem

In `frontend/src/lib/graph-adapter.ts`, the `addNodeWithPosition` function applies community-based colors to symbol nodes (`Function`, `Class`, `Method`, `Interface`) when they have a community membership. This overrides the label-based `NODE_COLORS` palette, causing the graph to show inconsistent colors that don't match the filter panel legend.

### Fix

Remove the community color override. All nodes always use `NODE_COLORS[node.label]` for their `color` attribute.

- `community` and `communityColor` node attributes are retained (used for spatial clustering in ForceAtlas2 positioning).
- Only the `color` attribute changes: it always comes from `NODE_COLORS[node.label] || '#9ca3af'`.
- `structuralNodes` already use `NODE_COLORS` and require no change.

**Files changed:** `frontend/src/lib/graph-adapter.ts`

---

## Task 2: Dark/Light Mode Toggle

### Architecture

**CSS-variable override + Sigma settings update + theme refs.** No Sigma reinitialization (no layout reset on toggle). Session-only (no localStorage).

### 2.1 CSS (`frontend/src/index.css`)

Dark mode is the default (existing `@theme` block unchanged). A new `:root.light` block overrides every theme variable:

| Token | Dark | Light |
|---|---|---|
| `--color-void` | `#06060a` | `#f0f2f5` |
| `--color-deep` | `#0a0a10` | `#e8eaef` |
| `--color-surface` | `#101018` | `#ffffff` |
| `--color-elevated` | `#16161f` | `#f8f9fc` |
| `--color-hover` | `#1c1c28` | `#eceef3` |
| `--color-border-subtle` | `#1e1e2a` | `#dde1e9` |
| `--color-border-default` | `#2a2a3a` | `#c8cdd8` |
| `--color-text-primary` | `#e4e4ed` | `#0f1117` |
| `--color-text-secondary` | `#8888a0` | `#4a5068` |
| `--color-text-muted` | `#5a5a70` | `#8890a8` |
| `--color-accent` | `#7c3aed` | `#7c3aed` (unchanged) |
| `--color-accent-dim` | `#5b21b6` | `#5b21b6` (unchanged) |

Body background and text color are also overridden in `.light`.

### 2.2 `useTheme` hook (`frontend/src/hooks/useTheme.ts`)

New file. Module-level singleton pattern (no React context needed for session-only state):

- Exports `useTheme(): { theme: 'dark' | 'light', toggleTheme: () => void }`
- `toggleTheme` adds/removes the `light` class on `document.documentElement`
- Uses a shared `useState` subscriber list (via a tiny custom event on `window`) so multiple components stay in sync

### 2.3 Sigma theme integration (`frontend/src/hooks/useSigma.ts`)

`useSigma` accepts a new optional `theme?: 'dark' | 'light'` parameter.

A `themeRef` is kept in sync via `useEffect` on `theme`. Three hardcoded dark values become dynamic:

1. **Label color** — `useEffect` on theme calls `sigma.setSetting('labelColor', { color: theme === 'light' ? '#0f1117' : '#e4e4ed' })`.

2. **Hover tooltip** (`defaultDrawNodeHover`) — reads `themeRef.current` at draw time:
   - Background fill: dark=`#12121c`, light=`#ffffff`
   - Text fill: dark=`#f5f5f7`, light=`#0f1117`
   - Border: uses `data.color` (unchanged)

3. **`dimColor` helper** — `getBgRgb()` reads `themeRef.current` and returns:
   - Dark: `{ r: 18, g: 18, b: 28 }`
   - Light: `{ r: 248, g: 249, b: 252 }` (matches `--color-elevated` light value)

### 2.4 `GraphCanvas` (`frontend/src/components/GraphCanvas.tsx`)

- Calls `useTheme()`, passes `theme` to `useSigma`.
- The hardcoded `radial-gradient / linear-gradient` background `<div>` becomes theme-conditional:
  - Dark: existing gradient (`#06060a → #0a0a10` with purple radial)
  - Light: `radial-gradient(circle at 50% 50%, rgba(124, 58, 237, 0.05) 0%, transparent 70%), linear-gradient(to bottom, #f0f2f5, #e8eaef)`

### 2.5 Toggle button (`frontend/src/components/Navbar.tsx`)

- Imports `useTheme`, `Sun`, `Moon` from lucide-icons.
- Adds an icon button on the right side of the navbar.
- Dark mode shows `Sun` icon (click → switch to light); light mode shows `Moon` icon (click → switch to dark).
- Uses existing navbar button styles (`border-border-subtle bg-elevated text-text-secondary hover:bg-hover`) — these automatically update via CSS variable overrides.

---

## Files Changed

| File | Change |
|---|---|
| `frontend/src/lib/graph-adapter.ts` | Remove community color override |
| `frontend/src/index.css` | Add `:root.light` variable overrides |
| `frontend/src/hooks/useTheme.ts` | New hook |
| `frontend/src/hooks/useSigma.ts` | Add `theme` param, `themeRef`, dynamic label/hover/dim |
| `frontend/src/components/GraphCanvas.tsx` | Pass `theme` to `useSigma`, conditional gradient |
| `frontend/src/components/Navbar.tsx` | Add toggle button |

---

## Non-Goals

- No persistence (localStorage) — session-only.
- No system preference detection (`prefers-color-scheme`) — manual toggle only.
- No changes to other pages (login, signup, history) — out of scope.

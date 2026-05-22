# DESIGN.md UI Unification Design

Date: 2026-05-22
Status: Approved for implementation planning

## Goal

Unify the entire `apps/web` UI around the visual language defined in the root
`DESIGN.md` while preserving AeroSpec Agent as a dense aircraft design
workbench. The result should feel coherent across the main workspace, Compare,
Settings, Deep Design, runtime feedback, and empty or error states.

## Scope

This design covers all frontend UI surfaces in `apps/web`:

- Workspace shell: top bar, split layout, CAD workspace, right-panel tabs,
  resize handles, and bottom results panel.
- Chat workflow: messages, composer, tool cards, diagnostics, agent run
  actions, run details, fallback notices, and workflow timelines.
- Design controls: parameter editor, sliders, source badges, version history,
  design rules, performance estimates, and VSPAERO result surfaces.
- Deep Design and graph UI: exploration panel, execution timeline,
  recommendation card, variant summaries, and thumbnails.
- Compare workflow: drawer, item cards, metric table, metric cells, export and
  clear actions, and current-version actions.
- Settings, metrics, and CAD viewer states: settings dropdown and forms, LLM
  test states, design metric cards, preview status, loading overlays, and empty
  viewer states.

Business workflows, API contracts, CAD generation behavior, and data flow are
out of scope except for minimal markup changes needed to remove style
divergence.

## Current State

The frontend already centralizes a large share of presentation in
`apps/web/src/app/globals.css`, but the active UI language differs from
`DESIGN.md`:

- Current tokens use an Outfit-based blue-cyan theme rather than the dark,
  near-achromatic Linear-inspired theme.
- The global `button` rule makes brand-primary styling the default, which
  forces secondary actions to override it locally.
- Several components rely on inline styles or hard-coded fallbacks, especially
  settings, metrics, Compare affordances, and small status surfaces.
- Similar semantic elements such as cards, status labels, toolbar actions, and
  empty/error states do not consistently share interaction states.

Recent frontend work has already started replacing isolated hard-coded Compare
colors with CSS variables. This effort should complete the unification at the
system level instead of continuing piecemeal overrides.

## Design Direction

`DESIGN.md` is the visual source of truth. The implementation should translate
it into workbench-appropriate tokens and reusable CSS semantics:

- Backgrounds use layered dark surfaces rooted in near-black page chrome.
- Borders stay low contrast and translucent unless stronger separation is
  required for function or accessibility.
- Text hierarchy uses neutral luminance steps rather than broad color variety.
- Brand indigo-violet is reserved for primary actions, active states, focus,
  links, and key runtime emphasis.
- Success, warning, and error colors stay semantic and do not become decorative
  palette accents.
- The CAD preview remains the dominant visual region; the shell should support
  focused repeated work rather than resemble a marketing page.

Typography should move from Outfit to the Inter family specified by
`DESIGN.md`, with the documented OpenType features enabled where supported.
Workbench headings should remain compact. Display-scale marketing typography
from `DESIGN.md` is not required inside dense panels.

## Styling Architecture

`globals.css` remains the styling center for this single-page frontend, but its
responsibilities should be clearer:

1. Design tokens for backgrounds, text, brand color, semantic states, borders,
   radii, shadows, spacing anchors, and font stacks.
2. Reset and base controls for body text, focus visibility, form fields,
   scrollbars, and disabled behavior.
3. Shared UI semantics for primary buttons, ghost actions, toolbar buttons,
   inputs, panels, cards, pills, badges, tables, overlays, empty states, and
   status feedback.
4. Workspace layout rules and component-specific styling for existing feature
   areas.
5. Responsive behavior and overflow controls for desktop and narrow viewport
   checks.

The implementation may change component markup where needed to replace inline
styles with semantic class names or to align repeated UI states. It should not
introduce a new UI framework, CSS runtime, or speculative component abstraction.

## Component Semantics

The unified UI should use a small set of repeated visual roles:

- Primary button: indigo-violet action reserved for the main next action.
- Ghost or subtle button: dark neutral actions for panels, secondary commands,
  drawer controls, and quiet toolbar affordances.
- Toolbar action: compact controls for dense operator surfaces.
- Panel and card: translucent dark surfaces with shared border, radius, and
  elevation rules.
- Input and textarea: dark input surfaces with clear focus rings and consistent
  placeholder treatment.
- Badge and pill: neutral labels separated from semantic status indicators.
- Runtime state: common running, success, warning, error, disabled, loading,
  and empty treatments across chat, graph, Compare, and CAD feedback.

Hover, active, focus-visible, and disabled behavior must be present for each
interactive role. The same role should not change visual meaning across feature
areas.

## Implementation Strategy

The preferred implementation path is system-first:

1. Replace the active token layer and base control behavior with
   `DESIGN.md`-aligned workbench tokens.
2. Audit inline styles, hard-coded colors, fallback colors, and duplicate
   interaction rules across frontend components.
3. Convert repeated local styling to semantic classes and align component state
   styling area by area.
4. Re-check layout hierarchy and overflow behavior after visual primitives are
   unified.

This path is preferred over a visual-only token swap because the current UI
contains enough local style divergence that a palette replacement alone would
leave inconsistent buttons, surfaces, and status feedback.

## Error Handling And Accessibility

UI unification must not hide error or progress information:

- Running, failed, warning, selected, disabled, and defaulted-data states need
  distinct text and surface signals.
- Focus-visible treatment must remain observable on keyboard-reachable
  controls.
- Text should retain sufficient contrast against the dark surface hierarchy.
- Narrow panels, tables, status strings, and button labels must avoid
  incoherent overlap or clipping.

## Verification

Verification should cover three layers:

1. Static frontend validation with the existing frontend tests and production
   build.
2. Browser review of critical desktop and narrow-viewport states after starting
   the Next.js dev server.
3. Regression checks for high-risk feature surfaces: Compare drawer and table,
   Settings form controls, Deep Design graph states, CAD loading feedback, chat
   runtime cards, and parameter/version panels.

Visual review should specifically check hierarchy, overflow, focus visibility,
empty states, status readability, and whether accent color remains intentional
instead of dominating the workbench.

## Non-Goals

- Replacing the existing workspace layout model or moving business state between
  panels.
- Adding a general-purpose component library before this frontend needs one.
- Reproducing Linear marketing layouts, oversized hero typography, or decorative
  visuals inside the workbench.
- Refactoring unrelated backend, CAD, graph, or API code during UI cleanup.


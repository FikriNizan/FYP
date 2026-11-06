---
name: TxB Retention Studio
description: A precise work-centred workspace for evidence-led committee decisions and RM follow-up.
colors:
  ink: "#182b47"
  muted: "#53647c"
  accent: "#285ed1"
  accent-dark: "#1947a6"
  nav: "#132742"
  nav-text: "#d9e5f7"
  canvas: "#f1f5fb"
  surface: "#fff"
  line: "#dce4f0"
  warning: "#80550d"
  danger: "#a32846"
typography:
  headline:
    fontFamily: "'Segoe UI', Arial, sans-serif"
    fontSize: "28px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.65px"
  title:
    fontFamily: "'Segoe UI', Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.15px"
  body:
    fontFamily: "'Segoe UI', Arial, sans-serif"
    fontSize: "14px"
    lineHeight: 1.55
  label:
    fontFamily: "'Segoe UI', Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
  technical:
    fontFamily: "ui-monospace, monospace"
    fontSize: "12px"
    lineHeight: 1.7
rounded:
  panel: "10px"
  control: "7px"
  field: "6px"
  badge: "5px"
spacing:
  compact: "8px"
  related: "12px"
  mobile-gutter: "16px"
  panel: "22px"
  desktop-gutter: "30px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  button-primary-hover:
    backgroundColor: "{colors.accent-dark}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#263e60"
    rounded: "{rounded.control}"
    padding: "9px 14px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "9px 11px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "22px"
  badge:
    backgroundColor: "#edf1f8"
    textColor: "#465b78"
    rounded: "{rounded.badge}"
    padding: "4px 8px"
  navigation:
    textColor: "{colors.nav-text}"
    rounded: "{rounded.control}"
    padding: "13px 11px"
---

# Design System: TxB Retention Studio

## Overview

**Creative North Star: "Corporate financial schedules"**

Precise navy navigation, cobalt actions and cool white work surfaces give the workspace the character of a readable financial schedule. Operate mode favours familiar controls, aligned evidence and a deliberate Segoe UI workhorse face. The system supports committee review and later RM work without suggesting a production banking service.

Information density comes from structured rows, compact labels and tabular numbers. White panels group work; restrained colour identifies selection and explicit state. Small authored SVG icons support navigation. No raster assets are shipped.

**Key Characteristics:**
- Navy wayfinding and cobalt interaction.
- Tabular values and aligned comparison rows.
- Restrained panels with visible boundaries.
- Explicit textual state and draft recovery.

Source authority is the imported `frontend/src/workspace.css`, sampled against App, Signals, ReviewForm and CaseDetail. `styles.css` and `architect.css` are unimported archives. PRODUCT.md owns product truth; the surface brief owns page composition.

## Colors

The palette combines cool financial-document neutrals with cobalt interaction and restrained semantic state.

### Primary
- **Cobalt action:** primary buttons, links, progress and selected work.
- **Deep cobalt:** primary-button hover.

### Secondary
- **Amber warning:** planned, deferred, overdue and preview states.
- **Rose risk:** risk values and flagged evidence; error notices use related rose treatments.

### Neutral
- **Navy rail / pale navigation text:** persistent workspace wayfinding.
- **Ink / muted ink:** content hierarchy and explanatory text.
- **Cool canvas / white surface / pale divider:** workspace, grouped work and row boundaries.

Green completion and purple attempted-state treatments are local semantic variants, recorded in the sidecar rather than promoted into general accents.

### Named Rules
**The Explicit State Rule.** Pair semantic colour with a readable state label; colour alone does not carry case or follow-up meaning.

## Typography

**Body and heading font:** Segoe UI with Arial and sans-serif fallbacks. This deliberate Operate choice applies to headings as well as controls; there is no separate display face.

**Technical font:** UI monospace for technical explanations and source identifiers.

### Hierarchy
- **Headline:** page titles; reduced to 25px at the mobile breakpoint.
- **Title:** panel headings; smaller headings use 14px with the same 650 weight.
- **Body:** evidence, prose and table values; tabular numerals are enabled globally.
- **Label:** forms and controls; supporting metadata commonly uses 12px.
- **Numbers:** prominent metrics use 32px with 650 weight and a 1.3 line height; actual contexts adapt this between 27px and 35px.

## Layout

The desktop shell uses a sticky 216px rail and a flexible work area. Main content has a 1540px maximum width and desktop gutters from the token scale. Panels and major two-column work areas share the panel spacing step. Review and case layouts pair flexible evidence with 320px and 340px editors respectively.

At 1250px, filters simplify and scenarios stack. At 1050px, the rail narrows to 185px and editors become normal-flow blocks. At 760px, navigation becomes horizontal, panels tighten to 18px, main gutters become the mobile step, forms enlarge to 16px and standard buttons/selects have 44px minimum height. Case editors precede activity. Signals stack their value below the label; wide tables retain local horizontal scrolling. At 380px, navigation labels stack below icons and remaining paired case metrics collapse.

Guide definition pairs use a bounded term column and a flexible description, then stack on mobile. Printed briefings use A4 with 16mm margins, full-width containment and 11px body text; navigation and controls disappear. Browser print is the established export path.

## Elevation & Depth

Borders and tonal separation do most of the work. White panels and metric groups share a faint ambient shadow. Selected filters use a smaller shadow; active navigation and the mobile help menu have context-specific lift. These are soft shadows, not hard offset decoration.

### Shadow Vocabulary
- **Panel:** `0 3px 12px rgb(22 42 76 / 4%)`.
- **Selected filter:** `0 2px 5px rgb(28 57 111 / 6%)`.
- **Active navigation:** `0 3px 8px rgb(4 18 43 / 15%)`.
- **Mobile help menu:** `0 8px 20px rgb(9 25 48 / 22%)`.

## Shapes

Panels use the largest recurring radius; controls and fields use smaller, precise corners. Badges are compact rounded rectangles rather than pills. Thin borders define surfaces, fields, table rows and comparison boundaries. Circles identify timeline events and numbered workflow steps.

## Components

### Buttons
Compact, explicit actions. Primary buttons use cobalt and white; secondary buttons use white, a cool border and dark text. Shared minimum height is 40px on desktop. Hover and active states change fill; primary hover deepens cobalt. Disabled controls lower opacity. Background and border transitions take 150ms with ease-out.

### Chips
Text-bearing status badges use compact padding and the badge radius. Open is blue; planned/deferred is amber; completed/closed is green; attempted is purple; cancelled is grey. Flagged is rose. These are status labels, not action buttons.

### Cards / Containers
White panels use a pale border, shared panel radius, ambient shadow and panel padding. Original assessment context uses a subtle blue-white tint alongside the current white context. Nested evidence inside case disclosures drops the extra panel border and shadow.

### Inputs / Fields
White fields use a cool stroke, field radius and visible labels. Textareas resize vertically. All keyboard-focused interactive controls receive a 3px blue outline with 3px offset. Error and success notices are separately labelled tinted regions; unsaved drafts use amber text and hints.

### Navigation
Navy links pair text with consistent authored outline SVGs (20px, 1.7 stroke). Hover lightens the rail surface; selected navigation uses a brighter blue fill and white text. Primary navigation stays visible on narrow screens; help and previews become a disclosure menu.

### Evidence rows and action editors
Signal rows align explanation and value on desktop, then stack on mobile. Original/latest assessment cards remain explicitly dated and distinct. Follow-up and case-management tabs use selected fills and semantic tab state; each editor exposes its own unsaved-state and discard controls. Their behaviour preserves separate drafts rather than encoding draft state only through appearance.

## Do's and Don'ts

### Do:
- **Do** pair colour with explicit state text.
- **Do** align numeric evidence with tabular numerals and keep identifiers readable through wrapping.
- **Do** preserve visible keyboard focus and labelled controls.
- **Do** use the active stylesheet as the visual source of truth.

### Don't:
- **Don't** substitute glyph characters for the authored navigation SVGs.
- **Don't** present preview or unavailable integrations as connected saved-data work.
- **Don't** merge original and latest evidence into an undated visual summary.

Recorded from source, not a claim of audited accessibility compliance. No independent dark theme, motion choreography or additional display type system is established.

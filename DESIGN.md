***

name: TxB Retention Studio
description: A precise work-centred workspace for evidence-led committee decisions and RM follow-up.
colors:
ink: "#343a40"
muted: "#5f6a75"
accent: "#3f6ad8"
accent-dark: "#3057bc"
nav: "#132742"
nav-text: "#d9e5f7"
canvas: "#f1f4f6"
surface: "#fff"
line: "#e5e9ef"
warning: "#80550d"
danger: "#c11f46"
crimson: "#d92550"
cyan: "#087e9f"
tile-navy: "#3c4a7d"
typography:
headline:
fontFamily: "'Open Sans Variable','Open Sans','Segoe UI',Arial,sans-serif"
fontSize: "28px"
fontWeight: 600
lineHeight: 1.3
letterSpacing: "-.6px"
title:
fontFamily: "'Open Sans Variable','Open Sans','Segoe UI',Arial,sans-serif"
fontSize: "14px"
fontWeight: 700
lineHeight: 1.3
letterSpacing: ".03em"
\# Panel titles are uppercase; briefing/context/prediction headings retain their own hierarchy.
body:
fontFamily: "'Open Sans Variable','Open Sans','Segoe UI',Arial,sans-serif"
fontSize: "14px"
lineHeight: 1.55
label:
fontFamily: "'Open Sans Variable','Open Sans','Segoe UI',Arial,sans-serif"
fontSize: "13px"
fontWeight: 600
technical:
fontFamily: "ui-monospace, monospace"
fontSize: "12px"
lineHeight: 1.7
rounded:
panel: "6px"
control: "5px"
field: "5px"
badge: "4px"
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
textColor: "{colors.ink}"
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
textColor: "#d4e0f4"
rounded: "6px"
padding: "13px 11px"
kpi-tile:
textColor: "{colors.surface}"
rounded: "{rounded.panel}"
padding: "21px 24px"
finance-card:
backgroundColor: "{colors.surface}"
textColor: "{colors.ink}"
rounded: "{rounded.panel}"
padding: "18px 20px 16px"
split-bar:
height: "16px"
rounded: "8px"
--------------

# Design System: TxB Retention Studio

## Overview

**Creative North Star: "Architect-influenced corporate financial schedule"**

Precise navy navigation, cobalt actions and cool white work surfaces give the workspace the character of a readable financial schedule. The navy rail and white header stay; cobalt interaction, gradient KPI tiles and self-hosted Open Sans establish the Architect theme. Operate mode favours familiar controls and aligned evidence. The system supports committee review and later RM work without suggesting a production banking service.

Information density comes from structured rows, compact labels and tabular numbers. White panels group work; restrained colour identifies selection and explicit state. Small authored SVG icons support navigation. No raster assets are shipped.

**Key Characteristics:**

* Navy wayfinding and cobalt interaction.
* Tabular values and aligned comparison rows.
* Restrained panels with visible boundaries.
* Explicit textual state and draft recovery.

Source authority is `frontend/src/workspace.css` followed by `frontend/src/workspace-architect.css`, in that import order. Every theme rule is screen-only. `styles.css` and `architect.css` remain unimported archives; `architect.css` is a different file from the active `workspace-architect.css`. PRODUCT.md owns product truth; the surface brief owns page composition.

## Colors

The palette combines cool financial-document neutrals with cobalt interaction and explicit semantic state. KPI tile semantics are navy for neutral assessed totals, rose for flagged customers and cyan for customers awaiting review. Green is reserved for completion/positive connected state, never pending counts. Crimson is limited to attrition-reference marks and the rose tile; danger text uses its separate darker token.

### Primary

* **Cobalt action:** primary buttons, links, progress and selected work.
* **Deep cobalt:** primary-button hover.

### Secondary

* **Amber warning:** planned, deferred, overdue and preview states.
* **Rose risk:** risk values and flagged evidence; error notices use related rose treatments.

### Neutral

* **Navy rail / pale navigation text:** persistent workspace wayfinding.
* **Ink / muted ink:** content hierarchy and explanatory text.
* **Cool canvas / white surface / pale divider:** workspace, grouped work and row boundaries.

Green completion and purple attempted-state treatments are local semantic variants, recorded in the sidecar rather than promoted into general accents.

### Named Rules

**The Explicit State Rule.** Pair semantic colour with a readable state label; colour alone does not carry case or follow-up meaning.

## Typography

**Body and heading font:** Open Sans Variable, Open Sans, Segoe UI, Arial and sans-serif fallbacks, self-hosted through `@fontsource-variable/open-sans`. Chart SVG text uses the same stack. No remote fonts are loaded. RM briefing print uses the same Open Sans stack; other print surfaces retain the existing Segoe UI/Arial stack.

**Technical font:** UI monospace for technical explanations and source identifiers.

### Hierarchy

* **Headline:** page titles; reduced to 25px at the mobile breakpoint.
* **Title:** panel titles use 14px/700, .03em tracking and uppercase. Briefing, assessment-context and prediction headings retain their own hierarchy and case.
* **Body:** evidence, prose and table values; tabular numerals are enabled globally.
* **Label:** forms and controls; supporting metadata commonly uses 12px.
* **Numbers:** prominent metrics use 32px with 650 weight and a 1.3 line height; actual contexts adapt this between 27px and 35px.

## Layout

The desktop shell uses a sticky 216px rail and a flexible work area. Main content has a 1540px maximum width and desktop gutters from the token scale. Panels and major two-column work areas share the panel spacing step. Review and case layouts pair flexible evidence with 320px and 340px editors respectively.

At 1250px, filters simplify and scenarios stack. At 1050px, the rail narrows to 185px and editors become normal-flow blocks. At 760px, navigation becomes horizontal, panels tighten to 18px, main gutters become the mobile step, forms enlarge to 16px and standard buttons/selects have 44px minimum height. Case editors precede activity. Signals stack their value below the label; wide tables retain local horizontal scrolling. At 380px, navigation labels stack below icons and remaining paired case metrics collapse.

Perspective views use the evidence column as an inline-size container. Service metrics have four columns at 620px and above, two below, and one at 340px or less. Activity rows put labels above the tracks below 560px. Finance cards have two columns at 520px and above, one below. Overview finance cards have four columns, two at viewport widths up to 1250px, one up to 760px.

Guide definition pairs use a bounded term column and a flexible description, then stack on mobile. Printed briefings use A4 with 16mm margins, full-width containment and the briefing-specific print type sizes below; navigation and controls disappear. Browser print is the established export path.

## Elevation & Depth

Borders and tonal separation do most of the work. White panels and metric groups share a faint ambient shadow. Selected filters use a smaller shadow; active navigation and the mobile help menu have context-specific lift. These are soft shadows, not hard offset decoration.

### Shadow Vocabulary

* **Panel:** `0 5px 24px #04091408,0 2px 5px #04091409`.
* **Selected filter:** `0 2px 5px rgb(28 57 111 / 6%)`.
* **Active navigation:** `0 4px 12px rgb(63 106 216 / 38%)`.
* **Mobile help menu:** `0 8px 20px rgb(9 25 48 / 22%)`.

## Shapes

Panels use the largest recurring radius; controls and fields use smaller, precise corners. Badges are compact rounded rectangles rather than pills. Thin borders define surfaces, fields, table rows and comparison boundaries. Circles identify timeline events and numbered workflow steps.

## Components

### Buttons

Compact, explicit actions. Primary buttons use cobalt and white; secondary buttons use white, a cool border and graphite text, with a pale-blue hover fill. Shared minimum height is 40px on desktop. Hover and active states change fill; primary hover deepens cobalt. Disabled controls lower opacity. Background and border transitions take 150ms with ease-out.

### Chips

Text-bearing status badges use compact padding and the badge radius. Open is blue; planned/deferred is amber; completed/closed is green; attempted is purple; cancelled is grey. Flagged is rose. These are status labels, not action buttons.

### Cards / Containers

White panels use a pale border, shared panel radius, ambient shadow and panel padding. Original assessment context uses a navy gradient with white text alongside the current white context; both stay dated and distinct. Nested evidence inside case disclosures drops the extra panel border and shadow.

### Inputs / Fields

White fields use a cool stroke, field radius and visible labels. Textareas resize vertically. All keyboard-focused interactive controls receive a 3px blue outline with 3px offset (screen colour #316cdd). Error and success notices are separately labelled tinted regions; unsaved drafts use amber text and hints.

### Navigation

Navy links pair text with consistent authored outline SVGs (20px, 1.7 stroke). Hover lightens the rail surface; selected navigation uses a brighter blue fill and white text. Primary navigation stays visible on narrow screens; help and previews become a disclosure menu.

### Evidence rows and action editors

Signal rows align explanation and value on desktop, then stack on mobile. Original/latest assessment cards remain explicitly dated and distinct. Follow-up and case-management tabs use selected fills and semantic tab state; each editor exposes its own unsaved-state and discard controls. Their behaviour preserves separate drafts rather than encoding draft state only through appearance.

### KPI gradient tiles

Three separate tiles use navy, rose and cyan gradients with white labels and numbers, 20px gaps, a faint decorative ring and the panel shadow. Awaiting review is cyan, not completion green.

### Finance cards and balance split

Shared cards use white surfaces, a 3px coloured top border, 36px icon circles and 24px/650 MYR values. Exposure uses cobalt; Historical estimate uses teal. Overview coverage bars are 5px with adjacent record counts. Missing values stay missing, genuine zeros stay zero. Perspective missing cards use dashed borders without shadows and an explicit missing caption. A 16px two-segment balance split appears only when both balances are numeric, non-negative and their sum is positive. Its legend and accessible label show complementary one-decimal shares. Fee/waiver bars compare only the two historical estimates when both exist and the larger is positive.

### Observed flow and reference lines

The chart uses a 780×280 viewBox with a plot from x=75 to 640 and direct two-line labels in the right gutter. Combined flow with a positive trailing twelve-month average alone gets the dotted navy average and dashed crimson half-average reference. The scale includes the average. The attrition reference is a level for the next three unobserved months, never an observed outcome. Pointer/touch tooltips show exact amounts and relative change from the average; keyboard users retain the exact-value disclosure table. Transparent path hit areas add no bar rectangles.

### Operations comparison and service strip

Activity uses two rows, each with a label, track and adjacent MYR value. Widths clamp for display only; the half-average dashed marker requires a positive average. Service rates use a neutral-blue 0–100% scale without inferred red/green verdicts or monthly trends. Missing rates have empty tracks. All decorative bars are hidden from assistive technology and values remain text.

### Interpretation callouts

Blue-tinted callouts pair an authored information icon with text. Operations preserves causal uncertainty; Finance separates exposure from historical estimates, profit, invoices and retention savings.

### RM briefing sheet

The sheet uses a header, four-cell At-a-glance strip and risk definition, original/latest context, activity, labelled model signals, Operations/Finance, current rationale/next step, recorded follow-ups when present, questions and an identifiers appendix. It shares the ink, muted, nav, line, canvas and warning tokens with the dashboard. Screen, browser print and PDF retain one structure, complete source IDs and explicit missing/zero states; interactive AI previews and controls stay out of documents. Local responsive rules stack the glance strip and context blocks on narrow screens.

Browser print sizes mirror the PDF: body 8.5pt, title 18pt and section headings 10.5pt, with smaller labelled metadata. The PDF embeds bundled static Open Sans 400/700; browser print uses the local Open Sans font stack. Browser print keeps the browser's own header/footer, while the direct PDF has a TxB internal-use footer with page numbers. Both are acceptable export presentations.

## Do's and Don'ts

### Do:

* **Do** pair colour with explicit state text.

* **Do** align numeric evidence with tabular numerals and keep identifiers readable through wrapping.

* **Do** preserve visible keyboard focus and labelled controls.

* **Do** use the active stylesheet as the visual source of truth.

* **Do** draw reference lines only for combined flow with a positive twelve-month average.

* **Do** show the attrition reference as a reference level, not an outcome.

### Don't:

* **Don't** substitute glyph characters for the authored navigation SVGs.

* **Don't** present preview or unavailable integrations as connected saved-data work.

* **Don't** merge original and latest evidence into an undated visual summary.

* **Don't** colour service rates red/green without a benchmark.

* **Don't** use green for pending counts.

* **Don't** render a balance split when either balance is missing.

* **Don't** add remote fonts.

Recorded from source, not a claim of audited accessibility compliance. No independent dark theme, motion choreography or additional display type system is established.

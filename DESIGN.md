---
name: ECDAT Operator Console
description: A calm, evidence-first interface for cryptographic discovery and migration assurance.
colors:
  verified-emerald: "#087f5b"
  navigation-ink: "#12231f"
  page-slate: "#f3f6f8"
  evidence-white: "#ffffff"
  secondary-slate: "#4a5b66"
  rule-slate: "#d7e0e4"
  medium-amber: "#9a5b00"
  critical-red: "#bd2d32"
typography:
  headline:
    fontFamily: "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.018em"
  body:
    fontFamily: "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "0.04em"
rounded:
  sm: "7px"
  md: "10px"
  lg: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.verified-emerald}"
    textColor: "{colors.evidence-white}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
    height: "40px"
  input:
    backgroundColor: "{colors.page-slate}"
    textColor: "{colors.navigation-ink}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  panel:
    backgroundColor: "{colors.evidence-white}"
    textColor: "{colors.navigation-ink}"
    rounded: "{rounded.lg}"
    padding: "22px"
---

# Design System: ECDAT Operator Console

## Overview

**Creative North Star: "The Assurance Ledger"**

ECDAT is an operational evidence surface, not a theatrical security dashboard. It uses the composure of a reviewed ledger: compact headings, visible measurement provenance, predictable controls, and enough density to compare findings without losing context.

The dark navigation rail anchors the application while cool, quiet work surfaces keep long sessions readable. Emerald means verified or actionable—not decoration. Amber and red are reserved for risk semantics.

**Key Characteristics:**

- Evidence-first hierarchy with scan status always close at hand.
- Restrained flat surfaces with light structural borders.
- One sans-serif family; monospace only for paths, identifiers, and raw evidence.
- Risk is always encoded with a label or count as well as color.
- Desktop density reflows into a single task column on narrow screens.

## Colors

The palette combines cool neutral work surfaces with a dark green-black anchor and sparse semantic accents.

### Primary

- **Verified Emerald:** Primary actions, completed states, coverage, and trustworthy evidence signals.

### Secondary

- **Medium Amber:** Medium risk and review-needed states.
- **Critical Red:** Critical risk, destructive actions, and blocking errors.

### Neutral

- **Navigation Ink:** Persistent application navigation and high-contrast headings.
- **Page Slate:** The continuous workspace behind evidence surfaces.
- **Evidence White:** Tables, panels, forms, and record surfaces.
- **Secondary Slate:** Explanatory text and metadata.
- **Rule Slate:** Borders, dividers, and inactive control boundaries.

**The Sparse Accent Rule.** Emerald marks action, selection, or verified state; it is never ambient decoration.

## Typography

**Display Font:** Inter with the platform sans-serif fallback stack  
**Body Font:** Inter with the platform sans-serif fallback stack  
**Label/Mono Font:** The system monospace stack for code and machine identifiers only

**Character:** Compact, neutral, and technical without becoming terminal-themed. Weight and spacing establish hierarchy instead of a second display face.

### Hierarchy

- **Headline** (700, 2rem, 1.12): Route titles and primary empty-state messages.
- **Title** (650, 1.12rem, 1.3): Panel headings and workflow sections.
- **Body** (400, 0.875rem, 1.5): Explanations and evidence descriptions, normally capped near 72 characters.
- **Label** (650, 0.75rem, 0.04em, uppercase where appropriate): Field labels, table headings, and compact measurement names.

**The Evidence Type Rule.** Paths and identifiers may use monospace; algorithms, actions, headings, and risk labels stay in the interface sans.

## Layout

The workspace uses a wide fluid container capped at 1440px with 24–32px desktop gutters. Pages begin with a compact route header, then use 16px gaps between evidence bands. Tables and metrics favor horizontal comparison on desktop. At 900px complex grids collapse; at 640px actions and scan controls stack; mobile navigation remains in document flow so it never covers the task.

## Elevation & Depth

The system is flat by default. One-pixel rules separate most surfaces; low ambient shadows identify major interactive or grouped regions, and the scan launch surface alone may use the medium elevation token.

### Shadow Vocabulary

- **Evidence lift** (`0 2px 5px rgba(18, 35, 44, 0.07)`): Major dashboard bands and tables.
- **Workflow lift** (`0 8px 24px rgba(18, 35, 44, 0.09)`): The primary scan-launch surface.

**The Flat-By-Default Rule.** Repeated records use borders; shadow is reserved for page-level grouping and transient overlays.

## Shapes

Controls use gently curved 7–10px corners. Major panels use 14px corners. Pills are reserved for compact status and risk chips. Borders are one pixel and semantic cards never rely on a thick colored edge.

## Components

### Buttons

- **Shape:** Compact rounded rectangle (7–8px radius), at least 40px high on desktop and enlarged in mobile navigation.
- **Primary:** Verified Emerald with white text and 9px/16px padding.
- **Hover / Focus:** Darker or brighter semantic fill with a visible three-pixel translucent emerald focus outline; no layout-shifting transform.
- **Secondary / Ghost:** Evidence White or transparent against a visible Rule Slate boundary.

### Chips

- **Style:** Small, labelled, and semantic; amber for Medium, muted teal for Low/verified, red for Critical.
- **State:** Every chip includes text or a count so hue is never the only signal.

### Cards / Containers

- **Corner Style:** 10px for records and 14px for page-level panels.
- **Background:** Evidence White over Page Slate.
- **Shadow Strategy:** Flat records, ambient lift for major grouped bands.
- **Border:** One-pixel Rule Slate.
- **Internal Padding:** 16–24px depending on density.

### Inputs / Fields

- **Style:** Page Slate fill, one-pixel boundary, 7–9px radius, and readable 14–15px text.
- **Focus:** Emerald boundary with a visible outer focus outline.
- **Error / Disabled:** Inline recovery text; disabled actions lose emphasis while retaining legible labels.

### Navigation

Navigation uses the Navigation Ink surface, muted green-gray inactive labels, solid darker selection, and a bright emerald New scan action. Below 860px it becomes a push-down menu controlled by a labelled hamburger button.

### Assurance Strip

Coverage, confidence, precision, recall, and F1 use compact aligned cells. Missing evaluation is a labelled “Not measured” state that explains the ground-truth requirement instead of drawing an empty gauge.

## Do's and Don'ts

### Do:

- **Do** place repository scanning and current posture within the first task viewport.
- **Do** show only non-zero risk categories in compact summaries while preserving all categories in filters.
- **Do** keep full machine paths in titles or details and show concise source context in repeated rows.
- **Do** state when precision is unavailable and why.

### Don't:

- **Don't** use color alone to communicate risk or scan status.
- **Don't** fabricate precision, safety, or coverage claims from confidence scores.
- **Don't** use gradients, glass effects, neon decoration, or technical-looking monospace outside evidence data.
- **Don't** bring back multi-step confirmation for a safe, read-only scan launch.

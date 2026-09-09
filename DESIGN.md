---
name: MarketBridge
description: A graphite market workstation where price, evidence, and risk lead every decision.
colors:
  workstation-black: "#0b0e11"
  ticker-black: "#080b0e"
  panel-graphite: "#11151b"
  raised-graphite: "#161b22"
  divider-steel: "#242a32"
  divider-soft: "#1c222a"
  primary-text: "#f0f3f6"
  secondary-text: "#8b949e"
  faint-text: "#646d78"
  signal-blue: "#3861fb"
  movement-green: "#16c784"
  movement-red: "#ea3943"
  caution-amber: "#d29922"
  modal-scrim: "rgba(0,0,0,.64)"
  qualified-text: "#75deb5"
  qualified-border: "#235b48"
  insufficient-evidence-text: "#e7b96d"
  insufficient-evidence-border: "#5d4825"
  integration-link: "#8faaff"
  watchlist-saved-text: "#b8c8ff"
  watchlist-saved-border: "#41578b"
  watchlist-saved-surface: "#151d2c"
  range-selected-surface: "#1b2b51"
  range-selected-text: "#a9c1ff"
  chart-label: "#b7c0ca"
  model-active-text: "#8fb5ff"
  model-active-border: "#345083"
  advisory-boundary-icon: "#6fa3ff"
  selected-row-surface: "#12213a"
  paper-banner-surface: "#112750"
  paper-banner-border: "#294373"
  paper-banner-text: "#9fb5d8"
  mobile-nav-active: "#8daaff"
  brand-icon-blue: "#4d78ff"
  selected-avatar-border: "#4b68a8"
  evidence-impact-amber: "#d6a94d"
typography:
  micro-status:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "8px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.05em"
  table-heading:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "9px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.045em"
  headline:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 680
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.04em"
  numeric:
    fontFamily: "Geist Mono, monospace"
    fontSize: "11px"
    fontWeight: 550
    lineHeight: 1.45
    letterSpacing: "normal"
  navigation:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  landing-lead:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  brand:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 680
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  asset-title:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "normal"
  page-title-mobile:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 680
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  quote-dense:
    fontFamily: "Geist Mono, monospace"
    fontSize: "25px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.04em"
  landing-title-mobile:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "38px"
    fontWeight: 680
    lineHeight: 0.98
    letterSpacing: "-0.055em"
  landing-display:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "48px"
    fontWeight: 680
    lineHeight: 0.98
    letterSpacing: "-0.055em"
rounded:
  skeleton: "3px"
  control: "4px"
  compact: "5px"
  search: "6px"
  standard: "7px"
  dialog: "8px"
  pill: "99px"
spacing:
  micro: "4px"
  compact: "8px"
  control: "10px"
  panel: "12px"
  section: "16px"
  workspace: "28px"
components:
  button-primary:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.primary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.compact}"
    padding: "0 13px"
    height: "35px"
  button-secondary:
    backgroundColor: "{colors.panel-graphite}"
    textColor: "{colors.primary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.compact}"
    padding: "0 13px"
    height: "35px"
  input-compact:
    backgroundColor: "{colors.workstation-black}"
    textColor: "{colors.primary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 8px"
    height: "30px"
  panel-standard:
    backgroundColor: "{colors.panel-graphite}"
    textColor: "{colors.primary-text}"
    rounded: "{rounded.standard}"
    padding: "15px 16px"
  status-pill:
    backgroundColor: "{colors.panel-graphite}"
    textColor: "{colors.secondary-text}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 7px"
---

# Design System: MarketBridge

## Overview

**Creative North Star: "The Proof-Carrying Workstation"**

MarketBridge is a sober graphite workstation built for fast financial inspection. Dense quote, chart, evidence, and risk structures sit inside thin seams and compact controls; aligned numerals and restrained state color make the interface feel operational rather than promotional.

The system always lets market state and provenance speak before learned analysis. Blue identifies focus, selection, and deliberate action; green and red are reserved for financial movement; unavailable or advisory boundaries are stated plainly instead of being disguised as finished capability.

**Key Characteristics:**

- Graphite surfaces separated by thin steel borders, not card-wall decoration.
- A dominant chart and quote band supported by an evidence-and-risk rail.
- Compact operator typography with tabular, monospaced financial values.
- Blue for interaction, restrained green/red for movement, amber for caution.
- Explicit delayed, offline, estimated, unavailable, and advisory states.
- Responsive reduction that preserves quote, chart, major risk, and primary actions.

## Colors

The palette is a cool, low-luminance graphite field with one precise interaction blue and narrowly governed semantic signals.

### Primary

- **Signal Blue:** The sole high-attention interaction color for selected tabs, chart reference data, focus treatment, and primary actions.

### Secondary

- **Movement Green:** Positive market movement and live-source indicators only; pair it with a sign, arrow, or label.
- **Movement Red:** Negative market movement only; pair it with a sign, arrow, or label.
- **Caution Amber:** Delayed or connecting data and evidence caution, never a decorative accent.
- **Evidence States:** Qualified and insufficient-evidence text each use a quieter matching border; evidence-impact amber is confined to evidence tables.
- **Selection Blues:** Selected ranges, rows, saved watchlist state, active mobile navigation, model status, advisory boundaries, and the brand mark use role-specific blue surfaces, text, or borders rather than one undifferentiated accent.
- **Paper Boundary:** The advisory banner uses its own deep blue surface, border, and muted text so execution limits remain persistent without reading as a primary action.

### Neutral

- **Workstation Black:** The application canvas and terminal grid foundation.
- **Ticker Black:** The darkest band behind the continuous market strip.
- **Panel Graphite:** Default panel, search, and bounded workspace surface.
- **Raised Graphite:** Dialogs, retry controls, and modestly elevated utility surfaces.
- **Divider Steel:** Primary one-pixel borders between functional regions.
- **Soft Divider:** Row rules and lower-emphasis internal partitions.
- **Primary Text:** Quotes, headings, and active controls.
- **Secondary Text:** Labels, metadata, inactive controls, and explanatory copy.
- **Faint Text:** Tertiary ranks and low-priority states that remain legible.

### Named Rules

**The Signal Economy Rule.** Blue means focus, selection, or action; green and red mean financial direction; amber means operational caution.

**The Evidence Before Accent Rule.** Never use saturated color to make an estimate, unavailable integration, or advisory action appear more authoritative than its evidence.

## Typography

**Display Font:** Geist (with Inter and system UI fallback)
**Body Font:** Geist (with Inter and system UI fallback)
**Label/Mono Font:** Geist Mono (with monospace fallback)

**Character:** Geist keeps the workstation neutral and compact; Geist Mono stabilizes prices, percentages, basis points, timestamps, and other values that must scan vertically. Hierarchy comes from weight, scale, alignment, and density rather than stylistic display type.

### Hierarchy

- **Headline:** Compact page identity (680 weight, 26px, 1.1 line-height) with tight tracking; reduce to 22px on narrow screens.
- **Title:** Panel and pane headers (600 weight, 13px, 1.45 line-height) with restrained negative tracking.
- **Body:** Default interface copy (400 weight, 14px, 1.45 line-height); mobile reduces to 13px.
- **Label:** Metadata, column headings, and compact controls (600 weight, 10px, 0.04em tracking), often uppercase where the value needs an explicit category.
- **Numeric:** Quotes and table values (550 weight, 11px, 1.45 line-height) in Geist Mono with tabular alignment; primary quotes scale to 20–27px.
- **Micro Status:** Paper-mode and compact state labels use 8px; table headings and secondary chart metadata use 9px.
- **Navigation and Brand:** Desktop routes use 12px labels; the wordmark uses 17px, reducing to 15px on mobile.
- **Asset Identity:** Asset titles use 20px; the dense quote uses 25px mono.
- **Landing Display:** The thesis uses 48px with a 15px lead, reducing to 38px on mobile.

### Named Rules

**The Column Scan Rule.** Prices, percentages, confidence, latency, divergence, and risk limits use the mono role and align to a shared edge.

**The Quiet Label Rule.** Small type is for metadata, not ambiguity: keep it high enough contrast and use explicit words for state.

## Layout

The desktop shell is a dense, chart-led workstation capped at 1600px. A 55px command header and 32px ticker frame the content. The asset screen uses a dense quote band, then a primary grid with a fluid chart column and a 310px right rail; the lower analysis region distributes summary, evidence, and risk across three bordered columns. Standard panels use 10–12px gaps and 15–16px internal padding, while general workspaces use 25–28px outer padding.

At 1100px, secondary header metrics disappear, rails narrow, and three-column analysis becomes two columns with risk spanning the next row. At 760px, the shell becomes single-column: quote information remains visible, the chart stays prominent, the quote/evidence/risk rail follows it, analysis stacks, the watchlist is removed from the asset page, and a fixed five-item mobile navigation appears. At 460px, tables convert into compact two-column records and metric grids reduce further rather than forcing unreadable desktop density.

**The First-Viewport Rule.** On desktop, the quote band, dominant chart, and right-side context must be visible before secondary analysis; on mobile, preserve quote, chart, major risk, and primary actions before anything else.

## Elevation & Depth

The system is flat and structurally layered. Depth comes from adjacent graphite tones, one-pixel borders, sticky positioning, and inset selection states; panels do not float by default. The command palette is the sole pronounced elevation because it temporarily interrupts the workstation.

### Shadow Vocabulary

- **Command Interruption:** A deep ambient shadow (`0 20px 70px rgba(0,0,0,.55)`) separates the command dialog from its dimmed backdrop.
- **Focus Inset:** A one-pixel blue inset (`inset 0 0 0 1px #4d70d8`) identifies focus inside the command input without changing layout.

### Named Rules

**The Flat-by-Default Rule.** Use tonal layering and thin borders for persistent structure; reserve a cast shadow for modal interruption.

## Shapes

The form language is compact and precise: 3px for loading skeletons; 4–5px radii for controls, badges, and buttons; 6px for search and avatars; 7px for standard panels; and 8px for dialogs. Fully rounded geometry is reserved for connection pills and tiny status lights. Borders are consistently one pixel. Connected regions share edges and remove interior corner rounding so the whole reads as one workstation, not a pile of cards.

**The Thin-Seam Rule.** Every border must explain structure, grouping, focus, or state; decorative outlines do not belong.

## Components

### Buttons

Buttons are restrained operator controls whose state is clearer than their ornament.

- **Shape:** Compact curved corners (4–5px radius), with 30–35px control height.
- **Primary:** Signal Blue with Primary Text, compact label type, and 13px horizontal padding.
- **Hover / Focus:** Hover changes the local surface or text; focus-visible receives a blue outline or inset ring. Disabled actions use desaturated graphite and explicit disabled copy.
- **Secondary / Ghost:** Panel Graphite or transparent fill with a steel border; active saved states may use a muted blue-tinted surface.

### Chips

- **Style:** Connection and count pills use one-pixel steel borders, compact padding, and Secondary Text.
- **State:** Status is communicated with text plus a six-pixel indicator; qualified and insufficient-evidence badges use restrained semantic border/text pairs.

### Cards / Containers

- **Corner Style:** Gently curved panels (7px radius); connected analysis regions keep only the outer corners.
- **Background:** Panel Graphite over Workstation Black, with Raised Graphite used sparingly.
- **Shadow Strategy:** Flat by default; use tonal layering and borders.
- **Border:** One-pixel Divider Steel outside and Soft Divider inside.
- **Internal Padding:** Usually 12–16px; dense data rows use 6–12px.

### Inputs / Fields

- **Style:** Workstation-dark fill, one-pixel steel border, 4–6px radius, and 30–32px height.
- **Focus:** Blue inset or border shift with no layout jump.
- **Error / Disabled:** State remains text-led; unavailable values use an em dash or precise explanation, and disabled historical ranges visibly reduce opacity.

### Navigation

Desktop navigation uses compact 12px labels and a two-pixel blue underline for the active route. Asset and rail tabs repeat the underline grammar at 10–11px. Below 760px, a fixed 56px five-item bottom navigation preserves the primary routes with icon-plus-label affordances.

### Financial Chart

The chart is the dominant analytical surface. MarketBridge reference data uses Signal Blue; reference bands use a muted steel line. A compact legend states symbol, price, change, and observation count, while missing data becomes an explicit unavailable panel rather than a fabricated series.

### Evidence and Risk Modules

Evidence is rendered as a compact source-and-impact table; risk is a parallel label/value monitor using mono values. AI status appears as a small dataset badge and must sit beside deterministic evidence and policy language, never above them in the hierarchy.

## Do's and Don'ts

### Do:

- **Do** lead asset detail with the quote band, chart, evidence quality, and risk state.
- **Do** use tabular mono numerals for prices, percentages, timestamps, latency, divergence, and exposure limits.
- **Do** pair positive/negative color with signs, arrows, or labels and pair connection color with explicit state text.
- **Do** show unavailable, delayed, estimated, synthetic, and advisory states in direct language.
- **Do** simplify secondary columns on mobile while preserving quote, chart, major risk, and primary actions.
- **Do** respect reduced-motion settings and retain visible keyboard focus.

### Don't:

- **Don't** turn the product into a generic AI dashboard or make learned output visually outrank evidence.
- **Don't** use green or red for decoration, navigation, generic success, or brand emphasis.
- **Don't** fabricate prices, chart history, news, portfolio holdings, fills, source independence, or live execution capability.
- **Don't** introduce large radii, soft card shadows, gradients, glass effects, or decorative finance imagery.
- **Don't** hide uncertainty behind blank space, spinner-only states, or optimistic action labels.
- **Don't** loosen deterministic risk restrictions through an AI recommendation or interaction treatment.

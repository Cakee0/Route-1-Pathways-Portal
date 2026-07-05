---
name: Route 1 Pathways
description: Minnesota food rescue marketplace — prairie palette, slab-serif voice, gold reserved for rescued value
colors:
  soil: "#2b2722"
  soil-soft: "#4a4239"
  pine: "#1f3d2e"
  pine-deep: "#162c21"
  field: "#3c6e4a"
  field-dark: "#2c5438"
  sprout: "#88a86a"
  sprout-soft: "#e4ecd9"
  harvest: "#c8881f"
  harvest-deep: "#a86d12"
  harvest-soft: "#f6e8cf"
  morning: "#edf0ea"
  paper: "#ffffff"
  stone-100: "#f3f4ee"
  stone-200: "#e5e6dd"
  stone-300: "#cfd1c4"
  ash: "#6f7268"
  clay: "#b4472e"
  clay-soft: "#f7e6e1"
typography:
  display:
    fontFamily: "Zilla Slab, Georgia, Times New Roman, serif"
    fontSize: "clamp(2.1rem, 5vw, 3.4rem)"
    fontWeight: 700
    lineHeight: 1.06
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Zilla Slab, Georgia, Times New Roman, serif"
    fontSize: "1.9rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Zilla Slab, Georgia, Times New Roman, serif"
    fontSize: "1.35rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Public Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.18em"
  data:
    fontFamily: "IBM Plex Mono, ui-monospace, SFMono-Regular, Consolas, monospace"
    fontWeight: 600
    fontFeature: "tnum"
rounded:
  sm: "7px"
  md: "13px"
  lg: "20px"
spacing:
  control-min: "44px"
components:
  button-primary:
    backgroundColor: "{colors.field}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "0.55rem 1.2rem"
    height: "{spacing.control-min}"
  button-primary-hover:
    backgroundColor: "{colors.field-dark}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "{colors.sprout-soft}"
    textColor: "{colors.field-dark}"
    rounded: "{rounded.sm}"
  button-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.clay}"
    rounded: "{rounded.sm}"
  button-value:
    backgroundColor: "{colors.harvest}"
    textColor: "{colors.soil}"
    rounded: "{rounded.sm}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.soil}"
    rounded: "{rounded.sm}"
    padding: "0.55rem 0.75rem"
    height: "{spacing.control-min}"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.md}"
  header:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.paper}"
---

# Design System: Route 1 Pathways

## 1. Overview

**Creative North Star: "A Minnesota Field Through the Season"**

The interface is the landscape it serves. Every color is a thing you can stand on or squint at in rural Minnesota: black-dirt soil, north-woods pine, a midsummer field, young sprouts, harvest gold, dawn light over stubble. The palette is never decorative — it is subject matter. Warmth comes from this commitment (earthy hues, slab-serif headlines, soil-tinted shadows), never from ornament, texture packs, or rustic kitsch.

This is a **product register** system: design serves the workflow of farmers, food-shelf staff, and neighbors moving surplus crops to people who need them. Components are sturdy and plainspoken — built like good farm equipment: generous 44px targets, clear labels, solid fills, nothing to figure out. The system explicitly rejects what PRODUCT.md rejects: generic corporate SaaS dashboards (cold slate grays, hero metrics, identical card grids), gig-economy app slickness, and rustic kitsch (barnwood textures, script fonts).

**Key Characteristics:**
- Palette drawn from a single physical scene, used semantically (gold = value, clay = error, field = action)
- Slab-serif display reserved for big agrarian moments; civic sans everywhere else; mono for ledger numbers
- Flat-ish surfaces with ambient, soil-tinted shadows — daylight, not UI chrome
- 44px minimum interactive targets (`--control-min`); the audience skews older
- Motion is composed and reduced-motion-safe: composed static fallbacks, never merely disabled

## 2. Colors: The Prairie Palette

One landscape, used semantically — every hue has a job, and harvest gold has exactly one.

### Primary
- **Midsummer Field** (#3c6e4a, `--field`): primary actions, links, the "go" of the interface. Hover deepens to **Field Dark** (#2c5438).
- **North-Woods Pine** (#1f3d2e, `--pine`): the chrome — header bar, hero bands, dark surfaces. Hover on dark goes **Pine Deep** (#162c21).

### Secondary
- **Harvest Gold** (#c8881f, `--harvest`): THE value color — dollars pledged, points, funding goals, and the thin gold line under the header. **Harvest Deep** (#a86d12) for hover/gradient ends; **Harvest Soft** (#f6e8cf) for value tints and gauge backing. Gold on light backgrounds must be large text only (4.32:1 at #a86d12 on white).
- **Young Sprout** (#88a86a, `--sprout`): secondary accents and growing states; **Sprout Soft** (#e4ecd9) for tints, hovers, and fills.

### Tertiary
- **Earthy Clay** (#b4472e, `--clay`): error and destructive — brick, not fire-engine red. **Clay Soft** (#f7e6e1) for error tints.

### Neutral
- **Prairie Loam** (#2b2722, `--soil`): body ink — a warm near-black. **Softened Soil** (#4a4239): secondary text (9.9:1 on white).
- **Morning** (#edf0ea, `--morning`): the app background — dawn over a field. Cool and green-tinted, deliberately NOT cream.
- **Paper** (#ffffff): cards and inputs.
- **Stone** ramp (#f3f4ee / #e5e6dd / #cfd1c4, `--stone-100/200/300`): faint fills, dividers, borders, input outlines.
- **Ash** (#6f7268): muted text — warm gray-green, never cold slate. Not for body copy on tinted backgrounds (4.29:1 on morning — fails).

### Named Rules
**The Value-Wears-Gold Rule.** Harvest gold appears ONLY on rescued value: money pledged, points earned, funding goals, and their gauges. Hardship numbers, decorations, and section accents never wear gold. If gold is on something that isn't value, it's wrong.

**The Not-Cream Rule.** The background is Morning (#edf0ea) — a cool green-tinted neutral. Never drift it toward cream/beige/parchment; warmth is carried by the palette's commitment and the type, not by a warm-tinted page.

**The 4.5 Rule.** Body text ≥4.5:1 against its background, always. When in doubt, step toward Soil. Known traps: harvest-deep small text on white, ash on morning.

## 3. Typography

**Display Font:** Zilla Slab (with Georgia fallback)
**Body Font:** Public Sans (with system-ui fallback)
**Label/Mono Font:** IBM Plex Mono (with ui-monospace fallback)

**Character:** Agrarian display, civic body, ledger data. Zilla Slab's slab serifs carry the barn-poster warmth; Public Sans is the plain-language civic servant; Plex Mono with tabular numerals makes every dollar and pound read like an honest ledger entry.

### Hierarchy
- **Display** (700, clamp(2.1rem, 5vw, 3.4rem), 1.06): landing hero only. Fluid sizing is for the marketing surface, not the app.
- **Headline** (700, 1.9rem, 1.1): page titles (h1).
- **Title** (600, 1.35rem, 1.15): section headings (h2). Zilla Slab stops here — h3 and below stay in Public Sans so slab remains special.
- **Body** (400, 0.9rem, 1.6): forms, tables, copy. Prose runs ≤65–75ch.
- **Label** (700, 0.78rem, 0.18em tracked, uppercase): the single named kicker style (hero eyebrow). Use sparingly — one kicker is voice, one per section is scaffolding.
- **Data** (`.num`, Plex Mono 600, tabular-nums): every price, quantity, point balance, and timestamp.

### Named Rules
**The Ledger Rule.** Numbers that represent value (dollars, pounds, points) are always set in IBM Plex Mono with tabular numerals via the `.num` class. Proportional digits on money are forbidden.

**The Slab-Stops-at-H2 Rule.** Zilla Slab appears in h1/h2/display and the brand mark only. Labels, buttons, data, and h3+ use Public Sans — display type in UI controls is prohibited.

## 4. Elevation

Depth is ambient daylight, not UI chrome. Surfaces are flat-ish: cards sit on Morning with a 1px Stone border and the faintest soil-tinted shadow; elevation appears only where something truly floats above the page (sticky header, modals, toast). All shadows are tinted with Soil (rgba(43,39,34,…)) — warmer than neutral black — so even depth belongs to the landscape.

### Shadow Vocabulary
- **Resting** (`box-shadow: 0 1px 2px rgba(43,39,34,.06), 0 1px 3px rgba(43,39,34,.05)`, `--shadow-sm`): cards at rest.
- **Floating** (`box-shadow: 0 4px 14px rgba(43,39,34,.10), 0 2px 5px rgba(43,39,34,.06)`, `--shadow-md`): sticky header, hover lifts.
- **Overlay** (`box-shadow: 0 14px 34px rgba(43,39,34,.16)`, `--shadow-lg`): modals only.

### Named Rules
**The Soil-Shadow Rule.** Every shadow derives from Soil (#2b2722), never neutral black. If a shadow reads cold or gray, it's off-palette.

**The Z-Scale Rule.** z-index is semantic: header 100 · modal 200–500 · toast 600 · skip-link 700. Arbitrary values (999, 9999) are forbidden.

## 5. Components

Sturdy and plainspoken — built like good farm equipment. Every interactive control honors `--control-min` (44px).

### Buttons
- **Shape:** gently rounded (7px, `--radius-sm`); min-height 44px; inline-flex centered.
- **Primary:** Midsummer Field (#3c6e4a) fill, Paper text, padding .55rem 1.2rem; hover deepens to Field Dark.
- **Value/Gold:** Harvest (#c8881f) fill with Soil text (4.9:1) — reserved for value-adjacent CTAs (register, donate); hover goes Harvest Soft with Soil text.
- **Hover / Focus:** background deepens (180ms ease); keyboard focus is the global 3px Harvest outline, offset 2px.
- **Secondary:** Sprout Soft fill, Field Dark text. **Danger:** Paper fill, Clay text, Stone border — destructive actions are quiet until hovered (Clay Soft fill).
- **Small (`.btn-sm`):** dense table rows only; floors at 36px (44px in the header).

### Cards / Containers
- **Corner Style:** 13px (`--radius-md`).
- **Background:** Paper on Morning.
- **Shadow Strategy:** Resting shadow + 1px Stone-200 border; hover may lift to Floating.
- **Internal Padding:** 1.25–1.5rem.
- **Never nested.** A card inside a card is a structure failure.

### Inputs / Fields
- **Style:** Paper background, 1.5px Stone-300 border, 7px radius, min-height 44px, Soil text at 0.9rem.
- **Focus:** 3px solid Harvest outline (offset 1px) + Field border — the same ring keyboard users see everywhere.
- **Error:** message in Clay on Clay Soft, `role="alert"`, adjacent to the field; hints use `aria-describedby`, never information-bearing placeholders.

### Navigation
- **Style:** Pine sticky header (60px) with the 2px Harvest rule beneath — the only gold in the chrome. Brand mark: Zilla Slab "Route 1" with the 1 in Harvest.
- **Links:** Public Sans 0.9rem, white at 80%; hover/active gain a white-15% pill. All targets ≥44px.
- **Mobile:** header wraps to two rows below 720px.

### The Harvest Fill (signature)
The brand's one flourish: a vessel that fills with gold toward a goal. Vertical grain-silo gauge on points; notched crate fill on funding bars and the landing impact vessel. The fill is a gradient from Harvest to Harvest Deep with faint Soil slat-lines; the vessel wall is Pine. Default state is full/current value (visible without JS); animation (scaleY rise, ~1.1s ease-out) is an enhancement layered on top. Gold gauges measure value only — see The Value-Wears-Gold Rule.

## 6. Do's and Don'ts

### Do:
- **Do** honor `--control-min`: 44px minimum for anything tappable — the audience skews older.
- **Do** set every value-number in Plex Mono `.num` with tabular numerals.
- **Do** use the 3px Harvest focus outline on every focusable element — inputs included.
- **Do** ship composed reduced-motion fallbacks (statically placed clouds, full gauges), not just `animation: none`.
- **Do** keep body text at ≥4.5:1; step toward Soil when close.
- **Do** use the existing tokens; if a value isn't a token, ask whether it should exist at all.

### Don't:
- **Don't** build "generic corporate SaaS dashboards" (PRODUCT.md's words): no cold slate grays, no hero-metric stat cards, no identical icon+heading+text card grids.
- **Don't** imitate "gig-economy app slickness" — no urgency patterns, no gradient-drenched CTAs.
- **Don't** add "rustic kitsch": no barnwood textures, no script fonts; warmth comes from the committed palette and type.
- **Don't** put Harvest gold on anything that isn't rescued value.
- **Don't** use `border-left`/`border-right` thicker than 1px as a colored accent stripe.
- **Don't** use gradient text (`background-clip: text`) or decorative glassmorphism, ever.
- **Don't** repeat the tracked-uppercase kicker above every section — one is voice, a cadence is AI scaffolding.
- **Don't** drift the background warm: Morning is cool-green (#edf0ea), not cream.
- **Don't** carry information in placeholders — placeholders vanish; hints live in visible `sub-text` lines.

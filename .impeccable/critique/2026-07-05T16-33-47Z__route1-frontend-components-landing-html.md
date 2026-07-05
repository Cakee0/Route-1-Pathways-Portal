---
target: landing
total_score: 27
p0_count: 0
p1_count: 3
timestamp: 2026-07-05T16-33-47Z
slug: route1-frontend-components-landing-html
---
# Critique — Route 1 landing page

Method: dual-agent (A: a3122f95f6620bb40 · B: aa12e904fa756d3b0). Browser visualization skipped: no browser automation tool exposed in this session.

## Design Health Score — 27/40 (Acceptable, borderline Good)

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | URL never changes; location bar lies about where you are |
| 2 | Match System / Real World | 3 | "Donation opportunities", undefined "earn rewards as you give" |
| 3 | User Control and Freedom | 1 | No routing/history: Back exits the site; CTAs are buttons, not links — nothing bookmarkable |
| 4 | Consistency and Standards | 3 | "Create free account" vs "Create your free account"; buttons where web standard is links |
| 5 | Error Prevention | 3 | Register hand-off `showRegisterTab?.click()` fails silently to login tab |
| 6 | Recognition Rather Than Recall | 4 | n/a — all three roles named and explained on-screen |
| 7 | Flexibility and Efficiency | 3 | No deep-linking; no efficient path from a shared link |
| 8 | Aesthetic and Minimalist Design | 4 | Restrained and on-palette; stat cards are the only template lapse |
| 9 | Error Recovery | 1 | Raw `Failed to load page: <msg>` with no retry, no way home |
| 10 | Help and Documentation | 2 | Footer has zero links — no privacy/terms/contact on a page asking for account creation |
| **Total** | | **27/40** | **Acceptable** |

## Anti-Patterns Verdict

Split verdict: **the hero clears the bar; below the fold the page collapses into the standard AI-landing skeleton.**

LLM assessment — what clears it: the hand-built SVG dawn scene (layered hills, barn, sun rising *behind* the hills via a deliberate sky/ground z-split), a reduced-motion fallback that statically *composes* the clouds instead of just disabling animation, and the gold "harvest fill" sweep on the CTA. What fails it:
- **Side-stripe border** — `.landing-stat { border-left: 4px solid var(--harvest) }` (styles.css:2897). Textbook banned pattern.
- **Hero-metric template** — big-number stat cards, which PRODUCT.md itself names as an anti-reference.
- **Identical card grid** — the route section degrades to three plain emoji cards below 860px when the dashed route line is `display:none`d — the one place the "route" concept exists, deleted where most visitors see it.
- **Eyebrow labels** — the uppercase tracked eyebrow → slab title → body rhythm on every section.

Deterministic scan: 1 finding — `single-font` at index.html:9 — judged a **false positive** (detector parses only the passed HTML and missed the three-family system defined in external styles.css: Zilla Slab / Public Sans / IBM Plex Mono, all actively used).

Visual overlays: not available this session (no browser automation tool); fallback signal reported.

## Overall Impression

Top 60% of the first viewport says "someone made this" — the right reaction. The section rhythm below (eyebrow/cards/stats) says "assembled from the same three blocks as everyone else." The single biggest opportunity: the signature harvest-fill motif appears only as a 0.38s button hover; the stats section begs to be one large gold vessel filling toward "100% reaches a Minnesota community."

## What's Working

1. **The hero scene is real design, not decoration** — palette-token-driven SVG fills, staggered daybreak choreography, composed reduced-motion fallback.
2. **Motif-integrated interaction** — the CTA's gold harvest-fill sweep, correctly removed under reduced motion.
3. **Copy voice is the brand** — "feed people — not landfills", "Help good food find its way home." Warm, civic, zero startup-speak.

## Priority Issues

- **[P1] No URLs / broken Back / dead-end errors** — `navigate()` (app.js:105) never touches history; Back after "Log in" exits the site; register page can't be linked from an email or flyer; fetch failure shows raw `Failed to fetch` with no recovery. **Fix**: hash routing (`#/`, `#/login`, `#/register`), CTAs as `<a href="#/register">`, retry/home block in the catch branch. **Suggested command**: /impeccable harden
- **[P1] Contrast failures** — `.landing-section-eyebrow` (#a86d12 @12px bold) = 4.32:1 on white and 3.76:1 on `--morning` (needs 4.5); CTA hover `--soil` on `--harvest-deep` gradient half = 4.14:1 at 16.3px; same on `#navRegisterBtn:hover`. **Fix**: eyebrows → `--field-dark` (like the hero's, 7.4:1); end hover gradient at `--harvest` or switch hover text to `--pine-deep`. **Suggested command**: /impeccable polish
- **[P1] Touch targets under 44px on the paths returning users need** — header "Log in" ≈30px, `.btn-sm` ≈32px, `.landing-login-link` ≈36px; audience skews older. **Fix**: `min-height: 44px` via padding. **Suggested command**: /impeccable adapt
- **[P2] Stats block: banned template + gold-discipline violation** — left-stripe hero-metric cards make hardship numbers wear the value color ("Value wears gold" broken). **Fix**: one large harvest-fill vessel at section scale; gold reserved for the "100% reaches a community" fill. **Suggested command**: /impeccable bolder
- **[P2] Trust scaffolding absent at the conversion moment** — uncited national stats, no named farm/partner/town, linkless footer. **Fix**: footer nav (About, Contact, Privacy), stat sources, one reassurance line under the CTA. **Suggested command**: /impeccable clarify

## Persona Red Flags

**Jordan (first-timer)**: unsure whether they buy, donate, or receive food until they scroll; "earn rewards" never defined; role-blind CTA ("I'm not a farmer — is this for me?"); uncited "40M+" → tab closed.

**Riley (stress tester)**: Back button ejects from site; offline click → raw error, no recovery; `showRegisterTab?.click()` silently lands on the wrong tab if login.html changes; pre-Chrome-105 browsers: `:has()` hero layout breaks and `translate`-property `@keyframes` piles all five clouds at left:0.

**Casey (distracted mobile)**: four sequential network hops before content on 3G; sub-44px secondary actions; 92vh hero hides "How it works" entirely below the fold with no scroll cue.

**Older food-shelf volunteer on cheap Android (project persona)**: most likely to hold exactly the browsers where `:has()`/`translate` animation fail; three infinite animations with `will-change` on a weak GPU (jank + battery); `.brand-sub` at ~9.3px illegible; raw emoji route icons (🥫 may render as tofu, none `aria-hidden`); their #1 task (log in) is the page's smallest target.

## Minor Observations

- Header/hero CTA copy mismatch ("Create free account" vs "Create your free account").
- h1 has a hard `<br>` welding two sentences; awkward rag under 700px; "⅓" in Plex Mono may fall to a fallback glyph — use "1 in 3".
- No per-view `<title>`/OG tags — shared links preview generically; matters for word-of-mouth acquisition.
- `background-attachment: fixed` on body is a mobile-jank source on low-end Android.
- Route line disappears below 860px instead of rotating vertical.
- GoatCounter manual SPA tracking is privacy-respecting and fits the civic brand — nice.

## Questions to Consider

1. The harvest fill is the signature — why does its largest landing expression last 0.38 seconds on a hover? What would the stats section become as one vessel filling from "⅓ lost" to "100% reaches a Minnesota community"?
2. The hero promises Minnesota; the evidence is national. What's stopping the page from showing one real rescued crop — a farm name, a town, pounds delivered?
3. Who is this landing for? Three audiences are explained, then one undifferentiated CTA funnels them into a generic register form. Would three role doors convert better, or does single-CTA simplicity win for the older majority?

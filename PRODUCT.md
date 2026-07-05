# Product

## Register

product

## Users

Three-sided Minnesota food-rescue marketplace:

- **Farmers** — list crop inventory (pricing, transport flags, donation eligibility). Often working outdoors or between tasks; need fast, low-friction CRUD.
- **Organizations** (restaurants, grocery stores, food shelves) — browse farmer listings, post wishlist items as donation opportunities, link farmers to requests. Food-shelf staff are frequently non-technical and time-pressed.
- **Consumers** — browse farmers, fund donation opportunities (individually or as a group), earn reward points. Motivated by community impact; many are older or on low-end devices.

The job to be done: move locally-grown produce to communities that need it, with as little interface friction as possible.

## Product Purpose

Route 1 connects surplus Minnesota farm produce with food organizations and community funders. Success = donation opportunities get funded and fulfilled: crops listed → wishlist requests linked → pledges completed → impact recorded. Every screen should shorten the path to that loop.

## Brand Personality

Warm, grounded, civic. Trustworthy and human — a community agriculture cooperative, not a tech startup. The committed visual system carries this: prairie palette (soil / pine / field-green / harvest gold), Zilla Slab agrarian display type, Public Sans civic body, IBM Plex Mono ledger data. Harvest gold is reserved as THE value color (dollars pledged, points, funding goals). Signature motif: "the harvest fill" — a gold gauge filling a vessel toward a goal.

## Anti-references

- Generic corporate SaaS dashboards (cold slate grays, hero metrics, identical card grids).
- Gig-economy app slickness (DoorDash/Instacart gradients and urgency patterns).
- Rustic kitsch — the warmth comes from the committed palette and type, not barnwood textures or script fonts.

## Design Principles

1. **The loop is the interface** — every screen advances list → request → pledge → fulfill; remove anything that doesn't.
2. **Value wears gold** — harvest gold appears only on rescued value (money, points, goals), keeping impact legible at a glance.
3. **Civic clarity over cleverness** — plain-language labels, visible state, no hidden gestures; food-shelf staff and older users must never guess.
4. **Warmth through commitment, not decoration** — the earthy palette and slab type carry the brand; resist adding ornament.
5. **Works tired, works small** — flows must survive low-end devices, spotty rural connections, and one-handed use.

## Accessibility & Inclusion

- Target: **WCAG 2.2 AA** — contrast ≥4.5:1 body text, full keyboard navigability, visible focus, screen-reader landmarks.
- `prefers-reduced-motion` alternatives for all animation.
- Generous touch targets and type sizes; audience skews toward older and less technical users.
- Performance is an accessibility feature here: static SPA must stay light for low-end devices and rural connections.

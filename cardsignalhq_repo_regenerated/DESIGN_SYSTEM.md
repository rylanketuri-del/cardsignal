# CardSignal — Design System

CardSignal uses a premium editorial aesthetic inspired by luxury finance and sports-card collecting. The UI should feel like a research report, not a generic dashboard.

## Design Tokens

Defined in `frontend/styles.css` `:root`:

### Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` / `--cream` | `#F7F5F2` | Page background |
| `--paper` | `#F1ECE5` | Secondary surfaces |
| `--panel` | `#FCFBF8` | Card/panel background |
| `--stone` | `#DCD6CE` | Borders |
| `--copper` | `#BB8455` | Primary accent, CTAs |
| `--bronze` | `#8A6747` | Labels, secondary accent |
| `--charcoal` | `#0F0F10` | Headlines, dark surfaces |
| `--charcoal-dark` | `#171717` | Featured Signal banner |
| `--text` | `#1D1D1F` | Body text |
| `--muted` | `#7D7873` | Captions, meta |
| `--sage` | `#708A72` | Constructive/hold signals |
| `--signal-green` | `#2F7D4A` | Positive movement, BUY |
| `--signal-red` / `--clay` | `#9A6656` | Negative movement, SELL |

### Typography

- **Display / headlines** — Cormorant, Georgia, serif (player names, section titles, large scores)
- **UI / body** — Inter, system sans-serif (labels, tables, forms, pills)
- **Eyebrow / label** — uppercase, letter-spacing `0.12–0.18em`, weight 800–900, bronze/copper color

### Radius & Shadow

| Token | Value |
|-------|-------|
| `--radius-sm` | 12px |
| `--radius-md` | 16px |
| `--radius-lg` | 24px |
| `--radius-xl` | 32px |
| `--radius-pill` | 999px |
| `--shadow-soft` | `0 10px 40px rgba(15,15,16,0.06)` |
| `--shadow-card` | `0 18px 60px rgba(15,15,16,0.08)` |
| `--shadow-hover` | `0 20px 70px rgba(15,15,16,0.10)` |

### Motion

- `--transition-fast` — 160ms ease (hover, pills)
- `--transition-base` — 220ms ease (panels, cards)
- Modal panel — `piPanelIn` / `piDrawerIn` keyframes

## Component Patterns

### Panels & Cards

- White/cream panels with `--stone` border, `--radius-lg` to `--radius-xl`, `--shadow-soft`
- Hover lift: `translateY(-2px)` + `--shadow-hover` on interactive cards (not hero banners)

### Pills & Badges

- **Recommendation** — BUY (green), HOLD (copper), SELL (clay)
- **Conviction** — High (sage), Medium (copper), Low (clay)
- **Status** — HOT (clay), RISING (sage/green), COOLING (blue)
- **BETA badge** — subtle bronze border, uppercase, letter-spaced

### Progress Bars

Signal breakdown bars use gradient fills per dimension:

- Performance — sage gradient
- Market — copper gradient
- Collector Demand — bronze gradient
- Momentum — clay gradient

Track: 12px height, rounded, stone background.

### Intelligence Rows

Card and player intel rows use a consistent grid:

- Thumbnail placeholder (dark gradient, copper inset glow)
- Name + price/meta (truncated, no overflow)
- Movement metric (green up / red down / muted flat)

Max 3 rows per section on homepage and modal Cards tab.

### Featured Signal Banner

- Full-width dark editorial banner (`--charcoal-dark`)
- Player photo stage with glass overlay
- Copper CTA pill with arrow
- Score and weekly movement in Cormorant display type

### Player Intelligence Modal

- **Backdrop** — `rgba(15,15,16,0.62)` with blur
- **Header** — charcoal gradient, player headshot, score, recommendation, status
- **Tabs** — pill style; active tab charcoal fill
- **Body** — scrollable cream panel; no horizontal overflow
- **Mobile** — full viewport drawer, `border-radius: 0`, slide-up animation

## Layout

- Max page width: 1400px, centered
- Homepage grid: 2-column for intelligence cards and charts; stacks at 980px
- Leaders table: horizontal scroll container with sticky header
- Modal: centered flex on desktop; stretch on mobile (`max-width: 980px` breakpoint)

## Accessibility

- Modal: `role="dialog"`, `aria-modal`, `aria-labelledby`, Escape to close
- Search results: `role="listbox"`, keyboard arrow navigation
- Tab buttons: `role="tab"`, `aria-selected`, `aria-controls`
- Focus visible on close button and tabs

## Do Not

- Introduce new color families outside the token palette
- Use guaranteed-return language in forecast or recommendation copy
- Break homepage layout when adding modal features
- Add horizontal overflow on mobile viewports
- Duplicate modal markup or tab event listeners

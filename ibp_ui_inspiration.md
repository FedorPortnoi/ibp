# Lusion.co UI/UX Design Analysis

> Comprehensive analysis of https://lusion.co/ — captured March 2026.
> Pages analyzed: Home, About, Projects, Project Detail (Devin AI), Menu Overlay.

---

## 1. Color Palette

### CSS Custom Properties (from `:root`)

| Variable | Value | Usage |
|----------|-------|-------|
| `--color-white` | `#fff` | Primary background (light pages) |
| `--color-off-white` | `#f0f1fa` | Body text on dark backgrounds, soft white |
| `--color-dark-white` | `#e4e6ef` | Muted white, secondary elements |
| `--color-off-white-semi` | `rgba(240, 241, 250, 0.7)` | Semi-transparent overlay text |
| `--color-black` | `#000000` | Primary text on light backgrounds |
| `--color-blue` | `#1a2ffb` | Brand accent blue |
| `--color-dark-blue` | `#071bdf` | Darker blue variant |
| `--color-green` | `#c1ff00` | Neon green accent (lime) |
| `--color-red` | `#ff4c41` | Error / alert red |
| `--color-error` | `#e90000` | Form error red |
| `--color-grey-blue` | `#2b2e3a` | Dark grey-blue (Let's Talk button bg) |
| `--color-purple` | `#8832f7` | Purple accent |
| `--header-color` | `#0016ec` | Header accent (home page) |

### Computed Colors (RGB → Hex)

| Color | Hex | Usage |
|-------|-----|-------|
| `rgb(0, 0, 0)` | `#000000` | Primary text, dark backgrounds |
| `rgb(255, 255, 255)` | `#ffffff` | Light text, button backgrounds |
| `rgb(240, 241, 250)` | `#f0f1fa` | Body text color (off-white), backgrounds |
| `rgb(26, 47, 251)` | `#1a2ffb` | Brand blue accent |
| `rgb(0, 22, 236)` | `#0016ec` | Header color (vibrant blue) |
| `rgb(43, 46, 58)` | `#2b2e3a` | Dark grey-blue (Let's Talk bg) |
| `rgb(228, 230, 239)` | `#e4e6ef` | Light grey border / divider |
| `rgb(18, 20, 22)` | `#121416` | Near-black (project detail bg) |
| `rgb(52, 57, 63)` | `#34393f` | Mid-grey |
| `rgb(193, 255, 0)` | `#c1ff00` | Neon lime green |
| `rgb(25, 39, 67)` | `#192743` | Dark navy (button text, menu text) |
| `rgb(100, 225, 206)` | `#64e1ce` | Teal/mint (project detail accent) |

### Color Strategy
- **Light pages** (Home, Projects): White `#fff` / off-white `#f0f1fa` background, black `#000` text
- **Dark pages** (About hero, Project detail, Footer CTA): Near-black `#121416` background, white `#fff` text
- **Accents are per-project**: Each project detail page has its own `--project-details-highlight` color (e.g., Devin AI uses teal `#64e1ce`)
- **Minimal color use**: 95% of the interface is monochrome (black/white), with a single accent color for CTAs and highlights

---

## 2. Typography

### Font Families

| Font | Weights | Style | Usage |
|------|---------|-------|-------|
| **Aeonik** | 400 (Regular), 500 (Medium), 400 Italic | Sans-serif | Primary font — all headings, body text, buttons, navigation |
| **IBM Plex Mono** | 400, 500 | Monospace | Secondary — numbers, counters, labels (e.g., "001", award counts) |
| **LusionMono** | 400 | Monospace | Custom — specialty elements |

Font files served as `.woff2` / `.woff` from `/assets/fonts/`.
Font-display: `block` (ensures text isn't shown until font loads).

### Type Scale (Computed)

| Element | Size | Weight | Line Height | Transform | Usage |
|---------|------|--------|-------------|-----------|-------|
| Hero title (h4) | `103.4px` | 400 | 1.0 (103.4px) | none | Mega headings — "Beyond Visions Within Reach" |
| Project title (h2) | `72px` | 400 | 0.95 (68.4px) | none | Project detail page title |
| Section heading (h5) | `48px` | 400 | 1.0 (48px) | uppercase | "Awards", "Articles", "Talks" |
| Newsletter heading (h3) | `38px` | 400 | 1.15 (43.7px) | none | "Subscribe to our newsletter" |
| Subheading (h1 on home) | `25.85px` | 400 | 1.1 (28.4px) | none | Hero subtext |
| Nav menu items | `26px` | 400 | 1.0 (26px) | uppercase | Menu overlay links |
| Body / links | `16px` | 400 | 1.15 (18.4px) | none | Default body text |
| Footer links | `17.5px` | 400 | 1.4 (24.5px) | none | Address, social links |
| Buttons (header) | `14px` | 500 | 1.15 (16.1px) | uppercase | "BACK", "MENU", nav buttons |
| Small labels | `12px` | 400 | 1.15 (13.8px) | uppercase | "SCROLL TO EXPLORE", "SERVICES" |
| Body small (project desc) | `12px` | 400 | 1.5 (18px) | none | Project descriptions |

### Typography Patterns
- **Almost exclusively weight 400** (Regular) — even massive headings are weight 400, relying on size alone for hierarchy
- **Weight 500** (Medium) only for buttons and interactive labels
- **Uppercase** used sparingly: navigation, labels, CTAs — never on body text or primary headings
- **Tight line heights** on large text (0.95-1.0), more generous on body text (1.15-1.5)
- **No letter-spacing adjustments** — all set to `normal`
- **No bold (700+) anywhere** on the site

---

## 3. Layout Patterns & Grid System

### Grid System (CSS Custom Properties)

```css
--grid-gap: 2vw;
--grid-space: calc((100% - 11 * var(--grid-gap)) / 12);
--base-padding-x: max(5vw, 40px);
--base-padding-y: clamp(30px, 4vw, 50px);
--global-border-radius: 20px;
```

- **12-column grid** with `2vw` gutters
- **Fluid padding**: `max(5vw, 40px)` horizontal, `clamp(30px, 4vw, 50px)` vertical
- Projects page uses a 12-column CSS Grid: `grid-template-columns: repeat(12, 1fr)` with `~20.68px` gap

### Layout Patterns Observed

1. **Full-bleed hero sections**: WebGL canvases that fill the entire viewport
2. **Two-column project grid**: Projects displayed in 2-column layout (roughly 50/50 split spanning 6 columns each)
3. **Asymmetric content layouts**: Project detail pages use left-aligned text with right-aligned media
4. **Scroll-hijacked single-page sections**: Home page content advances through transform-based "slides" rather than native scrolling
5. **Fixed header**: `position: fixed`, `z-index: 52`, transparent background, `height: ~129px`

### Spacing System
- Gaps observed: `6px`, `8px`, `10px`, `24px`, `60.5px`, `84px`, `168px`
- No strict 4px/8px base unit — spacing is fluid and viewport-relative

---

## 4. Animation & Motion Design

### Scroll-Driven Architecture
- The entire site uses **custom scroll handling** — native scroll is disabled (`overflow: hidden` on body, `scrollHeight === viewportHeight`)
- Content transitions are driven by **wheel events** mapped to virtual scroll position
- WebGL canvas (3 canvases on homepage: main WebGL2 `1034x605`, plus two 2D helper canvases)
- Built with **Astro** framework (visible in `_astro/hoisted.81170750.js` bundle path)

### CSS Transitions
| Element | Transition | Duration |
|---------|-----------|----------|
| Buttons (color/bg) | `color 0.4s, background-color 0.4s` | 400ms |
| Generic elements | `all` (transform-driven) | Varies |
| Footer social links hover | `transform: translate3d(2em, 0, 0)` | CSS transition |

### Keyframe Animations
```css
@keyframes arrow-animation {
  0% { transform: translateZ(0); }
  33% { transform: translate3d(0, 1em, 0); }
  100% { transform: translate3d(0, 1em, 0); }
}

@keyframes text-animation {
  0% { transform: translateZ(0); }
  33% { transform: translate3d(0, 1.5em, 0); }
  100% { transform: translate3d(0, 1.5em, 0); }
}
```

### Motion Patterns Observed
1. **WebGL 3D scenes** — Homepage: interactive 3D pipe/tube objects (blue, black, white, grey); About: particle cloud effect; Footer: 3D astronaut with floating stickers
2. **Character-by-character text reveals** — Project names on homepage use stacked `<span>` elements for letter-by-letter animation (4 copies per letter for slide effect)
3. **Word-by-word parallax text** — "Step into a new world and let your imagination run wild" — each word animates independently with transforms
4. **Scroll-to-reveal** — Sections fade/slide into view as the user scrolls through virtual scroll positions
5. **Cross/plus markers** — Small `+` symbols at corners rotate (`matrix(-1, 0, 0, -1, 0, 0)` — 180 degree rotation) during scroll
6. **Hover text slide** — Links use duplicate text layers that slide on hover (translate Y)
7. **"CONTINUE TO SCROLL" marquee** — Horizontal scrolling text banner

---

## 5. UI Components

### Navigation Header
- **Fixed position**, transparent background, `z-index: 52`
- Height: `~129px` (generous)
- Logo: "LUSION" wordmark, top-left
- Right side: squiggly line icon button → "LET'S TALK" pill button → "MENU" pill button
- Header adapts per page: On project detail pages, a "BACK" button appears; logo color changes to match project accent

### Buttons

| Button Type | Background | Text Color | Border Radius | Padding | Font |
|-------------|-----------|------------|---------------|---------|------|
| **"Let's Talk"** (dark) | `#2b2e3a` (grey-blue) | `#ffffff` | `87.5px` (pill) | `0 15.75px 0 22.75px` | 14px / 500 / uppercase |
| **"Menu"** (light) | `#ffffff` | `#192743` (navy) | `87.5px` (pill) | `0 15.75px 0 22.75px` | 14px / 500 / uppercase |
| **"Back"** (light) | `#ffffff` | `#000000` | `100px` (pill) | `0 21px 0 14px` | 14px / 500 / uppercase |
| **"Launch Project"** | `#ffffff` | `#192743` (navy) | `100px` (pill) | `16px 24px 16px 18px` | 16px / 500 / uppercase |
| **"See all projects"** | (link style) | contextual | — | — | With arrow icon |
| **"About us"** (link) | transparent | contextual | — | — | With arrow icon |

**Button patterns:**
- All buttons are **pill-shaped** (border-radius: 87.5px-100px)
- No borders (`border: 0`)
- Height: `~44.8px` (header buttons)
- Dot indicator (`•` or `••`) appears next to button text
- Transitions: `color 0.4s, background-color 0.4s`

### Menu Overlay
- Slides in from top-right as a white dropdown panel
- Contains: Home, About us, Projects, Contact (vertical list, uppercase)
- "Labs" link at bottom with icon and external arrow
- Active page indicated with a `•` dot
- Font size: `26px`, uppercase
- Clean white background, black text

### Project Cards (Projects Page)
- **No card borders or shadows** — cards are image + text only
- Large project thumbnails (images with rounded corners `20px` — `--global-border-radius`)
- Category tags appear above project name: `web • design • development • 3d`
- Project names use the mega-sized character-by-character animated text
- Two-column grid layout

### Footer
- **Two-section footer:**
  1. **CTA section** (dark bg with 3D astronaut): "IS YOUR BIG IDEA READY TO GO WILD?" + "Let's work together!" animated text + "CONTINUE TO SCROLL" marquee
  2. **Info section** (light bg): Address (Bristol, UK), social links (Twitter/X, Instagram, LinkedIn), email contacts, newsletter signup
- Newsletter: simple email input + send button with arrow icon
- Copyright: `©2025 LUSION Creative Studio`
- Bottom links: `R&D: labs.lusion.co`, `Built by Lusion with heart emoji`

### Newsletter Form
- Text input: `"Your email"` placeholder
- Send button: circular with arrow icon
- Heading: `"Subscribe to our newsletter"` at `47.25px`

### Counter/Progress Indicator
- Bottom-right of viewport: three 2-digit number displays (e.g., `00 00 01`)
- Appears to track scroll position / section index
- Uses monospace font

---

## 6. Interactive Elements & Hover States

### Hover Patterns
- **Link text slide**: Duplicate text layers — on hover, first layer slides up/away, second layer slides into view (`translate3d(0, 1.5em, 0)`)
- **Footer social links**: Text shifts right on hover (`translate3d(2em, 0, 0)`)
- **Button color swap**: `color 0.4s, background-color 0.4s` transition
- **Project cards**: Likely have scale/opacity transitions (WebGL-driven, not pure CSS)
- **Cursor**: Custom cursor implied by `cursor: pointer` everywhere, likely a custom WebGL cursor

### Interactive 3D Elements
- Homepage hero: 3D pipe/tube objects respond to mouse movement
- About page: Particle cloud is interactive
- Footer: 3D astronaut with floating emoji stickers
- Project detail: Device mockup with parallax effect

### Micro-interactions
- `+` cross markers rotate on scroll
- "SCROLL TO EXPLORE" / "CONTINUE TO SCROLL" indicators
- Progress counter updates in real-time
- Menu button text toggles between "Menu" / "Close"
- Squiggly line icon (between logo and buttons) appears to animate

---

## 7. Overall Design Language & Aesthetic

### Design Philosophy
Lusion practices a **"less is more" approach to color, more is more approach to motion"** design philosophy:

1. **Monochrome foundation** — The interface is almost entirely black and white, creating a gallery-like canvas that lets the 3D content and project work shine
2. **Single accent color per context** — Each project gets its own highlight color (teal, green, blue, etc.) applied via CSS custom properties
3. **WebGL-first experience** — This is not a traditional website with scroll; it's closer to an interactive art installation
4. **Typography as architecture** — Giant letterforms (100px+) at weight 400 create structure without visual heaviness
5. **Restrained UI chrome** — No card borders, no shadows, no gradients on UI elements. Buttons are simple pills.

### Key Design Principles
| Principle | Implementation |
|-----------|----------------|
| **Contrast** | Black/white dominance with single accent pops |
| **Scale** | Extreme type size range: 12px labels to 103px headings |
| **Motion** | Every section has scroll-triggered 3D or transform animation |
| **Whitespace** | Generous padding (`max(5vw, 40px)`), few elements per viewport |
| **Consistency** | One font family (Aeonik) for everything, pill buttons everywhere |
| **Craftsmanship** | Custom fonts, WebGL scenes, per-character text animation |

### Technology Stack
- **Framework**: Astro (SSG with islands architecture)
- **3D**: WebGL2 canvas (custom engine or Three.js bundled)
- **Scroll**: Custom scroll hijacking (no Lenis/Locomotive detected — likely custom)
- **Fonts**: Aeonik (commercial sans-serif), IBM Plex Mono, LusionMono (custom)
- **No GSAP, no Lenis, no Three.js on window** — all bundled/tree-shaken

### What Makes It Distinctive
1. **Scroll hijacking done right** — The entire page is a curated journey, not a scrollable document
2. **3D as content, not decoration** — The WebGL scenes ARE the hero content
3. **Restraint in UI** — Despite being a cutting-edge studio, the UI components are extremely simple (plain pills, no gradients, no fancy borders)
4. **Per-project theming** — CSS custom properties change the entire color scheme per project
5. **Monospace as punctuation** — IBM Plex Mono / LusionMono used for small labels and numbers adds technical precision
6. **Character-level text animation** — Each letter is a separately animated element (4 copies for slide transitions)

---

## Appendix: All CSS Custom Properties

```css
:root {
  /* Colors */
  --color-error: #e90000;
  --color-off-white: #f0f1fa;
  --color-white: #fff;
  --color-dark-white: #e4e6ef;
  --color-off-white-semi: rgba(240, 241, 250, .7);
  --color-black: #000000;
  --color-green: #c1ff00;
  --color-blue: #1a2ffb;
  --color-red: #ff4c41;
  --color-grey-blue: #2b2e3a;
  --color-dark-blue: #071bdf;
  --color-purple: #8832f7;

  /* Layout */
  --grid-space: calc((100% - 11 * var(--grid-gap)) / 12);
  --grid-gap: 2vw;
  --global-border-radius: 20px;
  --base-padding-x: max(5vw, 40px);
  --base-padding-y: clamp(30px, 4vw, 50px);

  /* Header */
  --header-color: #0016ec;
  --header-text-color: #000000;
  --header-size: clamp(1rem, 1vw, 2rem);
  --cross-size: clamp(.875rem, 1vw, 2rem);

  /* Project detail (per-project via inline styles) */
  --project-details-bg: #000;
  --project-details-highlight: #000;
  --project-details-btn-bg: #000;
  --project-details-btn-text: #000;
  --project-details-icon-bg: #000;
  --project-details-icon-color: #000;
  --project-details-text: #000;
  --project-details-btn-bg-hover: #000;
  --project-details-btn-text-hover: #fff;
}

/* Example project override (Devin AI): */
/* --project-details-bg: #121414 */
/* --project-details-highlight: #64e1ce */
/* --project-details-btn-bg: #ffffff */
/* --project-details-btn-text: #192743 */
/* --project-details-text: #ffffff */
```

---

## Appendix: Font Definitions

```css
@font-face {
  font-family: Aeonik;
  src: url("/assets/fonts/Aeonik-Regular.woff2") format("woff2");
  font-weight: 400;
  font-display: block;
}
@font-face {
  font-family: Aeonik;
  src: url("/assets/fonts/Aeonik-Medium.woff2") format("woff2");
  font-weight: 500;
  font-display: block;
}
@font-face {
  font-family: Aeonik;
  src: url("/assets/fonts/Aeonik-RegularItalic.woff2") format("woff2");
  font-weight: 400;
  font-style: italic;
  font-display: block;
}
@font-face {
  font-family: IBMPlexMono;
  src: url("/assets/fonts/IBMPlexMono-Regular.woff2") format("woff2");
  font-weight: 400;
  font-display: block;
}
@font-face {
  font-family: IBMPlexMono;
  src: url("/assets/fonts/IBMPlexMono-Medium.woff2") format("woff2");
  font-weight: 500;
  font-display: block;
}
@font-face {
  font-family: LusionMono;
  src: url("/assets/fonts/LusionMono.woff2") format("woff2");
  font-weight: 400;
  font-display: block;
}
```

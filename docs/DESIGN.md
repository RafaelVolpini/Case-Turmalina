---
name: Turmaline Executive
colors:
  surface: '#f8f9ff'
  surface-dim: '#d0dbed'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dee9fc'
  surface-container-highest: '#d9e3f6'
  on-surface: '#121c2a'
  on-surface-variant: '#3f4947'
  inverse-surface: '#27313f'
  inverse-on-surface: '#eaf1ff'
  outline: '#6f7977'
  outline-variant: '#bec9c6'
  surface-tint: '#1d6963'
  primary: '#00413c'
  on-primary: '#ffffff'
  primary-container: '#005a54'
  on-primary-container: '#89cfc7'
  inverse-primary: '#8dd3cb'
  secondary: '#725a42'
  on-secondary: '#ffffff'
  secondary-container: '#fedcbe'
  on-secondary-container: '#796048'
  tertiary: '#00422b'
  on-tertiary: '#ffffff'
  tertiary-container: '#005c3e'
  on-tertiary-container: '#49da9f'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a9f0e7'
  primary-fixed-dim: '#8dd3cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#00504b'
  secondary-fixed: '#fedcbe'
  secondary-fixed-dim: '#e1c1a4'
  on-secondary-fixed: '#291806'
  on-secondary-fixed-variant: '#59422c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9ff'
  on-background: '#121c2a'
  surface-variant: '#d9e3f6'
typography:
  display:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-page: 32px
  container-max: 1440px
  card-padding: 20px
---

## Brand & Style
The design system is engineered for operational oversight and executive decision-making. The brand personality is **Sophisticated, Data-Driven, and Operationally Excellent**. It balances the organic heritage of the coffee industry with the precision of a modern fintech platform.

The visual style is **Corporate / Modern** with a lean towards **Minimalism**. It utilizes a clean, "DaisyUI-inspired" aesthetic characterized by high-contrast functional elements, generous white space, and a clear information hierarchy. The interface prioritizes speed of comprehension, using subtle depth to separate analytical layers without distracting from the data.

## Colors
The palette is anchored by **Deep Turmaline Green**, representing stability and the premium nature of the product. **Warm Coffee Brown** is used sparingly for accents and secondary brand touchpoints to maintain a connection to the physical product.

- **Primary (#005A54):** Used for navigation, primary actions, and brand identification.
- **Secondary (#4B3621):** Used for categorical distinction in charts and subtle supporting elements.
- **Functional Colors:** Emerald Green (#10B981) denotes "Success" and positive growth; Deep Red (#DC2626) is reserved strictly for critical operational alerts and negative trends.
- **Neutral/Background:** A very light gray base (#F9FAFB) ensures a "breathable" dashboard environment with pure white cards to create a clear visual stack.

## Typography
This design system utilizes **Inter** exclusively to ensure maximum legibility across dense data tables and complex charts. The type scale is systematic, utilizing a tighter letter-spacing for large headlines to maintain a premium "executive" feel.

- **Headlines:** Use SemiBold (600) for section titles and Bold (700) for key metrics.
- **Data Display:** For tabular data, use `body-md` with tabular lining figures if available to ensure numbers align vertically.
- **Labels:** All-caps styling with 0.05em tracking is used for category headers and small badges to differentiate them from interactive text.

## Layout & Spacing
The layout follows a **Fixed Grid** philosophy on desktop to preserve the integrity of data visualizations, transitioning to a fluid single-column stack on mobile.

- **Grid:** A 12-column grid system with a 24px gutter.
- **Executive Dashboard View:** Metrics are typically grouped in 3 or 4 columns (spanning 4 or 3 grid units respectively).
- **Rhythm:** An 8px linear scale is used for all internal component spacing, while a 4px scale is used for fine-tuning text alignment and small icon-label gaps.
- **Breakpoints:** Desktop (1280px+), Tablet (768px - 1279px), Mobile (below 768px).

## Elevation & Depth
This design system uses **Tonal Layers** combined with very subtle **Ambient Shadows** to create a structured hierarchy.

1.  **Level 0 (Background):** #F9FAFB. The canvas for all content.
2.  **Level 1 (Cards/Surface):** Pure White (#FFFFFF). All primary content lives on these cards. They feature a 1px border (#E5E7EB) and a soft, low-opacity shadow (Y: 2px, Blur: 4px, Opacity: 0.05, Color: #000).
3.  **Level 2 (Modals/Popovers):** Higher elevation with a more pronounced shadow (Y: 10px, Blur: 20px, Opacity: 0.1) to focus the executive's attention on specific interactions.

Interactive elements (buttons) do not use shadows, but instead use solid color shifts to maintain a flat, professional aesthetic.

## Shapes
The shape language is **Soft**, communicating precision and modern efficiency. 

- **Primary Radius:** 0.25rem (4px) for input fields, checkboxes, and small buttons.
- **Large Radius (rounded-lg):** 0.5rem (8px) for data cards and main container wrappers.
- **Pill Radius:** Used exclusively for "Status Badges" (e.g., "Active", "Pending") and Ranking Indicators to distinguish them from actionable buttons.

## Components
- **Buttons:** Primary buttons are solid Deep Turmaline Green with white text. Secondary buttons use a "Ghost" style—1px borders in the secondary brown or neutral gray.
- **Cards:** The central container of the dashboard. Every card must have a consistent 20px internal padding and a 1px bottom border on the card header to separate titles from the data body.
- **Ranking Badges:** High-contrast circular or pill-shaped indicators. For top-tier performance, use the Primary color; for alerts, use the Danger color. 
- **Input Fields:** Minimalist design with a 1px border. On focus, the border transitions to Primary Green with a subtle 2px outer glow (ring).
- **Charts:** Use a coordinated palette of Turmaline Green, Coffee Brown, and muted Emerald. Avoid using more than 5 colors in a single visualization; use tints of the primary color for multi-series data.
- **Lists:** Data rows should have a subtle hover state (#F3F4F6) to assist with horizontal eye tracking across wide data sets.
# VISUAL LANGUAGE
## Visual Identity and Design System

**Purpose**: Define the visual identity that signals institutional professionalism, not retail SaaS aesthetics. The visual language must support operational efficiency and institutional credibility.

---

## CORE VISUAL IDENTITY

**The visual identity is**:
- Institutional
- Professional
- Information-dense
- Low-decoration
- Bloomberg/Koyfin-inspired
- Anti-SaaS startup

**The visual identity is NOT**:
- Playful
- Decorative
- SaaS startup
- Retail-focused
- Colorful
- Gradient-heavy

---

## COLOR PHILOSOPHY

### Primary Colors

**Backgrounds**:
- Primary background: `#0A0E14` (very dark blue-black)
- Secondary background: `#111827` (dark gray-blue)
- Tertiary background: `#1F2937` (medium gray)
- Card background: `#1F2937` (same as tertiary)

**Why**: Dark backgrounds reduce eye strain, support long sessions, signal professional tools.

### Accent Colors

**Signal colors**:
- Positive/Growth: `#10B981` (emerald green)
- Negative/Deterioration: `#EF4444` (red)
- Neutral/Stable: `#6B7280` (gray)
- Warning: `#F59E0B` (amber)
- Critical: `#DC2626` (darker red)

**Usage rules**:
- Use green for positive transitions only
- Use red for deterioration and critical alerts
- Use amber for warnings and caution
- Use gray for neutral/missing data
- Never use colors for decoration

### Text Colors

**Primary text**: `#F9FAFB` (off-white)
- High contrast for readability
- Used for all primary content

**Secondary text**: `#D1D5DB` (light gray)
- Used for labels and secondary information

**Tertiary text**: `#9CA3AF` (medium gray)
- Used for metadata and timestamps

**Disabled text**: `#6B7280` (dark gray)
- Used for disabled states

### Anti-Color Rules

**Never use**:
- Purple, pink, orange, yellow as primary colors
- Gradients for UI elements
- Bright, saturated colors
- Pastel colors
- Rainbow color schemes
- Color for decoration only

**Why**: These signal retail/SaaS aesthetics, not institutional tools.

---

## TYPOGRAPHY

### Font Family

**Primary font**: Inter or system-ui
- Clean, professional, readable
- Excellent screen rendering
- Institutional feel

**Secondary font**: JetBrains Mono for data
- Monospace for numbers and code
- Tabular figures for alignment
- Professional data presentation

### Font Sizes

**Hierarchy**:
- H1: 32px (page titles)
- H2: 24px (section headers)
- H3: 18px (card titles)
- Body: 14px (primary content)
- Small: 12px (labels, metadata)
- XSmall: 11px (timestamps, footnotes)

**Usage**:
- Maintain strict hierarchy
- Never use size for emphasis alone
- Size indicates information importance

### Font Weights

**Weights**:
- Regular (400): Body text
- Medium (500): Emphasis
- Semibold (600): Headers
- Bold (700): Critical alerts

**Usage**:
- Weight indicates importance
- Don't overuse bold
- Maintain hierarchy

### Typography Rules

- Left-align everything (except numbers)
- Never center-align body text
- Use sentence case for headers
- Never use ALL CAPS for body text
- Line height: 1.5 for body, 1.2 for headers
- Letter spacing: normal (never tracked out)

---

## SPACING PHILOSOPHY

### Spacing Scale

**Base unit**: 4px

**Scale**:
- 4px: Tight spacing
- 8px: Small spacing
- 12px: Medium spacing
- 16px: Standard spacing
- 24px: Large spacing
- 32px: Extra large spacing
- 48px: Section spacing

### Usage Rules

- Use 8px between related elements
- Use 16px between unrelated elements
- Use 24px for section breaks
- Use 32px for major sections
- Never use arbitrary spacing

### Padding

- Card padding: 16px
- Button padding: 8px 16px
- Input padding: 8px 12px
- Modal padding: 24px

---

## COMPONENT DESIGN

### Buttons

**Primary buttons**:
- Background: `#10B981` (green)
- Text: white
- Padding: 8px 16px
- Border radius: 4px
- No shadows
- No gradients

**Secondary buttons**:
- Background: transparent
- Border: 1px solid `#374151`
- Text: `#F9FAFB`
- Padding: 8px 16px
- Border radius: 4px

**Destructive buttons**:
- Background: `#EF4444` (red)
- Text: white
- Padding: 8px 16px
- Border radius: 4px

**Button rules**:
- No gradients
- No shadows
- Minimal border radius (4px max)
- No icons unless necessary
- Clear, actionable labels

### Cards

**Setup cards**:
- Background: `#1F2937`
- Border: 1px solid `#374151`
- Border radius: 4px
- Padding: 16px
- Shadow: none
- Hover: border color `#4B5563`

**Card rules**:
- Minimal decoration
- Information-dense
- Consistent layout
- No shadows (flat design)
- No gradients

### Inputs

**Text inputs**:
- Background: `#111827`
- Border: 1px solid `#374151`
- Text: `#F9FAFB`
- Padding: 8px 12px
- Border radius: 4px
- Focus: border color `#10B981`

**Input rules**:
- No shadows
- No floating labels
- Minimal decoration
- Clear focus states

### Tables

**Table design**:
- Background: transparent
- Border: 1px solid `#374151`
- Header background: `#111827`
- Row hover: `#1F2937`
- Text: `#F9FAFB`

**Table rules**:
- Minimal borders
- No zebra striping
- Dense information
- No decoration
- Monospace font for numbers

---

## ICONOGRAPHY

### Icon Style

- Line icons (not filled)
- 2px stroke width
- Minimal detail
- No decorative icons
- Lucide or Heroicons

### Icon Usage

- Use icons only for functional purposes
- No decorative icons
- Consistent stroke width
- No colored icons (use text color)

### Anti-Icon Rules

- Never use filled icons
- Never use decorative icons
- Never use colored icons
- Never use emoji
- Never use illustration-style icons

---

## LAYOUT PHILOSOPHY

### Grid System

- 12-column grid
- 8px gutters
- Max width: 1400px
- Centered content

### Layout Patterns

**Single column**: Primary layout
- Full width content
- No sidebars
- No multi-column dashboards

**Card grid**: Setup display
- Responsive grid
- Minimum card width: 300px
- Maximum cards per row: 4

### Layout Rules

- No multi-panel dashboards
- No sidebars
- No floating panels
- No complex layouts
- Simple, linear flow

---

## VISUAL HIERARCHY

### Hierarchy Principles

1. **Size**: Larger = more important
2. **Color**: Higher contrast = more important
3. **Position**: Top/left = more important
4. **Weight**: Bolder = more important

### Hierarchy Implementation

**Critical signals**:
- Largest size
- Highest contrast
- Top position
- Bold weight

**Secondary signals**:
- Medium size
- Medium contrast
- Middle position
- Regular weight

**Tertiary signals**:
- Small size
- Low contrast
- Bottom position
- Regular weight

---

## ANIMATION PHILOSOPHY

### Animation Rules

- Minimal animation
- No decorative animations
- Functional animations only
- Duration: 150-300ms
- Easing: ease-out

### Allowed Animations

- Hover states (color change only)
- Focus states (border color)
- Loading states (spinner only)
- Modal fade (300ms)

### Forbidden Animations

- Bounce
- Shake
- Rotate
- Scale (except on hover)
- Decorative animations
- Page transitions

---

## DATA VISUALIZATION

### Chart Style

- Line charts for trends
- Bar charts for comparisons
- No pie charts
- No 3D charts
- Minimal decoration

### Chart Colors

- Single color per dataset
- Use accent colors
- No gradients
- No fills (lines only)

### Chart Rules

- Minimal axes
- No grid lines (or very subtle)
- No legends (label directly)
- No decorative elements
- Bloomberg-style simplicity

---

## DARK MODE

**This is a dark-mode only product.**

- No light mode
- Dark mode is the default and only mode
- All designs assume dark backgrounds
- High contrast is mandatory

---

## RESPONSIVE DESIGN

### Breakpoints

- Desktop: 1400px+ (primary)
- Laptop: 1024-1399px
- Tablet: 768-1023px (secondary)
- Mobile: < 768px (not supported)

### Responsive Strategy

- Desktop: Full functionality
- Tablet: Scanning and monitoring
- Mobile: Not supported (not the use case)

---

## ACCESSIBILITY

### Contrast Requirements

- WCAG AA minimum
- 4.5:1 for normal text
- 3:1 for large text
- 3:1 for UI components

### Accessibility Features

- Keyboard navigation
- Screen reader support
- Focus indicators
- Aria labels
- Semantic HTML

---

## ANTI-AESTHETICS

### What to Avoid

**SaaS startup aesthetics**:
- ❌ Gradients
- ❌ Shadows
- ❌ Rounded corners (beyond 4px)
- ❌ Bright colors
- ❌ Playful illustrations
- ❌ Decorative elements
- ❌ Marketing copy
- ❌ Feature highlights

**Retail aesthetics**:
- ❌ "Hot picks" styling
- ❌ Excitement-driven design
- ❌ Gamification
- ❌ Notification spam
- ❌ FOMO design

**Decoration**:
- ❌ Unnecessary borders
- ❌ Background patterns
- ❌ Decorative icons
- ❌ Ornamental elements

### What to Embrace

**Institutional aesthetics**:
- ✅ Minimal decoration
- ✅ High information density
- ✅ Professional typography
- ✅ Functional color
- ✅ Bloomberg-style simplicity
- ✅ Data-focused design
- ✅ Operational efficiency

---

## DESIGN SYSTEM MAINTENANCE

### Component Library

- All components documented
- Usage guidelines provided
- Code examples included
- Anti-patterns listed

### Design Tokens

- Colors as variables
- Spacing as scale
- Typography as system
- Documented in code

### Updates

- Visual language evolves slowly
- Changes require consensus
- Document rationale for changes
- Maintain institutional feel

---

## VERSION CONTROL

**Current version**: v1.0.0
**Last review**: [Date]
**Next review**: [Date]

**Versioning tracks visual identity changes**, not implementation details.

---

## EMERGENCY DESIGN CHECK

**If design feels wrong**:
1. Review all principles
2. Identify violations
3. Revert to principle-aligned state
4. Document the drift
5. Update anti-patterns if needed

**This document is the visual identity guide. All design must align.**

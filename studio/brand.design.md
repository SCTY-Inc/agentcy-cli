---
name: Agentcy Studio Renderer Defaults
version: "2.0"

grounds:
  cream: { bg: "#FFF7ED", fg: "#3F0F00", primary: "#632405", secondary: "#80421A", accent: "#FF8600", dark: false }
  ink: { bg: "#1C1C1C", fg: "#F8F1E6", primary: "#F8F1E6", accent: "#FF8600", dark: true }

platforms:
  linkedin: { w: 1200, h: 1200, label: "LinkedIn 1:1" }
  twitter: { w: 1600, h: 900, label: "X/Twitter 16:9" }
  instagram: { w: 1080, h: 1350, label: "Instagram 4:5" }
  facebook: { w: 1200, h: 1200, label: "Facebook 1:1" }
  threads: { w: 1080, h: 1350, label: "Threads 4:5" }
  story: { w: 1080, h: 1920, label: "Story 9:16" }
---

## Renderer Defaults

This file only defines fallback color grounds and output platform dimensions.

Brand aesthetics live in each brand's `DESIGN.md`. Platform entries are output formats, not layout families. The renderer must not use this file to choose split panels, posters, report layouts, or other hardcoded creative templates.

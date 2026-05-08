---
id: givecare
name: GiveCare
positioning: Care as infrastructure, not as soft marketing language.
audiences:
  - id: caregivers
    summary: Family caregivers carrying operational work across home, health, and employment.
offers:
  - id: invisiblebench
    summary: Research and tooling that make caregiving systems more legible.
    url: https://invisiblebench.givecareapp.com
    cta: "Explore at invisiblebench.givecareapp.com"
  - id: pulse
    summary: Weekly caregiving systems newsletter.
    url: https://pulse.givecareapp.com
    cta: "Sign up at pulse.givecareapp.com"
proof_points:
  - 63 million Americans are caregivers.
  - Caregiving is operational work, not just emotional labor.
  - The U.S. care economy is worth $470B+ in unpaid labor annually.
pillars:
  - id: ai-safety-ethics
    perspective: AI in caregiving touches vulnerable people. How it's built matters as much as what it does. Consent, data dignity, algorithmic bias, trauma-informed design.
    signals: [AI regulation, healthcare AI safety, EU AI Act, data privacy, algorithmic bias, AI in eldercare, consent frameworks]
    format: opinionated-take
    frequency: weekly
  - id: policy-advocacy
    perspective: The systems that should support caregivers — legislation, funding, institutional programs — and whether they actually do.
    signals: [RAISE Act, ACL programs, MAHA ELEVATE, state caregiver legislation, CBO funding, Medicaid waivers, paid leave policy]
    format: analysis
    frequency: weekly
  - id: care-economy
    perspective: "Caregiving is infrastructure. 63 million people do this work. Here's the structural reality: who does it, what it costs, what breaks when it's invisible."
    signals: [BLS data, caregiver workforce studies, economic impact reports, time-use data, employer caregiver benefits, care deserts]
    format: data-driven
    frequency: weekly
    default_format: infographic
voice:
  tone: Warm, direct, grounded.
  style: Plainspoken, human, specific.
  do:
    - Name the structural problem directly.
    - Use concrete consequences and real-world language.
  dont:
    - Use therapeutic cliches.
    - Hide behind polished abstractions.
channels:
  social:
    objective: Build signal and authority around caregiving systems.
    platforms: [twitter, linkedin, instagram, threads]
    default_offer: pulse
  blog:
    objective: Publish durable thinking that sharpens the category.
  outreach:
    objective: Start useful conversations with partners, buyers, and institutions.
  respond:
    objective: Reply with care, clarity, and evidence.
formats:
  - id: standard
    description: editorial post with hook/body/cta and brand image
  - id: infographic
    description: data visualization with stat headline and key figures
    prompt_overlay: |
      Extract 3-5 concrete statistics or data points about the topic.
      Lead with the most surprising number. Visualize as a vertical
      infographic using brand palette. No decorative filler.
  - id: quote-card
    description: typographic pull-quote on textured background
    prompt_overlay: |
      Extract the single strongest claim or quote.
      Render as bold typography on a textured warm background.
      One line, maximum impact.
response_playbooks:
  - id: skeptical-comment
    trigger: skepticism
    approach: Clarify the claim, add evidence, and stay calm.
outreach_playbooks:
  - id: intro
    trigger: first-touch
    approach: Lead with one sharp observation and one clear ask.
---

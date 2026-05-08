#!/usr/bin/env node
/**
 * extract — brand scaffold generator
 *
 * Extracts visual tokens + page metadata from a URL, generates a full brand
 * directory with DESIGN.md (Google Labs spec) and BRAND.md (SCTY spec).
 *
 * Usage: node extract.mjs <url> --brand <name>
 *        node extract.mjs <url> --out design.md   (design.md only, no scaffold)
 */

import puppeteer from "puppeteer-core";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { execSync } from "child_process";
import { join, resolve } from "path";

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "/home/deploy/.cache/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-linux64/chrome-headless-shell",
  ];
  for (const c of candidates) {
    if (c && existsSync(c)) return c;
  }
  try {
    return execSync("which google-chrome chromium chromium-browser 2>/dev/null", { encoding: "utf-8" }).trim().split("\n")[0];
  } catch { /* ignore */ }
  throw new Error("No Chrome found. Set CHROME_PATH or install chromium.");
}

function findBrandsDir() {
  let dir = process.cwd();
  while (dir !== "/") {
    if (existsSync(join(dir, "brands"))) return join(dir, "brands");
    if (existsSync(join(dir, "pyproject.toml"))) return join(dir, "brands");
    dir = resolve(dir, "..");
  }
  return join(process.cwd(), "brands");
}

const SELECTORS = [
  "h1","h2","h3","h4","h5","h6",
  "p","a","button","input","textarea","select",
  "nav","header","footer","main","section","article",
  "li","td","th","label","span","div",
  "img","svg","video",
  "[class*=card]","[class*=btn]","[class*=hero]","[class*=container]",
  "[class*=modal]","[class*=badge]","[class*=chip]","[class*=tag]",
];

function extractStyles() {
  const selectors = window.__SELECTORS__;
  const seen = new Set();
  const results = { colors: {}, typography: {}, spacing: [], radii: [], shadows: [], elements: [], headings: [], links: [], buttons: [] };

  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el) || seen.size > 300) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      const cs = window.getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      seen.add(el);

      const tag = el.tagName.toLowerCase();
      const text = (el.textContent || "").trim().slice(0, 120);

      for (const prop of ["color", "backgroundColor", "borderColor"]) {
        const v = cs[prop];
        if (v && v !== "rgba(0, 0, 0, 0)" && v !== "transparent") {
          results.colors[v] = (results.colors[v] || 0) + 1;
        }
      }

      const typo = {
        fontFamily: cs.fontFamily,
        fontSize: cs.fontSize,
        fontWeight: cs.fontWeight,
        lineHeight: cs.lineHeight,
        letterSpacing: cs.letterSpacing,
      };
      const key = JSON.stringify(typo);
      if (!results.typography[key]) results.typography[key] = { ...typo, count: 0, tags: [] };
      results.typography[key].count++;
      if (!results.typography[key].tags.includes(tag)) results.typography[key].tags.push(tag);

      for (const side of ["Top", "Right", "Bottom", "Left"]) {
        const m = cs[`margin${side}`];
        const p = cs[`padding${side}`];
        if (m && m !== "0px") results.spacing.push(m);
        if (p && p !== "0px") results.spacing.push(p);
      }

      const r = cs.borderRadius;
      if (r && r !== "0px") results.radii.push(r);

      const s = cs.boxShadow;
      if (s && s !== "none") results.shadows.push(s);

      if (/^h[1-6]$/.test(tag) && text) results.headings.push(text.slice(0, 80));
      if (tag === "a" && text) results.links.push(text.slice(0, 60));
      if (tag === "button" && text) results.buttons.push(text.slice(0, 60));

      results.elements.push({ tag, text: text.slice(0, 40) });
    }
  }

  const title = document.title;
  const desc = document.querySelector('meta[name="description"]')?.content || "";
  const ogTitle = document.querySelector('meta[property="og:title"]')?.content || "";
  const ogDesc = document.querySelector('meta[property="og:description"]')?.content || "";
  const bodyText = document.body?.innerText?.slice(0, 2000) || "";

  return { ...results, meta: { title, description: desc || ogDesc, ogTitle, bodyText } };
}

// --- Normalization ---

function rgbToHex(rgb) {
  const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return rgb;
  return "#" + [m[1], m[2], m[3]].map((n) => parseInt(n).toString(16).padStart(2, "0")).join("");
}

function freqSort(arr) {
  const counts = {};
  for (const v of arr) counts[v] = (counts[v] || 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([v]) => v);
}

function normalizeColors(raw) {
  const entries = Object.entries(raw).sort((a, b) => b[1] - a[1]);
  const hexes = entries.map(([c]) => rgbToHex(c)).filter((h) => h.startsWith("#"));
  const unique = [...new Set(hexes)];
  const names = ["primary", "secondary", "tertiary", "surface", "on-surface", "neutral", "accent", "error"];
  const result = {};
  for (let i = 0; i < Math.min(unique.length, names.length); i++) {
    result[names[i]] = unique[i];
  }
  return result;
}

function normalizeTypography(raw) {
  const entries = Object.values(raw).sort((a, b) => b.count - a.count);
  const names = ["body", "heading-1", "heading-2", "heading-3", "label", "caption", "mono"];
  const result = {};
  for (let i = 0; i < Math.min(entries.length, names.length); i++) {
    const e = entries[i];
    const name = e.tags.some((t) => /^h[1-3]$/.test(t))
      ? `heading-${e.tags.find((t) => /^h\d$/.test(t))?.slice(1) || i + 1}`
      : names[i];
    result[name] = {
      fontFamily: e.fontFamily.split(",")[0].replace(/['"]/g, "").trim(),
      fontSize: e.fontSize,
      fontWeight: e.fontWeight,
      lineHeight: e.lineHeight,
    };
    if (e.letterSpacing && e.letterSpacing !== "normal") {
      result[name].letterSpacing = e.letterSpacing;
    }
  }
  return result;
}

function normalizeSpacing(raw) {
  const sorted = freqSort(raw).filter((v) => v !== "0px").slice(0, 8);
  const pxVals = sorted.map((v) => parseFloat(v)).filter((n) => !isNaN(n)).sort((a, b) => a - b);
  const unique = [...new Set(pxVals)];
  const names = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "4xl"];
  const result = {};
  for (let i = 0; i < Math.min(unique.length, names.length); i++) {
    result[names[i]] = `${unique[i]}px`;
  }
  return result;
}

function normalizeRadii(raw) {
  const sorted = freqSort(raw).slice(0, 5);
  const names = ["sm", "md", "lg", "xl", "full"];
  const result = {};
  for (let i = 0; i < sorted.length; i++) result[names[i]] = sorted[i];
  return result;
}

// --- YAML ---

function yamlValue(v) {
  if (typeof v === "string") return `"${v}"`;
  return String(v);
}

function toYaml(obj, indent = 0) {
  const pad = "  ".repeat(indent);
  let out = "";
  for (const [k, v] of Object.entries(obj)) {
    if (Array.isArray(v)) {
      if (v.length === 0) {
        out += `${pad}${k}: []\n`;
      } else if (typeof v[0] === "object" && v[0] !== null) {
        out += `${pad}${k}:\n`;
        for (const item of v) {
          const lines = toYaml(item, indent + 2).split("\n").filter(Boolean);
          out += `${pad}  - ${lines[0].trim()}\n`;
          for (const line of lines.slice(1)) out += `${pad}    ${line.trim()}\n`;
        }
      } else {
        out += `${pad}${k}:\n${v.map((item) => `${pad}  - ${yamlValue(item)}`).join("\n")}\n`;
      }
    } else if (typeof v === "object" && v !== null) {
      out += `${pad}${k}:\n${toYaml(v, indent + 1)}`;
    } else {
      out += `${pad}${k}: ${yamlValue(v)}\n`;
    }
  }
  return out;
}

// --- DESIGN.md (Google Labs spec) ---

function generateDesignMd(data) {
  const colors = normalizeColors(data.colors);
  const typography = normalizeTypography(data.typography);
  const spacing = normalizeSpacing(data.spacing);
  const rounded = normalizeRadii(data.radii);
  const shadows = freqSort(data.shadows).slice(0, 3);

  const frontmatter = { name: data.meta.title || "Untitled", version: "alpha", description: data.meta.description || "", colors, typography, spacing, rounded };

  const colorTable = Object.entries(colors).map(([n, h]) => `| \`${n}\` | \`${h}\` |`).join("\n");
  const typoTable = Object.entries(typography).map(([n, t]) => `| \`${n}\` | ${t.fontFamily} | ${t.fontSize} | ${t.fontWeight} |`).join("\n");
  const spacingTable = Object.entries(spacing).map(([n, v]) => `| \`${n}\` | ${v} |`).join("\n");
  const radiusTable = Object.entries(rounded).map(([n, v]) => `| \`${n}\` | ${v} |`).join("\n");

  return `---
${toYaml(frontmatter).trim()}
---

## Overview

Design tokens extracted from **${data.meta.title || "page"}**.

${data.meta.description ? `> ${data.meta.description}` : ""}

## Colors

| Token | Value |
|-------|-------|
${colorTable}

## Typography

| Token | Family | Size | Weight |
|-------|--------|------|--------|
${typoTable}

## Layout & Spacing

| Token | Value |
|-------|-------|
${spacingTable}

## Shapes

| Token | Radius |
|-------|--------|
${radiusTable}
${shadows.length > 0 ? `\n## Elevation & Depth\n\n${shadows.map((s) => `- \`${s}\``).join("\n")}\n` : ""}
## Do's and Don'ts

- **Do** use extracted tokens as a starting point
- **Do** verify contrast ratios meet WCAG AA
- **Don't** assume extracted values are intentional design decisions
`;
}

// --- BRAND.md (SCTY brand.md spec v0.3) ---

function generateBrandMd(data, brandName) {
  const name = data.meta.ogTitle || data.meta.title?.split(/[|\-–—]/)[0]?.trim() || brandName;
  const description = data.meta.description || "";
  const positioning = description.slice(0, 140) || `${name} — extracted brand scaffold.`;

  const headings = [...new Set(data.headings || [])].slice(0, 5);
  const ctas = [...new Set(data.buttons || [])].filter((t) => t.length > 2).slice(0, 3);

  const frontmatter = {
    name,
    positioning,
    voice: {
      tone: ["direct", "clear"],
      style: ["concise", "specific"],
      pov: "reader",
      do: ["Speak plainly about what the product does"],
      dont: ["Use vague marketing language"],
    },
    audience: {
      primary: "Extracted — review and refine",
    },
    message: {
      core_claim: positioning,
      proof_points: headings.length > 0 ? headings.slice(0, 3) : ["Review and add proof points"],
    },
    topics: {
      pillars: [
        {
          id: "primary",
          angle: "Review and define the primary content angle",
          signals: ["Review and add signals to monitor"],
        },
      ],
    },
    behavior: {
      create: ["Review and define content creation triggers"],
      avoid: ["Off-brand messaging", "Unverified claims"],
      escalate: ["Anything touching legal, health, or financial claims"],
    },
    safety: {
      risk_tolerance: "moderate",
      forbidden_claims: [],
      escalate: ["Crisis situations", "Legal questions"],
      delegation: {
        autonomous: ["Content drafting", "Signal monitoring"],
        human_required: ["Publishing", "Responses to complaints"],
      },
    },
  };

  if (ctas.length > 0) {
    frontmatter.offer = { core: ctas[0], cta: ctas[0] };
  }

  return `---
${toYaml(frontmatter).trim()}
---

## Overview

Brand contract for **${name}**. ${description}

This file was scaffolded from ${data.meta.title}. Review all sections and replace placeholder values.

## Voice

${frontmatter.voice.tone.join(", ")}. Speak to the reader, not about the brand.

## Audience

Review and define primary and secondary audience segments with pain points and goals.

## Topics

Define content pillars — the recurring angles this brand should own.
${headings.length > 0 ? `\nExtracted headings for reference:\n${headings.map((h) => `- ${h}`).join("\n")}` : ""}

## Behavior

Define when to create, engage, amplify, and what to avoid. Every engage rule needs a matching escalation path.

## Safety

Review risk tolerance, forbidden claims, and delegation boundaries. Add sensitive topics relevant to this industry.

## Do's and Don'ts

- **Do** review every scaffolded field before using in production
- **Do** add industry-specific safety constraints
- **Don't** deploy this scaffold without human review
- **Don't** remove the escalation rules without replacing them
`;
}

// --- Main ---

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("-"));
  const brandIdx = args.indexOf("--brand");
  const brandName = brandIdx !== -1 ? args[brandIdx + 1] : null;
  const outIdx = args.indexOf("--out");
  const outPath = outIdx !== -1 ? args[outIdx + 1] : null;

  if (!url) {
    console.error("Usage: node extract.mjs <url> --brand <name>");
    console.error("       node extract.mjs <url> --out design.md");
    process.exit(1);
  }

  console.error(`Extracting from ${url}...`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: findChrome(),
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });

    await page.evaluate((sels) => { window.__SELECTORS__ = sels; }, SELECTORS);
    const data = await page.evaluate(extractStyles);

    const designMd = generateDesignMd(data);

    if (brandName) {
      const brandsDir = findBrandsDir();
      const brandDir = join(brandsDir, brandName);

      if (existsSync(join(brandDir, "brand.md"))) {
        console.error(`Brand already exists at ${brandDir} — writing design.md only`);
        writeFileSync(join(brandDir, "design.md"), designMd);
        console.error(`Wrote ${join(brandDir, "design.md")}`);
        return;
      }

      for (const sub of ["", "assets", "input", "output"]) {
        mkdirSync(join(brandDir, sub), { recursive: true });
      }

      writeFileSync(join(brandDir, "design.md"), designMd);
      writeFileSync(join(brandDir, "brand.md"), generateBrandMd(data, brandName));

      console.error(`Created brand scaffold at ${brandDir}/`);
      console.error(`  design.md  — extracted visual tokens`);
      console.error(`  brand.md   — behavioral contract (review and refine)`);
      console.error(`  assets/    — logos, fonts`);
      console.error(`  input/     — briefs, docs`);
      console.error(`  output/    — rendered media (gitignored)`);
    } else if (outPath) {
      writeFileSync(outPath, designMd);
      console.error(`Wrote ${outPath}`);
    } else {
      process.stdout.write(designMd);
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});

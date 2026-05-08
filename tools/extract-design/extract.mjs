#!/usr/bin/env node
/**
 * extract-design — headless design.md generator
 *
 * Takes a URL, extracts computed styles via Puppeteer, outputs a design.md
 * in the Google Labs design.md spec format (YAML frontmatter + markdown body).
 *
 * Usage: node extract.mjs <url> [--out design.md]
 */

import puppeteer from "puppeteer-core";
import { writeFileSync, existsSync } from "fs";
import { execSync } from "child_process";

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

const SELECTORS = [
  "h1","h2","h3","h4","h5","h6",
  "p","a","button","input","textarea","select",
  "nav","header","footer","main","section","article",
  "li","td","th","label","span","div",
  "img","svg","video",
  "[class*=card]","[class*=btn]","[class*=hero]","[class*=container]",
  "[class*=modal]","[class*=badge]","[class*=chip]","[class*=tag]",
];

// --- DOM extraction (runs inside the page) ---

function extractStyles() {
  const selectors = window.__SELECTORS__;
  const seen = new Set();
  const results = { colors: {}, typography: {}, spacing: [], radii: [], shadows: [], elements: [] };

  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el) || seen.size > 300) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      const cs = window.getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      seen.add(el);

      const tag = el.tagName.toLowerCase();
      const text = (el.textContent || "").trim().slice(0, 80);

      // colors
      for (const prop of ["color", "backgroundColor", "borderColor"]) {
        const v = cs[prop];
        if (v && v !== "rgba(0, 0, 0, 0)" && v !== "transparent") {
          results.colors[v] = (results.colors[v] || 0) + 1;
        }
      }

      // typography
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

      // spacing
      for (const side of ["Top", "Right", "Bottom", "Left"]) {
        const m = cs[`margin${side}`];
        const p = cs[`padding${side}`];
        if (m && m !== "0px") results.spacing.push(m);
        if (p && p !== "0px") results.spacing.push(p);
      }

      // radii
      const r = cs.borderRadius;
      if (r && r !== "0px") results.radii.push(r);

      // shadows
      const s = cs.boxShadow;
      if (s && s !== "none") results.shadows.push(s);

      results.elements.push({ tag, text: text.slice(0, 40) });
    }
  }

  // meta
  const title = document.title;
  const desc = document.querySelector('meta[name="description"]')?.content || "";
  const favicon = document.querySelector('link[rel="icon"]')?.href || "";

  return { ...results, meta: { title, description: desc, favicon } };
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
  for (let i = names.length; i < unique.length && i < 12; i++) {
    result[`color-${i + 1}`] = unique[i];
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
  for (let i = 0; i < sorted.length; i++) {
    result[names[i]] = sorted[i];
  }
  return result;
}

// --- YAML serialization (no deps) ---

function yamlValue(v) {
  if (typeof v === "string") return `"${v}"`;
  return String(v);
}

function toYaml(obj, indent = 0) {
  const pad = "  ".repeat(indent);
  let out = "";
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === "object" && v !== null && !Array.isArray(v)) {
      out += `${pad}${k}:\n${toYaml(v, indent + 1)}`;
    } else {
      out += `${pad}${k}: ${yamlValue(v)}\n`;
    }
  }
  return out;
}

// --- Markdown generation ---

function generateDesignMd(data) {
  const colors = normalizeColors(data.colors);
  const typography = normalizeTypography(data.typography);
  const spacing = normalizeSpacing(data.spacing);
  const rounded = normalizeRadii(data.radii);
  const shadows = freqSort(data.shadows).slice(0, 3);

  const frontmatter = {
    name: data.meta.title || "Untitled",
    version: "alpha",
    description: data.meta.description || `Design tokens extracted from ${data.meta.title}`,
    colors,
    typography,
    spacing,
    rounded,
  };

  const colorTable = Object.entries(colors)
    .map(([name, hex]) => `| \`${name}\` | \`${hex}\` | ![](https://via.placeholder.com/16/${hex.slice(1)}/${hex.slice(1)}) |`)
    .join("\n");

  const typoTable = Object.entries(typography)
    .map(([name, t]) => `| \`${name}\` | ${t.fontFamily} | ${t.fontSize} | ${t.fontWeight} | ${t.lineHeight} |`)
    .join("\n");

  const spacingTable = Object.entries(spacing)
    .map(([name, val]) => `| \`${name}\` | ${val} |`)
    .join("\n");

  const radiusTable = Object.entries(rounded)
    .map(([name, val]) => `| \`${name}\` | ${val} |`)
    .join("\n");

  return `---
${toYaml(frontmatter).trim()}
---

## Overview

Design tokens extracted from **${data.meta.title || "page"}**.

${data.meta.description ? `> ${data.meta.description}` : ""}

## Colors

| Token | Value | Swatch |
|-------|-------|--------|
${colorTable}

## Typography

| Token | Family | Size | Weight | Line Height |
|-------|--------|------|--------|-------------|
${typoTable}

## Layout & Spacing

| Token | Value |
|-------|-------|
${spacingTable}

## Shapes

| Token | Radius |
|-------|--------|
${radiusTable}

${shadows.length > 0 ? `## Elevation & Depth\n\nExtracted shadows:\n${shadows.map((s) => `- \`${s}\``).join("\n")}\n` : ""}

## Components

${[...new Set(data.elements.map((e) => e.tag))].slice(0, 15).map((t) => `- \`${t}\``).join("\n")}

## Do's and Don'ts

- **Do** use the extracted tokens as a starting point, not a final spec
- **Do** verify contrast ratios meet WCAG AA (4.5:1 for text)
- **Don't** assume extracted values represent intentional design decisions
- **Don't** use colors that appear only once — they may be artifacts
`;
}

// --- Main ---

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("-"));
  const outIdx = args.indexOf("--out");
  const outPath = outIdx !== -1 ? args[outIdx + 1] : null;

  if (!url) {
    console.error("Usage: extract-design <url> [--out design.md]");
    process.exit(1);
  }

  console.error(`Extracting design tokens from ${url}...`);

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

    const md = generateDesignMd(data);

    if (outPath) {
      writeFileSync(outPath, md);
      console.error(`Wrote ${outPath}`);
    } else {
      process.stdout.write(md);
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});

// Renders the PNG app icons with Playwright (exact sizes, transparent "any" icons, full-bleed maskable).
// Source: ../landing/brand/icon.svg (the brand logo) when it exists, else static/favicon.svg. Run: npm run icons
import { chromium } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';

const source = existsSync('../landing/brand/icon.svg') ? '../landing/brand/icon.svg' : 'static/favicon.svg';
const svg = readFileSync(source, 'utf8');
const any = (s) => `<body style="margin:0;background:transparent">${svg.replace('<svg ', `<svg width="${s}" height="${s}" style="display:block" `)}</body>`;
const mask = (s) => `<body style="margin:0;background:#0f766e;display:flex;align-items:center;justify-content:center;width:${s}px;height:${s}px">${svg.replace('<svg ', `<svg width="${Math.round(s * 0.72)}" height="${Math.round(s * 0.72)}" `)}</body>`;
const browser = await chromium.launch();
for (const [file, size, html] of [['icon-192.png', 192, any], ['icon-512.png', 512, any], ['maskable-512.png', 512, mask], ['apple-touch-icon.png', 180, mask]]) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(html(size));
  await page.screenshot({ path: `static/icons/${file}`, omitBackground: true });
  await page.close();
}
await browser.close();
console.log(`icons rendered from ${source}`);

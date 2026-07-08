// screenshot.js -- optional Playwright helper for the design-to-react verify loop.
//
// Screenshots a list of routes from a running dev server so you can compare the
// generated UI against the source design (Figma reference PNG or the input image).
//
// Setup (run once, in any temp dir or the project):
//   npm install playwright
//   npx playwright install chromium
//
// Usage:
//   node screenshot.js --base http://localhost:3000 --out ./.design-cache/rendered \
//     --routes /dashboard,/products,/tasks
//
// Notes:
//   - Pass routes WITHOUT the basePath if the framework prepends one automatically.
//   - Full-page screenshots are captured at 1440x900 by default.

const { chromium } = require('playwright');

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

(async () => {
  const base = arg('base', 'http://localhost:3000').replace(/\/$/, '');
  const outDir = arg('out', './.design-cache/rendered');
  const width = parseInt(arg('width', '1440'), 10);
  const height = parseInt(arg('height', '900'), 10);
  const routes = arg('routes', '/')
    .split(',')
    .map((r) => r.trim())
    .filter(Boolean);

  const fs = require('fs');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width, height });

  for (const route of routes) {
    const url = `${base}${route.startsWith('/') ? route : '/' + route}`;
    const safe = route.replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'root';
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
      await page.screenshot({ path: `${outDir}/${safe}.png`, fullPage: true });
      console.log('captured:', route, '->', `${outDir}/${safe}.png`);
    } catch (err) {
      console.error('FAILED:', route, err.message);
    }
  }

  await browser.close();
})();

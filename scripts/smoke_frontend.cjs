// Optional UI smoke test: NODE_PATH may point to a provided Playwright runtime.
const { chromium } = require('playwright');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // Exercise the explicit downloaded-observations mode without a database.
  const fixtureTile = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#8395a0'; ctx.fillRect(0, 0, 256, 256);
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await page.route('https://tile.openstreetmap.org/**', route => route.fulfill({ contentType: 'image/png', body: Buffer.from(fixtureTile, 'base64') }));
  await page.route('**/api/v1/**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Database unavailable in snapshot smoke test' }) }));
  await page.goto(process.env.SMOKE_BASE_URL || 'http://127.0.0.1:5188', { waitUntil: 'networkidle' });
  await page.getByRole('link', { name: 'NASA + OSM snapshot', exact: true }).click();
  await page.getByText('NASA observation snapshot', { exact: false }).waitFor();
  await page.locator('canvas.maplibregl-canvas').waitFor();
  await page.waitForTimeout(2500);
  await page.waitForFunction(() => document.querySelector('.map-hud')?.textContent?.includes('ZOOM 10'));
  if (await page.locator('.map-error').count()) throw new Error('Map layer render error');
  const text = await page.locator('body').innerText();
  if (!text.includes('2782') || !text.includes('10 mapped facilities')) throw new Error('Observed snapshot counts missing');
  await page.getByRole('button', { name: 'Cluster', exact: true }).click();
  await page.getByRole('button', { name: 'Clustering Active', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Heatmap', exact: true }).click();
  await page.waitForTimeout(1000);
  await page.getByRole('button', { name: 'Timeline Replay', exact: true }).click();
  await page.getByRole('slider', { name: 'Acquisition timeline' }).fill('50');
  if (!(await page.locator('body').innerText()).includes('51 / 2782')) throw new Error('Timeline replay failed');
  await page.getByRole('button', { name: 'Replay Active', exact: true }).click();
  await page.screenshot({ path: path.join(__dirname, '../data/processed/operations-preview.png'), fullPage: true });
  await page.getByRole('link', { name: 'Model Intelligence' }).click();
  await page.getByText('Not evaluated', { exact: true }).first().waitFor();
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('UI smoke passed: observed snapshot navigation, map overlays (fixture basemap tiles), timeline replay, 2782 NASA detections, 10 OSM facilities, honest missing metrics; no uncaught page errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });

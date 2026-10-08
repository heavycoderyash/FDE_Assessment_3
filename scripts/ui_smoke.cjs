// Isolated headless test browser: never attaches to a user's browser/profile.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const baseURL = process.env.APP_URL || 'http://127.0.0.1:8501';
const screenshotDir = path.resolve(__dirname, '../docs/screenshots');

(async () => {
  const downloads = await fs.mkdtemp(path.join(os.tmpdir(), 'procure-ui-'));
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const checks = [];
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1120}, acceptDownloads: true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(baseURL);
    await page.locator('.request-item').last().waitFor();
    assert.equal(await page.locator('.request-item').count(), 10);
    assert.equal(await page.locator('#mode').inputValue(), 'offline');
    checks.push('workspace loads ten sample requests in offline mode');

    async function analyze(id, expected, architecture = 'single') {
      await page.locator(`.request-item[data-id="${id}"]`).click();
      await page.locator('.settings').evaluate(el => { el.open = true; });
      await page.locator('#architecture').selectOption(architecture);
      await page.getByRole('button', {name: 'Analyze request'}).click();
      await page.locator('#analysis-result').waitFor({state: 'visible'});
      assert.equal(await page.locator('#recommendation').innerText(), expected);
      await page.getByRole('button', {name: 'Analyze request'}).waitFor();
    }

    await analyze('REQ-1008', 'Check an existing tool first');
    assert.match(await page.locator('#next-step').innerText(), /unused license availability/);
    checks.push('existing catalog option produces a grounded license-fit handoff');

    const downloadEvent = page.waitForEvent('download');
    await page.locator('#handoff-button').click();
    const download = await downloadEvent;
    const handoffPath = path.join(downloads, 'handoff.json');
    await download.saveAs(handoffPath);
    const handoff = JSON.parse(await fs.readFile(handoffPath, 'utf8'));
    assert.equal(handoff.purchase_authorized, false);
    assert.equal(handoff.request.request_id, 'REQ-1008');
    assert.ok(handoff.reviewers.every(reviewer => reviewer.status === 'pending'));
    checks.push('downloaded handoff contains the analyzed request and pending human reviews');

    await analyze('REQ-1006', 'Request clarification', 'staged');
    assert.match(await page.locator('#missing-list').innerText(), /Annual cost/);
    assert.match(await page.locator('#risks').innerText(), /prompt injection detected/);
    assert.match(await page.locator('#metrics').innerText(), /0 LLM calls/);
    checks.push('staged incomplete/injected request asks for information and keeps zero LLM calls');

    await analyze('REQ-1009', 'Hold for manual evidence review');
    assert.match(await page.locator('#risks').innerText(), /vendor risk unavailable/);
    checks.push('real vendor HTTP outage is visible in the UI');

    await page.locator('#new-request').click();
    await page.locator('#requester').selectOption('E004');
    await page.locator('#product').fill('<img src=x onerror="window.injected=true"> Training');
    await page.locator('#vendor').fill('SignFlow');
    await page.locator('#category').fill('Professional Services');
    await page.locator('#cost').fill('950');
    await page.locator('#users').fill('12');
    await page.locator('#purpose').fill('Training package for additional Finance users.');
    await page.locator('#data-level').selectOption('none');
    await page.getByRole('button', {name: 'Analyze request'}).click();
    await page.locator('#analysis-result').waitFor({state: 'visible'});
    assert.equal(await page.evaluate(() => window.injected), undefined);
    assert.equal(await page.locator('#recommendation').innerText(), 'Route for required human reviews');
    checks.push('custom request analyzes successfully and HTML-looking input remains inert');

    await analyze('REQ-1005', 'Route for required human reviews');
    await page.locator('.settings').evaluate(el => { el.open = false; });
    await page.evaluate(() => window.scrollTo(0, 0));
    await fs.mkdir(screenshotDir, {recursive: true});
    await page.screenshot({path: path.join(screenshotDir, 'desktop.png')});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(screenshotDir, 'mobile.png'), fullPage: true});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    checks.push('desktop and mobile layouts render without horizontal page overflow');
    assert.deepEqual(errors, []);
    checks.push('no uncaught browser JavaScript errors');
    await fs.writeFile(path.join(screenshotDir, 'ui-verification.json'), JSON.stringify({checked_at: new Date().toISOString(), checks, passed: true}, null, 2) + '\n');
    console.log(`PASS: ${checks.length} UI checks`);
    for (const check of checks) console.log(`  - ${check}`);
  } finally {
    await browser.close();
    await fs.rm(downloads, {recursive: true, force: true});
  }
})().catch(error => {console.error(error); process.exitCode = 1;});

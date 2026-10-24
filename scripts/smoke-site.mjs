import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const pages = {
  '/index.html': await readFile(new URL('../index.html', import.meta.url)),
  '/index-en.html': await readFile(new URL('../index-en.html', import.meta.url)),
};
const server = createServer((request, response) => {
  if (request.url === '/favicon.ico') { response.writeHead(204).end(); return; }
  const pathname = new URL(request.url, 'http://localhost').pathname;
  const html = pages[pathname === '/' ? '/index.html' : pathname];
  if (!html) { response.writeHead(404).end(); return; }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
  response.end(html);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const localChromium = process.env.CHROMIUM_EXECUTABLE_PATH;
const browser = await chromium.launch(localChromium ? {
  executablePath: localChromium,
  args: ['--no-sandbox'],
} : {});
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.on('pageerror', error => errors.push(error.message));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const routes = ['home', 'lessons', 'lesson/1/0', 'practice', 'lab', 'tool', 'glossary', 'sources', 'progress'];
  for (const [filename, lang, dir] of [['index.html', 'he', 'rtl'], ['index-en.html', 'en', 'ltr']]) {
    for (const route of routes) {
      await page.goto(`${origin}/${filename}#${route}`);
      await page.locator('#main h1').waitFor();
      assert.equal(await page.locator('html').getAttribute('lang'), lang);
      assert.equal(await page.locator('html').getAttribute('dir'), dir);
      assert.ok((await page.locator('#main').innerText()).trim().length > 30, `${filename}#${route} must render useful content.`);
      assert.deepEqual(errors, [], `${filename}#${route} raised a browser error.`);
      console.log(`PASS ${filename}#${route}`);
    }
  }
  await page.goto(`${origin}/index.html#lesson/1/2`);
  await page.locator('[data-lang-switch]').click();
  await page.waitForURL('**/index-en.html#lesson/1/2');
  assert.equal(await page.locator('html').getAttribute('lang'), 'en');
  await page.locator('[data-lang-switch]').click();
  await page.waitForURL('**/index.html#lesson/1/2');
  assert.equal(await page.locator('html').getAttribute('lang'), 'he');
  assert.deepEqual(errors, [], 'Language switching raised a browser error.');
  console.log('PASS bilingual language switching');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}

import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const html = await readFile(new URL('../index.html', import.meta.url));
const server = createServer((request, response) => {
  if (request.url === '/favicon.ico') { response.writeHead(204).end(); return; }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
  response.end(html);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch();
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.on('pageerror', error => errors.push(error.message));
  const origin = `http://127.0.0.1:${server.address().port}`;
  for (const route of ['home', 'lessons', 'lesson/1/0', 'practice', 'lab', 'tool', 'glossary', 'sources', 'progress']) {
    await page.goto(`${origin}/#${route}`);
    await page.locator('#main').locator('h1').waitFor();
    assert.ok((await page.locator('#main').innerText()).trim().length > 30, `${route} must render useful content.`);
    assert.deepEqual(errors, [], `${route} raised a browser error.`);
    console.log(`PASS #${route}`);
  }
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}

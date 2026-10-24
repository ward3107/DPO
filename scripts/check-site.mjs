import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Script } from 'node:vm';

const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
assert.match(html, /<!doctype html>/i, 'The entry point must be an HTML document.');
assert.match(html, /<html\b[^>]*lang=["']he["'][^>]*dir=["']rtl["']/i, 'Preserve Hebrew RTL document semantics.');
assert.match(html, /<title>[^<]+<\/title>/i, 'The page needs an accessible title.');
assert.match(html, /\bid=["']main["']/, 'The app mounting target is required.');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
let executable = 0;
let data = 0;
for (const [, attrs, source] of scripts) {
  if (/type=["']application\/json["']/i.test(attrs)) {
    const payload = JSON.parse(source);
    assert.ok(payload && typeof payload === 'object', 'Embedded data must be valid JSON.');
    if (/id=["']course-data["']/.test(attrs)) {
      for (const key of ['lessons', 'modules', 'sources', 'lab']) {
        assert.ok(Array.isArray(payload[key]) && payload[key].length > 0, `Course ${key} must be available.`);
      }
    }
    data += 1;
  } else if (!/\bsrc=/.test(attrs)) {
    new Script(source, { filename: `index.html:inline-${executable + 1}` });
    executable += 1;
  }
}
assert.ok(executable > 0 && data > 0, 'The application and its embedded course data must exist.');
console.log(`Validated document, ${data} JSON data blocks and ${executable} executable script(s).`);

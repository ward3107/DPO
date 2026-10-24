import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Script } from 'node:vm';

async function check(filename, lang, dir) {
  const html = await readFile(new URL(`../${filename}`, import.meta.url), 'utf8');
  assert.match(html, /<!doctype html>/i, `${filename} must be an HTML document.`);
  assert.match(html, new RegExp(`<html\\b[^>]*lang=["']${lang}["'][^>]*dir=["']${dir}["']`, 'i'), `${filename} needs ${lang}/${dir} document semantics.`);
  assert.match(html, /<title>[^<]+<\/title>/i, `${filename} needs an accessible title.`);
  assert.match(html, /\bid=["']main["']/, `${filename} needs the app mounting target.`);
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
  let executable = 0;
  let data = 0;
  let course;
  for (const [, attrs, source] of scripts) {
    if (/type=["']application\/json["']/i.test(attrs)) {
      const payload = JSON.parse(source);
      assert.ok(payload && typeof payload === 'object', 'Embedded data must be valid JSON.');
      if (/id=["']course-data["']/.test(attrs)) {
        for (const key of ['lessons', 'modules', 'sources', 'lab']) {
          assert.ok(Array.isArray(payload[key]) && payload[key].length > 0, `Course ${key} must be available.`);
        }
        course = payload;
      }
      data += 1;
    } else if (!/\bsrc=/.test(attrs)) {
      new Script(source, { filename: `${filename}:inline-${executable + 1}` });
      executable += 1;
    }
  }
  assert.ok(executable > 0 && data > 0 && course, `${filename} needs application code and course data.`);
  console.log(`Validated ${filename}, ${data} JSON blocks and ${executable} executable scripts.`);
  return course;
}

const hebrew = await check('index.html', 'he', 'rtl');
const english = await check('index-en.html', 'en', 'ltr');
assert.deepEqual(english.lessons.map(({ id, questions }) => [id, questions.map(({ correct }) => correct)]), hebrew.lessons.map(({ id, questions }) => [id, questions.map(({ correct }) => correct)]), 'Both languages must have the same lessons and answer keys.');
assert.deepEqual(english.lab.map(({ id, correct }) => [id, correct]), hebrew.lab.map(({ id, correct }) => [id, correct]), 'Both languages must have the same lab tasks and answer keys.');

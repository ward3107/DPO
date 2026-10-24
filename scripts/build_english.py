#!/usr/bin/env python3
"""Build the English course from index.html with an installed Argos he->en model.

Install argostranslate in a temporary virtualenv and provide the verified
translate-he_en-1_5.argosmodel file with --model. Generated output is standalone.
"""
import argparse
import hashlib
import json
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HEBREW = re.compile(r'[\u0590-\u05ff]')
UI_PHRASE = re.compile(r'[\u0590-\u05ff][\u0590-\u05ff0-9 \t.,!?;:–—־״׳·/()%-]*')
COURSE = re.compile(r'(<script id="course-data" type="application/json">)(.*?)(</script>)', re.S)
MODEL_SHA256 = 'ff8ac0ce734a82f8508ff39eaa90c110f66a2df3a93f03cf6ca72c4a60093470'
_worker_translation = None


def translate_batch(batch):
    global _worker_translation
    import argostranslate.translate
    if _worker_translation is None:
        languages = argostranslate.translate.get_installed_languages()
        from_language = next(language for language in languages if language.code == 'he')
        to_language = next(language for language in languages if language.code == 'en')
        _worker_translation = from_language.get_translation(to_language)
    return {item: _worker_translation.translate(item) for item in batch}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True, help='Trusted Argos Hebrew to English .argosmodel')
    parser.add_argument('--source', type=Path, default=Path('index.html'))
    parser.add_argument('--output', type=Path, default=Path('index-en.html'))
    parser.add_argument('--cache', type=Path, default=Path('/tmp/dpo-en-cache.json'))
    parser.add_argument('--reuse-data', action='store_true', help='Keep already translated course data while rebuilding the English page')
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error('Translation model file is missing')
    digest = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        parser.error('Translation model SHA-256 does not match the verified package')
    import argostranslate.package
    import argostranslate.translate

    installed = argostranslate.translate.get_installed_languages()
    if not any(language.code == 'he' for language in installed):
        argostranslate.package.install_from_path(str(args.model))
    if args.cache.exists():
        cache = json.loads(args.cache.read_text())
    else:
        cache = {}
    overrides = json.loads(Path(__file__).with_name('english_overrides.json').read_text())
    phrases = overrides.get('phrases', {})
    previous_count = len(cache)
    pending = set()
    collecting = True

    def translate_part(value):
        if not HEBREW.search(value):
            return value
        left = len(value) - len(value.lstrip())
        right = len(value) - len(value.rstrip())
        prefix = value[:left]
        suffix = value[len(value) - right:] if right else ''
        core = value.strip()
        if not core:
            return value
        if core in phrases:
            return prefix + phrases[core] + suffix
        if core not in cache:
            if collecting:
                pending.add(core)
                return value
            raise RuntimeError(f'Missing translation for {core[:60]}')
        return prefix + cache[core] + suffix

    def translate_text(value):
        if not HEBREW.search(value):
            return value
        # Keep long legal readings in manageable paragraphs and retain line breaks.
        return '\n'.join(translate_long_line(line) for line in value.split('\n'))

    def translate_long_line(line):
        if not HEBREW.search(line):
            return line
        if len(line) <= 700:
            return translate_part(line)
        chunks = re.split(r'(?<=[.!?])\s+', line)
        parts, current = [], ''
        for chunk in chunks:
            if current and len(current) + len(chunk) > 650:
                parts.append(translate_part(current))
                current = ''
            if len(chunk) > 650:
                words = chunk.split(' ')
                for word in words:
                    if current and len(current) + len(word) > 650:
                        parts.append(translate_part(current))
                        current = ''
                    current = f'{current} {word}'.strip()
            else:
                current = f'{current} {chunk}'.strip()
        if current:
            parts.append(translate_part(current))
        return ' '.join(parts)

    def walk(value):
        if isinstance(value, str):
            return translate_text(value)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    source = args.source.read_text()
    match = COURSE.search(source)
    if not match:
        raise RuntimeError('Course data script was not found')
    source_digest = hashlib.sha256(match.group(2).encode()).hexdigest()
    data = json.loads(match.group(2))
    if args.reuse_data:
        previous_source = args.output.read_text() if args.output.exists() else ''
        previous_digest = re.search(r'<meta name="course-source-sha256" content="([a-f0-9]{64})">', previous_source)
        if previous_digest is None or previous_digest.group(1) != source_digest:
            parser.error('--reuse-data requires English data built from the current Hebrew course data')
        previous = COURSE.search(previous_source)
        if previous is None:
            parser.error('--reuse-data requires an existing English output file')
        english_data = json.loads(previous.group(2))
    else:
        walk(data)
    source = source[:match.start(2)] + '__ENGLISH_COURSE_DATA__' + source[match.end(2):]

    def translate_ui(match):
        translated = translate_part(match.group())
        # These fragments occur inside JavaScript strings, template literals and HTML.
        # Use typographic quotes so no translated text can terminate a string literal.
        return translated.replace("'", '’').replace('"', '”').replace('`', '’').replace('\\', '/').replace('\n', ' ').replace('${', '$ {')

    UI_PHRASE.sub(translate_ui, source)
    if pending:
        items = sorted(pending, key=len, reverse=True)
        batches = [items[index:index + 8] for index in range(0, len(items), 8)]
        workers = min(8, os.cpu_count() or 2)
        print('Translating', len(items), 'fragments with', workers, 'workers', flush=True)
        completed = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(translate_batch, batch) for batch in batches]):
                cache.update(future.result())
                completed += 1
                if completed % 10 == 0:
                    args.cache.write_text(json.dumps(cache, ensure_ascii=False))
                    print('Completed', min(completed * 8, len(items)), '/', len(items), flush=True)
        args.cache.write_text(json.dumps(cache, ensure_ascii=False))
    collecting = False
    if not args.reuse_data:
        english_data = walk(data)
    titles = overrides['lesson_titles']
    focus = overrides['lesson_focus']
    modules = overrides['module_titles']
    module_subtitles = overrides['module_subtitles']
    if len(titles) != len(english_data['lessons']) or len(focus) != len(titles):
        raise RuntimeError('English lesson override count does not match the course')
    if len(modules) != len(english_data['modules']) or len(module_subtitles) != len(modules):
        raise RuntimeError('English module override count does not match the course')
    for lesson, title, focus_text in zip(english_data['lessons'], titles, focus):
        lesson['title'] = title
        lesson['focus'] = focus_text
    for module, title, subtitle in zip(english_data['modules'], modules, module_subtitles):
        module['title'] = title
        module['sub'] = subtitle
    reviewed_first = overrides['first_lesson']
    for field, value in reviewed_first.items():
        if field == 'questions':
            for question, reviewed in zip(english_data['lessons'][0]['questions'], value):
                question.update(reviewed)
        else:
            english_data['lessons'][0][field] = value
    payload = json.dumps(english_data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    source = UI_PHRASE.sub(translate_ui, source)
    source = source.replace('__ENGLISH_COURSE_DATA__', payload, 1)
    source = source.replace('<html lang="he" dir="rtl">', '<html lang="en" dir="ltr">', 1)
    source = source.replace('<head>', f'<head><meta name="course-source-sha256" content="{source_digest}">', 1)
    source = source.replace('<body>', '<body><div class="translation-notice" role="note">English study translation. Verify legal wording against the Hebrew original and official sources. <a data-hebrew-original href="index.html">View Hebrew original</a>.</div>', 1)
    source = source.replace('</style></head>', 'html[lang=en] .choice,html[lang=en] .lab-line,html[lang=en] th,html[lang=en] td{text-align:left}html[lang=en] .case-story,html[lang=en] .law-rule{border-right:0;border-left:3px solid var(--purple);padding-right:0;padding-left:18px}.translation-notice{padding:8px 18px;text-align:center;background:#eee5c8;color:#27231c;font-size:.8rem}body.dark-mode .translation-notice{background:#5a4930;color:#fff1d7}.translation-notice a{color:inherit;text-decoration:underline}</style></head>', 1)
    args.output.write_text(source)
    args.cache.write_text(json.dumps(cache, ensure_ascii=False))
    print('Built', args.output, 'with', len(cache) - previous_count, 'new translated fragments; total cache', len(cache))


if __name__ == '__main__':
    main()

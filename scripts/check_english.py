#!/usr/bin/env python3
"""Check that the generated English course preserves all data and answer keys."""
import json
import hashlib
import re
from pathlib import Path

COURSE = re.compile(r'<script id="course-data" type="application/json">(.*?)</script>', re.S)
HEBREW = re.compile(r'[\u0590-\u05ff]')
URL = re.compile(r'https?://[^\s"<>]+')


def read(path):
    source = Path(path).read_text()
    match = COURSE.search(source)
    if not match:
        raise AssertionError(f'Course data is missing from {path}')
    return source, json.loads(match.group(1))


def compare(original, translated, path='course'):
    assert type(original) is type(translated), path
    if isinstance(original, dict):
        assert original.keys() == translated.keys(), path
        for key in original:
            compare(original[key], translated[key], f'{path}.{key}')
    elif isinstance(original, list):
        assert len(original) == len(translated), path
        for index, (left, right) in enumerate(zip(original, translated)):
            compare(left, right, f'{path}[{index}]')
    elif isinstance(original, str):
        assert URL.findall(original) == URL.findall(translated), path
        if not HEBREW.search(original):
            assert original == translated, path
    else:
        assert original == translated, path


he_source, he = read('index.html')
en_source, en = read('index-en.html')
compare(he, en)
assert '<html lang="en" dir="ltr">' in en_source
digest = hashlib.sha256(COURSE.search(he_source).group(1).encode()).hexdigest()
assert f'<meta name="course-source-sha256" content="{digest}">' in en_source
assert len(he['lessons']) == 48 and len(he['lab']) == 64
assert [lesson['id'] for lesson in he['lessons']] == [lesson['id'] for lesson in en['lessons']]
remaining = sum(bool(HEBREW.search(value)) for value in re.findall(r'"((?:[^"\\]|\\.)*)"', COURSE.search(en_source).group(1)))
print(f'Course structure, answer keys, links, and IDs match. Hebrew string fragments remaining: {remaining}.')

# Updating the English course

`index.html` is the Hebrew source. `index-en.html` is generated from it. Both are standalone static pages and use the same browser storage, so progress remains available when switching language.

To rebuild the English page from `/workspace/DPO`:

```bash
python3 -m venv /tmp/dpo-translate-venv
/tmp/dpo-translate-venv/bin/pip install 'torch==2.5.1+cpu' --index-url https://download.pytorch.org/whl/cpu
/tmp/dpo-translate-venv/bin/pip install 'argostranslate==1.10.0'
curl --fail --location --show-error https://argos-net.com/v1/translate-he_en-1_5.argosmodel -o /tmp/translate-he_en-1_5.argosmodel
XDG_DATA_HOME=/tmp/dpo-translate-data XDG_CACHE_HOME=/tmp/dpo-translate-cache XDG_CONFIG_HOME=/tmp/dpo-translate-config ARGOS_STANZA_AVAILABLE=false ARGOS_INTRA_THREADS=1 ARGOS_INTER_THREADS=1 /tmp/dpo-translate-venv/bin/python scripts/build_english.py --model /tmp/translate-he_en-1_5.argosmodel
```

The build script checks the model's SHA-256 and keeps resumable translations in `/tmp/dpo-en-cache.json`. Review the generated English page before publishing changes. The 48 reviewed lesson titles are in `english_overrides.json`. The English text is a study translation; original Hebrew legislation and official sources remain authoritative.

Run `python3 scripts/check_english.py` after rebuilding. It checks that IDs, links, numeric answer keys, and the course structure match the Hebrew source. Also run the page in a browser to review wording, language switching, and exercises.

When only interface code changes, append `--reuse-data` to the build command. The script checks the Hebrew course-data SHA-256 recorded in the English page and refuses to reuse translated data if the course content changed. For lesson, question, lab, source, or reading changes, rebuild without that flag.

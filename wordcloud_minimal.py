#!/usr/bin/env python3
"""
wordcloud_minimal.py

Minimal standalone script to generate a word cloud (PNG + PDF) from
`data/records.csv` or `data/frequencies.json`.

Usage:
    python wordcloud_minimal.py --data-dir data --out-dir outputs

Behavior:
- If `data/frequencies.json` exists it will be used.
- Otherwise the script will read `data/records.csv` and build frequencies
  from the `abstract` and `keywords` columns.
- It will try to use the `wordcloud` package; if not available it will
  fall back to a Pillow-only renderer that lays out words in rows.

This file intentionally keeps dependencies minimal and contains fallbacks
so it can run in constrained environments.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


def load_frequencies(freq_path: Path) -> Counter:
    if not freq_path.exists():
        return Counter()
    with freq_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    terms = data.get('terms', {}) if isinstance(data, dict) else {}
    return Counter(terms)


def load_records_and_build(records_path: Path) -> Counter:
    # try pandas first for convenience; fallback to csv module
    if not records_path.exists():
        return Counter()

    try:
        import pandas as pd
        df = pd.read_csv(records_path, dtype=str).fillna('')
        texts = (df.get('abstract', pd.Series([''] * len(df))).astype(str).fillna('')
                 + ' '
                 + df.get('keywords', pd.Series([''] * len(df))).astype(str).fillna(''))
        word_re = re.compile(r"\b[\w'-]{3,}\b", flags=re.UNICODE)

        STOP = _get_stopwords()
        counter = Counter()
        for txt in texts:
            for w in word_re.findall(str(txt).lower()):
                if w in STOP or w.isdigit():
                    continue
                counter[w] += 1
        return counter
    except Exception:
        # Fallback: read CSV with the stdlib csv module if pandas is not available
        import csv
        word_re = re.compile(r"\b[\w'-]{3,}\b", flags=re.UNICODE)
        STOP = _get_stopwords()
        counter = Counter()
        try:
            with records_path.open('r', encoding='utf-8', errors='ignore') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    abstract = (row.get('abstract') or '')
                    keywords = (row.get('keywords') or row.get('keyword') or '')
                    txt = f"{abstract} {keywords}"
                    for w in word_re.findall(txt.lower()):
                        if w in STOP or w.isdigit():
                            continue
                        counter[w] += 1
        except Exception:
            # Any error reading/parsing -> return empty counter
            return Counter()
        return counter


def parse_bib_files(data_dir: Path) -> list:
    """Parse all .bib files in data_dir and return a list of entry dicts.

    Each dict contains at least: id, title, abstract, keywords
    """
    bib_entries = []
    try:
        import bibtexparser
    except Exception:
        # bibtexparser not available; cannot parse .bib files
        return bib_entries

    for bibf in data_dir.glob('*.bib'):
        try:
            text = bibf.read_text(encoding='utf-8', errors='ignore')
            db = bibtexparser.loads(text)
            for entry in db.entries:
                eid = entry.get('ID') or entry.get('key') or entry.get('id') or None
                if not eid:
                    continue
                title = entry.get('title', '')
                abstract = entry.get('abstract', '')
                keywords = entry.get('keywords', '') or entry.get('keyword', '')
                bib_entries.append({'id': eid, 'title': title, 'abstract': abstract, 'keywords': keywords})
        except Exception:
            continue
    return bib_entries


def merge_new_entries_into_records(records_path: Path, new_entries: list) -> None:
    """Merge new_entries (list of dicts) into records.csv, avoiding duplicates by id.

    The function writes records.csv (creates if missing). Uses pandas if available
    for convenience, otherwise falls back to csv module.
    """
    if not new_entries:
        return
    # normalize new_entries into dict keyed by id
    new_by_id = {e['id']: e for e in new_entries}

    try:
        import pandas as pd
        if records_path.exists():
            df = pd.read_csv(records_path, dtype=str).fillna('')
        else:
            df = pd.DataFrame(columns=['id', 'title', 'abstract', 'keywords'])

        existing_ids = set(df['id'].astype(str).tolist()) if 'id' in df.columns else set()
        rows = [dict(r) for _, r in df.iterrows()] if not df.empty else []

        added = 0
        for nid, rec in new_by_id.items():
            if str(nid) in existing_ids:
                continue
            rows.append({'id': nid, 'title': rec.get('title',''), 'abstract': rec.get('abstract',''), 'keywords': rec.get('keywords','')})
            added += 1

        if added > 0:
            out_df = pd.DataFrame(rows)
            out_df.to_csv(records_path, index=False, encoding='utf-8')
        return
    except Exception:
        # fallback to csv module
        import csv
        existing_ids = set()
        rows = []
        if records_path.exists():
            with records_path.open('r', encoding='utf-8', errors='ignore') as fh:
                reader = csv.DictReader(fh)
                for r in reader:
                    existing_ids.add(r.get('id',''))
                    rows.append(r)

        added = 0
        for nid, rec in new_by_id.items():
            if str(nid) in existing_ids:
                continue
            rows.append({'id': nid, 'title': rec.get('title',''), 'abstract': rec.get('abstract',''), 'keywords': rec.get('keywords','')})
            added += 1

        # write back
        fieldnames = ['id','title','abstract','keywords']
        with records_path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k,'') for k in fieldnames})
        return
    except Exception:
        # fallback without pandas
        import csv
        word_re = re.compile(r"\b[\w'-]{3,}\b", flags=re.UNICODE)
        STOP = _get_stopwords()
        counter = Counter()
        if not records_path.exists():
            return counter
        with records_path.open('r', encoding='utf-8', errors='ignore') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                abstract = (row.get('abstract') or '')
                keywords = (row.get('keywords') or row.get('keyword') or '')
                txt = f"{abstract} {keywords}"
                for w in word_re.findall(txt.lower()):
                    if w in STOP or w.isdigit():
                        continue
                    counter[w] += 1
        return counter


def _get_stopwords():
    # Keep this small and local to avoid an nltk dependency
    base = {
        'the','and','for','with','that','this','from','using','use','research',
        'study','method','results','analysis','based','data','paper','also',
        'can','will','these','such','which','our','their','between','than'
    }
    return set(base)


def save_frequencies(freq_path: Path, counter: Counter) -> None:
    payload = {'total_terms': sum(counter.values()), 'terms': dict(counter)}
    freq_path.parent.mkdir(parents=True, exist_ok=True)
    with freq_path.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def generate_images(counter: Counter, out_png: Path, out_pdf: Path) -> dict:
    # Try to use wordcloud package for nicer rendering
    try:
        from wordcloud import WordCloud
        wc = WordCloud(width=1400, height=900, background_color='white', collocations=False)
        wc.generate_from_frequencies(counter)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        wc.to_file(str(out_png))
        # try convert to PDF using Pillow
        try:
            from PIL import Image
            im = Image.open(out_png).convert('RGB')
            im.save(out_pdf, 'PDF', resolution=300)
        except Exception:
            pass
        return {'png': str(out_png), 'pdf': str(out_pdf) if out_pdf.exists() else None, 'method': 'wordcloud'}
    except Exception:
        # Pillow-only fallback: layout words in rows with sizes proportional to counts
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as e:
            return {'png': None, 'pdf': None, 'error': f'Pillow not available: {e}'}

        W, H = 1400, 900
        img = Image.new('RGB', (W, H), color='white')
        draw = ImageDraw.Draw(img)

        top = counter.most_common(120)
        if not top:
            img.save(out_png)
            return {'png': str(out_png), 'pdf': None, 'method': 'pillow_empty'}

        freqs = [f for _, f in top]
        fmin, fmax = min(freqs), max(freqs)

        def norm_size(v):
            if fmax == fmin:
                return 28
            return int(18 + (v - fmin) / (fmax - fmin) * (120 - 18))

        # font selection - try common fonts
        def load_font(sz):
            candidates = ['arial.ttf', 'DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf']
            for c in candidates:
                try:
                    return ImageFont.truetype(c, sz)
                except Exception:
                    continue
            return ImageFont.load_default()

        padding = 8
        x, y = padding, padding
        max_row_h = 0
        for word, cnt in top:
            sz = norm_size(cnt)
            font = load_font(sz)
            w, h = draw.textsize(word, font=font)
            if x + w + padding > W:
                x = padding
                y += max_row_h + padding
                max_row_h = 0
            if y + h + padding > H:
                break
            draw.text((x, y), word, fill='black', font=font)
            x += w + padding
            if h > max_row_h:
                max_row_h = h

        out_png.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_png)
        try:
            img.convert('RGB').save(out_pdf, 'PDF', resolution=300)
        except Exception:
            pass
        return {'png': str(out_png), 'pdf': str(out_pdf) if out_pdf.exists() else None, 'method': 'pillow_fallback'}


def main(argv=sys.argv[1:]):
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir', default='data', help='Directory with records.csv or frequencies.json')
    p.add_argument('--out-dir', default='outputs', help='Directory to write nube_palabras.png/pdf')
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    records_path = data_dir / 'records.csv'
    freq_path = data_dir / 'frequencies.json'
    out_png = out_dir / 'nube_palabras.png'
    out_pdf = out_dir / 'nube_palabras.pdf'

    # First: detect .bib files in data_dir and merge new entries into records.csv
    try:
        new_bib_entries = parse_bib_files(data_dir)
        if new_bib_entries:
            print(f'Detected {len(new_bib_entries)} entries from .bib files; merging into records.csv')
            merge_new_entries_into_records(records_path, new_bib_entries)
    except Exception:
        # non-fatal
        pass

    counter = Counter()
    if freq_path.exists():
        counter = load_frequencies(freq_path)
        if not counter and records_path.exists():
            counter = load_records_and_build(records_path)
    else:
        if records_path.exists():
            counter = load_records_and_build(records_path)

    if not counter:
        print('No terms found. Ensure data/records.csv or data/frequencies.json is present.')
        return 1

    # Update frequencies.json
    try:
        save_frequencies(freq_path, counter)
    except Exception as e:
        print('Warning: could not write frequencies.json:', e)

    res = generate_images(counter, out_png, out_pdf)
    print('Result:', res)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

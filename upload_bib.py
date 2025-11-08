#!/usr/bin/env python3
"""
upload_bib.py

Simple CLI to copy a .bib file into the local `data/` folder used by the
Requerimiento5 notebook and server. Handles name collisions by appending a
timestamp suffix unless --overwrite is provided.

Usage:
    python upload_bib.py /path/to/file.bib
    python upload_bib.py /path/to/file.bib --name custom_name.bib
    python upload_bib.py /path/to/file.bib --overwrite
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from datetime import datetime
import sys


def install_argparse():
    return


def main(argv=sys.argv[1:]):
    p = argparse.ArgumentParser(description='Copy a .bib file into proyecto/requerimiento5/data/')
    p.add_argument('src', help='Path to the .bib file to upload')
    p.add_argument('--name', '-n', help='Optional destination filename (must end with .bib)')
    p.add_argument('--overwrite', '-o', action='store_true', help='Overwrite existing file if present')
    args = p.parse_args(argv)

    src_path = Path(args.src).expanduser().resolve()
    if not src_path.exists() or not src_path.is_file():
        print(f'Error: source file not found: {src_path}')
        return 2
    if src_path.suffix.lower() != '.bib':
        print('Error: only .bib files are allowed')
        return 3

    repo_dir = Path(__file__).parent
    data_dir = repo_dir / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.name:
        dest_name = Path(args.name).name
        if not dest_name.lower().endswith('.bib'):
            print('Error: --name must end with .bib')
            return 4
    else:
        dest_name = src_path.name

    dest_path = data_dir / dest_name
    if dest_path.exists():
        if args.overwrite:
            shutil.copy2(src_path, dest_path)
            print(f'Overwrote existing file: {dest_path}')
            return 0
        else:
            # create a unique name with timestamp
            ts = datetime.now().strftime('%Y%m%dT%H%M%S')
            base = dest_path.stem
            new_name = f"{base}_{ts}.bib"
            dest_path = data_dir / new_name

    shutil.copy2(src_path, dest_path)
    print(f'File copied to: {dest_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

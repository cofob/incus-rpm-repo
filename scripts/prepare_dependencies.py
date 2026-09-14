#!/usr/bin/env python3
"""Prepare dependency builds from official archives with pinned checksums."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from prepare import download

ROOT = Path(__file__).resolve().parents[1]


def main(top):
    top = Path(top).resolve()
    for folder in ('SOURCES', 'SPECS', 'BUILD', 'RPMS', 'SRPMS'):
        (top / folder).mkdir(parents=True, exist_ok=True)
    packages = json.loads((ROOT / 'packaging/dependencies/provenance.json').read_text())
    for name, package in packages.items():
        source = top / 'SOURCES' / package['filename']
        download(package['url'], source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != package['sha256']:
            raise RuntimeError(f'{name} source checksum mismatch')
        shutil.copy2(ROOT / 'packaging/dependencies' / f'{name}.spec', top / 'SPECS')


if __name__ == '__main__':
    main(*sys.argv[1:])

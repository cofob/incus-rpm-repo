#!/usr/bin/env python3
"""Fetch signed source and prepare an RPM build tree."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from releases import version

ROOT = Path(__file__).resolve().parents[1]


def download(url, path):
    with urllib.request.urlopen(url, timeout=120) as response, path.open('wb') as output:
        shutil.copyfileobj(response, output)


def go_version(value):
    # Rocky appends a distribution build string even in `go env GOVERSION`.
    numeric = value.strip().split()[0].removeprefix('go')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', numeric):
        raise ValueError('Invalid Go version')
    fields = tuple(map(int, numeric.split('.')))
    return fields + (0,) * (3 - len(fields))


def main(tag, top):
    major, minor, patch = version(tag)
    top = Path(top).resolve()
    for folder in ('SOURCES', 'SPECS', 'BUILD', 'RPMS', 'SRPMS'):
        (top / folder).mkdir(parents=True, exist_ok=True)
    # The signed archive uses 7.4 for feature .0 releases, but 7.0.0 for LTS.
    source_version = f'{major}.{minor}' if patch == 0 and minor != 0 else tag[1:]
    filename = f'incus-{source_version}.tar.xz'
    source = top / 'SOURCES' / filename
    base = 'https://linuxcontainers.org/downloads/incus/'
    download(base + filename, source)
    signature = source.with_suffix('.xz.asc')
    download(base + filename + '.asc', signature)
    with tempfile.TemporaryDirectory() as home:
        os.chmod(home, 0o700)
        subprocess.run(['gpg', '--homedir', home, '--batch', '--import', str(ROOT / 'keys/upstream.asc')], check=True)
        result = subprocess.run(['gpg', '--homedir', home, '--batch', '--status-fd', '1', '--verify', str(signature), str(source)],
                                check=True, text=True, capture_output=True)
        fingerprint = json.loads((ROOT / 'packaging/provenance.json').read_text())['upstream_signer']
        if f'[GNUPG:] VALIDSIG {fingerprint} ' not in result.stdout:
            raise RuntimeError('Unexpected upstream signature')
    with tarfile.open(source) as archive:
        prefix = f'incus-{source_version}/'
        go_mod = archive.extractfile(prefix + 'go.mod').read().decode()
        has_migrate = any(n.startswith(prefix + 'cmd/lxd-to-incus/') for n in archive.getnames())
    required = re.search(r'^go (\d+\.\d+(?:\.\d+)?)$', go_mod, re.M).group(1)
    # Use the newest stable patch in the required Go minor series if Rocky is too old.
    installed = subprocess.check_output(['go', 'env', 'GOVERSION'], text=True).strip()
    if go_version(installed) < go_version(required):
        with urllib.request.urlopen('https://go.dev/dl/?mode=json&include=all', timeout=60) as response:
            releases = json.load(response)
        choices = [r for r in releases if r['stable'] and
                   r['version'].startswith('go' + '.'.join(required.split('.')[:2]) + '.') and
                   go_version(r['version']) >= go_version(required)]
        release = max(choices, key=lambda r: go_version(r['version']))
        asset = next(f for f in release['files'] if f['os'] == 'linux' and f['arch'] == 'amd64' and f['kind'] == 'archive')
        path = top / 'go.tar.gz'
        download('https://go.dev/dl/' + asset['filename'], path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise RuntimeError('Go checksum mismatch')
        subprocess.run(['tar', '-xzf', str(path), '-C', '/usr/local'], check=True)
    for item in (ROOT / 'packaging/SOURCES').iterdir():
        shutil.copy2(item, top / 'SOURCES' / item.name)
    spec = (ROOT / 'packaging/incus.spec').read_text()
    spec = (f'%global source_version {source_version}\n%global rpm_version {tag[1:]}\n'
            f'%global has_lxd_migrate {int(has_migrate)}\n' + spec)
    (top / 'SPECS/incus.spec').write_text(spec)
    (top / 'release.json').write_text(json.dumps({'tag': tag, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                               'go_minimum': required}) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:])

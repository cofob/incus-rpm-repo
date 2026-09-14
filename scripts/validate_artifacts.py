#!/usr/bin/env python3
"""Check the identity of every Incus and dependency RPM before signing."""
import json
from pathlib import Path
import subprocess
import sys
from releases import version, RPM_RELEASE

ROOT = Path(__file__).resolve().parents[1]


def main(folder, tag, architecture='x86_64'):
    if architecture not in ('x86_64', 'aarch64'):
        raise ValueError('Unsupported architecture')
    version(tag)
    folder = Path(folder)
    release_info = json.loads((folder / 'release.json').read_text())
    if release_info.get('architecture') != architecture:
        raise ValueError('Build architecture does not match selected architecture')
    if release_info['tag'] != tag or release_info['rpm_release'] != RPM_RELEASE:
        raise ValueError('Build release does not match selected release')
    dependencies = json.loads((ROOT / 'packaging/dependencies/provenance.json').read_text())
    identities = {'incus': (tag[1:], f'{RPM_RELEASE}.el10')}
    identities.update({name: (package['version'], package['release']) for name, package in dependencies.items()})
    required = {'incus', 'incus-client', 'incus-tools', 'incus-agent',
                'cowsql', 'cowsql-devel', 'raft', 'raft-devel'}
    allowed = required | {name + suffix for name in required for suffix in ('-debuginfo', '-debugsource')}
    names, sources, seen = set(), set(), set()
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError('Invalid artifact entry')
        if path.name == 'release.json':
            continue
        if path.suffix != '.rpm':
            raise ValueError('Unexpected artifact')
        name, ver, release, arch = subprocess.check_output(
            ['rpm', '-qp', '--qf', '%{NAME}\t%{VERSION}\t%{RELEASE}\t%{ARCH}', str(path)], text=True).split('\t')
        base = name.split('-')[0]
        if name not in allowed or identities.get(base) != (ver, release):
            raise ValueError('Unexpected RPM identity')
        source = path.name.endswith('.src.rpm')
        file_arch = 'src' if source else arch
        if path.name != f'{name}-{ver}-{release}.{file_arch}.rpm' or (name, file_arch) in seen:
            raise ValueError('Unexpected or duplicate RPM filename')
        seen.add((name, file_arch))
        if source:
            if name not in identities:
                raise ValueError('Unexpected source RPM')
            sources.add(name)
        elif arch not in (architecture, 'noarch'):
            raise ValueError('Unexpected RPM architecture')
        else:
            names.add(name)
    if sources != set(identities) or not required <= names:
        raise ValueError('Missing required packages')


if __name__ == '__main__':
    main(*sys.argv[1:])
